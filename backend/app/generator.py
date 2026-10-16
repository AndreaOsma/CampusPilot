"""Generador de lecciones a partir de tus materiales (Aprender → Generar).

Cómo funciona:

1. Subes texto (`.md`/`.txt`: el manual convertido, tus apuntes, la transcripción de un
   vídeo resumen) y dices qué es.
2. **Barreras antes de llamar a nada**: se rechaza lo que parezca una actividad evaluable
   (PEC, práctica, reto, cuestionario, examen…) por nombre de fichero y por contenido. En
   asignaturas con la IA prohibida solo se admite manual, apuntes o vídeo resumen.
3. Se ejecuta Claude Code en modo no interactivo (`claude -p`) **sin herramientas**: no lee
   ficheros ni ejecuta comandos; solo recibe el texto por la entrada estándar y devuelve JSON
   validado contra un esquema (`--json-schema`).
4. Cada paso se valida con el mismo esquema que un curso importado (`source` obligatoria,
   datos coherentes) y, si trae expresiones de verificación, la respuesta se recalcula con
   safe_math. Lo que no cuadra se descarta o queda marcado para revisar.
5. El resultado es un **borrador**: lo revisas y eliges qué importar.

Credenciales: las lee el CLI de su entorno (`CLAUDE_CODE_OAUTH_TOKEN` de `claude setup-token`
para tu suscripción, uso personal; o `ANTHROPIC_API_KEY`). Nunca se guardan en la base de
datos ni llegan al navegador.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from . import ai, config, i18n, learn, models, svg_safe, syllabus
from .database import SessionLocal

logger = logging.getLogger("campus.generator")

MATERIAL_KINDS = {"manual": "Manual o módulo", "apuntes": "Mis apuntes", "video": "Vídeo resumen (transcripción)", "otro": "Otro material"}
SAFE_KINDS_FOR_FORBIDDEN = {"manual", "apuntes", "video"}

# Nombres de fichero que suelen ser enunciados de actividades evaluables.
_EVALUABLE_NAME = re.compile(
    r"(enunciad|pec\s*\d|\bpec\b|\bpr\s*\d|pr[aá]ctica\s*\d|reto\s*\d|cuestionari|examen|prueba[-_ ]de[-_ ]s[ií]ntesis|\bps\b|soluci[oó]n[-_ ]pec"
    # Lo mismo en inglés (otras universidades).
    r"|assignment|homework|coursework|\bquiz|\bexam\b|midterm|final[-_ ]exam|graded|problem[-_ ]set|\bpset\d*)",
    re.IGNORECASE,
)
# Frases que delatan el enunciado de una actividad (no un manual).
_EVALUABLE_TEXT = re.compile(
    r"(enunciado de la (actividad|pec|pr[aá]ctica)|fecha (l[ií]mite )?de entrega|criterios de (evaluaci[oó]n|correcci[oó]n)|"
    r"esta actividad (es|se) evalua|no est[aá] permitido el uso de herramientas de inteligencia artificial|"
    r"submission deadline|due date|grading (criteria|rubric)|this (assignment|activity) (is|will be) graded|"
    r"(use of )?(generative )?ai (tools )?(is )?not (allowed|permitted))",
    re.IGNORECASE,
)

FIGURE_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {"svg": {"type": "string"}, "alt": {"type": "string"}, "caption": {"type": "string"}},
    "required": ["svg", "alt"],
}
# Lo mismo para el generador de lecciones y el de teoría: cómo dibujar una figura.
FIGURE_RULES = """Figuras: una tarjeta de teoría puede llevar "figure" cuando un dibujo enseña mejor que el texto (el plano complejo con un punto y su módulo y argumento, un diagrama de flujo, la estructura de un programa, una tabla de verdad como cuadrícula…). Como mucho una figura por lección; si no aporta, "figure": null. "figure" = {"svg": "<svg …>", "alt": "qué muestra, en una frase", "caption": "pie corto"}. El SVG: con viewBox (unos 360×240), sin width/height fijos, solo formas (path, line, circle, ellipse, rect, polygon, polyline), text/tspan, g y marker en defs para flechas; nada de script, style, image, foreignObject, enlaces ni CSS. Se ve sobre fondo blanco: trazos y texto oscuros (#1f2937), un color de acento (#2563eb) y otro para destacar (#dc2626); texto de 12 a 16 px con font-family="sans-serif" en el <svg>, en el idioma pedido, que no se corte. Exacto con el material: mismas cantidades, ejes con su etiqueta. Menos de 6 KB."""

STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ref": {"type": "string"},
        "kind": {"type": "string", "enum": ["info", "choice", "truefalse", "numeric", "complex", "order", "param", "match"]},
        "prompt": {"type": "string"},
        "source": {"type": "string"},
        "explanation": {"type": "string"},
        "hints": {"type": "array", "items": {"type": "string"}},
        "concepts": {"type": "array", "items": {"type": "string"}},
        "objectives": {"type": "array", "items": {"type": "string"}},
        "worked": {"type": "string"},
        "data": {"type": "object"},
        "figure": FIGURE_SCHEMA,
        "material": {"type": "string"},
        "page": {"type": ["integer", "null"]},
    },
    "required": ["ref", "kind", "prompt", "source", "explanation", "data"],
}
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "refusal": {"type": ["string", "null"]},
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string"},
                    "title": {"type": "string"},
                    "lessons": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"ref": {"type": "string"}, "title": {"type": "string"}, "steps": {"type": "array", "items": STEP_SCHEMA}},
                            "required": ["ref", "title", "steps"],
                        },
                    },
                },
                "required": ["ref", "title", "lessons"],
            },
        },
    },
    "required": ["units"],
}

