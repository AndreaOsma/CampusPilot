"""Enlaces iCal del campus virtual (Ajustes → Calendario de la universidad)."""
from __future__ import annotations

from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import calendar_feeds, models
from ..crud import get_or_404
from ..database import get_db

router = APIRouter(prefix="/api/calendar-feeds", tags=["calendar"])


class FeedIn(BaseModel):
    name: str = Field(default="", max_length=120)
    # Vacío al editar = conservar el enlace guardado (la API no lo devuelve entero).
    url: str = Field(default="", max_length=1000)
    subject_id: Optional[int] = None
    mode: Literal["events", "activities"] = "events"
    enabled: bool = True


def _out(feed: models.CalendarFeed) -> dict:
    parts = urlparse(feed.url)
    return {
        "id": feed.id, "name": feed.name, "subject_id": feed.subject_id, "mode": feed.mode, "enabled": feed.enabled,
        "url_hint": f"{parts.scheme}://{parts.hostname or ''}/…", "items": feed.items, "last_error": feed.last_error,
        "last_sync": feed.last_sync.isoformat() if feed.last_sync else None,
    }


def _apply(db: Session, feed: models.CalendarFeed, payload: FeedIn) -> None:
    if payload.subject_id is not None and db.get(models.Subject, payload.subject_id) is None:
        raise HTTPException(status_code=422, detail="Esa asignatura no existe")
    if payload.url.strip():
        url = calendar_feeds.normalize_url(payload.url)
        if urlparse(url).scheme not in ("http", "https"):
            raise HTTPException(status_code=422, detail="El enlace tiene que empezar por https:// (o webcal://)")
        feed.url = url
    feed.name = payload.name.strip() or urlparse(feed.url).hostname or "Campus"
    feed.subject_id, feed.mode, feed.enabled = payload.subject_id, payload.mode, payload.enabled


async def _sync(db: Session, feed: models.CalendarFeed) -> dict:
    try:
        counts = await run_in_threadpool(calendar_feeds.sync, db, feed)
    except ValueError as exc:
        db.rollback()
        feed.last_error = str(exc)[:500]
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — red caída, campus sin responder…
        db.rollback()
        feed.last_error = f"No se pudo descargar: {exc}"[:500]
        db.commit()
        raise HTTPException(status_code=502, detail=feed.last_error)
    return {**_out(feed), "counts": counts}


@router.get("")
def list_feeds(db: Session = Depends(get_db)):
    return [_out(f) for f in db.query(models.CalendarFeed).order_by(models.CalendarFeed.id)]


@router.post("", status_code=201)
async def create_feed(payload: FeedIn, db: Session = Depends(get_db)):
    if not payload.url.strip():
        raise HTTPException(status_code=422, detail="Pega el enlace iCal del calendario de tu campus")
    feed = models.CalendarFeed(url="")
    _apply(db, feed, payload)
    db.add(feed)
    db.commit()
    db.refresh(feed)
    # Primera sincronización ya: si el enlace no vale, mejor saberlo al guardarlo.
    try:
        return await _sync(db, feed)
    except HTTPException:
        db.delete(feed)
        db.commit()
        raise


@router.put("/{feed_id}")
def update_feed(feed_id: int, payload: FeedIn, db: Session = Depends(get_db)):
    feed = get_or_404(db, models.CalendarFeed, feed_id, "Calendario")
    _apply(db, feed, payload)
    db.commit()
    return _out(feed)


@router.post("/{feed_id}/sync")
async def sync_feed(feed_id: int, db: Session = Depends(get_db)):
    return await _sync(db, get_or_404(db, models.CalendarFeed, feed_id, "Calendario"))


@router.delete("/{feed_id}", status_code=204)
def delete_feed(feed_id: int, keep: bool = False, db: Session = Depends(get_db)):
    """Quita el enlace; con keep=false, también lo que trajo y aún no ha pasado."""
    feed = get_or_404(db, models.CalendarFeed, feed_id, "Calendario")
    if not keep:
        prefix = f"ical:{feed.id}:%"
        for Model in (models.Event, models.Activity):
            for row in db.query(Model).filter(Model.pack_ref.like(prefix)):
                if not (Model is models.Activity and (row.grade is not None or row.done)):
                    db.delete(row)
    db.delete(feed)
    db.commit()
