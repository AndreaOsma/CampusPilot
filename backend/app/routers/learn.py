"""Aprender: cursos, lecciones paso a paso, corrección en el servidor, repaso, racha y XP."""
from __future__ import annotations

import logging
import random
import re
from urllib.parse import quote
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from .. import anki, clock, config, degree_plan, game, generator, learn, materials, models, syllabus, tutor
from ..crud import get_or_404
from ..database import get_db
from ..schemas import UrlStr
from ..settings_store import load_settings

router = APIRouter(prefix="/api/learn", tags=["learn"])


class AnswerIn(BaseModel):
    response: Any = None
    first_try: bool = True
    token: Optional[str] = Field(default=None, max_length=2000)
    confidence: Optional[Literal["high", "low"]] = None
    used_hint: bool = False
    # Aciertos seguidos que lleva quien estudia (para la misión de racha de aciertos).
    combo: int = Field(default=0, ge=0, le=1000)


class CompleteIn(BaseModel):
    correct: int = Field(ge=0, le=1000)
    total: int = Field(ge=0, le=1000)
    seconds: int = Field(default=0, ge=0, le=24 * 3600)


class TheoryIn(BaseModel):
    theory: str = Field(default="", max_length=50_000)
    theory_url: UrlStr = ""


def _lesson_summary(lesson: models.Lesson, locked: bool) -> dict:
    return {
        "id": lesson.id,
        "title": lesson.title,
        "steps": len([s for s in lesson.steps if s.kind != "info"]),
        "done": lesson.completed_at is not None,
        "best_ratio": lesson.best_ratio,
        "has_theory": bool(lesson.theory.strip() or lesson.theory_url),
        # Nivel (corona) = veces completada, hasta 5.
        "level": min(5, lesson.runs),
        "locked": locked,
    }


def _course_summary(db: Session, course: models.Course, with_units: bool) -> dict:
    lessons = [lesson for u in course.units for lesson in u.lessons]
    done = sum(1 for lesson in lessons if lesson.completed_at)
    next_lesson = next((lesson for lesson in lessons if not lesson.completed_at), None)
    subject = db.get(models.Subject, course.subject_id) if course.subject_id else None
    out = {
        "id": course.id,
        "slug": course.slug,
        "title": course.title,
        "description": course.description,
        "source_note": course.source_note,
        "subject_id": course.subject_id,
        "subject_name": subject.name if subject else None,
        "lessons_total": len(lessons),
        "lessons_done": done,
        "next_lesson_id": next_lesson.id if next_lesson else None,
    }
    if with_units:
        # Camino lineal: abierta la primera sin hacer y todo lo anterior; lo demás, con candado.
        first_pending = next((i for i, lesson in enumerate(lessons) if not lesson.completed_at), len(lessons))
        index = {lesson.id: i for i, lesson in enumerate(lessons)}
        out["units"] = [
            {
                "id": u.id,
                "title": u.title,
                "done": bool(u.lessons) and all(lesson.completed_at for lesson in u.lessons),
                "chest_claimed": u.chest_claimed,
                "lessons": [_lesson_summary(lesson, index[lesson.id] > first_pending) for lesson in u.lessons],
            }
            for u in course.units
        ]
    return out


@router.get("/courses")
def list_courses(db: Session = Depends(get_db)):
    return [_course_summary(db, c, False) for c in db.query(models.Course).order_by(models.Course.id)]


@router.get("/courses/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db)):
    return _course_summary(db, get_or_404(db, models.Course, course_id, "Curso"), True)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, models.Course, course_id, "Curso"))
    db.commit()


@router.get("/courses/{course_id}/export")
def export_course(course_id: int, db: Session = Depends(get_db)):
    course = get_or_404(db, models.Course, course_id, "Curso")
    return JSONResponse(learn.export_course(course), headers={"Content-Disposition": f'attachment; filename="{course.slug}.json"'})


