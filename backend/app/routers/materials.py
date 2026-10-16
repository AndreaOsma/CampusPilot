"""Biblioteca de materiales por asignatura (ver materials.py)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import config, generator, materials, models
from ..crud import get_or_404
from ..database import get_db

router = APIRouter(prefix="/api/materials", tags=["materials"])


async def read_upload(f: UploadFile) -> tuple[str, str, Optional[bytes]]:
    """(nombre, texto, bytes del PDF o None) de un material subido; 4xx legible si no vale."""
    name = (f.filename or "material").rsplit("/", 1)[-1][:200]
    lower = name.lower()
    if lower.endswith(".pdf"):
        raw = await f.read(config.MAX_PDF_BYTES + 1)
        try:
            # pypdf es CPU puro y lento con PDFs grandes: fuera del bucle de eventos.
            return name, await run_in_threadpool(generator.pdf_to_text, raw, name), raw
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if lower.endswith((".md", ".txt", ".markdown")):
        raw = await f.read(config.MAX_MATERIAL_BYTES + 1)
        if len(raw) > config.MAX_MATERIAL_BYTES:
            raise HTTPException(status_code=413, detail=f"«{name}» supera 1,5 MB de texto: súbelo por partes")
        try:
            return name, raw.decode("utf-8"), None
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail=f"«{name}» no es texto UTF-8")
    raise HTTPException(status_code=422, detail=f"«{name}»: sube PDF, Markdown (.md) o texto (.txt)")


@router.get("")
def list_materials(subject_id: int, db: Session = Depends(get_db)):
    rows = db.query(models.Material).filter_by(subject_id=subject_id).order_by(models.Material.module_ref, models.Material.filename)
    return [materials.out(m) for m in rows]


@router.post("", status_code=201)
async def upload_material(file: UploadFile = File(...), subject_id: int = Form(...), kind: str = Form("manual"),
                          module_ref: str = Form("", max_length=64), db: Session = Depends(get_db)):
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura")
    name, text, pdf = await read_upload(file)
    try:
        generator.check_material(name, text, kind, subject)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return materials.out(materials.save(db, subject, name, text, kind, module_ref, pdf))


class MaterialPatch(BaseModel):
    module_ref: str = Field(default="", max_length=64)


@router.patch("/{material_id}")
def patch_material(material_id: int, payload: MaterialPatch, db: Session = Depends(get_db)):
    row = get_or_404(db, models.Material, material_id, "Material")
    row.module_ref = payload.module_ref
    db.commit()
    return materials.out(row)


@router.get("/{material_id}/file")
def material_file(material_id: int, db: Session = Depends(get_db)):
    """El PDF original, para abrirlo en el navegador por la página (#page=N)."""
    row = get_or_404(db, models.Material, material_id, "Material")
    path = materials.file_path(row.id)
    if not row.has_file or not path.is_file():
        raise HTTPException(status_code=404, detail="Este material no tiene PDF guardado")
    return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})


@router.delete("/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db)):
    materials.delete(db, get_or_404(db, models.Material, material_id, "Material"))
