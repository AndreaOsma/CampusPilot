"""Aprender: un curso interactivo por asignatura, por pasos, con racha y XP.

Un curso es un JSON (`format: "campus-pilot-course"`) con unidades → lecciones → pasos.
Tipos de paso y su `data`:

- ``info``: tarjeta de lectura, sin respuesta.
- ``choice``: ``{"options": [..], "correct": [índices]}`` (una o varias correctas).
- ``truefalse``: ``{"answer": true|false}``.
- ``numeric``: ``{"answer": x, "tolerance": t, "period": p?, "unit": "rad"?}``; con ``period``
  se acepta cualquier valor equivalente (ángulos: 2π).
- ``complex``: ``{"re": a, "im": b, "tolerance": t}`` — se responde parte real e imaginaria.
- ``order``: ``{"items": [..]}`` en el orden correcto; la app los baraja.
- ``match``: ``{"pairs": [["izquierda", "derecha"], …]}`` (3 a 6 parejas); la app baraja la
  columna derecha y se emparejan tocando.
- Un ``choice`` cuyo enunciado lleva ``___`` se presenta como frase con hueco.
- ``param``: el mismo ejercicio con números nuevos cada vez. ``{"vars": {"a": {"min": -5,
  "max": 5, "nonzero": true}}, "show": {"z1": {"cx": ["a", "b"]}, "s": {"expr": "a+b"}},
  "answer": {"kind": "complex", "re": "a*c-b*d", "im": "a*d+b*c", "tolerance": 0.001}}``. El
  enunciado y la explicación usan ``{z1}``, ``{a}``… La solución la calcula el código
  (safe_math), nunca el modelo; la instancia viaja firmada para corregir con esos números.

Opcionales en cualquier paso: ``hints`` (pistas graduales), ``concepts`` (etiquetas para el
mapa de dominio), ``worked`` (ejemplo resuelto que se enseña solo la primera vez) y, en
``choice``, ``data.option_feedback`` (por qué cada opción es incorrecta). En ``numeric`` y
``complex``, ``data.verify`` / ``data.verify_re`` + ``data.verify_im`` recalculan la respuesta:
si no coincide, el paso se marca para revisar.

Reglas del contenido (las comprueba la validación, no la buena voluntad):

- Todo paso evaluable lleva ``source``: de dónde sale en el material (unidad, ejemplo o
  ejercicio). Pensado para asignaturas donde solo se puede estudiar con ejercicios del
  manual identificados, nunca con actividades evaluables.
- La teoría de cada lección la escribe quien estudia (en la app o en sus apuntes): el import
  no la trae ni la pisa.
- Reimportar actualiza enunciados y soluciones por ``ref`` sin perder el progreso.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import random
import re
import secrets
from datetime import date, timedelta
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from . import clock, models, safe_math, svg_safe
from .schemas import UrlStr

COURSE_FORMAT = "campus-pilot-course"
MAX_COURSE_BYTES = 2 * 1024 * 1024
LEITNER_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
XP_FIRST_TRY = 10
XP_RETRY = 4
XP_LESSON = 10

Ref = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]
ObjectiveCode = Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,16}$")]
StepKind = Literal["info", "choice", "truefalse", "numeric", "complex", "order", "param", "match"]
_VAR_RE = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
_PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]{0,15})\}")
PARAM_CHECK_SAMPLES = 25


class StepIn(BaseModel):
    ref: Ref
    kind: StepKind
    prompt: str = Field(min_length=1, max_length=4000)
    data: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(default="", max_length=6000)
    source: str = Field(default="", max_length=300)
    hints: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(default_factory=list, max_length=3)
    concepts: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(default_factory=list, max_length=5)
    # Objetivos de aprendizaje del plan docente que practica (sus códigos: "O3"…).
    objectives: list[ObjectiveCode] = Field(default_factory=list, max_length=6)
    worked: str = Field(default="", max_length=6000)

    @model_validator(mode="after")
    def _check(self):
        self.concepts = sorted({c.strip().lower() for c in self.concepts if c.strip()})
        self.objectives = list(dict.fromkeys(self.objectives))
        d = self.data
        if self.kind != "info" and not self.source.strip():
            raise ValueError(f"Paso {self.ref}: falta «source» (de dónde sale en el material)")
        if self.kind == "info" and "cite" in d:
            c = d["cite"]
            ok = isinstance(c, dict) and isinstance(c.get("material_id"), int) and (c.get("page") is None or (isinstance(c.get("page"), int) and 1 <= c["page"] <= 10000))
            if not ok:
                self.data = d = {k: v for k, v in d.items() if k != "cite"}
        if self.kind == "info" and "figure" in d:
            # Figura de la teoría (SVG): siempre saneada, venga de la IA o de un JSON importado.
            try:
                figure = svg_safe.clean_figure(d["figure"])
            except ValueError as exc:
                raise ValueError(f"Paso {self.ref}: {exc}")
            self.data = {**d, "figure": figure} if figure else {k: v for k, v in d.items() if k != "figure"}
        if self.kind == "choice":
            opts, correct = d.get("options"), d.get("correct")
            if not isinstance(opts, list) or not 2 <= len(opts) <= 8 or not all(isinstance(o, str) and o for o in opts):
                raise ValueError(f"Paso {self.ref}: «options» necesita de 2 a 8 textos")
            if not isinstance(correct, list) or not correct or not all(isinstance(i, int) and 0 <= i < len(opts) for i in correct):
                raise ValueError(f"Paso {self.ref}: «correct» debe listar índices válidos")
            fb = d.get("option_feedback")
            if fb is not None and (not isinstance(fb, list) or len(fb) != len(opts) or not all(isinstance(x, str) for x in fb)):
                raise ValueError(f"Paso {self.ref}: «option_feedback» necesita un texto por opción")
        elif self.kind == "truefalse":
            if not isinstance(d.get("answer"), bool):
                raise ValueError(f"Paso {self.ref}: «answer» debe ser true o false")
        elif self.kind == "numeric":
            if not _is_num(d.get("answer")) or not _is_num(d.get("tolerance", 0)) or d.get("tolerance", 0) < 0:
                raise ValueError(f"Paso {self.ref}: «answer» y «tolerance» numéricos")
            if "period" in d and (not _is_num(d["period"]) or d["period"] <= 0):
                raise ValueError(f"Paso {self.ref}: «period» debe ser positivo")
        elif self.kind == "complex":
            if not _is_num(d.get("re")) or not _is_num(d.get("im")) or not _is_num(d.get("tolerance", 0)):
                raise ValueError(f"Paso {self.ref}: «re», «im» y «tolerance» numéricos")
        elif self.kind == "order":
            items = d.get("items")
            if not isinstance(items, list) or not 2 <= len(items) <= 10 or not all(isinstance(i, str) and i for i in items):
                raise ValueError(f"Paso {self.ref}: «items» necesita de 2 a 10 textos")
            if len(set(items)) != len(items):
                raise ValueError(f"Paso {self.ref}: «items» no puede repetir textos")
        elif self.kind == "param":
            _check_param(self.ref, d, self.prompt)
        elif self.kind == "match":
            pairs = d.get("pairs")
            ok = isinstance(pairs, list) and 3 <= len(pairs) <= 6 and all(
                isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) and y.strip() for y in x) for x in pairs
            )
            if not ok:
                raise ValueError(f"Paso {self.ref}: «pairs» necesita de 3 a 6 parejas [izquierda, derecha]")
            if len({x[0] for x in pairs}) != len(pairs) or len({x[1] for x in pairs}) != len(pairs):
                raise ValueError(f"Paso {self.ref}: las parejas no pueden repetir textos")
        return self


def _check_param(ref: str, d: dict, prompt: str) -> None:
    vars_ = d.get("vars")
    if not isinstance(vars_, dict) or not 1 <= len(vars_) <= 8:
        raise ValueError(f"Paso {ref}: «vars» necesita de 1 a 8 variables")
    for name, spec in vars_.items():
        if not _VAR_RE.match(name) or not isinstance(spec, dict):
            raise ValueError(f"Paso {ref}: variable no válida «{name}»")
        lo, hi = spec.get("min"), spec.get("max")
        if not isinstance(lo, int) or not isinstance(hi, int) or isinstance(lo, bool) or lo > hi or hi - lo > 1000:
            raise ValueError(f"Paso {ref}: «{name}» necesita min/max enteros (rango ≤ 1000)")
    show = d.get("show", {})
    if not isinstance(show, dict) or not all(_VAR_RE.match(k) for k in show):
        raise ValueError(f"Paso {ref}: «show» no válido")
    ans = d.get("answer")
    if not isinstance(ans, dict) or ans.get("kind") not in ("numeric", "complex"):
        raise ValueError(f"Paso {ref}: «answer.kind» debe ser numeric o complex")
    exprs = [ans.get("value")] if ans["kind"] == "numeric" else [ans.get("re"), ans.get("im")]
    if not all(isinstance(e, str) and e.strip() for e in exprs):
        raise ValueError(f"Paso {ref}: faltan las expresiones de la respuesta")
    # Las llaves que no son variables se dejan tal cual: son LaTeX (\frac{z_1}{z_2}).
    if not set(_PLACEHOLDER_RE.findall(prompt)) & (set(vars_) | set(show)):
        raise ValueError(f"Paso {ref}: el enunciado no usa ninguna variable: no cambiaría de una vez a otra")
    # Tiene que poder instanciarse: probamos varias tiradas.
    rng = random.Random(ref)
    ok = 0
    last_err = ""
    for _ in range(PARAM_CHECK_SAMPLES):
        try:
            instantiate_param(d, rng)
            ok += 1
        except safe_math.MathError as exc:
            last_err = str(exc)
    if ok < PARAM_CHECK_SAMPLES // 2:
        raise ValueError(f"Paso {ref}: la plantilla falla demasiado al generar números ({last_err})")


def _fmt_num(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.4g}"


def _fmt_cx(re_: float, im_: float) -> str:
    if abs(im_) < 1e-12:
        return _fmt_num(re_)
    im_abs = abs(im_)
    im_txt = "" if abs(im_abs - 1) < 1e-12 else _fmt_num(im_abs)
    if abs(re_) < 1e-12:
        return f"{'-' if im_ < 0 else ''}{im_txt}i"
    return f"{_fmt_num(re_)} {'-' if im_ < 0 else '+'} {im_txt}i"


def instantiate_param(d: dict, rng: random.Random, values: Optional[dict] = None) -> tuple[dict, dict, dict]:
    """(valores de las variables, textos para el enunciado, solución {re, im} o {value})."""
    if values is None:
        values = {}
        for name, spec in d["vars"].items():
            pool = [v for v in range(spec["min"], spec["max"] + 1) if not (spec.get("nonzero") and v == 0)]
            if not pool:
                raise safe_math.MathError(f"Sin valores posibles para {name}")
            values[name] = rng.choice(pool)
    texts = {k: _fmt_num(v) for k, v in values.items()}
    env = dict(values)
    for key, spec in (d.get("show") or {}).items():
        if isinstance(spec, dict) and "cx" in spec:
            a, b = (safe_math.evaluate(str(x), env) for x in spec["cx"])
            texts[key] = _fmt_cx(a, b)
        elif isinstance(spec, dict) and "expr" in spec:
            v = safe_math.evaluate(str(spec["expr"]), env)
            env[key] = v
            texts[key] = _fmt_num(v)
        else:
            raise safe_math.MathError(f"«show.{key}» no válido")
    ans = d["answer"]
    if ans["kind"] == "numeric":
        sol = {"value": safe_math.evaluate(ans["value"], env)}
    else:
        sol = {"re": safe_math.evaluate(ans["re"], env), "im": safe_math.evaluate(ans["im"], env)}
    return values, texts, sol


def render(text: str, texts: dict) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: texts.get(m.group(1), m.group(0)), text)


def verify_issue(kind: str, d: dict) -> Optional[str]:
    """Si el paso trae expresiones de verificación, comprueba que dan la respuesta guardada."""
    try:
        if kind == "numeric" and d.get("verify"):
            v = safe_math.evaluate(str(d["verify"]))
            if not _close(v, float(d["answer"]), max(float(d.get("tolerance", 0)), 1e-6), d.get("period")):
                return f"La verificación da {v:.6g}, no {d['answer']}"
        if kind == "complex" and d.get("verify_re") and d.get("verify_im"):
            a, b = safe_math.evaluate(str(d["verify_re"])), safe_math.evaluate(str(d["verify_im"]))
            tol = max(float(d.get("tolerance", 0)), 1e-6)
            if not (_close(a, float(d["re"]), tol) and _close(b, float(d["im"]), tol)):
                return f"La verificación da {_fmt_cx(a, b)}, no {_fmt_cx(float(d['re']), float(d['im']))}"
    except (safe_math.MathError, TypeError, ValueError) as exc:
        return f"No se pudo verificar: {exc}"
    return None


# ---------- Instancias firmadas (param) ----------

def _secret(db: Session) -> bytes:
    row = db.get(models.Setting, "_learn_secret")
    if row is None:
        row = models.Setting(key="_learn_secret", value=secrets.token_hex(32))
        db.add(row)
        db.commit()
    return str(row.value).encode()


def sign_instance(db: Session, step_id: int, values: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"s": step_id, "v": values}, separators=(",", ":")).encode()).decode()
    sig = hmac.new(_secret(db), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def read_instance(db: Session, step_id: int, token: str) -> Optional[dict]:
    try:
        payload, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    good = hmac.new(_secret(db), payload.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, good):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        return None
    return data.get("v") if data.get("s") == step_id and isinstance(data.get("v"), dict) else None


class LessonIn(BaseModel):
    ref: Ref
    title: str = Field(min_length=1, max_length=200)
    theory_url: UrlStr = ""
    steps: list[StepIn] = Field(min_length=1, max_length=60)


class UnitIn(BaseModel):
    ref: Ref
    source: Optional[Ref] = None
    title: str = Field(min_length=1, max_length=200)
    # Módulo del plan docente de la asignatura ("" = sin asignar).
    module: str = Field(default="", max_length=64)
    lessons: list[LessonIn] = Field(min_length=1, max_length=40)


class CourseIn(BaseModel):
    format: Literal["campus-pilot-course"]
    format_version: Literal[1]
    slug: Ref
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    source_note: str = Field(default="", max_length=2000)
    subject_code: str = Field(default="", max_length=32)
    subject_name: str = Field(default="", max_length=200)
    units: list[UnitIn] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _unique(self):
        seen: set[str] = set()
        units_seen: set[tuple[str, str]] = set()
        for u in self.units:
            if (u.source or "", u.ref) in units_seen:
                raise ValueError(f"Unidad repetida: {u.ref}")
            units_seen.add((u.source or "", u.ref))
            for lesson in u.lessons:
                key = f"{u.source or ''}:{u.ref}/{lesson.ref}"
                if key in seen:
                    raise ValueError(f"Lección repetida: {key}")
                seen.add(key)
                refs = [s.ref for s in lesson.steps]
                if len(set(refs)) != len(refs):
                    raise ValueError(f"Lección {key}: pasos con el mismo ref")
        return self


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def describe_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first.get("loc", ()))
    msg = str(first.get("msg", "")).replace("Value error, ", "")
    return f"{where}: {msg}" if where else msg


def load_course(data: bytes) -> CourseIn:
    if len(data) > MAX_COURSE_BYTES:
        raise ValueError("El curso supera los 2 MB")
    try:
        raw = json.loads(data)
    except ValueError:
        raise ValueError("JSON no válido")
    if not isinstance(raw, dict):
        raise ValueError("El curso debe ser un objeto JSON")
    return CourseIn.model_validate(raw)


# ---------- Importar ----------

def _find_subject(db: Session, code: str, name: str) -> Optional[models.Subject]:
    q = db.query(models.Subject)
    if code:
        s = q.filter(models.Subject.code == code).order_by(models.Subject.id).first()
        if s:
            return s
    if name:
        return q.filter(models.Subject.name == name).order_by(models.Subject.id).first()
    return None


def course_for_subject(db: Session, subject: models.Subject) -> models.Course:
    """El curso de la asignatura; se crea vacío si aún no tiene."""
    course = db.query(models.Course).filter_by(subject_id=subject.id).first()
    if course is None:
        course = models.Course(slug=f"asig-{subject.id}", subject_id=subject.id, title=subject.name, description="", source_note="")
        db.add(course)
        db.flush()
    return course


def import_course(db: Session, course_in: CourseIn, subject: Optional[models.Subject] = None) -> models.Course:
    """Suma las unidades del JSON al curso de su asignatura. Reimportar la misma fuente
    reemplaza solo sus unidades (por `source`); las de otras fuentes se quedan."""
    subject = subject or _find_subject(db, course_in.subject_code, course_in.subject_name)
    if subject is None:
        raise ValueError("Elige la asignatura de este curso: cada curso pertenece a una asignatura")
    course = course_for_subject(db, subject)
    course.title = subject.name
    if course_in.description and not course.description:
        course.description = course_in.description
    if course_in.source_note and course_in.source_note not in course.source_note:
        course.source_note = "\n".join(x for x in (course.source_note, course_in.source_note) if x)[:2000]
    db.flush()

    def source_of(u_in: UnitIn) -> str:
        return u_in.source or course_in.slug

    sources = {source_of(u) for u in course_in.units}
    others = [u for u in course.units if u.source not in sources]
    first_slot = next((i for i, u in enumerate(course.units) if u.source in sources), len(others))
    first_slot = min(first_slot, len(others))
    units = {(u.source, u.ref): u for u in course.units if u.source in sources}
    keep_units = set()
    imported: list[models.CourseUnit] = []
    for u_in in course_in.units:
        unit = units.get((source_of(u_in), u_in.ref))
        if unit is None:
            unit = models.CourseUnit(course_id=course.id, ref=u_in.ref, source=source_of(u_in), title=u_in.title)
            db.add(unit)
            db.flush()
        unit.title = u_in.title
        if u_in.module:
            unit.module_ref = u_in.module
        imported.append(unit)
        keep_units.add(unit.id)

        lessons = {lesson.ref: lesson for lesson in unit.lessons}
        keep_lessons = set()
        for lpos, l_in in enumerate(u_in.lessons):
            lesson = lessons.get(l_in.ref)
            if lesson is None:
                lesson = models.Lesson(unit_id=unit.id, ref=l_in.ref, title=l_in.title, theory="")
                db.add(lesson)
                db.flush()
            lesson.title, lesson.position = l_in.title, lpos
            if l_in.theory_url and not lesson.theory_url:
                lesson.theory_url = l_in.theory_url
            keep_lessons.add(lesson.id)

            steps = {s.ref: s for s in lesson.steps}
            keep_steps = set()
            # La teoría añadida después (Generar → teoría, refs teoria-*) se queda delante si lo
            # que se reimporta no trae teoría propia para esta lección.
            kept_theory = [] if any(s.kind == "info" for s in l_in.steps) else [
                s for s in lesson.steps if s.kind == "info" and s.ref.startswith("teoria-")
            ]
            for tpos, step in enumerate(sorted(kept_theory, key=lambda s: s.position)):
                step.position = tpos
                keep_steps.add(step.id)
            for spos, s_in in enumerate(l_in.steps, start=len(kept_theory)):
                step = steps.get(s_in.ref)
                if step is None:
                    step = models.LessonStep(lesson_id=lesson.id, ref=s_in.ref, kind=s_in.kind, prompt=s_in.prompt)
                    db.add(step)
                    db.flush()
                step.position, step.kind, step.prompt = spos, s_in.kind, s_in.prompt
                step.data, step.explanation, step.source = s_in.data, s_in.explanation, s_in.source
                step.hints, step.concepts, step.worked = s_in.hints, s_in.concepts, s_in.worked
                step.objectives = s_in.objectives
                keep_steps.add(step.id)
            for step in list(lesson.steps):
                if step.id not in keep_steps:
                    db.delete(step)
        for lesson in list(unit.lessons):
            if lesson.id not in keep_lessons:
                db.delete(lesson)
    for unit in list(course.units):
        if unit.source in sources and unit.id not in keep_units:
            db.delete(unit)
    for pos, unit in enumerate(others[:first_slot] + imported + others[first_slot:]):
        unit.position = pos
    db.commit()
    db.refresh(course)
    return course


def export_course(course: models.Course) -> dict:
    """El curso sin progreso ni teoría personal."""
    return {
        "format": COURSE_FORMAT,
        "format_version": 1,
        "slug": course.slug,
        "title": course.title,
        "description": course.description,
        "source_note": course.source_note,
        "subject_code": course.subject.code if course.subject else "",
        "subject_name": course.subject.name if course.subject else "",
        "units": [
            {
                "ref": u.ref,
                "source": u.source or None,
                "title": u.title,
                "module": u.module_ref or "",
                "lessons": [
                    {
                        "ref": lesson.ref,
                        "title": lesson.title,
                        "steps": [
                            {
                                "ref": s.ref, "kind": s.kind, "prompt": s.prompt,
                                # La cita apunta a la biblioteca de esta instalación: fuera no vale.
                                "data": {k: v for k, v in (s.data or {}).items() if k != "cite"}, "explanation": s.explanation,
                                "source": s.source, "hints": s.hints or [], "concepts": s.concepts or [], "worked": s.worked or "",
                                "objectives": s.objectives or [],
                            }
                            for s in lesson.steps
                        ],
                    }
                    for lesson in u.lessons
                ],
            }
            for u in course.units
        ],
    }


# ---------- Jugar ----------

def public_step(db: Session, step: models.LessonStep, rng: Optional[random.Random] = None, show_worked: bool = False) -> dict:
    """Lo que ve la app antes de responder: nunca la solución."""
    rng = rng or random.Random()
    out: dict[str, Any] = {
        "id": step.id,
        "kind": step.kind,
        "prompt": step.prompt,
        "source": step.source,
        "hints": step.hints or [],
        "concepts": step.concepts or [],
    }
    if show_worked and step.worked:
        out["worked"] = step.worked
    d = step.data or {}
    if step.kind == "choice":
        out["options"] = d.get("options", [])
        out["multiple"] = len(d.get("correct", [])) > 1
    elif step.kind == "order":
        items = list(d.get("items", []))
        shuffled = items[:]
        for _ in range(10):
            rng.shuffle(shuffled)
            if shuffled != items:
                break
        out["items"] = shuffled
    elif step.kind == "numeric":
        out["unit"] = d.get("unit", "")
    elif step.kind == "match":
        pairs = d.get("pairs", [])
        right = [p[1] for p in pairs]
        shuffled = right[:]
        for _ in range(10):
            rng.shuffle(shuffled)
            if shuffled != right:
                break
        out["left"] = [p[0] for p in pairs]
        out["right"] = shuffled
    elif step.kind == "param":
        values, texts, _ = instantiate_param(d, rng)
        out["prompt"] = render(step.prompt, texts)
        out["answer_kind"] = d["answer"]["kind"]
        out["unit"] = d["answer"].get("unit", "")
        out["token"] = sign_instance(db, step.id, values)
    if step.kind == "info":
        out["explanation"] = step.explanation
        if (step.data or {}).get("figure"):
            out["figure"] = step.data["figure"]
        cite = (step.data or {}).get("cite")
        if cite:
            # Solo si el material sigue en la biblioteca y tiene su PDF (un .md no se abre por página).
            m = db.get(models.Material, cite.get("material_id"))
            if m is not None and m.has_file:
                out["cite"] = cite
    return out


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            x = float(v.strip().replace(",", ".").replace("−", "-"))
            return x if math.isfinite(x) else None
        except ValueError:
            return None
    return None


def _close(x: float, target: float, tol: float, period: Optional[float] = None) -> bool:
    diff = x - target
    if period:
        diff = (diff + period / 2) % period - period / 2
    return abs(diff) <= tol + 1e-9


def check(step: models.LessonStep, response: Any, values: Optional[dict] = None) -> tuple[bool, str, str]:
    """(¿correcta?, solución en texto, explicación ya adaptada a la instancia)."""
    d = step.data or {}
    expl = step.explanation
    if step.kind == "info":
        return True, "", expl
    if step.kind == "choice":
        opts, correct = d.get("options", []), sorted(d.get("correct", []))
        chosen = sorted(set(response)) if isinstance(response, list) and all(isinstance(i, int) for i in response) else None
        return chosen == correct, " · ".join(opts[i] for i in correct), expl
    if step.kind == "truefalse":
        return response is d.get("answer"), "Verdadero" if d.get("answer") else "Falso", expl
    if step.kind == "numeric":
        x = _num(response)
        ans, tol, period = float(d["answer"]), float(d.get("tolerance", 0)), d.get("period")
        shown = f"{ans:g}{(' ' + d['unit']) if d.get('unit') else ''}"
        return x is not None and _close(x, ans, tol, period), shown, expl
    if step.kind == "complex":
        x, y = _cx_response(response)
        tol = float(d.get("tolerance", 0))
        a, b = float(d["re"]), float(d["im"])
        return x is not None and y is not None and _close(x, a, tol) and _close(y, b, tol), _fmt_cx(a, b), expl
    if step.kind == "order":
        items = d.get("items", [])
        return response == items, " → ".join(items), expl
    if step.kind == "match":
        pairs = d.get("pairs", [])
        ok = isinstance(response, list) and len(response) == len(pairs) and all(r == p[1] for r, p in zip(response, pairs))
        return ok, " · ".join(f"{a} ↔ {b}" for a, b in pairs), expl
    if step.kind == "param":
        if values is None:
            return False, "", expl
        _, texts, sol = instantiate_param(d, random.Random(), values)
        tol = float(d["answer"].get("tolerance", 0.001))
        if d["answer"]["kind"] == "numeric":
            x = _num(response)
            ok = x is not None and _close(x, sol["value"], tol, d["answer"].get("period"))
            shown = _fmt_num(sol["value"])
            texts = {**texts, "value": shown}
        else:
            x, y = _cx_response(response)
            ok = x is not None and y is not None and _close(x, sol["re"], tol) and _close(y, sol["im"], tol)
            shown = _fmt_cx(sol["re"], sol["im"])
            texts = {**texts, "re": _fmt_num(sol["re"]), "im": _fmt_num(sol["im"]), "result": shown}
        return ok, shown, render(expl, texts)
    return False, "", expl


def _cx_response(response: Any) -> tuple[Optional[float], Optional[float]]:
    if not isinstance(response, dict):
        return None, None
    return _num(response.get("re")), _num(response.get("im"))


def option_feedback(step: models.LessonStep, response: Any) -> list[str]:
    """Por qué fallan las opciones elegidas que no eran correctas."""
    d = step.data or {}
    fb, correct = d.get("option_feedback"), set(d.get("correct", []))
    if step.kind != "choice" or not isinstance(fb, list) or not isinstance(response, list):
        return []
    return [fb[i] for i in response if isinstance(i, int) and 0 <= i < len(fb) and i not in correct and fb[i]]


def record_answer(
    db: Session, step: models.LessonStep, ok: bool, first_try: bool, today: Optional[date] = None,
    confident: Optional[bool] = None, used_hint: bool = False, combo: int = 0,
) -> int:
    """Actualiza el repaso espaciado del paso y suma XP. Devuelve la XP ganada.

    Fallar con confianza alta es lo más valioso de detectar: el paso vuelve a repaso mañana
    y queda contado aparte para el mapa de dominio."""
    today = today or clock.today()
    if step.kind == "info":
        return 0
    if confident and not ok:
        step.confident_wrong += 1
    if ok:
        step.correct += 1
        if step.box:  # solo entra en repaso lo que alguna vez se falló
            step.box = min(5, step.box + 1)
            step.due_on = today + timedelta(days=LEITNER_DAYS[step.box])
    else:
        step.wrong += 1
        step.box = 1
        step.due_on = today + timedelta(days=LEITNER_DAYS[1])
    xp = (XP_FIRST_TRY if first_try and not used_hint else XP_RETRY) if ok else 0
    add_xp(db, xp, today=today)
    from . import game

    row = game.day(db, today)
    if ok:
        row.correct += 1
    row.best_combo = max(row.best_combo, combo)
    db.commit()
    return xp


def add_xp(db: Session, xp: int, lessons: int = 0, today: Optional[date] = None) -> None:
    if not xp and not lessons:
        return
    from . import game

    row = game.day(db, today)  # única forma de crear la fila del día (evita duplicados)
    row.xp += xp
    row.lessons += lessons


def streak(db: Session, today: Optional[date] = None) -> int:
    """Días seguidos con XP (o salvados con un protector). Hoy sin XP aún no rompe la racha."""
    from . import game

    return game.streak(db, today)
