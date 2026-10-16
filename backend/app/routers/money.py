"""Dinero y trámites: gastos, becas/ayudas, trámites con plazo y coste estimado de matrícula."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import evaluation, models
from ..crud import crud_router, get_or_404, require
from ..database import get_db
from ..schemas import ExpenseIn, ExpenseOut, GrantIn, GrantOut, ProcedureIn, ProcedureOut
from ..settings_store import load_settings


def _validate_expense(db: Session, payload: BaseModel) -> None:
    require(db, models.Subject, payload.subject_id, "La asignatura")
    require(db, models.Term, payload.term_id, "El semestre")


expenses = crud_router(
    "expenses", models.Expense, ExpenseIn, ExpenseOut, label="Gasto", filters=("term_id", "subject_id", "category"),
    order_by=(models.Expense.date.desc(), models.Expense.id.desc()), validate=_validate_expense,
)
grants = crud_router(
    "grants", models.Grant, GrantIn, GrantOut, label="Beca", filters=("status",),
    order_by=(models.Grant.deadline, models.Grant.id),
)
procedures = crud_router(
    "procedures", models.Procedure, ProcedureIn, ProcedureOut, label="Trámite", filters=("status", "category"),
    order_by=(models.Procedure.deadline, models.Procedure.id),
)

extra = APIRouter(prefix="/api", tags=["money"])


@extra.get("/money/summary")
def money_summary(db: Session = Depends(get_db)):
    by_category: dict[str, float] = {}
    by_term: dict[str, float] = {}
    terms = {t.id: t.label for t in db.query(models.Term).all()}
    total = 0.0
    for e in db.query(models.Expense).all():
        total += e.amount
        by_category[e.category] = by_category.get(e.category, 0) + e.amount
        label = terms.get(e.term_id, "Sin semestre") if e.term_id else "Sin semestre"
        by_term[label] = by_term.get(label, 0) + e.amount
    granted = sum(g.amount or 0 for g in db.query(models.Grant).filter(models.Grant.status.in_(("granted", "paid"))))
    return {
        "total": round(total, 2),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "by_term": {k: round(v, 2) for k, v in by_term.items()},
        "grants_total": round(granted, 2),
        "currency": load_settings(db).currency,
    }


@extra.get("/terms/{term_id}/tuition-estimate")
def tuition_estimate(term_id: int, db: Session = Depends(get_db)):
    """Créditos del semestre × precio por crédito (el de la asignatura o el de ajustes).
    El precio sube en segundas y siguientes matrículas: cada asignatura lleva su intento."""
    term = get_or_404(db, models.Term, term_id, "Semestre")
    default_price = load_settings(db).default_price_per_credit
    rows = []
    for s in db.query(models.Subject).filter_by(term_id=term.id).order_by(models.Subject.name):
        price = s.price_per_credit if s.price_per_credit is not None else default_price
        rows.append({"subject_id": s.id, "name": s.name, "ects": s.ects, "attempt": s.attempt, "price_per_credit": price, "amount": round(price * s.ects, 2)})
    return {"term_id": term.id, "label": term.label, "rows": rows, "total": round(sum(r["amount"] for r in rows), 2)}


@extra.get("/grants/eligibility")
def grants_eligibility(db: Session = Depends(get_db)):
    """¿Cumples la nota media que pide cada beca? (con la media de la carrera principal)."""
    career = db.query(models.Career).filter_by(archived=False).order_by(models.Career.id).first()
    average = evaluation.career_summary(db, career)["average"] if career else None
    out = {}
    for g in db.query(models.Grant).all():
        if g.min_average is None:
            out[g.id] = None
        else:
            out[g.id] = None if average is None else average >= g.min_average
    return {"average": average, "meets_min_average": out}


routers = (expenses, grants, procedures, extra)