INSTRUCTIONS = """Eres el generador de ejercicios de estudio de Campus Pilot. Por la entrada estándar recibes material de una asignatura universitaria. Conviértelo en lecciones interactivas cortas y devuelve SOLO el JSON del esquema.

Reglas (obligatorias):
1. Usa únicamente el material recibido. Cada ejercicio sale de algo concreto del texto: un ejemplo resuelto, un ejercicio con solución, una definición, una propiedad o un procedimiento explicado. No inventes contenido que no esté.
2. "source" en cada paso: la referencia exacta dentro del material (título o número de apartado y, si existe, número de ejemplo, ejercicio o página). Sin referencia no hay paso.
3. Primero la teoría, luego las preguntas: cada lección empieza con 1 a 3 tarjetas "info" que enseñan, sacado del material, lo que hace falta para resolver sus ejercicios (definiciones, propiedades, el procedimiento paso a paso y, si lo hay, un ejemplo corto del propio material). En una tarjeta "info": "prompt" es el título de la tarjeta, "explanation" es el cuerpo (como mucho unas 120 palabras: listas "- ", **negrita** y fórmulas $…$), "data" es {} y "source" es el apartado exacto del material que hay que leer para ampliarla, "material" el nombre del material de donde sale (el de su cabecera «===== MATERIAL: … =====») y "page" la página (las marcas <!-- página N -->) si la hay, o null. Explica con tus palabras lo que dice el material; no añadas nada que no esté en él. "worked" solo para copiar fielmente la resolución de un ejemplo resuelto del material, con su referencia en "source".
4. Si el material es el enunciado de una actividad evaluable (PEC, práctica, reto, cuestionario, examen o similar), no generes nada: devuelve "units": [] y explica el motivo en "refusal".
5. Idioma: {LANG}. Fórmulas en LaTeX entre $…$ (en JSON, escapa las barras: "\\\\frac").
6. Agrupa por apartados del material: una unidad por bloque grande, lecciones cortas de 5 a 8 ejercicios (unos 3 minutos) además de su teoría, de lo fácil a lo difícil, variando los tipos de paso. "ref" en minúsculas con guiones.
7. Tipos de paso y su "data":
   - info: {} (tarjeta de teoría, ver la regla 3; sin "hints"; puede llevar "figure", ver la regla 11)
   - choice: {"options": [3-4 textos], "correct": [índices], "option_feedback": [un texto por opción: para las incorrectas, por qué fallan; para la correcta, ""]}
   - truefalse: {"answer": true|false}
   - numeric: {"answer": número, "tolerance": número, "verify": "expresión que calcula la respuesta"} (+ "period": 6.283185307 si es un ángulo en radianes, "unit")
   - complex: {"re": número, "im": número, "tolerance": número, "verify_re": "expresión", "verify_im": "expresión"}
   - order: {"items": [pasos en el orden correcto]}
   - match: {"pairs": [["concepto", "definición o resultado"], …]} con 3 a 6 parejas (ideal para definiciones, notaciones y fórmulas)
   - Para rellenar un hueco, usa choice con "___" en el enunciado (la opción correcta completa la frase).
   - param (mismo procedimiento con números nuevos cada vez; úsalo cuando el material enseñe un cálculo mecánico): {"vars": {"a": {"min": -6, "max": 6, "nonzero": true}, …}, "show": {"z1": {"cx": ["a", "b"]}, "k": {"expr": "a+b"}}, "answer": {"kind": "numeric", "value": "expresión"} o {"kind": "complex", "re": "expresión", "im": "expresión", "tolerance": 0.001}}. El "prompt" y la "explanation" usan {a}, {z1}… y la explicación puede usar {result}, {re}, {im} o {value}.
   Las expresiones solo admiten números, las variables, + - * / ** y sqrt, sin, cos, tan, atan, atan2, asin, acos, exp, log, abs, pi, e.
8. "hints": 1 o 2 pistas graduales que orienten sin dar la respuesta. "concepts": 1 a 3 etiquetas cortas en minúscula (p. ej. "conjugado", "forma polar"). "explanation": la resolución breve, como la del material.
9. Calcula con cuidado: la app recalcula "verify" y descarta lo que no cuadre.
10. Si al final viene el plan docente de la asignatura: que la teoría y los ejercicios trabajen sus objetivos de aprendizaje (los del módulo, si se indica), y en "objectives" de cada paso pon los códigos (O1, O2…) de los objetivos que practica. Sin plan docente, "objectives": [].
11. """ + FIGURE_RULES + """
"""


