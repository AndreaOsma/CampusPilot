"""Estudio: sesiones (focus o a mano), horas por asignatura y tarjetas de repaso.

Las tarjetas son solo preguntas: se responde sin mirar y uno mismo se evalúa ("lo sabía" /
"no"). Repaso espaciado tipo Leitner, como la teoría de Bitácora.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import clock, models
from ..crud import crud_router, get_or_404, require
from ..database import get_db
from ..schemas import CardImportIn, CardIn, CardOut, CardReviewIn, SessionIn, SessionOut

# Días hasta el siguiente repaso según la caja (1–5).
LEITNER_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
MAX_IMPORT_CARDS = 500

_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
_HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$")


def _validate_subject_ref(db: Session, payload: BaseModel) -> None:
    require(db, models.Subject, payload.subject_id, "La asignatura")


sessions = crud_router(
    "sessions", models.StudySession, SessionIn, SessionOut, label="Sesión", filters=("subject_id", "kind"),
    order_by=(models.StudySession.date.desc(), models.StudySession.id.desc()), validate=_validate_subject_ref,
)


cards = crud_router(
    "cards", models.ReviewCard, CardIn, CardOut, label="Tarjeta", filters=("subject_id", "deck"),
    order_by=(models.ReviewCard.due_on, models.ReviewCard.id), validate=_validate_subject_ref,
    create_defaults=lambda: {"box": 1, "due_on": clock.today()},
)

extra = APIRouter(prefix="/api", tags=["study"])


def parse_questions(markdown: str) -> tuple[str, list[str]]:
    """(título del primer encabezado #, preguntas). Cada elemento de lista es una pregunta;
    las líneas sangradas que siguen a un elemento se le añaden (preguntas de varias líneas)."""
    title = ""
    questions: list[str] = []
    in_quote_or_code = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_quote_or_code = not in_quote_or_code
            continue
        if in_quote_or_code or line.lstrip().startswith(">"):
            continue
        heading = _HEADING_RE.match(line)
        if heading and not title:
            title = heading.group(1)
            continue
        item = _ITEM_RE.match(line)
        if item:
            questions.append(item.group(1))
        elif questions and line.startswith(("   ", "\t")) and line.strip():
            questions[-1] += " " + line.strip()
    return title, questions


@extra.post("/cards/import")
def import_cards(payload: CardImportIn, db: Session = Depends(get_db)):
    require(db, models.Subject, payload.subject_id, "La asignatura")
    title, questions = parse_questions(payload.markdown)
    deck = payload.deck or re.sub(r"^Preguntas de repaso\s*[—–-]\s*", "", title)[:160]
    existing = {c.question for c in db.query(models.ReviewCard).filter_by(deck=deck, subject_id=payload.subject_id)}
    added = 0
    today = clock.today()
    for q in questions[:MAX_IMPORT_CARDS]:
        q = q[:4000]
        if q in existing:
            continue
        db.add(
            models.ReviewCard(
                subject_id=payload.subject_id, deck=deck, question=q, source=payload.source, box=1, due_on=today
            )
        )
        existing.add(q)
        added += 1
    db.commit()
    return {"deck": deck, "found": len(questions), "added": added}


@extra.get("/cards-due", response_model=list[CardOut])
def due_cards(subject_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(models.ReviewCard).filter(models.ReviewCard.due_on <= clock.today())
    if subject_id is not None:
        q = q.filter(models.ReviewCard.subject_id == subject_id)
    return q.order_by(models.ReviewCard.box, models.ReviewCard.due_on).limit(max(1, min(limit, 200))).all()


@extra.post("/cards/{card_id}/review", response_model=CardOut)
def review_card(card_id: int, payload: CardReviewIn, db: Session = Depends(get_db)):
    card = get_or_404(db, models.ReviewCard, card_id, "Tarjeta")
    today = clock.today()
    if payload.knew:
        card.box = min(5, card.box + 1)
    else:
        card.box = 1
        card.lapses += 1
    card.reviews += 1
    card.last_reviewed = today
    card.due_on = today + timedelta(days=LEITNER_DAYS[card.box])
    db.commit()
    db.refresh(card)
    return card


@extra.get("/study/stats")
def study_stats(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    """Minutos por asignatura en el rango y, si la asignatura tiene horas/semana estimadas,
    lo esperado para ese rango (semanas × horas)."""
    end = end or clock.today()
    start = start or end - timedelta(days=27)
    rows = (
        db.query(models.StudySession.subject_id, func.sum(models.StudySession.minutes))
        .filter(models.StudySession.date.between(start, end))
        .group_by(models.StudySession.subject_id)
        .all()
    )
    weeks = max(1, ((end - start).days + 1)) / 7
    subjects = {s.id: s for s in db.query(models.Subject).all()}
    out = []
    for subject_id, minutes in rows:
        s = subjects.get(subject_id)
        out.append(
            {
                "subject_id": subject_id,
                "subject_name": s.name if s else "Sin asignatura",
                "minutes": int(minutes or 0),
                "expected_minutes": round(s.weekly_hours * 60 * weeks) if s and s.weekly_hours else None,
            }
        )
    for s in subjects.values():
        if s.status == "enrolled" and s.weekly_hours and s.id not in {r["subject_id"] for r in out}:
            out.append(
                {"subject_id": s.id, "subject_name": s.name, "minutes": 0, "expected_minutes": round(s.weekly_hours * 60 * weeks)}
            )
    daily = (
        db.query(models.StudySession.date, func.sum(models.StudySession.minutes))
        .filter(models.StudySession.date.between(start, end))
        .group_by(models.StudySession.date)
        .all()
    )
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "by_subject": sorted(out, key=lambda r: -r["minutes"]),
        "daily": [{"date": d.isoformat(), "minutes": int(m or 0)} for d, m in sorted(daily)],
    }


routers = (sessions, cards, extra)
