"""Plan de estudio semanal de una asignatura (Aprender → Esta semana). Sin IA: reglas.

Con el temario del plan docente, las fechas de la agenda y el progreso de Aprender:

1. **Calendario**: las semanas (lunes a domingo) desde el inicio del semestre (o la primera
   actividad) hasta la última entrega evaluable (o el fin del semestre).
2. **Reparto**: los módulos, en orden, en esas semanas, en proporción a sus apartados. Es lo
   que haría quien prepara una guía de estudio sin más información: se ve y se puede seguir.
3. **Esta semana**: los módulos que tocan; lo que va **atrasado** (módulos de semanas pasadas
   con lecciones sin hacer o sin material aún); las **entregas** de los próximos 14 días; los
   **objetivos más flojos** de lo ya visto, y el repaso pendiente.

Devuelve datos, no frases: el texto lo pone el frontend en el idioma de la app.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import clock, models, syllabus

HORIZON_WEEKS = 26


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _deadline(a: models.Activity) -> Optional[date]:
    return a.window_end or a.due_date


def weeks_for(subject: models.Subject, today: date) -> list[date]:
    """Semanas desde el inicio del semestre (o hoy / la primera entrega) hasta la última entrega
    evaluable (estudiar para llegar a ella), o el fin del semestre, o 12 semanas."""
    dates = [d for a in subject.activities if a.evaluable for d in [_deadline(a)] if d]
    if subject.term and subject.term.start_date:
        start = subject.term.start_date
    else:
        start = min([today, *dates])
    if dates:
        end = max(dates)
    elif subject.term and subject.term.end_date:
        end = subject.term.end_date
    else:
        end = today + timedelta(weeks=12)
    first, last = _monday(start), _monday(max(end, start))
    weeks = []
    w = first
    while w <= last and len(weeks) < HORIZON_WEEKS:
        weeks.append(w)
        w += timedelta(weeks=1)
    return weeks or [_monday(today)]


def allocate(modules: list[dict], n_weeks: int) -> list[list[str]]:
    """Reparte los módulos (en orden) en n semanas según su número de apartados."""
    if not modules:
        return [[] for _ in range(n_weeks)]
    weights = [max(1, len(m.get("topics") or [])) for m in modules]
    total = sum(weights)
    out: list[list[str]] = [[] for _ in range(n_weeks)]
    acc = 0.0
    for m, w in zip(modules, weights):
        a = int(acc / total * n_weeks)
        acc += w
        b = max(a + 1, round(acc / total * n_weeks))
        for i in range(a, min(b, n_weeks)):
            out[i].append(m["ref"])
    return out


def build(db: Session, subject: models.Subject, today: Optional[date] = None) -> dict:
    today = today or clock.today()
    modules = syllabus.modules_of(subject)
    course = db.query(models.Course).filter_by(subject_id=subject.id).first()
    units = list(course.units) if course else []
    lessons_by_module: dict[str, list[models.Lesson]] = {}
    for u in units:
        lessons_by_module.setdefault(u.module_ref or "", []).extend(u.lessons)

    weeks = weeks_for(subject, today)
    plan = allocate(modules, len(weeks))
    now = _monday(today)
    current = next((i for i, w in enumerate(weeks) if w == now), len(weeks) - 1 if now > weeks[-1] else 0)

    def module_state(ref: str) -> dict:
        lessons = lessons_by_module.get(ref, [])
        pending = [lesson for lesson in lessons if not lesson.completed_at]
        m = next(x for x in modules if x["ref"] == ref)
        return {"ref": ref, "title": m["title"], "lessons": len(lessons), "done": len(lessons) - len(pending),
                "next_lesson_id": pending[0].id if pending else None, "has_material": bool(lessons) or _has_material(db, subject, ref)}

    this_week = [module_state(r) for r in plan[current]] if now >= weeks[0] else []
    behind = []
    for i in range(0, current if now >= weeks[0] else 0):
        for ref in plan[i]:
            if ref in plan[current] or any(b["ref"] == ref for b in behind):
                continue
            st = module_state(ref)
            if st["lessons"] == 0 or st["done"] < st["lessons"]:
                behind.append(st)

    deadlines = sorted(
        ({"activity_id": a.id, "name": a.name, "kind": a.kind, "date": _deadline(a).isoformat(), "days": (_deadline(a) - today).days}
         for a in subject.activities if a.evaluable and not a.done and _deadline(a) and 0 <= (_deadline(a) - today).days <= 14),
        key=lambda x: x["days"],
    )

    seen_modules = {r for wk in plan[: current + 1] for r in wk}
    seen_codes = {c for m in modules if m["ref"] in seen_modules for c in m.get("objectives") or []}
    steps = [s for u in units for lesson in u.lessons for s in lesson.steps if s.kind != "info"]
    weak = []
    for o in syllabus.objectives_of(subject):
        if seen_codes and o["code"] not in seen_codes:
            continue
        mine = [s for s in steps if o["code"] in (s.objectives or [])]
        ok, ko = sum(s.correct for s in mine), sum(s.wrong for s in mine)
        if ok + ko >= 3 and ok / (ok + ko) < 0.6:
            weak.append({"code": o["code"], "text": o["text"], "mastery": round(ok / (ok + ko), 3)})
    weak.sort(key=lambda x: x["mastery"])
    due_reviews = sum(1 for s in steps if s.box and s.due_on and s.due_on <= today)

    minutes = sum(x.minutes for x in db.query(models.StudySession).filter(
        models.StudySession.subject_id == subject.id, models.StudySession.date >= now, models.StudySession.date <= today))
    return {
        "subject_id": subject.id,
        "course_id": course.id if course else None,
        "has_plan": bool(modules),
        "weeks": [{"start": w.isoformat(), "modules": plan[i]} for i, w in enumerate(weeks)],
        "current_week": current,
        "this_week": this_week,
        "behind": behind,
        "deadlines": deadlines,
        "weak_objectives": weak[:3],
        "due_reviews": due_reviews,
        "hours_goal": subject.weekly_hours,
        "minutes_this_week": minutes,
    }


def _has_material(db: Session, subject: models.Subject, ref: str) -> bool:
    return db.query(models.Material.id).filter_by(subject_id=subject.id, module_ref=ref).first() is not None