def pdf_to_text(data: bytes, name: str) -> str:
    """Texto de un PDF con una marca por página (para que las fuentes citen la página).
    Lanza ValueError si no es un PDF válido, es demasiado grande o no tiene texto."""
    import io

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if len(data) > config.MAX_PDF_BYTES:
        raise ValueError(f"«{name}» supera los {config.MAX_PDF_BYTES // (1024 * 1024)} MB")
    if not data.startswith(b"%PDF"):
        raise ValueError(f"«{name}» no es un PDF")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError(f"«{name}» está protegido con contraseña")
        pages = reader.pages
        if len(pages) > config.MAX_PDF_PAGES:
            raise ValueError(f"«{name}» tiene más de {config.MAX_PDF_PAGES} páginas: súbelo por partes")
        texts = [(page.extract_text() or "").strip() for page in pages]
    except PdfReadError:
        raise ValueError(f"«{name}» no se puede leer como PDF")
    # Un escaneado sin OCR da páginas casi vacías.
    if sum(len(t) for t in texts) < 20 * max(1, len(texts)):
        raise ValueError(f"«{name}» apenas tiene texto (¿es un escaneado?): pasa antes un OCR o súbelo en Markdown")
    text = "\n\n".join(f"<!-- página {i} -->\n{t}" for i, t in enumerate(texts, start=1))
    return text


def status(db: Session) -> dict:
    st = ai.status(db)
    lg = i18n.lang(db)
    return {**st, "kinds": {k: i18n.tr(lg, v) for k, v in MATERIAL_KINDS.items()}}


def check_material(name: str, text: str, kind: str, subject: Optional[models.Subject]) -> None:
    """Lanza ValueError si el material no se puede usar para generar."""
    if kind not in MATERIAL_KINDS:
        raise ValueError("Tipo de material no válido")
    if subject is not None and subject.ai_policy == "forbidden" and kind not in SAFE_KINDS_FOR_FORBIDDEN:
        raise ValueError(
            f"«{subject.name}» prohíbe la IA en las actividades evaluables: solo se puede generar desde el manual, tus apuntes o un vídeo resumen."
        )
    if _EVALUABLE_NAME.search(name):
        raise ValueError(f"«{name}» parece el enunciado o la solución de una actividad evaluable: no se usa para generar.")
    head = text[:20000]
    if _EVALUABLE_TEXT.search(head):
        raise ValueError(f"«{name}» contiene texto de un enunciado de actividad evaluable: no se usa para generar.")


