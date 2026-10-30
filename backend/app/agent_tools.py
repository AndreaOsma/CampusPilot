"""Herramientas para asistentes (ágora): logística del estudio — agenda, entregas, notas,
hábitos y horas de estudio. Ver dev/lib/agent-api; token en CAMPUS_AGENT_TOKEN.

Deliberadamente NO expone materiales ni enunciados: un asistente general no debe hacer actividades
evaluables (muchas universidades lo prohíben). Única excepción, «repaso» (Andrea, 2026-10-28): preguntas
de autoevaluación de las lecciones, sacadas del manual, para repasar por voz con ágora — y solo de
asignaturas cuyo plan docente permite la IA (ai_policy allowed/limited); «unknown» cuenta como prohibida."""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import agenda, clock, learn, models
from .agent_api import AgentError, AgentRegistry

agent = AgentRegistry("campus-pilot", "Campus Pilot", "Estudios: agenda, entregas, notas, hábitos y horas de estudio (solo logística).",
                      token_env="CAMPUS_AGENT_TOKEN")


def _subject(db: Session, text: str) -> models.Subject:
    n = text.strip().lower()
    rows = db.query(models.Subject).all()
    hits = [s for s in rows if s.code.lower() == n or s.name.lower() == n] or [s for s in rows if n in s.name.lower()]
    active = [s for s in hits if s.status == "enrolled"]
    hits = active if len(hits) > 1 and len(active) == 1 else hits
    if len(hits) != 1:
        raise AgentError("No sé qué asignatura es «{}»{}".format(
            text, ". Coinciden: " + "; ".join(s.name for s in hits[:10]) if hits else ". Usa la herramienta asignaturas."), 404)
    return hits[0]


class Dias(BaseModel):
    dias: int = Field(14, ge=1, le=120)


@agent.tool("agenda", "Entregas, exámenes, eventos y ventanas de los próximos N días")
def agenda_(db: Session, p: Dias):
    today = clock.today()
    keep = ("type", "title", "date", "end_date", "time", "end_time", "subject_name", "done", "kind", "evaluable", "ai_forbidden")
    return [{k: v for k, v in it.items() if k in keep and v not in (None, "", [])} for it in agenda.serialize(agenda.build(db, today, today + timedelta(days=p.dias)))]


@agent.tool("entregas_pendientes", "Actividades sin entregar (incluye las vencidas del último mes)")
def entregas_pendientes(db: Session):
    today = clock.today()
    rows = (db.query(models.Activity).filter(models.Activity.done.is_(False), models.Activity.due_date.isnot(None),
                                             models.Activity.due_date >= today - timedelta(days=30))
            .order_by(models.Activity.due_date).all())
    return [{"id": a.id, "actividad": a.name, "asignatura": a.subject.name if a.subject else None, "entrega": a.due_date,
             "hora": a.due_time, "evaluable": a.evaluable, "peso": a.weight, "vencida": a.due_date < today} for a in rows]


@agent.tool("asignaturas", "Asignaturas con estado, créditos y notas (las que tienen nota o están en curso)")
def asignaturas(db: Session):
    out = []
    for s in db.query(models.Subject).order_by(models.Subject.plan_semester, models.Subject.name):
        graded = [a for a in s.activities if a.grade is not None]
        if s.status in ("pending", "dropped") and not graded and s.final_grade is None:
            continue
        out.append({"codigo": s.code, "asignatura": s.name, "estado": s.status, "creditos": s.ects, "nota_final": s.final_grade,
                    "notas": [{"actividad": a.name, "nota": a.grade, "sobre": a.max_grade} for a in graded]})
    return out


class Rango(BaseModel):
    dias: int = Field(28, ge=1, le=365)


