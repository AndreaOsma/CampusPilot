"""Agenda unificada (entregas, ventanas, eventos, trámites, becas) y su feed iCal.

Una "semana cargada" (▲) es la que tiene entregas evaluables de al menos
`heavy_week_subjects` asignaturas distintas: el aviso que antes vivía a mano en el
calendario de texto.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models


@dataclass
class AgendaItem:
    uid: str
    type: str  # activity | window | event | procedure | grant
    id: int
    title: str
    date: date
    end_date: Optional[date] = None
    time: Optional[str] = None
    end_time: Optional[str] = None
    kind: str = ""
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    done: bool = False
    evaluable: bool = False
    ai_forbidden: bool = False
    url: str = ""


def _subjects(db: Session) -> dict[int, models.Subject]:
    return {s.id: s for s in db.query(models.Subject).all()}


def build(db: Session, start: date, end: date) -> list[AgendaItem]:
    subjects = _subjects(db)
    items: list[AgendaItem] = []

    def subj(sid: Optional[int]) -> tuple[Optional[str], bool]:
        s = subjects.get(sid) if sid else None
        return (s.name, s.ai_policy == "forbidden") if s else (None, False)

    acts = db.query(models.Activity).filter(
        or_(
            models.Activity.due_date.between(start, end),
            (models.Activity.window_start <= end) & (models.Activity.window_end >= start),
        )
    )
    for a in acts:
        name, forbidden = subj(a.subject_id)
        if a.window_start and a.window_end and a.window_start <= end and a.window_end >= start:
            items.append(
                AgendaItem(
                    f"window-{a.id}", "window", a.id, a.name, a.window_start, a.window_end, kind=a.kind,
                    subject_id=a.subject_id, subject_name=name, done=a.done, evaluable=a.evaluable, ai_forbidden=forbidden,
                )
            )
        if a.due_date and start <= a.due_date <= end:
            items.append(
                AgendaItem(
                    f"activity-{a.id}", "activity", a.id, a.name, a.due_date, time=a.due_time, kind=a.kind,
                    subject_id=a.subject_id, subject_name=name, done=a.done, evaluable=a.evaluable, ai_forbidden=forbidden,
                )
            )

    evs = db.query(models.Event).filter(
        or_(
            models.Event.date.between(start, end),
            (models.Event.end_date.isnot(None)) & (models.Event.date <= end) & (models.Event.end_date >= start),
        )
    )
    for e in evs:
        name, _ = subj(e.subject_id)
        items.append(
            AgendaItem(
                f"event-{e.id}", "event", e.id, e.title, e.date, e.end_date, e.start_time, e.end_time, e.kind,
                e.subject_id, name, e.done, url=e.url,
            )
        )

    for p in db.query(models.Procedure).filter(models.Procedure.deadline.between(start, end)):
        items.append(
            AgendaItem(f"procedure-{p.id}", "procedure", p.id, p.title, p.deadline, kind=p.category, done=p.status == "done", url=p.url)
        )
    for g in db.query(models.Grant).filter(models.Grant.deadline.between(start, end)):
        items.append(
            AgendaItem(
                f"grant-{g.id}", "grant", g.id, f"Beca: {g.name}", g.deadline, kind="grant",
                done=g.status not in ("idea", "preparing"), url=g.url,
            )
        )
    items.sort(key=lambda i: (i.date, i.time or "99:99", i.title))
    return items


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def heavy_weeks(items: list[AgendaItem], min_subjects: int) -> dict[date, list[str]]:
    """Semanas (lunes) con entregas evaluables de >= min_subjects asignaturas distintas."""
    per_week: dict[date, set[str]] = {}
    for it in items:
        if it.type not in ("activity", "window") or not it.evaluable or not it.subject_name:
            continue
        # Una ventana cuenta en la semana en que se cierra (es cuando aprieta).
        key = week_start(it.end_date if it.type == "window" and it.end_date else it.date)
        per_week.setdefault(key, set()).add(it.subject_name)
    return {w: sorted(s) for w, s in per_week.items() if len(s) >= min_subjects}


def serialize(items: list[AgendaItem]) -> list[dict]:
    out = []
    for it in items:
        d = asdict(it)
        d["date"] = it.date.isoformat()
        d["end_date"] = it.end_date.isoformat() if it.end_date else None
        out.append(d)
    return out


# ---------- iCal ----------

def _esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Pliega a 75 octetos (RFC 5545 §3.1) sin partir caracteres UTF-8."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 75:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def _dt(d: date, t: Optional[str]) -> str:
    if t:
        # Hora local "flotante" (sin TZID): cada cliente la pinta en su zona, sin VTIMEZONE.
        return f":{d.strftime('%Y%m%d')}T{t.replace(':', '')}00"
    return f";VALUE=DATE:{d.strftime('%Y%m%d')}"


def to_ics(items: list[AgendaItem], name: str = "Campus Pilot") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Campus Pilot//ES",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_esc(name)}",
    ]
    for it in items:
        prefix = {"window": "🪟 ", "procedure": "📋 ", "grant": "💶 "}.get(it.type, "")
        title = f"{prefix}{it.title}" + (f" · {it.subject_name}" if it.subject_name else "")
        lines += ["BEGIN:VEVENT", f"UID:{it.uid}@campus-pilot", f"DTSTAMP:{stamp}", f"SUMMARY:{_esc(title)}"]
        if it.time:
            lines.append("DTSTART" + _dt(it.date, it.time))
            end_t = it.end_time or it.time
            lines.append("DTEND" + _dt(it.end_date or it.date, end_t))
        else:
            lines.append("DTSTART" + _dt(it.date, None))
            # DTEND de día completo es exclusivo: el día siguiente al último.
            lines.append("DTEND" + _dt((it.end_date or it.date) + timedelta(days=1), None))
        if it.url:
            lines.append(f"URL:{_esc(it.url)}")
        if it.done:
            lines.append("X-CAMPUS-DONE:TRUE")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