def clean_draft(payload: dict, codes: Optional[set[str]] = None, cited: Optional[dict[str, int]] = None) -> tuple[dict, list[dict]]:
    """Valida paso a paso; descarta lo inválido y marca lo que no verifica. (borrador, avisos).
    `codes`: objetivos válidos del plan docente (los demás se quitan de cada paso)."""
    warnings: list[dict] = []
    units_out = []
    for u_i, unit in enumerate(payload.get("units") or []):
        if not isinstance(unit, dict):
            continue
        lessons_out = []
        for l_i, lesson in enumerate(unit.get("lessons") or []):
            if not isinstance(lesson, dict):
                continue
            steps_out = []
            seen: set[str] = set()
            for s_i, raw in enumerate(lesson.get("steps") or []):
                if not isinstance(raw, dict):
                    continue
                figure = raw.get("figure") if raw.get("kind") == "info" else None
                # Teoría: de qué material de la biblioteca y qué página, para abrir el PDF ahí.
                cite_id = (cited or {}).get(str(raw.get("material") or "")) if raw.get("kind") == "info" else None
                page = raw.get("page") if isinstance(raw.get("page"), int) and 1 <= raw.get("page") <= 10000 else None
                raw = {k: raw[k] for k in ("ref", "kind", "prompt", "source", "explanation", "hints", "concepts", "objectives", "worked", "data") if k in raw}
                raw["data"] = {k: v for k, v in (raw.get("data") if isinstance(raw.get("data"), dict) else {}).items() if k != "figure"}
                if figure:
                    # Una figura mal hecha no tira la tarjeta: se queda sin dibujo y se avisa.
                    try:
                        clean = svg_safe.clean_figure(figure)
                        if clean:
                            raw["data"]["figure"] = clean
                    except ValueError as exc:
                        warnings.append({"step": raw.get("ref"), "lesson": lesson.get("title"), "level": "figure", "message": f"Figura descartada: {exc}"})
                if cite_id:
                    raw["data"]["cite"] = {"material_id": cite_id, "page": page}
                if isinstance(raw.get("objectives"), list):
                    raw["objectives"] = [c for c in raw["objectives"] if isinstance(c, str) and c in (codes or set())]
                raw["ref"] = _slug(str(raw.get("ref") or f"p{s_i + 1}"))
                while raw["ref"] in seen:
                    raw["ref"] = f"{raw['ref']}-{s_i}"
                seen.add(raw["ref"])
                try:
                    step = learn.StepIn.model_validate(raw)
                    # La teoría también cita de dónde sale: es lo que hay que ir a leer al manual.
                    if step.kind == "info" and not step.source.strip():
                        raise ValueError(f"Tarjeta {step.ref}: falta «source» (qué apartado del material leer)")
                except (ValidationError, ValueError) as exc:
                    message = learn.describe_error(exc) if isinstance(exc, ValidationError) else str(exc)
                    warnings.append({"step": raw.get("ref"), "lesson": lesson.get("title"), "level": "dropped", "message": message})
                    continue
                item = step.model_dump()
                issue = learn.verify_issue(step.kind, step.data)
                if issue:
                    item["flag"] = issue
                    warnings.append({"step": step.ref, "lesson": lesson.get("title"), "level": "review", "message": issue})
                steps_out.append(item)
            # Primero la teoría, luego las preguntas, aunque el modelo las mezcle.
            steps_out.sort(key=lambda x: x["kind"] != "info")
            if steps_out:
                lessons_out.append({"ref": _slug(str(lesson.get("ref") or f"l{l_i + 1}")), "title": str(lesson.get("title") or "Lección")[:200], "steps": steps_out})
        if lessons_out:
            units_out.append({"ref": _slug(str(unit.get("ref") or f"u{u_i + 1}")), "title": str(unit.get("title") or "Unidad")[:200], "lessons": lessons_out})
    return {"units": units_out, "refusal": payload.get("refusal")}, warnings


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-.")[:60]
    if not s:
        return "x"
    return s if s[0].isalnum() else f"x{s}"[:60]


