"""Bandeja de la universidad (ver inbox.py).

- `POST /inbox/ingest` y `GET /inbox/export`: fuera de `/api`, con token propio cada una
  (el Worker de correo y la copia local no pueden pasar por el SSO). Sin token configurado
  responden 404.
- `/api/inbox/*`: la bandeja en la app, detrás del SSO como el resto.
"""
from __future__ import annotations

import hmac
import json
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import config, inbox, models
from ..crud import get_or_404, require
from ..database import get_db

public = APIRouter(prefix="/inbox", tags=["inbox"], include_in_schema=False)
api = APIRouter(prefix="/api/inbox", tags=["inbox"])


def _check_token(request: Request, expected: str) -> None:
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    header = request.headers.get("authorization", "")
    given = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not given or not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Token no válido")


@public.post("/ingest", status_code=201)
async def ingest(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    _check_token(request, config.INBOX_TOKEN)
    raw = await request.body()
    if len(raw) > config.MAX_INBOX_BYTES:
        raise HTTPException(status_code=413, detail="Correo demasiado grande")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="JSON no válido")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Se esperaba un objeto JSON")
    try:
        msg, created = inbox.ingest(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if created and msg.classify_status == "pending":
        if inbox.should_classify(db):
            background.add_task(inbox.classify, msg.id)
        else:
            msg.classify_status = "off"
            db.commit()
    return {"id": msg.id, "status": "created" if created else "duplicate"}


@public.get("/export")
def export(request: Request, since_id: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=500), db: Session = Depends(get_db)):
    _check_token(request, config.INBOX_EXPORT_TOKEN)
    rows = (
        db.query(models.InboxMessage)
        .filter(models.InboxMessage.id > since_id, models.InboxMessage.classify_status.notin_(("pending", "running")))
        .order_by(models.InboxMessage.id)
        .limit(limit)
        .all()
    )
    return {"items": [inbox.export_item(m) for m in rows]}


class InboxOut(BaseModel):
    id: int
    received_at: str
    sender: str
    title: str
    body: str
    status: str
    subject_id: Optional[int]
    kind: str
    summary: str
    proposals: list[dict]
    classify_status: str
    classify_error: str


def _out(msg: models.InboxMessage) -> InboxOut:
    return InboxOut(
        id=msg.id, received_at=msg.received_at.isoformat(timespec="minutes"), sender=msg.sender, title=msg.title, body=msg.body,
        status=msg.status, subject_id=msg.subject_id, kind=msg.kind, summary=msg.summary, proposals=list(msg.proposals or []),
        classify_status=msg.classify_status, classify_error=msg.classify_error,
    )


@api.get("", response_model=list[InboxOut])
def list_messages(status: Optional[Literal["new", "read", "archived", "open"]] = None, subject_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.InboxMessage)
    if status == "open":
        q = q.filter(models.InboxMessage.status != "archived")
    elif status:
        q = q.filter(models.InboxMessage.status == status)
    if subject_id is not None:
        q = q.filter(models.InboxMessage.subject_id == subject_id)
    return [_out(m) for m in q.order_by(models.InboxMessage.received_at.desc(), models.InboxMessage.id.desc()).limit(500)]


@api.get("/stats")
def stats(db: Session = Depends(get_db)):
    q = db.query(models.InboxMessage)
    pending = sum(
        1 for m in q.filter(models.InboxMessage.status != "archived") for p in (m.proposals or []) if p.get("state") == "pending"
    )
    return {"new": q.filter(models.InboxMessage.status == "new").count(), "pending_proposals": pending, "ingest_configured": bool(config.INBOX_TOKEN or (config.INBOX_PULL_URL and config.INBOX_PULL_TOKEN))}


@api.get("/{msg_id}", response_model=InboxOut)
def get_message(msg_id: int, db: Session = Depends(get_db)):
    return _out(get_or_404(db, models.InboxMessage, msg_id, "Correo"))


class InboxUpdate(BaseModel):
    status: Optional[Literal["new", "read", "archived"]] = None
    subject_id: Optional[int] = None
    kind: Optional[Literal["announcement", "grade", "video_check", "forum", "deadline", "admin", "other"]] = None
    clear_subject: bool = False


@api.put("/{msg_id}", response_model=InboxOut)
def update_message(msg_id: int, payload: InboxUpdate, db: Session = Depends(get_db)):
    msg = get_or_404(db, models.InboxMessage, msg_id, "Correo")
    if payload.status:
        msg.status = payload.status
    if payload.clear_subject:
        msg.subject_id = None
    elif payload.subject_id is not None:
        require(db, models.Subject, payload.subject_id, "La asignatura")
        msg.subject_id = payload.subject_id
    if payload.kind:
        msg.kind = payload.kind
    db.commit()
    db.refresh(msg)
    return _out(msg)


@api.post("/{msg_id}/classify", response_model=InboxOut)
def reclassify(msg_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    msg = get_or_404(db, models.InboxMessage, msg_id, "Correo")
    if not inbox.should_classify(db):
        raise HTTPException(status_code=409, detail="La clasificación no está disponible (falta la credencial de Claude o el módulo está desactivado)")
    msg.classify_status, msg.classify_error = "pending", ""
    db.commit()
    background.add_task(inbox.classify, msg.id)
    db.refresh(msg)
    return _out(msg)


class ProposalAction(BaseModel):
    action: Literal["accept", "dismiss"]


@api.post("/{msg_id}/proposals/{index}", response_model=InboxOut)
def resolve(msg_id: int, index: int, payload: ProposalAction, db: Session = Depends(get_db)):
    msg = get_or_404(db, models.InboxMessage, msg_id, "Correo")
    try:
        return _out(inbox.resolve_proposal(db, msg, index, payload.action))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@api.delete("/{msg_id}", status_code=204)
def delete_message(msg_id: int, db: Session = Depends(get_db)):
    msg = get_or_404(db, models.InboxMessage, msg_id, "Correo")
    db.delete(msg)
    db.commit()
