"""Plan docente de una asignatura (ficha de la asignatura → Plan docente).

Subes el plan docente que publica la universidad (PDF o texto) y la IA lo pasa a datos:

- **Objetivos de aprendizaje** tal como los marca la universidad (conocimientos, habilidades,
  competencias), con un código corto ("O1", "O2"…).
- **Temario** por módulos, con los objetivos que trabaja cada uno.
- **Recursos** (manuales, vídeos…), **evaluación** (modelo, grupos, pesos y mínimos) y
  **fechas** de las actividades.

Como el generador, sale un borrador (GenerationJob con `draft.mode = "plan"`) que se revisa
antes de aplicarlo. Al aplicarlo, los objetivos y el temario se guardan en la asignatura y
Aprender los usa: el generador alinea teoría y ejercicios con ellos, cada paso lleva los
objetivos que practica y hay dominio por objetivo. La evaluación y las fechas solo se tocan
si se eligen en la revisión (por defecto no, si la asignatura ya las tiene), y la política de
IA nunca se relaja: solo se rellena si estaba sin indicar.

Un plan docente no es el enunciado de una actividad: aquí no se generan ejercicios ni se
resuelve nada, solo se organiza (por eso no pasa por generator.check_material, cuyo filtro de
"criterios de evaluación" lo rechazaría).
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from . import ai, config, i18n, models
from .database import SessionLocal

logger = logging.getLogger("campus.syllabus")

ObjectiveKind = Literal["general", "conocimiento", "habilidad", "competencia"]
_CODE_RE = re.compile(r"^[A-Za-z0-9._-]{1,16}$")


class Objective(BaseModel):
    code: str = Field(pattern=_CODE_RE.pattern)
    kind: ObjectiveKind = "conocimiento"
    text: str = Field(min_length=1, max_length=600)


class Module(BaseModel):
    ref: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    topics: list[str] = Field(default_factory=list, max_length=40)
    objectives: list[str] = Field(default_factory=list, max_length=40)


class Resource(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    kind: str = Field(default="", max_length=40)


class PlanGroup(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    weight: float = Field(ge=0, le=100)
    min_grade: Optional[float] = Field(default=None, ge=0, le=100)
    role: Optional[Literal["ec", "pf"]] = None


class PlanActivity(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    kind: str = Field(default="other", max_length=16)
    group: str = Field(default="", max_length=80)
    weight: float = Field(default=1, ge=0, le=100)
    window_start: Optional[date] = None
    due_date: Optional[date] = None
    evaluable: bool = True


class Syllabus(BaseModel):
    summary: str = Field(default="", max_length=2000)
    objectives: list[Objective] = Field(default_factory=list, max_length=80)
    modules: list[Module] = Field(default_factory=list, max_length=30)
    resources: list[Resource] = Field(default_factory=list, max_length=60)


class PlanDraft(Syllabus):
    eval_model: Optional[Literal["weighted", "ec_pf"]] = None
    ec_pass: Optional[float] = Field(default=None, ge=0, le=100)
    pf_min: Optional[float] = Field(default=None, ge=0, le=100)
    groups: list[PlanGroup] = Field(default_factory=list, max_length=20)
    activities: list[PlanActivity] = Field(default_factory=list, max_length=200)
    ai_policy: Literal["allowed", "limited", "forbidden", "unknown"] = "unknown"
    ai_policy_note: str = Field(default="", max_length=2000)


_STR = {"type": "string"}
_NUM_OR_NULL = {"type": ["number", "null"]}
PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "refusal": {"type": ["string", "null"]},
        "summary": _STR,
        "objectives": {"type": "array", "items": {"type": "object", "properties": {
            "code": _STR, "kind": {"type": "string", "enum": ["general", "conocimiento", "habilidad", "competencia"]}, "text": _STR,
        }, "required": ["code", "kind", "text"]}},
        "modules": {"type": "array", "items": {"type": "object", "properties": {
            "ref": _STR, "title": _STR, "topics": {"type": "array", "items": _STR}, "objectives": {"type": "array", "items": _STR},
        }, "required": ["ref", "title", "topics", "objectives"]}},
        "resources": {"type": "array", "items": {"type": "object", "properties": {"title": _STR, "kind": _STR}, "required": ["title"]}},
        "eval_model": {"type": ["string", "null"], "enum": ["weighted", "ec_pf", None]},
        "ec_pass": _NUM_OR_NULL,
        "pf_min": _NUM_OR_NULL,
        "groups": {"type": "array", "items": {"type": "object", "properties": {
            "name": _STR, "weight": {"type": "number"}, "min_grade": _NUM_OR_NULL, "role": {"type": ["string", "null"], "enum": ["ec", "pf", None]},
        }, "required": ["name", "weight"]}},
        "activities": {"type": "array", "items": {"type": "object", "properties": {
            "name": _STR, "kind": _STR, "group": _STR, "weight": {"type": "number"},
            "window_start": {"type": ["string", "null"]}, "due_date": {"type": ["string", "null"]}, "evaluable": {"type": "boolean"},
        }, "required": ["name", "kind"]}},
        "ai_policy": {"type": "string", "enum": ["allowed", "limited", "forbidden", "unknown"]},
        "ai_policy_note": _STR,
    },
    "required": ["objectives", "modules"],
}

PLAN_INSTRUCTIONS = """Eres el asistente de organización de Campus Pilot. Por la entrada estándar recibes el plan docente de UNA asignatura universitaria. Pásalo a datos y devuelve SOLO el JSON del esquema.

