"""Fábrica de routers CRUD: listar (con filtros), crear, leer, actualizar y borrar.

Cada recurso declara sus filtros de consulta y un `validate(db, payload)` opcional que
comprueba que las claves foráneas existen y son coherentes (p. ej. que el grupo de una
actividad sea de su misma asignatura) antes de escribir.
"""
# Sin `from __future__ import annotations`: FastAPI tiene que ver las clases reales de
# schema_in en las rutas generadas, no la cadena "schema_in" (la tomaría por un query param).
from typing import Any, Callable, Optional, Type

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import Base, get_db

Validator = Callable[[Session, BaseModel], None]


def get_or_404(db: Session, model: Type[Base], obj_id: Optional[int], label: str = "Elemento") -> Any:
    row = db.get(model, obj_id) if obj_id is not None else None
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} no encontrado")
    return row


def require(db: Session, model: Type[Base], obj_id: Optional[int], label: str) -> Any:
    """Como get_or_404 pero para referencias dentro del cuerpo: 422, no 404."""
    if obj_id is None:
        return None
    row = db.get(model, obj_id)
    if row is None:
        raise HTTPException(status_code=422, detail=f"{label} no existe")
    return row


def crud_router(
    path: str,
    model: Type[Base],
    schema_in: Type[BaseModel],
    schema_out: Type[BaseModel],
    *,
    label: str,
    filters: tuple[str, ...] = (),
    order_by: tuple = (),
    validate: Optional[Validator] = None,
    create_defaults: Optional[Callable[[], dict]] = None,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=[path])

    @router.get(f"/{path}", response_model=list[schema_out])
    def list_rows(request: Request, db: Session = Depends(get_db), limit: int = Query(default=1000, ge=1, le=5000)):
        q = db.query(model)
        for name in filters:
            raw = request.query_params.get(name)
            if raw is None or raw == "":
                continue
            column = getattr(model, name)
            if raw == "null":
                q = q.filter(column.is_(None))
                continue
            try:
                value: Any = int(raw)
            except ValueError:
                value = raw
            q = q.filter(column == value)
        if order_by:
            q = q.order_by(*order_by)
        return q.limit(limit).all()

    @router.post(f"/{path}", response_model=schema_out, status_code=201)
    def create_row(payload: schema_in, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        if validate:
            validate(db, payload)
        row = model(**(create_defaults() if create_defaults else {}), **payload.model_dump(mode="python"))
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @router.get(f"/{path}/{{obj_id}}", response_model=schema_out)
    def get_row(obj_id: int, db: Session = Depends(get_db)):
        return get_or_404(db, model, obj_id, label)

    @router.put(f"/{path}/{{obj_id}}", response_model=schema_out)
    def update_row(obj_id: int, payload: schema_in, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        row = get_or_404(db, model, obj_id, label)
        if validate:
            validate(db, payload)
        for key, value in payload.model_dump(mode="python").items():
            setattr(row, key, value)
        db.commit()
        db.refresh(row)
        return row

    @router.delete(f"/{path}/{{obj_id}}", status_code=204)
    def delete_row(obj_id: int, db: Session = Depends(get_db)):
        db.delete(get_or_404(db, model, obj_id, label))
        db.commit()

    return router
