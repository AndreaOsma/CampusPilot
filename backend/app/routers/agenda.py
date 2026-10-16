"""Semestre: agenda unificada, eventos, hábitos, feed iCal y panel de inicio."""
from __future__ import annotations

import hmac
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import agenda, clock, command, config, evaluation, models
from ..crud import crud_router, get_or_404, require
from ..database import get_db
from ..schemas import EventIn, EventOut, HabitIn, HabitOut
from ..settings_store import load_settings

MAX_RANGE_DAYS = 800
ICS_PAST_DAYS = 120
ICS_FUTURE_DAYS = 400


def _validate_subject_ref(db: Session, payload: BaseModel) -> None:
    require(db, models.Subject, payload.subject_id, "La asignatura")


events = crud_router(
    "events", models.Event, EventIn, EventOut, label="Evento", filters=("subject_id",),
    order_by=(models.Event.date, models.Event.start_time), validate=_validate_subject_ref,
)
habits = crud_router(
    "habits", models.Habit, HabitIn, HabitOut, label="Hábito", filters=("subject_id",),
    order_by=(models.Habit.id,), validate=_validate_subject_ref,
)

extra = APIRouter(tags=["agenda"])


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    start = start or agenda.week_start(clock.today())
    end = end or start + timedelta(days=55)
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=f"Rango de fechas no válido (máximo {MAX_RANGE_DAYS} días)")
    return start, end


@extra.get("/api/agenda")
def get_agenda(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    start, end = _range(start, end)
    items = agenda.build(db, start, end)
    heavy = agenda.heavy_weeks(items, load_settings(db).heavy_week_subjects)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "items": agenda.serialize(items),
        "heavy_weeks": [{"week": w.isoformat(), "subjects": s} for w, s in sorted(heavy.items())],
    }


@extra.post("/api/habits/{habit_id}/check")
def toggle_habit(habit_id: int, day: date | None = None, db: Session = Depends(get_db)):
    get_or_404(db, models.Habit, habit_id, "Hábito")
    day = day or clock.today()
    row = db.query(models.HabitCheck).filter_by(habit_id=habit_id, date=day).first()
    if row:
        db.delete(row)
        done = False
    else:
        db.add(models.HabitCheck(habit_id=habit_id, date=day))
        done = True
    db.commit()
    return {"habit_id": habit_id, "date": day.isoformat(), "done": done}


@extra.get("/api/habits-week")
def habits_week(start: date | None = None, db: Session = Depends(get_db)):
    start = start or agenda.week_start(clock.today())
    end = start + timedelta(days=6)
    checks = db.query(models.HabitCheck).filter(models.HabitCheck.date.between(start, end)).all()
    out: dict[int, list[str]] = {}
    for c in checks:
        out.setdefault(c.habit_id, []).append(c.date.isoformat())
    return {"start": start.isoformat(), "checks": out}


def _ics_response(db: Session) -> Response:
    today = clock.today()
    items = agenda.build(db, today - timedelta(days=ICS_PAST_DAYS), today + timedelta(days=ICS_FUTURE_DAYS))
    return Response(
        agenda.to_ics(items),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="campus-pilot.ics"', "Cache-Control": "no-store"},
    )


@extra.get("/api/calendar.ics")
def calendar_ics(db: Session = Depends(get_db)):
    return _ics_response(db)


@extra.get("/ical/{token}.ics", include_in_schema=False)
def calendar_ics_token(token: str, db: Session = Depends(get_db)):
    """Feed para apps de calendario (no pasan por el SSO). Desactivado sin CAMPUS_ICAL_TOKEN."""
    if not config.ICAL_TOKEN or not hmac.compare_digest(token.encode(), config.ICAL_TOKEN.encode()):
        raise HTTPException(status_code=404, detail="Not found")
    return _ics_response(db)


@extra.get("/api/dashboard")
def dashboard(days: int = Query(default=14, ge=1, le=60), db: Session = Depends(get_db)):
    today = clock.today()
    settings = load_settings(db)
    week = agenda.week_start(today)
    items = agenda.build(db, today, today + timedelta(days=days))
    week_items = agenda.build(db, week, week + timedelta(days=13))
    heavy = agenda.heavy_weeks(week_items, settings.heavy_week_subjects)

    open_windows = [
        i for i in agenda.build(db, today, today) if i.type == "window" and not i.done
    ]
    overdue = (
        db.query(models.Activity)
        .filter(models.Activity.due_date < today, models.Activity.due_date >= today - timedelta(days=30))
        .filter(models.Activity.done.is_(False))
        .order_by(models.Activity.due_date)
        .all()
    )

    checked = {c.habit_id for c in db.query(models.HabitCheck).filter_by(date=today)}
    habits_today = [
        {"id": h.id, "title": h.title, "subject_id": h.subject_id, "done": h.id in checked}
        for h in db.query(models.Habit).filter_by(active=True)
        if today.weekday() in (h.weekdays or [])
    ]

    minutes_week = (
        db.query(func.coalesce(func.sum(models.StudySession.minutes), 0))
        .filter(models.StudySession.date.between(week, week + timedelta(days=6)))
        .scalar()
    )
    cards_due = db.query(models.ReviewCard).filter(models.ReviewCard.due_on <= today).count()

    enrolled = db.query(models.Subject).filter_by(status="enrolled").order_by(models.Subject.name).all()
    careers = db.query(models.Career).filter_by(archived=False).order_by(models.Career.id).all()

    return {
        "today": today.isoformat(),
        "upcoming": agenda.serialize([i for i in items if not i.done and i.type != "window"]),
        "open_windows": agenda.serialize(open_windows),
        "overdue": [
            {"id": a.id, "title": a.name, "subject_id": a.subject_id, "date": a.due_date.isoformat()} for a in overdue
        ],
        "heavy_weeks": [{"week": w.isoformat(), "subjects": s} for w, s in sorted(heavy.items())],
        "habits_today": habits_today,
        "study_minutes_week": int(minutes_week or 0),
        "cards_due": cards_due,
        "enrolled": [
            {
                "id": s.id,
                "name": s.name,
                "ects": s.ects,
                "ai_policy": s.ai_policy,
                "evaluation": evaluation.subject_eval(s),
            }
            for s in enrolled
        ],
        "careers": [evaluation.career_summary(db, c) | {"name": c.name} for c in careers],
        **command.build(db, today, enrolled, items, cards_due, settings.learn_daily_xp, settings.modules.get("bandeja", True)),
    }


routers = (events, habits, extra)
