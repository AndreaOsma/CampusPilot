"""Crear la carrera entera desde el plan de estudios (Módulos → Desde el plan de estudios).

Subes el documento oficial del grado (la página o el PDF con la tabla de asignaturas por
curso/semestre, créditos y tipo) y la IA lo pasa a un **módulo de estudios** (`packs.Pack`):
la misma pieza que instalan los módulos del catálogo. Sale un borrador que revisas; al
aplicarlo se instala como cualquier módulo (carrera con todas las asignaturas en pendiente) y
puedes descargar el JSON para compartirlo con otras personas de tu universidad.

Al modelo se le pide un esquema sencillo (asignaturas, créditos, tipo, semestre, menciones,
escala de notas) y aquí se construye y valida el Pack: lo que no cuadra se descarta con aviso
en vez de tirar todo el plan.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from . import ai, config, i18n, models, packs
from .database import SessionLocal

logger = logging.getLogger("campus.degree")

_STR = {"type": "string"}
_NUM_OR_NULL = {"type": ["number", "null"]}
DEGREE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "refusal": {"type": ["string", "null"]},
        "institution": _STR,
        "degree": _STR,
        "description": _STR,
        "credits_total": {"type": "number"},
        "credit_label": _STR,
        "grade_max": _NUM_OR_NULL,
        "pass_mark": _NUM_OR_NULL,
        "term_system": {"type": "string", "enum": ["semesters", "trimesters", "quarters", "annual"]},
        "year_start_month": {"type": ["integer", "null"]},
        "requirements": {"type": "object", "properties": {k: {"type": "number"} for k in models.SUBJECT_KINDS}},
        "tracks": {"type": "array", "items": {"type": "object", "properties": {"id": _STR, "name": _STR}, "required": ["id", "name"]}},
        "subjects": {"type": "array", "items": {"type": "object", "properties": {
            "code": _STR, "name": _STR, "credits": {"type": "number"},
            "kind": {"type": "string", "enum": list(models.SUBJECT_KINDS)},
            "plan_semester": {"type": ["integer", "null"]}, "track": {"type": ["string", "null"]},
        }, "required": ["name", "credits", "kind"]}},
    },
    "required": ["degree", "subjects"],
}

DEGREE_INSTRUCTIONS = """Eres el asistente de organización de Campus Pilot. Por la entrada estándar recibes el plan de estudios oficial de UNA titulación universitaria (de cualquier universidad y país). Pásalo a datos y devuelve SOLO el JSON del esquema.