Reglas (obligatorias):
1. Copia, no inventes. Todo sale del plan docente; si un dato no está, déjalo vacío o null.
2. "objectives": los objetivos/resultados de aprendizaje y competencias que marca el plan, con su texto literal (puedes quitar viñetas). "kind": general (objetivos generales), conocimiento, habilidad o competencia, según el apartado donde aparecen. "code": O1, O2… en orden. Omite las competencias genéricas de la titulación copiadas de la memoria del grado o de un real decreto si el plan ya da objetivos específicos de la asignatura.
3. "modules": los módulos o temas de "Contenidos", en orden, con "ref" en minúsculas con guiones (m1, m2…), su título y sus apartados en "topics". En "objectives" pon los códigos de los objetivos de conocimiento o habilidad que trabaja cada módulo, deducidos de su contenido (un objetivo puede estar en varios módulos).
4. "resources": los materiales y recursos de aprendizaje listados (título y soporte: pdf, audiovisual, web…).
5. Evaluación: "eval_model" = "ec_pf" si combina evaluación continua y prueba final con mínimos; "weighted" si es una suma ponderada; null si no se puede saber. "ec_pass" y "pf_min": las notas mínimas de EC y PF si las da. "groups": los bloques que forman la nota final (p. ej. EC 50 % y PF 50 % con mínimo 4; o PEC 30 % y PR 70 %), con "role" "ec"/"pf" en el modelo ec_pf.
6. "activities": cada actividad con fecha de la tabla de fechas (nombre tal cual, "window_start" = fecha de inicio y "due_date" = fecha de entrega, en formato AAAA-MM-DD). "kind": pec, pr, quiz, exam, video u other. "group": el nombre del grupo de evaluación al que cuenta. "weight": su peso relativo dentro del grupo si el plan lo da (si no, 1).
7. "ai_policy": forbidden si prohíbe la IA generativa salvo que se indique lo contrario, allowed si la permite, limited si la permite con condiciones, unknown si no dice nada. "ai_policy_note": la frase clave del plan.
8. "summary": dos o tres frases de qué trata la asignatura, sacadas de su descripción.
9. Si lo que recibes no es un plan docente (p. ej. es el enunciado de una actividad evaluable), no devuelvas nada: listas vacías y el motivo en "refusal".
10. Idioma: {LANG} (salvo los objetivos, que van con el texto literal del plan, y los nombres de módulos y actividades, tal cual).
"""


def parse_draft(payload: dict) -> tuple[dict, list[dict]]:
    """Valida lo que devuelve el modelo, pieza a pieza: lo que no cuadra se descarta con aviso."""
    warnings: list[dict] = []
    clean: dict[str, Any] = {}
    item_models = {"objectives": Objective, "modules": Module, "resources": Resource, "groups": PlanGroup, "activities": PlanActivity}
    for key, model in item_models.items():
        items = []
        for raw in payload.get(key) or []:
            try:
                items.append(model.model_validate(raw).model_dump(mode="json"))
            except ValidationError as exc:
                warnings.append({"step": key, "lesson": str((raw or {}).get("name") or (raw or {}).get("title") or (raw or {}).get("code") or ""),
                                 "level": "dropped", "message": exc.errors()[0].get("msg", "")})
        clean[key] = items
    for key in ("summary", "eval_model", "ec_pass", "pf_min", "ai_policy", "ai_policy_note"):
        if payload.get(key) is not None:
            clean[key] = payload[key]
    try:
        draft = PlanDraft.model_validate(clean)
    except ValidationError as exc:
        raise ValueError(f"El plan extraído no es válido: {exc.errors()[0].get('msg', '')}")
    # Los objetivos de cada módulo tienen que existir; códigos únicos.
    codes: set[str] = set()
    objectives = []
    for o in draft.objectives:
        if o.code not in codes:
            codes.add(o.code)
            objectives.append(o)
    draft.objectives = objectives
    for m in draft.modules:
        m.objectives = [c for c in dict.fromkeys(m.objectives) if c in codes]
    return {"mode": "plan", "plan": draft.model_dump(mode="json"), "refusal": payload.get("refusal"), "units": []}, warnings


def run_plan_job(job_id: int, text: str) -> None:
    """En segundo plano, como generator.run_job."""
    with SessionLocal() as db:
        job = db.get(models.GenerationJob, job_id)
        if job is None:
            return
        job.status = "running"
        db.commit()
        try:
            payload, cost = ai.complete_json(ai.resolve(db), i18n.prompt_lang(db, PLAN_INSTRUCTIONS), PLAN_SCHEMA, text, "generator", config.GENERATOR_TIMEOUT_S)
            draft, warnings = parse_draft(payload)
            job.draft, job.warnings, job.cost_usd = draft, warnings, cost
            plan = draft["plan"]
            if not plan["objectives"] and not plan["modules"]:
                job.status = "error"
                job.error = draft.get("refusal") or "No salieron objetivos ni temario de este documento: ¿es el plan docente?"
            else:
                job.status = "done"
        except ai.AiTimeout:
            job.status, job.error = "error", "La extracción tardó demasiado y se canceló."
        except Exception as exc:  # noqa: BLE001 — el error se enseña en el trabajo
            logger.exception("Plan docente %s fallido", job_id)
            job.status, job.error = "error", str(exc)[:1000]
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def activity_exists(subject: models.Subject, act: dict) -> bool:
    """¿Ya hay en la agenda algo que parece esta actividad? (misma entrega o mismo nombre)."""
    due = act.get("due_date")
    for row in subject.activities:
        if _norm(row.name) == _norm(act["name"]):
            return True
        if due and row.due_date and row.due_date.isoformat() == due and (row.kind == act.get("kind") or not act.get("kind")):
            return True
    return False


ACTIVITY_KINDS = set(models.ACTIVITY_KINDS)


def apply_plan(db: Session, job: models.GenerationJob, use_eval: bool, activities: list[int]) -> models.Subject:
    subject = db.get(models.Subject, job.subject_id) if job.subject_id else None
    if subject is None:
        raise ValueError("La asignatura de este plan ya no existe")
    plan = PlanDraft.model_validate((job.draft or {}).get("plan") or {})
    subject.syllabus = {
        **Syllabus.model_validate(plan.model_dump()).model_dump(mode="json"),
        "source": ", ".join(job.filenames)[:300],
        "imported_on": datetime.now(timezone.utc).date().isoformat(),
    }
    if plan.ai_policy != "unknown" and subject.ai_policy == "unknown":
        subject.ai_policy = plan.ai_policy
        subject.ai_policy_note = subject.ai_policy_note or plan.ai_policy_note

    if use_eval and plan.groups:
        if plan.eval_model:
            subject.eval_model = plan.eval_model
        cfg = dict(subject.eval_config or {})
        if plan.ec_pass is not None:
            cfg["ec_pass"] = plan.ec_pass
        if plan.pf_min is not None:
            cfg["pf_min"] = plan.pf_min
        subject.eval_config = cfg
        existing = {_norm(g.name): g for g in subject.groups}
        for pos, g in enumerate(plan.groups):
            row = existing.get(_norm(g.name))
            if row is None:
                row = models.EvalGroup(subject_id=subject.id, name=g.name)
                db.add(row)
                subject.groups.append(row)
            row.weight, row.min_grade, row.role, row.position = g.weight, g.min_grade, g.role, pos
        db.flush()

    groups = {_norm(g.name): g for g in subject.groups}
    for idx in activities:
        if not 0 <= idx < len(plan.activities):
            continue
        a = plan.activities[idx]
        ref = f"plan:{subject.id}:{_norm(a.name).replace(' ', '-')}"[:160]
        row = db.query(models.Activity).filter_by(pack_ref=ref).first()
        if row is None:
            row = models.Activity(subject_id=subject.id, pack_ref=ref)
            db.add(row)
        group = groups.get(_norm(a.group)) if a.group else None
        row.name, row.kind = a.name, a.kind if a.kind in ACTIVITY_KINDS else "other"
        row.weight, row.evaluable = a.weight, a.evaluable
        row.group_id = group.id if group else row.group_id
        row.due_date = a.due_date
        row.window_start, row.window_end = (a.window_start, a.due_date) if a.window_start else (None, None)
    db.commit()
    db.refresh(subject)
    return subject


# ---------- Lo que usa Aprender ----------

def objectives_of(subject: Optional[models.Subject]) -> list[dict]:
    return list((subject.syllabus or {}).get("objectives") or []) if subject else []


def modules_of(subject: Optional[models.Subject]) -> list[dict]:
    return list((subject.syllabus or {}).get("modules") or []) if subject else []


def prompt_block(subject: Optional[models.Subject], module_ref: str = "") -> str:
    """Objetivos y temario para el prompt del generador ("" si no hay plan docente)."""
    objectives = objectives_of(subject)
    if not objectives:
        return ""
    modules = modules_of(subject)
    module = next((m for m in modules if m["ref"] == module_ref), None)
    lines = ["===== PLAN DOCENTE DE LA ASIGNATURA (objetivos de aprendizaje y temario) ====="]
    if module:
        lines.append(f"Este material es del módulo «{module['title']}» ({module['ref']}): {', '.join(module['topics'])}.")
        lines.append(f"Objetivos de ese módulo: {', '.join(module['objectives']) or '—'}.")
    lines.append("Objetivos:")
    lines += [f"- {o['code']} ({o['kind']}): {o['text']}" for o in objectives]
    if modules:
        lines.append("Temario:")
        lines += [f"- {m['ref']} · {m['title']} → {', '.join(m['objectives']) or '—'}" for m in modules]
    return "\n".join(lines)


def valid_codes(subject: Optional[models.Subject]) -> set[str]:
    return {o["code"] for o in objectives_of(subject)}