@router.get("/courses/{course_id}/anki")
def export_anki(course_id: int, only_missed: bool = False, theory: bool = True, db: Session = Depends(get_db)):
    """Las tarjetas del curso para importarlas en Anki (texto con cabeceras de Anki)."""
    course = get_or_404(db, models.Course, course_id, "Curso")
    ascii_name = re.sub(r"[^a-z0-9.-]+", "-", course.title.lower()).strip("-") or "curso"
    utf8_name = quote(f"{course.title}-anki.txt")
    return Response(anki.export_course(course, only_missed, theory), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}-anki.txt\"; filename*=UTF-8''{utf8_name}"})


@router.post("/import")
async def import_course(file: UploadFile = File(...), subject_id: Optional[int] = Form(None), db: Session = Depends(get_db)):
    data = await file.read(learn.MAX_COURSE_BYTES + 1)
    subject = get_or_404(db, models.Subject, subject_id, "Asignatura") if subject_id else None
    try:
        course_in = learn.load_course(data)
        course = learn.import_course(db, course_in, subject)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Curso no válido — {learn.describe_error(exc)}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _course_summary(db, course, False)


@router.put("/courses/{course_id}/subject")
def set_course_subject(course_id: int, payload: CourseSubjectIn, db: Session = Depends(get_db)):
    """Asigna a una asignatura un curso antiguo que no tenía. Si esa asignatura ya tiene curso,
    sus unidades se mueven allí (al final) y el suelto desaparece: nada de progreso se pierde."""
    course = get_or_404(db, models.Course, course_id, "Curso")
    subject = get_or_404(db, models.Subject, payload.subject_id, "Asignatura")
    target = db.query(models.Course).filter_by(subject_id=subject.id).first()
    if target is None or target.id == course.id:
        course.subject_id, course.title = subject.id, subject.name
        db.commit()
        return _course_summary(db, course, False)
    start = len(target.units)
    for i, unit in enumerate(list(course.units)):
        unit.course_id, unit.position = target.id, start + i
    db.flush()
    db.expire(course)
    db.delete(course)
    db.commit()
    db.refresh(target)
    return _course_summary(db, target, False)


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: int, db: Session = Depends(get_db)):
    lesson = get_or_404(db, models.Lesson, lesson_id, "Lección")
    course = lesson.unit.course
    ordered = [x for u in course.units for x in u.lessons]
    idx = ordered.index(lesson)
    rng = random.Random()
    return {
        "id": lesson.id,
        "title": lesson.title,
        "unit_title": lesson.unit.title,
        "course_id": course.id,
        "course_title": course.title,
        "theory": lesson.theory,
        "theory_url": lesson.theory_url,
        "done": lesson.completed_at is not None,
        "next_lesson_id": ordered[idx + 1].id if idx + 1 < len(ordered) else None,
        "steps": [learn.public_step(db, s, rng, show_worked=lesson.runs == 0) for s in lesson.steps],
    }


@router.put("/lessons/{lesson_id}/theory")
def put_theory(lesson_id: int, payload: TheoryIn, db: Session = Depends(get_db)):
    lesson = get_or_404(db, models.Lesson, lesson_id, "Lección")
    lesson.theory, lesson.theory_url = payload.theory, payload.theory_url
    db.commit()
    return {"theory": lesson.theory, "theory_url": lesson.theory_url}


@router.post("/steps/{step_id}/answer")
def answer(step_id: int, payload: AnswerIn, db: Session = Depends(get_db)):
    step = get_or_404(db, models.LessonStep, step_id, "Paso")
    values = None
    if step.kind == "param":
        values = learn.read_instance(db, step.id, payload.token or "")
        if values is None:
            raise HTTPException(status_code=422, detail="Este ejercicio caducó: recarga la lección")
    ok, solution, explanation = learn.check(step, payload.response, values)
    xp = learn.record_answer(
        db, step, ok, payload.first_try, confident=payload.confidence == "high" if payload.confidence else None,
        used_hint=payload.used_hint, combo=payload.combo,
    )
    return {
        "correct": ok,
        "solution": solution,
        "explanation": explanation,
        "source": step.source,
        "xp": xp,
        "option_feedback": [] if ok else learn.option_feedback(step, payload.response),
        "confident_wrong": bool(payload.confidence == "high" and not ok),
    }