Reglas (obligatorias):
1. Copia, no inventes: nombres, códigos y créditos tal cual aparecen. Si un dato no está, vacío o null.
2. "subjects": TODAS las asignaturas del plan, una vez cada una. "kind": basica (formación básica), obligatoria, optativa, mencion (de una mención/itinerario/especialidad), practicas (prácticas externas), tfg (trabajo de fin de grado/máster), otra. "plan_semester": el semestre recomendado contando desde 1 (curso 2, 2.º semestre = 4); en planes anuales, el curso. "track": el id de su mención si es de una.
3. "tracks": las menciones/itinerarios/especialidades, con un "id" corto en minúsculas con guiones.
4. "requirements": créditos exigidos por tipo para titularse (p. ej. {"basica": 60, "obligatoria": 120, "optativa": 48, "tfg": 12}).
5. "credits_total": créditos totales; "credit_label": cómo se llaman (ECTS, créditos, credits…).
6. Escala de notas si el documento la da ("grade_max", "pass_mark"; p. ej. 10/5, 20/10, 4/2); si no, null. "term_system" y "year_start_month" (mes en que empieza el curso) según el país y el documento.
7. Si lo que recibes no es un plan de estudios, no devuelvas asignaturas y explica el motivo en "refusal".
8. Idioma: {LANG} para "description"; lo demás, como en el documento.
"""


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60] or "plan"


def build_pack(payload: dict) -> tuple[dict, list[dict]]:
    """Del JSON del modelo a un Pack válido. (pack como dict, avisos)."""
    warnings: list[dict] = []
    degree = str(payload.get("degree") or "").strip()[:200] or "Mi titulación"
    institution = str(payload.get("institution") or "").strip()[:200]
    tracks, track_ids = [], set()
    for t in payload.get("tracks") or []:
        tid = _slug(str((t or {}).get("id") or (t or {}).get("name") or ""))
        if tid and tid not in track_ids and (t or {}).get("name"):
            track_ids.add(tid)
            tracks.append({"id": tid, "name": str(t["name"])[:200]})
    subjects, refs = [], set()
    for raw in payload.get("subjects") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        base = _slug(str(raw.get("code") or "") or name)[:56] or "asig"
        ref, n = base, 2
        while ref in refs:
            ref, n = f"{base}-{n}", n + 1
        track = _slug(str(raw.get("track") or "")) if raw.get("track") else None
        item = {"ref": ref, "code": str(raw.get("code") or "")[:32], "name": name[:200], "ects": raw.get("credits"),
                "kind": raw.get("kind") or "obligatoria", "plan_semester": raw.get("plan_semester"),
                "track": track if track in track_ids else None}
        clean = {k: v for k, v in item.items() if v not in (None, "")}
        try:
            packs.PackSubject.model_validate(clean)
            subjects.append(clean)
            refs.add(ref)
        except ValidationError as exc:
            warnings.append({"step": "subjects", "lesson": name, "level": "dropped", "message": exc.errors()[0].get("msg", "")})
    cfg: dict[str, Any] = {"credit_label": str(payload.get("credit_label") or "ECTS")[:20]}
    if payload.get("grade_max") and payload.get("pass_mark") is not None:
        cfg["grade_max"], cfg["pass_mark"] = payload["grade_max"], payload["pass_mark"]
    if payload.get("term_system") in ("semesters", "trimesters", "quarters", "annual"):
        cfg["term_system"] = payload["term_system"]
    if isinstance(payload.get("year_start_month"), int) and 1 <= payload["year_start_month"] <= 12:
        cfg["year_start_month"] = payload["year_start_month"]
    requirements = {k: float(v) for k, v in (payload.get("requirements") or {}).items() if k in models.SUBJECT_KINDS and isinstance(v, (int, float)) and 0 <= v <= 1000}
    total = payload.get("credits_total")
    if not isinstance(total, (int, float)) or not 1 <= total <= 1000:
        total = round(sum(s["ects"] for s in subjects)) or 240
    pack = {
        "format": packs.PACK_FORMAT, "format_version": packs.PACK_FORMAT_VERSION,
        "slug": _slug(f"{institution} {degree}"), "name": f"{institution} · {degree}" if institution else degree,
        "institution": institution, "degree": degree, "description": str(payload.get("description") or "")[:4000],
        "ects_total": int(round(total)), "requirements": requirements, "config": cfg, "tracks": tracks, "subjects": subjects,
        "updated": datetime.now(timezone.utc).date().isoformat(),
    }
    try:
        validated = packs.parse_pack(pack)
    except ValidationError as exc:
        # La escala que dio el modelo no cuadra (p. ej. aprobado > máximo): sin ella, por defecto.
        warnings.append({"step": "config", "lesson": "", "level": "dropped", "message": packs.describe_error(exc)})
        pack["config"] = {"credit_label": cfg["credit_label"]}
        validated = packs.parse_pack(pack)
    return validated.model_dump(mode="json"), warnings


def run_degree_job(job_id: int, text: str) -> None:
    with SessionLocal() as db:
        job = db.get(models.GenerationJob, job_id)
        if job is None:
            return
        job.status = "running"
        db.commit()
        try:
            payload, cost = ai.complete_json(ai.resolve(db), i18n.prompt_lang(db, DEGREE_INSTRUCTIONS), DEGREE_SCHEMA, text, "generator", config.GENERATOR_TIMEOUT_S)
            pack, warnings = build_pack(payload)
            job.draft = {"mode": "career", "units": [], "pack": pack, "refusal": payload.get("refusal")}
            job.warnings, job.cost_usd = warnings, cost
            if not pack["subjects"]:
                job.status, job.error = "error", payload.get("refusal") or "No salieron asignaturas de este documento: ¿es el plan de estudios?"
            else:
                job.status = "done"
        except ai.AiTimeout:
            job.status, job.error = "error", "La extracción tardó demasiado y se canceló."
        except Exception as exc:  # noqa: BLE001
            logger.exception("Plan de estudios %s fallido", job_id)
            job.status, job.error = "error", str(exc)[:1000]
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()


def apply(db, job: models.GenerationJob) -> models.Career:
    pack = packs.parse_pack((job.draft or {}).get("pack") or {})
    return packs.install(db, pack)
