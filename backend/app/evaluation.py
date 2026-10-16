"""Puente entre el ORM y grades.py: resumen de evaluación por asignatura y de la carrera."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from sqlalchemy.orm import Session

from . import grades, models
from .schemas import CareerConfig

DONE_STATUSES = ("passed", "convalidated")


def career_config(career: Optional[models.Career]) -> CareerConfig:
    try:
        return CareerConfig.model_validate((career.config if career else None) or {})
    except ValueError:
        return CareerConfig()


def eval_data(subject: models.Subject) -> grades.EvalData:
    cfg = subject.eval_config or {}
    cc = career_config(subject.career)
    k = cc.grade_max / 10  # valores por defecto pensados en 0–10, llevados a la escala
    return grades.EvalData(
        model=subject.eval_model,
        groups=[grades.GroupData(g.id, g.name, g.weight, g.min_grade, g.role) for g in subject.groups],
        activities=[
            grades.ActivityData(a.id, a.group_id, a.weight, a.grade, a.max_grade, a.evaluable) for a in subject.activities
        ],
        ec_pass=float(cfg.get("ec_pass", cc.pass_mark)),
        pf_min=float(cfg.get("pf_min", 4 * k)),
        no_show_grade=float(cfg.get("no_show_grade", 3 * k)),
        scale=cc.grade_max,
        pass_grade=cc.pass_mark,
    )


def subject_eval(
    subject: models.Subject, hypothetical: Optional[dict[int, float]] = None, target: Optional[float] = None
) -> dict:
    result = grades.evaluate(eval_data(subject), hypothetical or {}, target)
    out = asdict(result)
    out["official_grade"] = subject.final_grade
    cc = career_config(subject.career)
    out["scale"], out["pass_mark"] = cc.grade_max, cc.pass_mark
    return out


def effective_grade(subject: models.Subject) -> Optional[float]:
    """Nota que cuenta para la media: la oficial si existe; si no, la calculada (solo si aprobada)."""
    if subject.final_grade is not None:
        return subject.final_grade
    if subject.status == "passed":
        res = grades.evaluate(eval_data(subject))
        return res.final if res.passed else None
    return None


def career_summary(db: Session, career: models.Career) -> dict:
    subjects = db.query(models.Subject).filter_by(career_id=career.id).all()
    done = [s for s in subjects if s.status in DONE_STATUSES]
    by_kind: dict[str, dict[str, float]] = {}
    for s in subjects:
        k = by_kind.setdefault(s.kind, {"done": 0.0, "enrolled": 0.0, "total": 0.0})
        k["total"] += s.ects
        if s.status in DONE_STATUSES:
            k["done"] += s.ects
        elif s.status == "enrolled":
            k["enrolled"] += s.ects
    avg = grades.career_average([(s.ects, effective_grade(s)) for s in done])
    return {
        "career_id": career.id,
        "ects_done": sum(s.ects for s in done),
        "ects_enrolled": sum(s.ects for s in subjects if s.status == "enrolled"),
        "ects_goal": career.ects_goal,
        "average": round(avg, 3) if avg is not None else None,
        "by_kind": by_kind,
        "requirements": career.requirements or {},
        "config": career_config(career).model_dump(),
        "subjects": len(subjects),
    }
