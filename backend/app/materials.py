"""Biblioteca de materiales (Aprender → Biblioteca).

Lo que subes para generar lecciones o teoría se queda guardado por asignatura (y módulo del
plan docente, si lo hay): así se puede regenerar o ampliar sin volver a subirlo, el tutor
responde con él y la teoría enlaza al PDF por la página que cita. El texto va en la base de
datos (es lo que lee la IA y entra en las copias); el PDF original, en `DATA_DIR/materials/`
con el id como nombre (nunca el nombre que trae el archivo). Pasa las mismas barreras que el
generador: nada que parezca el enunciado de una actividad evaluable.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from . import config, generator, models

logger = logging.getLogger("campus.materials")

FILES_DIR = config.DATA_DIR / "materials"


VIDEO_MIME = {".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}


def file_path(material_id: int, mime: str = "application/pdf") -> Path:
    return FILES_DIR / (f"{int(material_id)}.pdf" if mime == "application/pdf" else f"{int(material_id)}.video")


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
        _drop_images(row.id)  # otro PDF: sus imágenes se sacan de nuevo al generar
        row.has_file, row.file_mime = True, "application/pdf"
    db.commit()
    db.refresh(row)
    return row


def attach_video(db: Session, row: models.Material, tmp: Path, mime: str) -> models.Material:
    """Mueve a su sitio el vídeo ya escrito en disco (por trozos, sin cargarlo en memoria)."""
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    file_path(row.id, "application/pdf").unlink(missing_ok=True)
    tmp.replace(file_path(row.id, mime))
    row.has_file, row.file_mime = True, mime
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, row: models.Material) -> None:
    file_path(row.id).unlink(missing_ok=True)
    file_path(row.id, "video").unlink(missing_ok=True)
    _drop_images(row.id)
    db.delete(row)
    db.commit()


# ---------- Imágenes del manual (para la teoría de Aprender) ----------
# Del PDF guardado se sacan las imágenes de contenido (capturas, esquemas, diagramas) a
# `materials/<id>-img/`, con un catálogo. Fuera lo que se repite en muchas páginas (logos,
# cabeceras) y lo pequeño (iconos, adornos). Al generar, cada página del texto lleva al final una
# línea por imagen con lo que se lee justo antes de ella: así la IA puede poner en una tarjeta la
# imagen que ilustra lo que explica (no ve la imagen, solo dónde está). Sin Pillow (p. ej. en el
# móvil) no hay imágenes y todo sigue funcionando igual.

IMAGE_REF = re.compile(r"^p(\d{1,5})-(\d{1,3})$")
MIN_W, MIN_H, MIN_AREA = 200, 120, 60_000
REPEATED_PAGES = 2   # una imagen idéntica en más páginas que esto es un logo, un adorno o una portada
MAX_PER_PAGE = 6
MAX_SIDE = 1600      # se reduce lo más grande: la tarjeta no necesita más
CATALOG = "catalogo.json"


def images_dir(material_id: int) -> Path:
    return FILES_DIR / f"{int(material_id)}-img"


def _drop_images(material_id: int) -> None:
    d = images_dir(material_id)
    if d.is_dir():
        for f in d.iterdir():
            f.unlink(missing_ok=True)
        d.rmdir()


def _page_images(page) -> tuple[list[tuple[str, object]], dict[str, str]]:
    """(imágenes de la página como (nombre, ImageFile), texto que se lee justo antes de cada una)."""
    before: dict[str, str] = {}
    seen: list[str] = []

    def on_text(text, *_):
        if text and text.strip():
            seen.append(text)

    def on_op(op, args, *_):
        if op == b"Do" and args:
            tail = re.sub(r"\s+", " ", " ".join(seen[-12:])).strip()
            before.setdefault(str(args[0]).lstrip("/"), tail[-140:])

    try:
        page.extract_text(visitor_text=on_text, visitor_operand_before=on_op)
    except Exception:  # noqa: BLE001 — sin contexto la imagen sigue valiendo
        pass
    out = []
    try:
        for im in page.images:
            out.append((im.name.rsplit(".", 1)[0], im))
    except Exception:  # noqa: BLE001 — una página rara no tira el resto
        logger.warning("Imágenes ilegibles en una página", exc_info=True)
    return out, before


def extract_images(material_id: int, pdf: bytes) -> list[dict]:
    """Saca las imágenes de contenido del PDF y guarda su catálogo. [] si no hay o falta Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return []
    from pypdf import PdfReader

    Image.MAX_IMAGE_PIXELS = 40_000_000  # una imagen gigante dentro de un PDF no tumba el servidor
    _drop_images(material_id)
    reader = PdfReader(io.BytesIO(pdf))
    pages = []
    counts: Counter[str] = Counter()
    for number, page in enumerate(reader.pages, start=1):
        found, before = _page_images(page)
        kept = []
        for name, im in found:
            try:
                w, h = im.image.size
            except Exception:  # noqa: BLE001 — formato raro o bomba de descompresión: fuera
                continue
            if w < MIN_W or h < MIN_H or w * h < MIN_AREA:
                continue
            digest = hashlib.sha1(im.data).hexdigest()
            counts[digest] += 1
            kept.append((name, im, digest))
        pages.append((number, kept, before))
    catalog: list[dict] = []
    out_dir = images_dir(material_id)
    for number, kept, before in pages:
        n = 0
        for name, im, digest in kept:
            if counts[digest] > REPEATED_PAGES or n >= MAX_PER_PAGE:
                continue
            n += 1
            ref = f"p{number}-{n}"
            img = im.image
            if max(img.size) > MAX_SIDE:
                img = img.copy()
                img.thumbnail((MAX_SIDE, MAX_SIDE))
            photo = im.name.lower().endswith((".jpg", ".jpeg", ".jp2"))
            ext, fmt = (".jpg", "JPEG") if photo else (".png", "PNG")
            if img.mode not in (("RGB", "L") if photo else ("RGB", "RGBA", "L", "LA", "P")):
                img = img.convert("RGBA" if not photo and "A" in img.mode else "RGB")
            out_dir.mkdir(parents=True, exist_ok=True)
            img.save(out_dir / f"{ref}{ext}", fmt, **({"quality": 85} if photo else {"optimize": True}))
            catalog.append({"ref": ref, "page": number, "file": f"{ref}{ext}", "w": img.size[0], "h": img.size[1],
                            "before": before.get(name, "")})
    if catalog:
        (out_dir / CATALOG).write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    return catalog