def run_job(job_id: int, material: str, module_ref: str = "", cited: Optional[dict[str, int]] = None) -> None:
    """Se ejecuta en segundo plano (hilo de FastAPI BackgroundTasks)."""
    with SessionLocal() as db:
        job = db.get(models.GenerationJob, job_id)
        if job is None:
            return
        job.status = "running"
        db.commit()
        try:
            subject = db.get(models.Subject, job.subject_id) if job.subject_id else None
            plan = syllabus.prompt_block(subject, module_ref)
            text = f"{material}\n\n{plan}" if plan else material
            payload, cost = ai.complete_json(ai.resolve(db), i18n.prompt_lang(db, INSTRUCTIONS), OUTPUT_SCHEMA, text, "generator", config.GENERATOR_TIMEOUT_S)
            draft, warnings = clean_draft(payload, syllabus.valid_codes(subject), cited)
            if module_ref and any(m["ref"] == module_ref for m in syllabus.modules_of(subject)):
                draft["module_ref"] = module_ref
            job.draft, job.warnings, job.cost_usd = draft, warnings, cost
            if not draft["units"]:
                job.status = "error"
                job.error = draft.get("refusal") or "No salió ningún ejercicio válido de este material."
            else:
                job.status = "done"
        except ai.AiTimeout:
            job.status, job.error = "error", "La generación tardó demasiado y se canceló."
        except Exception as exc:  # noqa: BLE001 — el error se enseña en el trabajo
            logger.exception("Generación %s fallida", job_id)
            job.status, job.error = "error", str(exc)[:1000]
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()


def fail_interrupted() -> None:
    """Al arrancar: lo que estaba en marcha murió con el proceso anterior."""
    with SessionLocal() as db:
        for job in db.query(models.GenerationJob).filter(models.GenerationJob.status.in_(("queued", "running"))):
            job.status, job.error = "error", "Interrumpido por un reinicio del servidor."
        db.commit()


def merge_into_course(db: Session, job: models.GenerationJob, exclude: set[str], subject: Optional[models.Subject] = None) -> models.Course:
    """Suma el borrador (sin los pasos excluidos) al curso de su asignatura. Reimportar el mismo
    borrador reemplaza sus unidades en vez de duplicarlas."""
    subject = subject or (db.get(models.Subject, job.subject_id) if job.subject_id else None)
    if subject is None:
        raise ValueError("Elige la asignatura: las lecciones se añaden al curso de una asignatura")
    job.subject_id = subject.id
    units = []
    for u in (job.draft or {}).get("units", []):
        lessons = []
        for lesson in u["lessons"]:
            steps = [{k: v for k, v in s.items() if k != "flag"} for s in lesson["steps"] if f"{u['ref']}/{lesson['ref']}/{s['ref']}" not in exclude]
            if steps:
                lessons.append({"ref": lesson["ref"], "title": lesson["title"], "steps": steps})
        if lessons:
            units.append({"ref": f"g{job.id}-{u['ref']}"[:64], "source": f"g{job.id}", "title": u["title"], "lessons": lessons,
                          "module": (job.draft or {}).get("module_ref", "")})
    if not units:
        raise ValueError("No hay pasos seleccionados")
    course_in = learn.CourseIn.model_validate({
        "format": learn.COURSE_FORMAT, "format_version": 1, "slug": f"g{job.id}", "title": subject.name,
        "description": "Generado a partir de tus materiales. Revisa los ejercicios: si alguno está mal, edítalo o bórralo.",
        "source_note": f"Generado desde: {', '.join(job.filenames)}"[:2000], "units": units,
    })
    return learn.import_course(db, course_in, subject)



# ---------- Teoría para lecciones que ya existen ----------
# Mismo flujo (material → borrador → revisar → añadir), pero en vez de lecciones nuevas saca
# tarjetas de teoría para las lecciones del curso de la asignatura, que se ponen delante de
# sus preguntas. Así las lecciones generadas antes de que hubiera teoría se ponen al día.

THEORY_PREFIX = "teoria-"
THEORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "refusal": {"type": ["string", "null"]},
        "lessons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lesson": {"type": "string"},
                    "objectives": {"type": "array", "items": {"type": "string"}},
                    "module": {"type": "string"},
                    "cards": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "source": {"type": "string"}, "figure": FIGURE_SCHEMA,
                                           "material": {"type": "string"}, "page": {"type": ["integer", "null"]}},
                            "required": ["title", "body", "source"],
                        },
                    },
                },
                "required": ["lesson", "cards"],
            },
        },
    },
    "required": ["lessons"],
}