@agent.tool("horas_de_estudio", "Minutos estudiados por asignatura en los últimos N días")
def horas_de_estudio(db: Session, p: Rango):
    end = clock.today()
    start = end - timedelta(days=p.dias - 1)
    rows = (db.query(models.StudySession.subject_id, func.sum(models.StudySession.minutes))
            .filter(models.StudySession.date.between(start, end)).group_by(models.StudySession.subject_id).all())
    names = {s.id: s.name for s in db.query(models.Subject)}
    return {"desde": start, "hasta": end, "total_min": int(sum(m or 0 for _, m in rows)),
            "por_asignatura": {names.get(sid, "Sin asignatura"): int(m or 0) for sid, m in rows}}


@agent.tool("habitos", "Hábitos activos y qué días de esta semana están hechos")
def habitos(db: Session):
    start = agenda.week_start(clock.today())
    done: dict[int, list[date]] = {}
    for c in db.query(models.HabitCheck).filter(models.HabitCheck.date.between(start, start + timedelta(days=6))):
        done.setdefault(c.habit_id, []).append(c.date)
    return [{"habito": h.title, "dias_semana": h.weekdays, "hechos_esta_semana": sorted(done.get(h.id, []))}
            for h in db.query(models.Habit).filter_by(active=True)]


class Estudio(BaseModel):
    minutos: int = Field(gt=0, le=24 * 60)
    asignatura: Optional[str] = Field(None, max_length=200, description="Código o nombre; vacío = sin asignatura")
    fecha: date = Field(default_factory=lambda: clock.today())
    nota: str = Field("", max_length=300)


def _estudio_preview(db: Session, p: Estudio) -> str:
    s = _subject(db, p.asignatura) if p.asignatura else None
    return f"Apuntar {p.minutos} min de estudio el {p.fecha.strftime('%d/%m')}" + (f" en {s.name}" if s else " sin asignatura") + (f" («{p.nota}»)" if p.nota else "")


@agent.tool("registrar_estudio", "Apunta una sesión de estudio", write=True, preview=_estudio_preview)
def registrar_estudio(db: Session, p: Estudio):
    s = _subject(db, p.asignatura) if p.asignatura else None
    row = models.StudySession(subject_id=s.id if s else None, date=p.fecha, minutes=p.minutos, kind="manual", note=p.nota)
    db.add(row)
    db.commit()
    return {"fecha": row.date, "minutos": row.minutes, "asignatura": s.name if s else None}


class Habito(BaseModel):
    habito: str = Field(min_length=1, max_length=200)
    fecha: date = Field(default_factory=lambda: clock.today())


def _habit(db: Session, name: str) -> models.Habit:
    n = name.strip().lower()
    rows = db.query(models.Habit).filter_by(active=True).all()
    hits = [h for h in rows if h.title.lower() == n] or [h for h in rows if n in h.title.lower()]
    if len(hits) != 1:
        raise AgentError("No sé qué hábito es «{}». Hay: {}".format(name, "; ".join(h.title for h in rows)), 404)
    return hits[0]


def _habito_preview(db: Session, p: Habito) -> str:
    return f"Marcar «{_habit(db, p.habito).title}» como hecho el {p.fecha.strftime('%d/%m')}"


@agent.tool("marcar_habito", "Marca un hábito como hecho un día", write=True, preview=_habito_preview)
def marcar_habito(db: Session, p: Habito):
    h = _habit(db, p.habito)
    if not db.query(models.HabitCheck).filter_by(habit_id=h.id, date=p.fecha).first():
        db.add(models.HabitCheck(habit_id=h.id, date=p.fecha))
        db.commit()
    return {"habito": h.title, "fecha": p.fecha, "hecho": True}


class Entregada(BaseModel):
    actividad_id: int


def _activity_label(db: Session, activity_id: int) -> str:
    a = db.get(models.Activity, activity_id)
    if a is None:
        raise AgentError(f"No existe la actividad {activity_id}", 404)
    return "Marcar como entregada «{}»{}".format(a.name, f" ({a.subject.name})" if a.subject else "")


@agent.tool("marcar_entregada", "Marca una actividad como entregada (por id, de entregas_pendientes)", write=True,
            preview=lambda db, p: _activity_label(db, p.actividad_id))
