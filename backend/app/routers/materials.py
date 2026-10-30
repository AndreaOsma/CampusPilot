"""Biblioteca de materiales por asignatura (ver materials.py)."""
from __future__ import annotations

import secrets
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


@router.post("/video", status_code=201)
async def upload_video(video: UploadFile = File(...), transcript: Optional[UploadFile] = File(None), subject_id: int = Form(...),
                       module_ref: str = Form("", max_length=64), db: Session = Depends(get_db)):
    """Un vídeo de la asignatura con su transcripción (opcional): el vídeo se ve en la app y la
    transcripción es lo que leen el generador y el tutor (como un material «video»)."""
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura")
    name = (video.filename or "video").rsplit("/", 1)[-1][:200]
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    mime = materials.VIDEO_MIME.get(ext)
    if not mime:
        raise HTTPException(status_code=422, detail=f"«{name}»: sube el vídeo en MP4, WebM o MOV")
    text = ""
    if transcript is not None and transcript.filename:
        _, text, _ = await read_upload(transcript)
    try:
        generator.check_material(name, text, "video", subject)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    materials.FILES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = materials.FILES_DIR / f".subida-{secrets.token_hex(8)}"
    size = 0
    try:
        with tmp.open("wb") as fh:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > config.MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail=f"El vídeo pasa de {config.MAX_VIDEO_BYTES // 1024 // 1024} MB")
                fh.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="El vídeo está vacío")
        row = materials.save(db, subject, name, text, "video", module_ref)
        return materials.out(materials.attach_video(db, row, tmp, mime))
    finally:
        tmp.unlink(missing_ok=True)


@router.get("/{material_id}/file")
def material_file(material_id: int, db: Session = Depends(get_db)):
    """El fichero original: el PDF para abrirlo por la página (#page=N) o el vídeo para verlo
    (FileResponse atiende Range, así se puede saltar a cualquier minuto)."""
    row = get_or_404(db, models.Material, material_id, "Material")
    mime = row.file_mime or "application/pdf"
    path = materials.file_path(row.id, mime)
    if not row.has_file or not path.is_file():
        raise HTTPException(status_code=404, detail="Este material no tiene archivo guardado")
    return FileResponse(path, media_type=mime, headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})


@router.get("/{material_id}/images/{ref}")
def material_image(material_id: int, ref: str, db: Session = Depends(get_db)):
    """Una imagen sacada del PDF (la que enseña una tarjeta de teoría)."""
    get_or_404(db, models.Material, material_id, "Material")
    path = materials.image_file(material_id, ref)
    if path is None:
        raise HTTPException(status_code=404, detail="Esa imagen no está en el material")
    mime = "image/jpeg" if path.suffix == ".jpg" else "image/png"
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})


@router.delete("/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db)):
    materials.delete(db, get_or_404(db, models.Material, material_id, "Material"))