THEORY_INSTRUCTIONS = """Eres el profesor de teoría de Campus Pilot. Por la entrada estándar recibes material de una asignatura universitaria y, al final, la lista de las lecciones que ya existen (cada una con su clave «L<número>», su título y sus ejercicios). Escribe, para cada lección, la teoría que hay que leer antes de sus ejercicios, y devuelve SOLO el JSON del esquema.

Reglas (obligatorias):
1. Usa únicamente el material recibido: explica con tus palabras lo que dice, sin añadir nada que no esté. Si una lección no tiene nada en el material, no la incluyas.
2. De 1 a 3 tarjetas por lección, de lo básico a lo concreto, que cubran lo que piden sus ejercicios (definiciones, propiedades, el procedimiento paso a paso y, si lo hay, un ejemplo corto del propio material). No resuelvas los ejercicios de la lección.
3. "title": el título de la tarjeta. "body": como mucho unas 120 palabras; listas "- ", **negrita** y fórmulas en LaTeX entre $…$ (en JSON, escapa las barras: "\\\\frac"). "source": el apartado exacto del material (título o número y, si existe, página) que hay que leer para ampliarla; "material": el nombre del material de su cabecera «===== MATERIAL: … =====»; "page": la página (marcas <!-- página N -->) o null.
4. "lesson": la clave tal cual aparece en la lista (p. ej. "L12").
5. Si el material es el enunciado de una actividad evaluable (PEC, práctica, reto, cuestionario, examen o similar), no generes nada: devuelve "lessons": [] y explica el motivo en "refusal".
6. Idioma: {LANG}.
7. Si viene el plan docente de la asignatura: que la teoría cubra los objetivos de aprendizaje que trabajan los ejercicios de cada lección; en "objectives" pon sus códigos (O1, O2…) y en "module" el ref del módulo del temario al que pertenece la lección. Sin plan docente, "objectives": [] y "module": "".
8. """ + FIGURE_RULES.replace("una tarjeta de teoría puede llevar", "una tarjeta puede llevar") + """
"""


def subject_lessons(db: Session, subject: models.Subject) -> list[models.Lesson]:
    course = db.query(models.Course).filter_by(subject_id=subject.id).first()
    return [lesson for u in course.units for lesson in u.lessons] if course else []


def lessons_brief(lessons: list[models.Lesson]) -> str:
    """Las lecciones para el modelo: clave, título y enunciados (sin soluciones)."""
    out = ["===== LECCIONES QUE YA EXISTEN ====="]
    for lesson in lessons:
        out.append(f"\n[L{lesson.id}] {lesson.unit.title} › {lesson.title}")
        for s in lesson.steps:
            if s.kind != "info":
                out.append(f"- {s.prompt[:300]}")
    return "\n".join(out)


def clean_theory(payload: dict, lessons: list[models.Lesson], cited: Optional[dict[str, int]] = None) -> tuple[dict, list[dict]]:
    """Convierte la respuesta en un borrador con forma de curso (unidad → lección → tarjetas)
    para revisarlo igual que uno de lecciones nuevas. Refs: u<id de unidad>, l<id de lección>."""
    by_key = {f"L{lesson.id}": lesson for lesson in lessons}
    subject = lessons[0].unit.course.subject if lessons else None
    codes = syllabus.valid_codes(subject)
    modules = {m["ref"] for m in syllabus.modules_of(subject)}
    meta: dict[str, dict] = {}
    units: dict[int, dict] = {}
    for item in payload.get("lessons") or []:
        lesson = by_key.get(str(item.get("lesson", "")).strip()) if isinstance(item, dict) else None
        if lesson is None:
            continue
        steps = [
            {"ref": f"{THEORY_PREFIX}{i + 1}", "kind": "info", "prompt": str(c.get("title", "")), "explanation": str(c.get("body", "")),
             "source": str(c.get("source", "")), "data": {}, "figure": c.get("figure"), "material": c.get("material"), "page": c.get("page")}
            for i, c in enumerate(x for x in item.get("cards") or [] if isinstance(x, dict))
        ]
        meta[f"l{lesson.id}"] = {
            "objectives": [c for c in dict.fromkeys(item.get("objectives") or []) if isinstance(c, str) and c in codes][:6],
            "module": item.get("module") if item.get("module") in modules else "",
        }
        for st in steps:
            st["objectives"] = meta[f"l{lesson.id}"]["objectives"]
        unit = units.setdefault(lesson.unit_id, {"ref": f"u{lesson.unit_id}", "title": lesson.unit.title, "lessons": []})
        unit["lessons"].append({"ref": f"l{lesson.id}", "title": lesson.title, "steps": steps[:3]})
    order = {lesson.id: i for i, lesson in enumerate(lessons)}
    for unit in units.values():
        unit["lessons"].sort(key=lambda x: order[int(x["ref"][1:])])
    draft, warnings = clean_draft({"units": list(units.values()), "refusal": payload.get("refusal")}, codes, cited)
    # clean_draft rehace los refs con _slug; los de aquí ya son válidos y son las claves de vuelta.
    for u in draft["units"]:
        for l_d in u["lessons"]:
            l_d.update(meta.get(l_d["ref"], {}))
    return {**draft, "mode": "theory"}, warnings