@router.post("/lessons/{lesson_id}/complete")
def complete(lesson_id: int, payload: CompleteIn, db: Session = Depends(get_db)):
    lesson = get_or_404(db, models.Lesson, lesson_id, "Lección")
    ratio = payload.correct / payload.total if payload.total else 1.0
    first_time = lesson.completed_at is None
    perfect = payload.total > 0 and payload.correct >= payload.total
    lesson.completed_at = lesson.completed_at or datetime.now(timezone.utc).replace(tzinfo=None)
    lesson.best_ratio = max(lesson.best_ratio or 0, min(1.0, ratio))
    lesson.runs += 1
    bonus = (learn.XP_LESSON if first_time else learn.XP_LESSON // 2) + (game.PERFECT_BONUS_XP if perfect else 0)
    learn.add_xp(db, bonus, lessons=1)
    if perfect:
        game.day(db).perfect_lessons += 1
    db.commit()
    unit = lesson.unit
    return {
        "xp": bonus,
        "perfect": perfect,
        "ratio": ratio,
        "level": min(5, lesson.runs),
        "streak": learn.streak(db),
        "unit_done": all(x.completed_at for x in unit.lessons),
        "unit_id": unit.id,
        "chest_available": all(x.completed_at for x in unit.lessons) and not unit.chest_claimed,
        "game": game.state(db, load_settings(db).learn_daily_xp),
    }


@router.get("/game")
def game_state(db: Session = Depends(get_db)):
    out = game.state(db, load_settings(db).learn_daily_xp)
    db.commit()
    return out


@router.post("/quests/{quest_id}/claim")
def claim_quest(quest_id: str, db: Session = Depends(get_db)):
    try:
        gems = game.claim_quest(db, quest_id, load_settings(db).learn_daily_xp)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return {"gems": gems, "game": game.state(db, load_settings(db).learn_daily_xp)}


@router.post("/units/{unit_id}/chest")
def open_chest(unit_id: int, db: Session = Depends(get_db)):
    unit = get_or_404(db, models.CourseUnit, unit_id, "Unidad")
    try:
        gems = game.open_chest(db, unit)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return {"gems": gems, "game": game.state(db, load_settings(db).learn_daily_xp)}


@router.post("/shop/{item}")
def shop(item: str, db: Session = Depends(get_db)):
    try:
        game.buy(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return game.state(db, load_settings(db).learn_daily_xp)


@router.get("/review")
def review(limit: int = 15, db: Session = Depends(get_db)):
    """Pasos fallados cuyo repaso toca hoy (o antes), mezclados."""
    today = clock.today()
    steps = (
        db.query(models.LessonStep)
        .filter(models.LessonStep.box > 0, models.LessonStep.due_on <= today)
        .order_by(models.LessonStep.box, models.LessonStep.due_on)
        .limit(max(1, min(limit, 50)))
        .all()
    )
    rng = random.Random()
    rng.shuffle(steps)
    return {"steps": [learn.public_step(db, s, rng) | {"lesson_title": s.lesson.title} for s in steps]}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    today = clock.today()
    row = db.get(models.LearnDay, today)
    goal = load_settings(db).learn_daily_xp
    week = {d.date.isoformat(): d.xp for d in db.query(models.LearnDay).filter(models.LearnDay.date > date.fromordinal(today.toordinal() - 7))}
    due = db.query(models.LessonStep).filter(models.LessonStep.box > 0, models.LessonStep.due_on <= today).count()
    total = sum(d.xp for d in db.query(models.LearnDay))
    confident_wrong = sum(s.confident_wrong for s in db.query(models.LessonStep).filter(models.LessonStep.confident_wrong > 0))
    return {
        "confident_wrong": confident_wrong,
        "today_xp": row.xp if row else 0,
        "goal": goal,
        "streak": learn.streak(db, today),
        "review_due": due,
        "total_xp": total,
        "week": week,
    }


# ---------- Dominio por concepto, práctica dirigida y examen ----------

def _course_steps(course: models.Course) -> list[models.LessonStep]:
    return [s for u in course.units for lesson in u.lessons for s in lesson.steps if s.kind != "info"]


@router.get("/courses/{course_id}/concepts")
def concepts(course_id: int, db: Session = Depends(get_db)):
    """Dominio por concepto: aciertos / intentos, con los fallos con confianza aparte.
    Sin intentos, el dominio es None (aún no se sabe)."""
    course = get_or_404(db, models.Course, course_id, "Curso")
    agg: dict[str, dict] = {}
    for s in _course_steps(course):
        for c in s.concepts or []:
            row = agg.setdefault(c, {"concept": c, "steps": 0, "correct": 0, "wrong": 0, "confident_wrong": 0, "due": 0})
            row["steps"] += 1
            row["correct"] += s.correct
            row["wrong"] += s.wrong
            row["confident_wrong"] += s.confident_wrong
            if s.box and s.due_on and s.due_on <= clock.today():
                row["due"] += 1
    out = []
    for row in agg.values():
        tries = row["correct"] + row["wrong"]
        row["mastery"] = round(row["correct"] / tries, 3) if tries else None
        out.append(row)
    # Lo más flojo primero; lo no practicado al final.
    return sorted(out, key=lambda r: (r["mastery"] is None, r["mastery"] if r["mastery"] is not None else 2, r["concept"]))


@router.get("/courses/{course_id}/practice")
def practice(course_id: int, concept: str = "", objective: str = "", limit: int = 10, db: Session = Depends(get_db)):
    """Pasos de un concepto o de un objetivo del plan docente (o de los más flojos), mezclados de todas las lecciones."""
    course = get_or_404(db, models.Course, course_id, "Curso")
    steps = _course_steps(course)
    if objective:
        steps = [s for s in steps if objective in (s.objectives or [])]
        text = next((o["text"] for o in syllabus.objectives_of(course.subject) if o["code"] == objective), objective)
        rng = random.Random()
        rng.shuffle(steps)
        return {"title": f"Objetivo {objective}: {text}"[:200], "steps": [learn.public_step(db, s, rng) | {"lesson_title": s.lesson.title} for s in steps[: max(1, min(limit, 30))]]}
    if concept:
        steps = [s for s in steps if concept.lower() in (s.concepts or [])]
    else:
        steps.sort(key=lambda s: (s.correct - 2 * s.wrong - 3 * s.confident_wrong))
        steps = steps[: max(limit * 2, 10)]
    rng = random.Random()
    rng.shuffle(steps)
    return {"title": f"Práctica: {concept}" if concept else "Práctica de lo más flojo", "steps": [learn.public_step(db, s, rng) | {"lesson_title": s.lesson.title} for s in steps[: max(1, min(limit, 30))]]}


@router.get("/courses/{course_id}/exam")
def exam(course_id: int, n: int = 10, minutes: int = 30, db: Session = Depends(get_db)):
    """Tanda mixta de todo el curso, sin corrección hasta el final (la decide la app)."""
    course = get_or_404(db, models.Course, course_id, "Curso")
    steps = _course_steps(course)
    rng = random.Random()
    rng.shuffle(steps)
    n = max(3, min(n, 40))
    return {
        "title": f"Examen · {course.title}",
        "minutes": max(5, min(minutes, 180)),
        "steps": [learn.public_step(db, s, rng) | {"lesson_title": s.lesson.title} for s in steps[:n]],
    }


# ---------- Generador ----------

class ImportDraftIn(BaseModel):
    subject_id: Optional[int] = None
    exclude: list[str] = Field(default_factory=list, max_length=2000)
    # Solo para un plan docente: aplicar la evaluación y qué actividades (índices) añadir a la agenda.
    use_eval: bool = False
    activities: list[int] = Field(default_factory=list, max_length=200)


class CourseSubjectIn(BaseModel):
    subject_id: int


def _job_out(job: models.GenerationJob, with_draft: bool = False, db: Optional[Session] = None) -> dict:
    draft = job.draft or {}
    steps = sum(len(lesson["steps"]) for u in draft.get("units", []) for lesson in u["lessons"])
    out = {
        "id": job.id,
        "status": job.status,
        "title": job.title,
        "subject_id": job.subject_id,
        "material_kind": job.material_kind,
        "filenames": job.filenames,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error": job.error,
        "steps": steps,
        "review": sum(1 for w in job.warnings if w.get("level") == "review"),
        "dropped": sum(1 for w in job.warnings if w.get("level") == "dropped"),
        "cost_usd": job.cost_usd,
        # lessons: lecciones nuevas · theory: teoría para las lecciones que ya existen.
        "mode": draft.get("mode", "lessons"),
    }
    if out["mode"] == "career":
        out["steps"] = len((draft.get("pack") or {}).get("subjects") or [])
    if out["mode"] == "plan":
        plan = draft.get("plan") or {}
        out["steps"] = len(plan.get("objectives") or [])
        out["plan_counts"] = {k: len(plan.get(k) or []) for k in ("objectives", "modules", "activities")}
    if with_draft:
        out["draft"] = draft
        out["warnings"] = job.warnings
        if out["mode"] == "plan" and job.subject_id and db is not None:
            subject = db.get(models.Subject, job.subject_id)
            if subject is not None:
                # Para la revisión: qué hay ya en la asignatura, y así no duplicar.
                out["subject_state"] = {
                    "has_groups": bool(subject.groups),
                    "has_plan": bool(subject.syllabus),
                    "existing": [syllabus.activity_exists(subject, a) for a in (draft.get("plan") or {}).get("activities", [])],
                }
    return out


class TutorTurn(BaseModel):
    role: Literal["user", "tutor"]
    text: str = Field(max_length=6000)


class TutorIn(BaseModel):
    subject_id: int
    question: str = Field(min_length=2, max_length=2000)
    history: list[TutorTurn] = Field(default_factory=list, max_length=20)
    module_ref: str = Field(default="", max_length=64)
    material_ids: list[int] = Field(default_factory=list, max_length=20)


@router.post("/tutor")
async def ask_tutor(payload: TutorIn, db: Session = Depends(get_db)):
    """Pregunta sobre la teoría; responde solo con los materiales de la biblioteca, citando."""
    subject = get_or_404(db, models.Subject, payload.subject_id, "Asignatura")
    st = generator.status(db)
    if not st["enabled"]:
        raise HTTPException(status_code=503, detail=f"La IA no está configurada: {st['reason']}. Configúrala en Ajustes → Inteligencia artificial.")
    try:
        return await run_in_threadpool(tutor.ask, db, subject, payload.question, [h.model_dump() for h in payload.history],
                                       payload.module_ref, payload.material_ids)
    except ValueError as exc:  # incluye tutor.Refused
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — proveedor caído, tiempo agotado…
        logging.getLogger("campus.tutor").exception("tutor failed")
        raise HTTPException(status_code=502, detail=f"La IA no respondió: {str(exc)[:300]}")


@router.get("/generator/status")
def generator_status(db: Session = Depends(get_db)):
    return generator.status(db)


@router.post("/generate", status_code=202)
async def generate(
    background: BackgroundTasks,
    files: list[UploadFile] = File(default=[]),
    # Materiales ya guardados en la biblioteca (en vez de, o además de, subir archivos).
    material_ids: list[int] = Form(default=[]),
    # Lo subido se guarda en la biblioteca de la asignatura (para reutilizarlo y citar páginas).
    save: bool = Form(True),
    material_kind: str = Form("manual"),
    title: str = Form(""),
    subject_id: Optional[int] = Form(None),
    mode: Literal["lessons", "theory"] = Form("lessons"),
    module_ref: str = Form("", max_length=64),
    db: Session = Depends(get_db),
):
    st = generator.status(db)
    if not st["enabled"]:
        raise HTTPException(status_code=503, detail=f"La IA no está configurada: {st['reason']}. Configúrala en Ajustes → Inteligencia artificial.")
    if db.query(models.GenerationJob).filter(models.GenerationJob.status.in_(("queued", "running"))).count():
        raise HTTPException(status_code=409, detail="Ya hay una generación en marcha: espera a que termine")
    if not 1 <= len(files) + len(material_ids) <= 8:
        raise HTTPException(status_code=422, detail="Sube o elige de 1 a 8 materiales")
    subject = db.get(models.Subject, subject_id) if subject_id else None
    if subject is None:
        raise HTTPException(status_code=422, detail="Elige la asignatura: las lecciones se añaden a su curso")
    if mode == "theory" and not generator.subject_lessons(db, subject):
        raise HTTPException(status_code=422, detail=f"«{subject.name}» aún no tiene lecciones a las que añadir teoría")
    from .materials import read_upload

    parts: list[str] = []
    names: list[str] = []
    cited: dict[str, int] = {}  # nombre del material → id en la biblioteca (para citar página)
    total = 0
    uploads = []
    for f in files:
        name, text, pdf = await read_upload(f)
        try:
            generator.check_material(name, text, material_kind, subject)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        uploads.append((name, text, pdf))
    for mid in material_ids:
        row = db.get(models.Material, mid)
        if row is None or row.subject_id != subject.id:
            raise HTTPException(status_code=422, detail="Ese material no es de esta asignatura")
        try:
            materials.check(row, subject)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        uploads.append((row.filename, row.text, None))
        cited[row.filename] = row.id
    for name, text, pdf in uploads:
        total += len(text.encode("utf-8"))
        if total > config.MAX_MATERIAL_BYTES:
            raise HTTPException(status_code=413, detail="El material supera 1,5 MB de texto en total: súbelo por partes (un módulo o bloque cada vez)")
        if save and name not in cited:
            cited[name] = materials.save(db, subject, name, text, material_kind, module_ref, pdf).id
        names.append(name)
        parts.append(f"===== MATERIAL: {name} =====\n{text}")
    job = models.GenerationJob(
        status="queued", subject_id=subject.id if subject else None, material_kind=material_kind,
        title=(title or (f"Teoría · {subject.name}" if mode == "theory" else subject.name))[:200], filenames=names,
        draft={"mode": "theory", "units": []} if mode == "theory" else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    material = "\n\n".join(parts)
    if mode == "theory":
        background.add_task(generator.run_theory_job, job.id, material, cited)
    else:
        background.add_task(generator.run_job, job.id, material, module_ref, cited)
    return _job_out(job)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return [_job_out(j) for j in db.query(models.GenerationJob).order_by(models.GenerationJob.id.desc()).limit(20)]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    return _job_out(get_or_404(db, models.GenerationJob, job_id, "Generación"), with_draft=True, db=db)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.GenerationJob, job_id, "Generación")
    if job.status == "running":
        raise HTTPException(status_code=409, detail="No se puede borrar mientras se genera")
    db.delete(job)
    db.commit()


@router.post("/jobs/{job_id}/import")
def import_job(job_id: int, payload: ImportDraftIn, db: Session = Depends(get_db)):
    job = get_or_404(db, models.GenerationJob, job_id, "Generación")
    if job.status != "done":
        raise HTTPException(status_code=409, detail="El borrador aún no está listo")
    subject = get_or_404(db, models.Subject, payload.subject_id, "Asignatura") if payload.subject_id else None
    if (job.draft or {}).get("mode") == "career":
        try:
            career = degree_plan.apply(db, job)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:500])
        return {"career_id": career.id, "slug": career.pack_slug}
    if (job.draft or {}).get("mode") == "plan":
        try:
            subject = syllabus.apply_plan(db, job, payload.use_eval, payload.activities)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"subject_id": subject.id, "objectives": len(subject.syllabus.get("objectives", [])), "modules": len(subject.syllabus.get("modules", []))}
    try:
        if (job.draft or {}).get("mode") == "theory":
            result = generator.add_theory(db, job, set(payload.exclude))
        else:
            result = generator.merge_into_course(db, job, set(payload.exclude), subject)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"El borrador no es válido — {learn.describe_error(exc)}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _course_summary(db, result, False)
