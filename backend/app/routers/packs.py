"""Módulos de estudios: catálogo, instalar (del catálogo o subido), aplicar un semestre,
descargar y desinstalar."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import config, degree_plan, models, packs
from ..database import get_db

router = APIRouter(prefix="/api/packs", tags=["packs"])


def _installed_pack(db: Session, slug: str) -> packs.Pack:
    row = db.get(models.InstalledPack, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Ese módulo no está instalado")
    return packs.parse_pack(row.content)


@router.get("")
def list_packs(db: Session = Depends(get_db)):
    installed = {r.slug: r for r in db.query(models.InstalledPack).all()}
    careers = {c.pack_slug: c.id for c in db.query(models.Career).filter(models.Career.pack_slug.isnot(None))}
    applied = {t.pack_ref for t in db.query(models.Term).filter(models.Term.pack_ref.isnot(None))}

    def with_state(summary: dict, in_catalog: bool) -> dict:
        row = installed.get(summary["slug"])
        summary["in_catalog"] = in_catalog
        summary["installed_version"] = row.version if row else None
        summary["career_id"] = careers.get(summary["slug"])
        for t in summary["terms"]:
            t["applied"] = f"{summary['slug']}:{t['ref']}" in applied
        return summary

    catalog = [with_state(packs.summary(p), True) for p in packs.catalog()]
    in_catalog = {p["slug"] for p in catalog}
    uploaded = [
        with_state(packs.summary(packs.parse_pack(r.content)), False) for slug, r in installed.items() if slug not in in_catalog
    ]
    return catalog + uploaded


@router.get("/schema")
def pack_schema():
    """JSON Schema del formato de módulo, para quien quiera crear el de su universidad."""
    return packs.Pack.model_json_schema()


@router.post("/validate")
async def validate_pack(file: UploadFile = File(...)):
    """Comprueba un módulo sin instalarlo: errores legibles o un resumen de lo que trae."""
    data = await file.read(config.MAX_PACK_BYTES + 1)
    try:
        pack = packs.load_upload(data)
    except ValidationError as exc:
        return {"ok": False, "errors": [packs.describe_one(e) for e in exc.errors()[:20]]}
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)]}
    return {"ok": True, "errors": [], "summary": packs.summary(pack)}


@router.post("/from-plan", status_code=202)
async def pack_from_plan(background: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Plan de estudios oficial → borrador de módulo de estudios (lo hace la IA de Ajustes)."""
    from .syllabus import ai_ready, read_document

    ai_ready(db)
    name, text = await read_document(file, "plan-de-estudios")
    job = models.GenerationJob(status="queued", material_kind="otro", title=f"Plan de estudios · {name}"[:200], filenames=[name],
                               draft={"mode": "career", "units": []})
    db.add(job)
    db.commit()
    db.refresh(job)
    background.add_task(degree_plan.run_degree_job, job.id, f"===== PLAN DE ESTUDIOS ({name}) =====\n{text}")
    return {"id": job.id, "status": job.status}


@router.post("/upload")
async def upload_pack(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read(config.MAX_PACK_BYTES + 1)
    try:
        pack = packs.load_upload(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Módulo no válido — {packs.describe_error(exc)}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    career = packs.install(db, pack)
    return {"slug": pack.slug, "career_id": career.id}


@router.post("/{slug}/install")
def install_pack(slug: str, db: Session = Depends(get_db)):
    pack = packs.catalog_pack(slug)
    if pack is None:
        # Reinstalar uno subido a mano: reaplica su copia guardada.
        pack = _installed_pack(db, slug)
    career = packs.install(db, pack)
    return {"slug": pack.slug, "career_id": career.id}


@router.post("/{slug}/terms/{term_ref}/apply")
def apply_term(slug: str, term_ref: str, db: Session = Depends(get_db)):
    pack = packs.catalog_pack(slug) or _installed_pack(db, slug)
    try:
        return packs.apply_term(db, pack, term_ref)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ese semestre no está en el módulo")


@router.get("/{slug}/download")
def download_pack(slug: str, db: Session = Depends(get_db)):
    path = packs.pack_path(slug)
    if path is not None:
        return FileResponse(path, media_type="application/json", filename=f"{slug}.json")
    row = db.get(models.InstalledPack, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Módulo no encontrado")
    from fastapi.responses import JSONResponse

    return JSONResponse(row.content, headers={"Content-Disposition": f'attachment; filename="{slug}.json"'})


@router.delete("/{slug}", status_code=204)
def uninstall_pack(slug: str, delete_career: bool = False, db: Session = Depends(get_db)):
    if db.get(models.InstalledPack, slug) is None:
        raise HTTPException(status_code=404, detail="Ese módulo no está instalado")
    packs.uninstall(db, slug, delete_career)
