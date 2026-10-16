"""Expediente: carreras, semestres, asignaturas, grupos de evaluación y actividades."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import evaluation, models, packs
from ..crud import crud_router, get_or_404, require
from ..database import get_db
from ..schemas import (
    ActivityIn,
    ActivityOut,
    CareerIn,
    CareerOut,
    EvalGroupIn,
    EvalGroupOut,
    SimulateIn,
    SubjectIn,
    SubjectOut,
    TermIn,
    TermOut,
)


def _validate_term(db: Session, payload: BaseModel) -> None:
    require(db, models.Career, payload.career_id, "La carrera")


def _check_scale(career: models.Career, **values) -> None:
    """Notas dentro de la escala de la carrera (0–10, 0–20…)."""
    top = evaluation.career_config(career).grade_max
    for name, v in values.items():
        if v is not None and v > top + 1e-9:
            raise HTTPException(status_code=422, detail=f"{name}: la nota máxima de esta carrera es {top:g}")


def _validate_subject(db: Session, payload: BaseModel) -> None:
    career = require(db, models.Career, payload.career_id, "La carrera")
    term = require(db, models.Term, payload.term_id, "El semestre")
    if term is not None and term.career_id != payload.career_id:
        raise HTTPException(status_code=422, detail="El semestre es de otra carrera")
    cfg = payload.eval_config
    _check_scale(career, **{"Nota final": payload.final_grade, "Aprobado de la EC": cfg.ec_pass, "Mínimo de la PF": cfg.pf_min,
                            "Nota de no presentado": cfg.no_show_grade})


def _validate_group(db: Session, payload: BaseModel) -> None:
    subject = require(db, models.Subject, payload.subject_id, "La asignatura")
    _check_scale(subject.career, **{"Nota mínima": payload.min_grade})


def _validate_activity(db: Session, payload: BaseModel) -> None:
    require(db, models.Subject, payload.subject_id, "La asignatura")
    group = require(db, models.EvalGroup, payload.group_id, "El grupo")
    if group is not None and group.subject_id != payload.subject_id:
        raise HTTPException(status_code=422, detail="El grupo es de otra asignatura")


careers = crud_router("careers", models.Career, CareerIn, CareerOut, label="Carrera", order_by=(models.Career.id,))
terms = crud_router(
    "terms", models.Term, TermIn, TermOut, label="Semestre", filters=("career_id",),
    order_by=(models.Term.start_date,), validate=_validate_term,
)
subjects = crud_router(
    "subjects", models.Subject, SubjectIn, SubjectOut, label="Asignatura",
    filters=("career_id", "term_id", "status", "kind"),
    order_by=(models.Subject.plan_semester, models.Subject.name), validate=_validate_subject,
)
groups = crud_router(
    "groups", models.EvalGroup, EvalGroupIn, EvalGroupOut, label="Grupo", filters=("subject_id",),
    order_by=(models.EvalGroup.position, models.EvalGroup.id), validate=_validate_group,
)
activities = crud_router(
    "activities", models.Activity, ActivityIn, ActivityOut, label="Actividad", filters=("subject_id", "group_id"),
    order_by=(models.Activity.due_date, models.Activity.window_start, models.Activity.id), validate=_validate_activity,
)

extra = APIRouter(prefix="/api", tags=["academic"])


@extra.get("/careers/{career_id}/summary")
def career_summary(career_id: int, db: Session = Depends(get_db)):
    return evaluation.career_summary(db, get_or_404(db, models.Career, career_id, "Carrera"))


@extra.get("/careers/{career_id}/export-pack")
def export_pack(career_id: int, db: Session = Depends(get_db)):
    """Tu carrera como módulo de estudios, para compartirla (sin notas ni nada personal)."""
    return packs.export_career(db, get_or_404(db, models.Career, career_id, "Carrera"))


@extra.get("/subjects/{subject_id}/evaluation")
def subject_evaluation(subject_id: int, target: Optional[float] = None, db: Session = Depends(get_db)):
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura")
    top = evaluation.career_config(subject.career).grade_max
    if target is not None and not 0 <= target <= top:
        raise HTTPException(status_code=422, detail=f"El objetivo va de 0 a {top:g}")
    return evaluation.subject_eval(subject, target=target)


@extra.post("/subjects/{subject_id}/simulate")
def simulate(subject_id: int, payload: SimulateIn, db: Session = Depends(get_db)):
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura")
    top = evaluation.career_config(subject.career).grade_max
    if (payload.target is not None and payload.target > top) or any(v > top for v in payload.hypothetical.values()):
        raise HTTPException(status_code=422, detail=f"Las notas van de 0 a {top:g}")
    own = {a.id for a in subject.activities}
    hypothetical = {k: v for k, v in payload.hypothetical.items() if k in own}
    return evaluation.subject_eval(subject, hypothetical, payload.target)


@extra.get("/evaluations")
def evaluations(career_id: int | None = None, term_id: int | None = None, db: Session = Depends(get_db)):
    """Resumen de evaluación de varias asignaturas a la vez (panel, listado del semestre)."""
    q = db.query(models.Subject)
    if career_id is not None:
        q = q.filter(models.Subject.career_id == career_id)
    if term_id is not None:
        q = q.filter(models.Subject.term_id == term_id)
    else:
        q = q.filter(models.Subject.status == "enrolled")
    return {s.id: evaluation.subject_eval(s) for s in q.all()}


routers = (careers, terms, subjects, groups, activities, extra)
