"""Centro de mando de «Hoy»: qué toca hoy, qué está en riesgo y cuánta carga viene.

Todo sale de datos que ya existen (actividades con fecha y horas estimadas, horas semanales de
cada asignatura, sesiones de estudio, tarjetas, Aprender y la bandeja): no hay nada que
mantener a mano.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import false, func
from sqlalchemy.orm import Session

from . import agenda, evaluation, game, i18n, models


def at_risk(enrolled: list[models.Subject], evals: dict[int, dict], lg: str = "es") -> list[dict]:
    """Asignaturas que ya no se aprueban, con un mínimo suspendido o que piden mucho en lo pendiente."""
    out = []
    for s in enrolled:
        ev = evals[s.id]
        scale = ev.get("scale") or 10
        failed_min = [g["name"] for g in ev["groups"] if g["meets_min"] is False]
        if ev["passed"] is False or (ev["pending"] and not ev["achievable"]):
            out.append({"id": s.id, "name": s.name, "level": "crit", "reason": i18n.tr(lg, "Ya no llega al aprobado")})
        elif failed_min:
            out.append({"id": s.id, "name": s.name, "level": "crit", "reason": i18n.tr(lg, "Por debajo del mínimo en {groups}", groups=", ".join(failed_min))})
        elif ev["needed"] is not None and ev["needed"] >= 0.75 * scale:
            out.append({"id": s.id, "name": s.name, "level": "warn", "reason": i18n.tr(lg, "Necesitas {n} de media en lo que queda", n=f"{ev['needed']:g}")})
    return sorted(out, key=lambda x: (x["level"] != "crit", x["name"]))


def week_load(db: Session, today: date, enrolled: list[models.Subject], weeks: int = 4) -> list[dict]:
    """Horas previstas por semana: las semanales de cada asignatura + las estimadas de lo que vence."""
    start = agenda.week_start(today)
    base = sum(s.weekly_hours or 0 for s in enrolled)
    ids = [s.id for s in enrolled]
    acts = (
        db.query(models.Activity)
        .filter(models.Activity.subject_id.in_(ids) if ids else false())
        .filter(models.Activity.due_date.between(start, start + timedelta(days=7 * weeks - 1)))
        .all()
    )
    per_week: dict[date, list[models.Activity]] = defaultdict(list)
    for a in acts:
        per_week[agenda.week_start(a.due_date)].append(a)
    out = []
    for i in range(weeks):
        w = start + timedelta(days=7 * i)
        due = per_week.get(w, [])
        extra = sum(a.estimated_hours or 0 for a in due if not a.done)
        out.append({"week": w.isoformat(), "hours": round(base + extra, 1), "deliveries": sum(1 for a in due if a.evaluable)})
    return out


def _studied_this_week(db: Session, today: date) -> dict[Optional[int], int]:
    start = agenda.week_start(today)
    rows = (
        db.query(models.StudySession.subject_id, func.coalesce(func.sum(models.StudySession.minutes), 0))
        .filter(models.StudySession.date.between(start, start + timedelta(days=6)))
        .group_by(models.StudySession.subject_id)
        .all()
    )
    return {sid: int(m) for sid, m in rows}


def next_lessons(db: Session, enrolled: list[models.Subject]) -> list[dict]:
    """Siguiente lección pendiente del curso de cada asignatura que cursas."""
    out = []
    by_subject = {c.subject_id: c for c in db.query(models.Course).filter(models.Course.subject_id.in_([s.id for s in enrolled]))} if enrolled else {}
    for s in enrolled:
        course = by_subject.get(s.id)
        if course is None:
            continue
        lessons = [lesson for u in course.units for lesson in u.lessons]
        nxt = next((lesson for lesson in lessons if not lesson.completed_at), None)
        if nxt is not None:
            out.append({"subject_id": s.id, "subject_name": s.name, "lesson_id": nxt.id, "title": nxt.title,
                        "done": sum(1 for x in lessons if x.completed_at), "total": len(lessons)})
    return out


def today_plan(db: Session, today: date, enrolled: list[models.Subject], cards_due: int, lessons: list[dict], lg: str = "es") -> list[dict]:
    """De 1 a 3 cosas concretas para hoy, de más a menos urgente."""
    plan: list[dict] = []
    names = {s.id: s.name for s in enrolled}
    soon = (
        db.query(models.Activity)
        .filter(models.Activity.subject_id.in_(list(names)) if names else false())
        .filter(models.Activity.done.is_(False), models.Activity.evaluable.is_(True))
        .filter(models.Activity.due_date.between(today, today + timedelta(days=7)))
        .order_by(models.Activity.due_date)
        .first()
    )
    if soon is not None:
        days = (soon.due_date - today).days
        when = i18n.tr(lg, "hoy") if days == 0 else i18n.tr(lg, "mañana") if days == 1 else i18n.tr(lg, "en {n} días", n=days)
        plan.append({"kind": "deliver", "subject_id": soon.subject_id, "activity_id": soon.id,
                     "title": i18n.tr(lg, "Avanza «{name}»", name=soon.name), "detail": i18n.tr(lg, "{subject} · vence {when}", subject=names.get(soon.subject_id, ""), when=when)})

    # La asignatura a la que más horas le faltan esta semana (según sus horas semanales).
    studied = _studied_this_week(db, today)
    weekday = today.weekday() + 1
    gaps = []
    for s in enrolled:
        if not s.weekly_hours:
            continue
        expected = s.weekly_hours * 60 * weekday / 7
        gap = expected - studied.get(s.id, 0)
        if gap >= 30 and not any(p.get("subject_id") == s.id for p in plan):
            gaps.append((gap, s))
    if gaps:
        gap, s = max(gaps, key=lambda x: x[0])
        lesson = next((x for x in lessons if x["subject_id"] == s.id), None)
        plan.append({"kind": "study", "subject_id": s.id, "lesson_id": lesson["lesson_id"] if lesson else None,
                     "title": i18n.tr(lg, "Estudia {name}", name=s.name),
                     "detail": i18n.tr(lg, "Vas {h} h por detrás esta semana", h=f"{round(gap / 60, 1):g}")
                     + (i18n.tr(lg, " · siguiente lección: {title}", title=lesson["title"]) if lesson else "")})

    if cards_due:
        plan.append({"kind": "review", "title": i18n.tr(lg, "Repasa {n} tarjeta" if cards_due == 1 else "Repasa {n} tarjetas", n=cards_due),
                     "detail": i18n.tr(lg, "Repaso espaciado pendiente")})
    elif lessons and len(plan) < 3 and not any(p.get("lesson_id") for p in plan):
        x = lessons[0]
        plan.append({"kind": "lesson", "subject_id": x["subject_id"], "lesson_id": x["lesson_id"],
                     "title": i18n.tr(lg, "Una lección de {name}", name=x["subject_name"]), "detail": x["title"]})
    return plan[:3]


def next_exam(items: list[agenda.AgendaItem]) -> Optional[dict]:
    exams = [i for i in items if not i.done and i.kind == "exam" and i.type in ("activity", "event")]
    if not exams:
        return None
    return agenda.serialize([min(exams, key=lambda i: (i.date, i.time or ""))])[0]


def inbox_pending(db: Session) -> dict:
    new = db.query(models.InboxMessage).filter_by(status="new").count()
    proposals = 0
    for msg in db.query(models.InboxMessage).filter(models.InboxMessage.status != "archived"):
        proposals += sum(1 for p in (msg.proposals or []) if p.get("state") == "pending")
    return {"new": new, "proposals": proposals}


def learn_state(db: Session, goal_xp: int) -> dict:
    g = game.state(db, goal_xp)
    return {"streak": g["streak"], "today_xp": g["today_xp"], "goal": g["goal"]}


def build(db: Session, today: date, enrolled: list[models.Subject], items: list[agenda.AgendaItem], cards_due: int,
          goal_xp: int, with_inbox: bool) -> dict:
    evals = {s.id: evaluation.subject_eval(s) for s in enrolled}
    lessons = next_lessons(db, enrolled)
    lg = i18n.lang(db)
    return {
        "today_plan": today_plan(db, today, enrolled, cards_due, lessons, lg),
        "at_risk": at_risk(enrolled, evals, lg),
        "week_load": week_load(db, today, enrolled),
        "next_exam": next_exam(items),
        "next_lessons": lessons,
        "learn": learn_state(db, goal_xp),
        "inbox_pending": inbox_pending(db) if with_inbox else None,
    }
