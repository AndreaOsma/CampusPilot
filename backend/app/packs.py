"""Módulos de estudios: lo específico de una titulación, empaquetado en un JSON que cada
cual instala si le sirve (plan de estudios, reglas de evaluación, política de IA por
asignatura, calendario de un semestre, trámites con plazo…).

- **Catálogo**: los `*.json` de `PACKS_DIR` (vienen en la imagen). Se puede instalar
  también un módulo subido a mano, y exportar tu carrera como módulo para compartirla.
- **Instalar** crea (o actualiza) una carrera con sus asignaturas, todas en "pendiente".
- **Aplicar un semestre** del módulo crea el semestre, matricula sus asignaturas y añade
  sus actividades, eventos, hábitos y trámites.

Todo es idempotente: cada fila creada lleva `pack_ref = "<slug>:<ref>"` y reinstalar
actualiza fechas y nombres sin tocar lo tuyo (notas, hechos, apuntes, cambios de estado).
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from . import clock, config, models
from .schemas import (
    ActivityKind,
    AiPolicy,
    CareerConfig,
    EvalConfig,
    SubjectOffered,
    EvalModel,
    EventKind,
    GroupRole,
    LinkItem,
    ProcedureCategory,
    SubjectKind,
    TimeStr,
    TrackDef,
    UrlStr,
)

logger = logging.getLogger("campus.packs")

PACK_FORMAT = "campus-pilot-pack"
PACK_FORMAT_VERSION = 1
Ref = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]


class PackGroup(BaseModel):
    ref: Ref
    name: str = Field(min_length=1, max_length=80)
    weight: float = Field(ge=0, le=100)
    min_grade: Optional[float] = Field(default=None, ge=0, le=100)
    role: Optional[GroupRole] = None


class PackSubject(BaseModel):
    ref: Ref
    code: str = Field(default="", max_length=32)
    name: str = Field(min_length=1, max_length=200)
    ects: float = Field(gt=0, le=60)
    kind: SubjectKind = "obligatoria"
    plan_semester: Optional[int] = Field(default=None, ge=1, le=20)
    offered: Optional[SubjectOffered] = None
    track: Optional[str] = Field(default=None, max_length=64)
    ai_policy: AiPolicy = "unknown"
    ai_policy_note: str = Field(default="", max_length=2000)
    eval_model: EvalModel = "weighted"
    eval_config: EvalConfig = Field(default_factory=EvalConfig)
    groups: list[PackGroup] = Field(default_factory=list, max_length=20)
    links: list[LinkItem] = Field(default_factory=list, max_length=20)


class PackActivity(BaseModel):
    ref: Ref
    subject: Ref
    group: Optional[str] = None
    name: str = Field(min_length=1, max_length=160)
    kind: ActivityKind = "other"
    weight: float = Field(default=1, ge=0, le=100)
    due_date: Optional[date] = None
    due_time: TimeStr = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    evaluable: bool = True
    estimated_hours: Optional[float] = Field(default=None, ge=0, le=500)
    notes: str = Field(default="", max_length=2000)


class PackEvent(BaseModel):
    ref: Ref
    subject: Optional[str] = None
    title: str = Field(min_length=1, max_length=200)
    kind: EventKind = "other"
    date: date
    end_date: Optional[date] = None
    start_time: TimeStr = None
    end_time: TimeStr = None
    url: UrlStr = ""
    notes: str = Field(default="", max_length=2000)


class PackHabit(BaseModel):
    ref: Ref
    subject: Optional[str] = None
    title: str = Field(min_length=1, max_length=200)
    weekdays: list[int] = Field(default_factory=list, max_length=7)


class PackProcedure(BaseModel):
    ref: Ref
    title: str = Field(min_length=1, max_length=200)
    category: ProcedureCategory = "admin"
    window_start: Optional[date] = None
    deadline: Optional[date] = None
    url: UrlStr = ""
    notes: str = Field(default="", max_length=2000)


class PackTerm(BaseModel):
    ref: Ref
    label: str = Field(min_length=1, max_length=40)
    start_date: date
    end_date: Optional[date] = None
    subjects: list[str] = Field(default_factory=list, max_length=40)
    activities: list[PackActivity] = Field(default_factory=list, max_length=1000)
    events: list[PackEvent] = Field(default_factory=list, max_length=500)
    habits: list[PackHabit] = Field(default_factory=list, max_length=50)
    procedures: list[PackProcedure] = Field(default_factory=list, max_length=100)


class Pack(BaseModel):
    format: Literal["campus-pilot-pack"]
    format_version: Literal[1]
    slug: Ref
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1", max_length=32)
    description: str = Field(default="", max_length=4000)
    institution: str = Field(default="", max_length=200)
    degree: str = Field(default="", max_length=200)
    ects_total: int = Field(default=240, ge=1, le=1000)
    source_url: UrlStr = ""
    updated: Optional[date] = None
    authors: list[str] = Field(default_factory=list, max_length=20)
    requirements: dict[str, float] = Field(default_factory=dict)
    # Reglas de la universidad (escala de notas, aprobado, créditos, calendario y nombres).
    # Opcional: sin ella, 0–10 con aprobado 5, ECTS y semestres.
    config: Optional[CareerConfig] = None
    tracks: list[TrackDef] = Field(default_factory=list, max_length=20)
    subjects: list[PackSubject] = Field(default_factory=list, max_length=300)
    terms: list[PackTerm] = Field(default_factory=list, max_length=40)
    procedures: list[PackProcedure] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _refs(self):
        top = self.config.grade_max if self.config else 10
        for s in self.subjects:
            cfg = s.eval_config
            if any(v > top for v in (cfg.ec_pass, cfg.pf_min, cfg.no_show_grade)) or any(
                g.min_grade is not None and g.min_grade > top for g in s.groups
            ):
                raise ValueError(f"Asignatura {s.ref}: notas por encima de la máxima ({top:g})")
        subject_refs = {s.ref for s in self.subjects}
        if len(subject_refs) != len(self.subjects):
            raise ValueError("Hay asignaturas con el mismo ref")
        groups = {s.ref: {g.ref for g in s.groups} for s in self.subjects}
        for term in self.terms:
            for ref in term.subjects:
                if ref not in subject_refs:
                    raise ValueError(f"Semestre {term.label}: asignatura desconocida '{ref}'")
            for act in term.activities:
                if act.subject not in subject_refs:
                    raise ValueError(f"Actividad {act.ref}: asignatura desconocida '{act.subject}'")
                if act.group and act.group not in groups[act.subject]:
                    raise ValueError(f"Actividad {act.ref}: grupo desconocido '{act.group}'")
            for item in (*term.events, *term.habits):
                if item.subject and item.subject not in subject_refs:
                    raise ValueError(f"{item.ref}: asignatura desconocida '{item.subject}'")
        return self


def parse_pack(raw: dict) -> Pack:
    return Pack.model_validate(raw)


def describe_one(err: dict) -> str:
    where = ".".join(str(p) for p in err.get("loc", ()))
    msg = str(err.get("msg", "")).replace("Value error, ", "")
    return f"{where}: {msg}" if where else msg


def describe_error(exc: ValidationError) -> str:
    return describe_one(exc.errors()[0])


# ---------- Catálogo ----------

def catalog() -> list[Pack]:
    packs: list[Pack] = []
    if not config.PACKS_DIR.is_dir():
        return packs
    for path in sorted(config.PACKS_DIR.glob("*.json")):
        try:
            packs.append(parse_pack(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, ValidationError):
            logger.exception("Módulo de estudios no válido: %s", path.name)
    return packs


def catalog_pack(slug: str) -> Optional[Pack]:
    return next((p for p in catalog() if p.slug == slug), None)


def summary(pack: Pack) -> dict:
    return {
        "slug": pack.slug,
        "name": pack.name,
        "version": pack.version,
        "description": pack.description,
        "institution": pack.institution,
        "degree": pack.degree,
        "ects_total": pack.ects_total,
        "credit_label": pack.config.credit_label if pack.config else "ECTS",
        "source_url": pack.source_url,
        "updated": pack.updated.isoformat() if pack.updated else None,
        "subjects": len(pack.subjects),
        "tracks": [t.model_dump() for t in pack.tracks],
        "terms": [{"ref": t.ref, "label": t.label, "subjects": len(t.subjects)} for t in pack.terms],
    }


# ---------- Instalar ----------

def _ref(pack: Pack, ref: str) -> str:
    return f"{pack.slug}:{ref}"


def install(db: Session, pack: Pack) -> models.Career:
    row = db.get(models.InstalledPack, pack.slug)
    content = json.loads(pack.model_dump_json())
    if row is None:
        db.add(models.InstalledPack(slug=pack.slug, name=pack.name, version=pack.version, content=content))
    else:
        row.name, row.version, row.content = pack.name, pack.version, content

    career = db.query(models.Career).filter_by(pack_slug=pack.slug).first()
    if career is None:
        career = models.Career(pack_slug=pack.slug, name=pack.degree or pack.name, institution=pack.institution)
        db.add(career)
    career.ects_goal = pack.ects_total
    career.requirements = dict(pack.requirements)
    if pack.config is not None:
        career.config = pack.config.model_dump()
    career.tracks = [t.model_dump() for t in pack.tracks]
    db.flush()

    existing = {s.pack_ref: s for s in db.query(models.Subject).filter(models.Subject.career_id == career.id)}
    for ps in pack.subjects:
        subject = existing.get(_ref(pack, ps.ref))
        if subject is None:
            subject = models.Subject(
                career_id=career.id,
                pack_ref=_ref(pack, ps.ref),
                name=ps.name,
                status="pending",
                ai_policy=ps.ai_policy,
                ai_policy_note=ps.ai_policy_note,
                eval_model=ps.eval_model,
                eval_config=ps.eval_config.model_dump(),
                links=[link.model_dump() for link in ps.links],
            )
            db.add(subject)
            db.flush()
            for pos, pg in enumerate(ps.groups):
                db.add(
                    models.EvalGroup(
                        subject_id=subject.id, name=pg.name, weight=pg.weight,
                        min_grade=pg.min_grade, role=pg.role, position=pos,
                    )
                )
        # Datos descriptivos del plan: siempre al día con el módulo.
        subject.code, subject.name, subject.ects = ps.code, ps.name, ps.ects
        subject.kind, subject.plan_semester, subject.track = ps.kind, ps.plan_semester, ps.track
        subject.offered = ps.offered

    for proc in pack.procedures:
        _upsert_procedure(db, pack, proc)
    db.commit()
    db.refresh(career)
    return career


def _upsert_procedure(db: Session, pack: Pack, proc: PackProcedure) -> None:
    ref = _ref(pack, proc.ref)
    row = db.query(models.Procedure).filter_by(pack_ref=ref).first()
    if row is None:
        row = models.Procedure(pack_ref=ref, status="todo", notes=proc.notes)
        db.add(row)
    row.title, row.category = proc.title, proc.category
    row.window_start, row.deadline, row.url = proc.window_start, proc.deadline, proc.url


def apply_term(db: Session, pack: Pack, term_ref: str) -> dict:
    term_def = next((t for t in pack.terms if t.ref == term_ref), None)
    if term_def is None:
        raise KeyError(term_ref)
    career = db.query(models.Career).filter_by(pack_slug=pack.slug).first()
    if career is None:
        career = install(db, pack)

    t_ref = _ref(pack, term_def.ref)
    term = db.query(models.Term).filter_by(pack_ref=t_ref).first()
    if term is None:
        term = models.Term(career_id=career.id, pack_ref=t_ref)
        db.add(term)
    term.label, term.start_date, term.end_date = term_def.label, term_def.start_date, term_def.end_date
    db.flush()

    subjects = {s.pack_ref: s for s in db.query(models.Subject).filter(models.Subject.career_id == career.id)}
    counts = {"subjects": 0, "activities": 0, "events": 0, "habits": 0, "procedures": 0}

    for ref in term_def.subjects:
        subject = subjects.get(_ref(pack, ref))
        if subject is None:
            continue
        subject.term_id = term.id
        if subject.status == "pending":
            subject.status = "enrolled"
        counts["subjects"] += 1

    for act in term_def.activities:
        subject = subjects.get(_ref(pack, act.subject))
        if subject is None:
            continue
        group_id = None
        if act.group:
            group_name = next(g.name for s in pack.subjects if s.ref == act.subject for g in s.groups if g.ref == act.group)
            group = next((g for g in subject.groups if g.name == group_name), None)
            group_id = group.id if group else None
        ref = _ref(pack, f"{term_def.ref}.{act.ref}")
        row = db.query(models.Activity).filter_by(pack_ref=ref).first()
        if row is None:
            row = models.Activity(subject_id=subject.id, pack_ref=ref, notes=act.notes)
            db.add(row)
        row.group_id = group_id if group_id is not None else row.group_id
        row.name, row.kind, row.weight, row.evaluable = act.name, act.kind, act.weight, act.evaluable
        row.due_date, row.due_time = act.due_date, act.due_time
        row.window_start, row.window_end = act.window_start, act.window_end
        row.estimated_hours = act.estimated_hours
        counts["activities"] += 1

    for ev in term_def.events:
        subject = subjects.get(_ref(pack, ev.subject)) if ev.subject else None
        ref = _ref(pack, f"{term_def.ref}.{ev.ref}")
        row = db.query(models.Event).filter_by(pack_ref=ref).first()
        if row is None:
            row = models.Event(pack_ref=ref, notes=ev.notes)
            db.add(row)
        row.subject_id = subject.id if subject else None
        row.title, row.kind, row.date, row.end_date = ev.title, ev.kind, ev.date, ev.end_date
        row.start_time, row.end_time, row.url = ev.start_time, ev.end_time, ev.url
        counts["events"] += 1

    for hb in term_def.habits:
        subject = subjects.get(_ref(pack, hb.subject)) if hb.subject else None
        ref = _ref(pack, f"{term_def.ref}.{hb.ref}")
        row = db.query(models.Habit).filter_by(pack_ref=ref).first()
        if row is None:
            row = models.Habit(pack_ref=ref, active=True)
            db.add(row)
        row.subject_id = subject.id if subject else None
        row.title, row.weekdays = hb.title, sorted(set(d for d in hb.weekdays if 0 <= d <= 6))
        counts["habits"] += 1

    for proc in term_def.procedures:
        _upsert_procedure(db, pack, proc.model_copy(update={"ref": f"{term_def.ref}.{proc.ref}"}))
        counts["procedures"] += 1

    db.commit()
    return {"term_id": term.id, "career_id": career.id, **counts}


def uninstall(db: Session, slug: str, delete_career: bool) -> None:
    row = db.get(models.InstalledPack, slug)
    if row is not None:
        db.delete(row)
    if delete_career:
        for career in db.query(models.Career).filter_by(pack_slug=slug).all():
            db.delete(career)
        db.query(models.Procedure).filter(models.Procedure.pack_ref.like(f"{slug}:%")).delete(synchronize_session=False)
    db.commit()


# ---------- Exportar una carrera como módulo ----------

def _slugify(text: str) -> str:
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s or "modulo")[:60]


def export_career(db: Session, career: models.Career) -> dict:
    """Módulo con la estructura de la carrera, sin nada personal (notas, estados, apuntes)."""
    subjects = db.query(models.Subject).filter_by(career_id=career.id).order_by(models.Subject.plan_semester, models.Subject.name).all()
    refs: dict[int, str] = {}
    used: set[str] = set()
    out_subjects = []
    for s in subjects:
        base = _slugify(s.code or s.name)
        ref, n = base, 2
        while ref in used:
            ref, n = f"{base}-{n}", n + 1
        used.add(ref)
        refs[s.id] = ref
        out_subjects.append(
            {
                "ref": ref,
                "code": s.code,
                "name": s.name,
                "ects": s.ects,
                "kind": s.kind,
                "plan_semester": s.plan_semester,
                "offered": s.offered,
                "track": s.track,
                "ai_policy": s.ai_policy,
                "ai_policy_note": s.ai_policy_note,
                "eval_model": s.eval_model,
                "eval_config": s.eval_config or {},
                "groups": [
                    {"ref": f"g{g.id}", "name": g.name, "weight": g.weight, "min_grade": g.min_grade, "role": g.role}
                    for g in s.groups
                ],
                "links": [link for link in (s.links or []) if str(link.get("url", "")).startswith(("https://", "http://"))],
            }
        )

    terms = []
    for term in career.terms:
        term_subjects = [s for s in subjects if s.term_id == term.id]
        acts = []
        for s in term_subjects:
            for a in s.activities:
                acts.append(
                    {
                        "ref": f"a{a.id}",
                        "subject": refs[s.id],
                        "group": f"g{a.group_id}" if a.group_id else None,
                        "name": a.name,
                        "kind": a.kind,
                        "weight": a.weight,
                        "due_date": a.due_date.isoformat() if a.due_date else None,
                        "due_time": a.due_time,
                        "window_start": a.window_start.isoformat() if a.window_start else None,
                        "window_end": a.window_end.isoformat() if a.window_end else None,
                        "evaluable": a.evaluable,
                        "estimated_hours": a.estimated_hours,
                    }
                )
        terms.append(
            {
                "ref": _slugify(term.label),
                "label": term.label,
                "start_date": term.start_date.isoformat(),
                "end_date": term.end_date.isoformat() if term.end_date else None,
                "subjects": [refs[s.id] for s in term_subjects],
                "activities": acts,
            }
        )

    pack = {
        "format": PACK_FORMAT,
        "format_version": PACK_FORMAT_VERSION,
        "slug": _slugify(career.name),
        "name": career.name,
        "version": clock.today().isoformat(),
        "description": "",
        "institution": career.institution,
        "degree": career.name,
        "ects_total": career.ects_goal,
        "updated": clock.today().isoformat(),
        "requirements": career.requirements or {},
        "config": career.config or None,
        "tracks": career.tracks or [],
        "subjects": out_subjects,
        "terms": terms,
    }
    parse_pack(pack)  # lo que exportamos tiene que poder instalarse
    return pack


def load_upload(data: bytes) -> Pack:
    if len(data) > config.MAX_PACK_BYTES:
        raise ValueError("El módulo supera los 2 MB")
    try:
        raw = json.loads(data)
    except ValueError:
        raise ValueError("JSON no válido")
    if not isinstance(raw, dict):
        raise ValueError("El módulo debe ser un objeto JSON")
    return parse_pack(raw)


def pack_path(slug: str) -> Optional[Path]:
    for path in config.PACKS_DIR.glob("*.json"):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("slug") == slug:
                return path
        except (OSError, ValueError):
            continue
    return None
