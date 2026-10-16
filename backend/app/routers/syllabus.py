"""Plan docente de una asignatura: importarlo (borrador con IA) y consultarlo con el progreso de Aprender."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from .. import clock, config, generator, models, study_plan, syllabus
from ..crud import get_or_404
from ..database import get_db

router = APIRouter(prefix="/api/subjects", tags=["syllabus"])


def ai_ready(db: Session) -> None:
    """503 sin IA configurada; 409 si ya hay un trabajo en marcha (uno cada vez)."""
    st = generator.status(db)
    if not st["enabled"]:
        raise HTTPException(status_code=503, detail=f"La IA no está configurada: {st['reason']}. Configúrala en Ajustes → Inteligencia artificial.")
    if db.query(models.GenerationJob).filter(models.GenerationJob.status.in_(("queued", "running"))).count():
        raise HTTPException(status_code=409, detail="Ya hay una generación en marcha: espera a que termine")


async def read_document(file: UploadFile, default_name: str) -> tuple[str, str]:
    """(nombre, texto) de un PDF, Markdown, HTML o texto subido; 4xx legible si no vale."""
    name = (file.filename or default_name).rsplit("/", 1)[-1][:200]
    lower = name.lower()
    if lower.endswith(".pdf"):
        raw = await file.read(config.MAX_PDF_BYTES + 1)
        try:
            text = await run_in_threadpool(generator.pdf_to_text, raw, name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    elif lower.endswith((".md", ".txt", ".markdown", ".html", ".htm")):
        raw = await file.read(config.MAX_MATERIAL_BYTES + 1)
        if len(raw) > config.MAX_MATERIAL_BYTES:
            raise HTTPException(status_code=413, detail="El documento supera 1,5 MB de texto")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail=f"«{name}» no es texto UTF-8")
    else:
        raise HTTPException(status_code=422, detail=f"«{name}»: súbelo en PDF, Markdown, HTML o texto")
    return name, text


@router.post("/{subject_id}/syllabus/import", status_code=202)
async def import_syllabus(subject_id: int, background: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura")
    ai_ready(db)
    name, text = await read_document(file, "plan-docente")
    job = models.GenerationJob(status="queued", subject_id=subject.id, material_kind="otro", title=f"Plan docente · {subject.name}"[:200],
                               filenames=[name], draft={"mode": "plan", "units": []})
    db.add(job)
    db.commit()
    db.refresh(job)
    background.add_task(syllabus.run_plan_job, job.id, f"===== PLAN DOCENTE: {subject.name} ({name}) =====\n{text}")
    return {"id": job.id, "status": job.status}


@router.get("/{subject_id}/syllabus")
def get_syllabus(subject_id: int, db: Session = Depends(get_db)):
    """El plan docente con el progreso de Aprender: lecciones por módulo y dominio por objetivo."""
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura")
    plan = dict(subject.syllabus or {})
    course = db.query(models.Course).filter_by(subject_id=subject.id).first()
    units = list(course.units) if course else []
    steps = [s for u in units for lesson in u.lessons for s in lesson.steps if s.kind != "info"]
    today = clock.today()
    objectives = []
    for o in plan.get("objectives") or []:
        mine = [s for s in steps if o["code"] in (s.objectives or [])]
        correct, wrong = sum(s.correct for s in mine), sum(s.wrong for s in mine)
        objectives.append({**o, "steps": len(mine), "correct": correct, "wrong": wrong,
                           "mastery": round(correct / (correct + wrong), 3) if correct + wrong else None,
                           "due": sum(1 for s in mine if s.box and s.due_on and s.due_on <= today)})
    modules = []
    for m in plan.get("modules") or []:
        lessons = [lesson for u in units if u.module_ref == m["ref"] for lesson in u.lessons]
        modules.append({**m, "lessons": len(lessons), "lessons_done": sum(1 for lesson in lessons if lesson.completed_at)})
    return {
        "subject_id": subject.id,
        "course_id": course.id if course else None,
        "has_plan": bool(plan),
        "summary": plan.get("summary", ""),
        "source": plan.get("source", ""),
        "imported_on": plan.get("imported_on"),
        "objectives": objectives,
        "modules": modules,
        "resources": plan.get("resources") or [],
        "unassigned_units": [{"id": u.id, "title": u.title} for u in units if not u.module_ref],
    }


@router.delete("/{subject_id}/syllabus", status_code=204)
def delete_syllabus(subject_id: int, db: Session = Depends(get_db)):
    """Quita el plan docente (los objetivos ya puestos en los pasos se quedan, sin efecto)."""
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura")
    subject.syllabus = {}
    db.commit()


@router.get("/{subject_id}/study-plan")
def get_study_plan(subject_id: int, db: Session = Depends(get_db)):
    """Qué toca esta semana: módulos del plan docente repartidos hasta la última entrega."""
    return study_plan.build(db, get_or_404(db, models.Subject, subject_id, "Asignatura"))