def marcar_entregada(db: Session, p: Entregada):
    a = db.get(models.Activity, p.actividad_id)
    if a is None:
        raise AgentError(f"No existe la actividad {p.actividad_id}", 404)
    a.done = True
    db.commit()
    return {"actividad": a.name, "entregada": True}

# ---------- Avisos (para el parte de la mañana y los avisos por umbral de ágora) ----------
# Formato común: {"nivel": "urgente" | "pronto", "clave": id estable (para no repetir), "texto", "ver"?}


@agent.tool("avisos", "Entregas en las próximas 48 h sin marcar y entregas vencidas")
def avisos(db: Session):
    today, out = clock.today(), []
    for a in db.query(models.Activity).filter(models.Activity.done.is_(False), models.Activity.due_date.isnot(None),
                                              models.Activity.due_date >= today - timedelta(days=7), models.Activity.due_date <= today + timedelta(days=2)):
        days = (a.due_date - today).days
        subj = f" ({a.subject.name})" if a.subject else ""
        out.append({"nivel": "urgente", "clave": f"entrega-{a.id}-{a.due_date}",
                    "texto": "«{}»{} {}".format(a.name, subj, f"venció el {a.due_date:%d/%m}" if days < 0 else "se entrega HOY" + (f" a las {a.due_time}" if a.due_time else "") if days == 0 else f"se entrega en {days} día(s) ({a.due_date:%d/%m})"),
                    "ver": "/semestre"})
    return out


# ── repaso por voz ───────────────────────────────────────────────────────────

REVIEW_POLICIES = ("allowed", "limited")
REVIEW_KINDS = ("choice", "truefalse", "numeric")  # se pueden preguntar y contestar de palabra


class Repaso(BaseModel):
    asignatura: Optional[str] = Field(None, max_length=120)
    n: int = Field(5, ge=1, le=10)


@agent.tool("repaso", "Preguntas de autoevaluación del manual (con su solución) para repasar de palabra con Andrea: "
            "primero las que tocan por repaso espaciado y las falladas. Solo asignaturas cuyo plan docente permite la IA; "
            "nunca enunciados de PEC/PR ni exámenes. Pregunta una a una, espera su respuesta y corrígela con la solución")
def repaso(db: Session, p: Repaso):
    q = (db.query(models.LessonStep).join(models.Lesson).join(models.CourseUnit).join(models.Course).join(models.Subject)
         .filter(models.Subject.ai_policy.in_(REVIEW_POLICIES), models.LessonStep.kind.in_(REVIEW_KINDS)))
    if p.asignatura:
        subj = _subject(db, p.asignatura)
        if subj.ai_policy not in REVIEW_POLICIES:
            raise AgentError("«{}» no permite la IA en su plan docente (o no lo dice): no la repaso contigo. "
                             "Si el plan sí lo permite, cámbialo en Campus Pilot.".format(subj.name), 403)
        q = q.filter(models.Subject.id == subj.id)
    today = clock.today()
    steps = q.all()
    if not steps:
        return {"preguntas": [], "mensaje": "No hay preguntas para repasar: ninguna asignatura con lecciones permite la IA "
                                           "(o no lo dice su plan docente)."}
    # Toca hoy o antes > falladas > nunca vistas > el resto; dentro de cada grupo, al azar.
    rng = random.Random()
    def rank(st):
        due = st.due_on is not None and st.due_on <= today
        return (0 if due else 1 if st.wrong > st.correct else 2 if st.correct + st.wrong == 0 else 3, rng.random())
    out = []
    for st in sorted(steps, key=rank)[:p.n]:
        _, solution, expl = learn.check(st, None)
        item = {"id": st.id, "asignatura": st.lesson.unit.course.subject.name, "leccion": st.lesson.title,
                "tipo": {"choice": "elige", "truefalse": "verdadero o falso", "numeric": "número"}[st.kind],
                "pregunta": st.prompt, "solucion": solution, "explicacion": expl, "fuente": st.source}
        if st.kind == "choice":
            item["opciones"] = (st.data or {}).get("options", [])
        out.append(item)
    return {"preguntas": out}