def image_catalog(row: models.Material) -> list[dict]:
    """El catálogo de imágenes del material; si es un PDF que aún no lo tiene, lo crea."""
    if not row.has_file or (row.file_mime or "application/pdf") != "application/pdf":
        return []
    path = images_dir(row.id) / CATALOG
    if not path.is_file():
        pdf = file_path(row.id)
        if not pdf.is_file():
            return []
        try:
            return extract_images(row.id, pdf.read_bytes())
        except Exception:  # noqa: BLE001 — sin imágenes se genera igual
            logger.exception("No se pudieron sacar las imágenes del material %s", row.id)
            return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def image_file(material_id: int, ref: str) -> Optional[Path]:
    """Ruta de una imagen del catálogo (o None): el ref se comprueba, nunca se usa tal cual en la ruta."""
    if not IMAGE_REF.match(ref or ""):
        return None
    for name in (f"{ref}.png", f"{ref}.jpg"):
        p = images_dir(material_id) / name
        if p.is_file():
            return p
    return None


def generation_text(row: models.Material, catalog: list[dict]) -> str:
    """El texto del material para generar: el de siempre y, al final de cada página, sus imágenes."""
    if not catalog:
        return row.text
    by_page: dict[int, list[str]] = {}
    for img in catalog:
        hint = f" — aparece tras «…{img['before']}»" if img.get("before") else ""
        by_page.setdefault(img["page"], []).append(f"[imagen {img['ref']}{hint}]")
    parts = re.split(r"(<!-- página \d+ -->)", row.text)
    out, current = [], None
    for part in parts:
        m = re.fullmatch(r"<!-- página (\d+) -->", part)
        if m:
            if current in by_page:
                out.append("\n" + "\n".join(by_page.pop(current)) + "\n\n")
            current = int(m.group(1))
        out.append(part)
    if current in by_page:
        out.append("\n" + "\n".join(by_page.pop(current)) + "\n")
    return "".join(out)


def as_part(row: models.Material) -> str:
    """El material como entra en el prompt (el nombre es por lo que la IA lo cita)."""
    return f"===== MATERIAL: {row.filename} =====\n{row.text}"


def check(row: models.Material, subject: models.Subject) -> None:
    """Las barreras del generador, otra vez: la política de IA de la asignatura puede haber cambiado."""
    generator.check_material(row.filename, row.text, row.kind, subject)


def out(row: models.Material) -> dict:
    return {
        "id": row.id, "subject_id": row.subject_id, "module_ref": row.module_ref, "kind": row.kind, "filename": row.filename,
        "pages": row.pages, "has_file": row.has_file, "file_mime": row.file_mime or ("application/pdf" if row.has_file else ""),
        "chars": len(row.text), "created_at": row.created_at.isoformat(),
    }
