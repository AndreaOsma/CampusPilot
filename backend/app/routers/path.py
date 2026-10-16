"""Trayectoria: cursos, certificaciones, proyectos, prácticas… y las competencias que suman."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..crud import crud_router, require
from ..database import get_db
from ..schemas import PathItemIn, PathItemOut


def _validate(db: Session, payload: BaseModel) -> None:
    require(db, models.Subject, payload.subject_id, "La asignatura")


items = crud_router(
    "path", models.PathItem, PathItemIn, PathItemOut, label="Elemento", filters=("kind", "status"),
    order_by=(models.PathItem.start_date.desc(), models.PathItem.id.desc()), validate=_validate,
)

extra = APIRouter(prefix="/api", tags=["path"])


@extra.get("/path-skills")
def skills(db: Session = Depends(get_db)):
    """Competencias agregadas: en cuántos elementos aparece cada una y cuántos están hechos."""
    agg: dict[str, dict] = {}
    for item in db.query(models.PathItem).filter(models.PathItem.status != "dropped"):
        for skill in item.skills or []:
            key = skill.lower()
            row = agg.setdefault(key, {"skill": skill, "count": 0, "done": 0})
            row["count"] += 1
            if item.status == "done":
                row["done"] += 1
    return sorted(agg.values(), key=lambda r: (-r["done"], -r["count"], r["skill"].lower()))


routers = (items, extra)
