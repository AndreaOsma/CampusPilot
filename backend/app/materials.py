"""Biblioteca de materiales (Aprender → Biblioteca).

Lo que subes para generar lecciones o teoría se queda guardado por asignatura (y módulo del
plan docente, si lo hay): así se puede regenerar o ampliar sin volver a subirlo, el tutor
responde con él y la teoría enlaza al PDF por la página que cita. El texto va en la base de
datos (es lo que lee la IA y entra en las copias); el PDF original, en `DATA_DIR/materials/`
con el id como nombre (nunca el nombre que trae el archivo). Pasa las mismas barreras que el
generador: nada que parezca el enunciado de una actividad evaluable.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from . import config, generator, models

FILES_DIR = config.DATA_DIR / "materials"


def file_path(material_id: int) -> Path:
    return FILES_DIR / f"{int(material_id)}.pdf"


def save(db: Session, subject: models.Subject, filename: str, text: str, kind: str, module_ref: str = "",
         pdf: Optional[bytes] = None) -> models.Material:
    """Guarda (o sustituye, si ya hay uno con el mismo nombre en la asignatura) un material ya comprobado."""
    row = db.query(models.Material).filter_by(subject_id=subject.id, filename=filename).first()
    if row is None:
        row = models.Material(subject_id=subject.id, filename=filename, text="")
        db.add(row)
    row.text, row.kind = text, kind
    row.module_ref = module_ref or row.module_ref or ""
    row.pages = len(re.findall(r"<!-- página \d+ -->", text)) or None
    db.flush()
    if pdf is not None:
        FILES_DIR.mkdir(parents=True, exist_ok=True)
        file_path(row.id).write_bytes(pdf)
        row.has_file = True
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, row: models.Material) -> None:
    file_path(row.id).unlink(missing_ok=True)
    db.delete(row)
    db.commit()


def as_part(row: models.Material) -> str:
    """El material como entra en el prompt (el nombre es por lo que la IA lo cita)."""
    return f"===== MATERIAL: {row.filename} =====\n{row.text}"


def check(row: models.Material, subject: models.Subject) -> None:
    """Las barreras del generador, otra vez: la política de IA de la asignatura puede haber cambiado."""
    generator.check_material(row.filename, row.text, row.kind, subject)


def out(row: models.Material) -> dict:
    return {
        "id": row.id, "subject_id": row.subject_id, "module_ref": row.module_ref, "kind": row.kind, "filename": row.filename,
        "pages": row.pages, "has_file": row.has_file, "chars": len(row.text), "created_at": row.created_at.isoformat(),
    }