def run_theory_job(job_id: int, material: str, cited: Optional[dict[str, int]] = None) -> None:
    """Como run_job, para el modo teoría (hilo de BackgroundTasks)."""
    with SessionLocal() as db:
        job = db.get(models.GenerationJob, job_id)
        if job is None:
            return
        job.status = "running"
        db.commit()
        try:
            subject = db.get(models.Subject, job.subject_id) if job.subject_id else None
            lessons = subject_lessons(db, subject) if subject else []
            if not lessons:
                raise RuntimeError("Esta asignatura aún no tiene lecciones")
            text = "\n\n".join(x for x in (material, syllabus.prompt_block(subject), lessons_brief(lessons)) if x)
            payload, cost = ai.complete_json(ai.resolve(db), i18n.prompt_lang(db, THEORY_INSTRUCTIONS), THEORY_SCHEMA, text, "generator", config.GENERATOR_TIMEOUT_S)
            draft, warnings = clean_theory(payload, lessons, cited)
            job.draft, job.warnings, job.cost_usd = draft, warnings, cost
            if not draft["units"]:
                job.status = "error"
                job.error = draft.get("refusal") or "No salió teoría válida para ninguna lección con este material."
            else:
                job.status = "done"
        except ai.AiTimeout:
            job.status, job.error = "error", "La generación tardó demasiado y se canceló."
        except Exception as exc:  # noqa: BLE001 — el error se enseña en el trabajo
            logger.exception("Generación de teoría %s fallida", job_id)
            job.status, job.error = "error", str(exc)[:1000]
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()


def add_theory(db: Session, job: models.GenerationJob, exclude: set[str]) -> models.Course:
    """Pone las tarjetas del borrador delante de las preguntas de cada lección. Sustituye la
    teoría que haya puesto antes este modo (refs teoria-*); el resto de pasos no se toca."""
    subject = db.get(models.Subject, job.subject_id) if job.subject_id else None
    if subject is None:
        raise ValueError("La asignatura de este borrador ya no existe")
    valid = {lesson.id: lesson for lesson in subject_lessons(db, subject)}
    added = 0
    for u in (job.draft or {}).get("units", []):
        for l_d in u["lessons"]:
            lesson = valid.get(int(l_d["ref"][1:]))
            if lesson is None:
                continue  # borrada desde que se generó
            cards = [s for s in l_d["steps"] if f"{u['ref']}/{l_d['ref']}/{s['ref']}" not in exclude]
            if not cards:
                continue
            for step in list(lesson.steps):
                if step.kind == "info" and step.ref.startswith(THEORY_PREFIX):
                    lesson.steps.remove(step)
                    db.delete(step)
            rest = sorted(lesson.steps, key=lambda s: s.position)
            objectives = l_d.get("objectives") or []
            for pos, c in enumerate(cards):
                db.add(models.LessonStep(lesson_id=lesson.id, ref=c["ref"], position=pos, kind="info", prompt=c["prompt"],
                                         explanation=c["explanation"], source=c["source"], data=c.get("data") or {}, objectives=objectives))
            for pos, step in enumerate(rest, start=len(cards)):
                step.position = pos
                # Los ejercicios sin objetivos heredan los de su lección (no se pisa lo que ya tengan).
                if objectives and not step.objectives:
                    step.objectives = objectives
            if l_d.get("module") and not lesson.unit.module_ref:
                lesson.unit.module_ref = l_d["module"]
            added += len(cards)
    if not added:
        raise ValueError("No hay tarjetas seleccionadas")
    db.commit()
    return learn.course_for_subject(db, subject)
