"""Esquemas Pydantic: validación de toda entrada de la API (longitudes, rangos, enums, URLs)."""
from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from . import models

SubjectKind = Literal[models.SUBJECT_KINDS]  # type: ignore[valid-type]
SubjectStatus = Literal[models.SUBJECT_STATUSES]  # type: ignore[valid-type]
SubjectOffered = Literal[models.SUBJECT_OFFERED]  # type: ignore[valid-type]
TermSystem = Literal[models.TERM_SYSTEMS]  # type: ignore[valid-type]
# Periodo personal: año de inicio del curso + periodo (S1–S2, T1–T3, Q1–Q4 o A = anual).
PLAN_TERM_PATTERN = r"^\d{4}(S[12]|T[1-3]|Q[1-4]|A)$"
AiPolicy = Literal[models.AI_POLICIES]  # type: ignore[valid-type]
EvalModel = Literal[models.EVAL_MODELS]  # type: ignore[valid-type]
GroupRole = Literal[models.GROUP_ROLES]  # type: ignore[valid-type]
ActivityKind = Literal[models.ACTIVITY_KINDS]  # type: ignore[valid-type]
EventKind = Literal[models.EVENT_KINDS]  # type: ignore[valid-type]
SessionKind = Literal[models.SESSION_KINDS]  # type: ignore[valid-type]
ExpenseCategory = Literal[models.EXPENSE_CATEGORIES]  # type: ignore[valid-type]
GrantStatus = Literal[models.GRANT_STATUSES]  # type: ignore[valid-type]
ProcedureCategory = Literal[models.PROCEDURE_CATEGORIES]  # type: ignore[valid-type]
ProcedureStatus = Literal[models.PROCEDURE_STATUSES]  # type: ignore[valid-type]
PathKind = Literal[models.PATH_KINDS]  # type: ignore[valid-type]
PathStatus = Literal[models.PATH_STATUSES]  # type: ignore[valid-type]

ModuleId = Literal["semestre", "estudio", "aprender", "dinero", "trayectoria", "bandeja"]

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
# obsidian:// abre la nota en la bóveda local; nada de javascript:, data:, file:…
_ALLOWED_SCHEMES = ("https://", "http://", "obsidian://", "mailto:")


def check_url(value: str) -> str:
    value = (value or "").strip()
    if value and not value.lower().startswith(_ALLOWED_SCHEMES):
        raise ValueError("La URL debe empezar por https://, http://, obsidian:// o mailto:")
    return value


def check_time(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    if not _TIME_RE.match(value):
        raise ValueError("Hora con formato HH:MM")
    return value


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


UrlStr = Annotated[str, Field(max_length=500), AfterValidator(check_url)]
TimeStr = Annotated[Optional[str], AfterValidator(check_time)]
# En la escala de la carrera (0–10, 0–20, 0–100…): el máximo real se comprueba contra CareerConfig.
Grade = Annotated[Optional[float], Field(ge=0, le=100)]


# ---------- Ajustes ----------

class NotificationSettings(BaseModel):
    enabled: bool = False
    topic: str = Field(default="campus-pilot", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    hour: int = Field(default=8, ge=0, le=23)
    days_before: list[int] = Field(default_factory=lambda: [7, 3, 1, 0])

    @field_validator("days_before")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if len(v) > 10 or any(d < 0 or d > 60 for d in v):
            raise ValueError("Días de aviso entre 0 y 60 (máximo 10 valores)")
        return sorted(set(v), reverse=True)


class SettingsModel(BaseModel):
    modules: dict[ModuleId, bool] = Field(
        default_factory=lambda: {"semestre": True, "estudio": True, "aprender": True, "dinero": True, "trayectoria": True, "bandeja": True}
    )
    # Idioma de la interfaz (y del resumen de la bandeja).
    language: Literal["es", "en"] = "es"
    # Meta diaria de XP en Aprender.
    learn_daily_xp: int = Field(default=30, ge=5, le=1000)
    # Sonidos de acierto/fallo en Aprender.
    learn_sounds: bool = True
    default_price_per_credit: float = Field(default=0, ge=0, le=10000)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    # Semana "cargada" (▲): entregas de al menos tantas asignaturas distintas.
    heavy_week_subjects: int = Field(default=2, ge=2, le=10)
    obsidian_vault: str = Field(default="", max_length=120)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


# ---------- Carreras y semestres ----------

class TrackDef(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)


Label = Annotated[str, Field(min_length=1, max_length=40)]


class CareerLabels(BaseModel):
    """Cómo llama tu universidad a cada cosa (vacío = nombre genérico)."""

    subject_kinds: dict[SubjectKind, Label] = Field(default_factory=dict)
    activity_kinds: dict[ActivityKind, Label] = Field(default_factory=dict)
    ec: str = Field(default="", max_length=40)  # p. ej. "EC" / "Evaluación continua"
    pf: str = Field(default="", max_length=40)  # p. ej. "PF" / "Examen final"


class GradeLetter(BaseModel):
    """Una letra de la escala (A, B, C+…, o SB/NT/AP/SS): desde `min` (incluido); al
    apuntar la nota con la letra se guarda `value`."""

    label: str = Field(min_length=1, max_length=12)
    min: float = Field(ge=0, le=100)
    value: float = Field(ge=0, le=100)


class CareerConfig(BaseModel):
    grade_max: float = Field(default=10, gt=0, le=100)
    pass_mark: float = Field(default=5, ge=0, le=100)
    decimals: int = Field(default=2, ge=0, le=3)
    credit_label: str = Field(default="ECTS", min_length=1, max_length=20)
    term_system: TermSystem = "semesters"
    # Mes en que empieza el curso (9 = septiembre; 3 = marzo en el hemisferio sur…).
    year_start_month: int = Field(default=9, ge=1, le=12)
    labels: CareerLabels = Field(default_factory=CareerLabels)
    # Escala con letras (vacía = solo números). Se guarda de mayor a menor.
    letters: list[GradeLetter] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def _pass_in_scale(self):
        if self.pass_mark > self.grade_max:
            raise ValueError("El aprobado no puede ser mayor que la nota máxima")
        if self.letters:
            if len({x.label for x in self.letters}) != len(self.letters):
                raise ValueError("Las letras de la escala no se pueden repetir")
            for x in self.letters:
                if x.min > self.grade_max or x.value > self.grade_max:
                    raise ValueError(f"La letra {x.label} se sale de la escala (máximo {self.grade_max:g})")
            self.letters = sorted(self.letters, key=lambda x: -x.min)
            if self.letters[-1].min > 0:
                raise ValueError("La letra más baja tiene que empezar en 0")
        return self


def _check_requirements(v: dict[str, float]) -> dict[str, float]:
    for k, x in v.items():
        if k not in models.SUBJECT_KINDS:
            raise ValueError(f"Tipo de asignatura desconocido: {k}")
        if not 0 <= x <= 1000:
            raise ValueError("Los créditos exigidos van de 0 a 1000")
    return v


class CareerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    institution: str = Field(default="", max_length=200)
    ects_goal: int = Field(default=240, ge=1, le=1000)
    track: Optional[str] = Field(default=None, max_length=64)
    requirements: Annotated[dict[str, float], AfterValidator(_check_requirements)] = Field(default_factory=dict)
    config: CareerConfig = Field(default_factory=CareerConfig)
    archived: bool = False

    @field_validator("config", mode="before")
    @classmethod
    def _empty_config(cls, v):
        return v or {}


class CareerOut(ORM, CareerIn):
    id: int
    pack_slug: Optional[str]
    tracks: list[TrackDef] = []


class TermIn(BaseModel):
    career_id: int
    label: str = Field(min_length=1, max_length=40)
    start_date: date
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def _range(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("El semestre no puede acabar antes de empezar")
        return self


class TermOut(ORM, TermIn):
    id: int


# ---------- Asignaturas y evaluación ----------

class LinkItem(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    url: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(check_url)]



class EvalConfig(BaseModel):
    # En la escala de la carrera; se comprueban contra su nota máxima al guardar.
    ec_pass: float = Field(default=5, ge=0, le=100)
    pf_min: float = Field(default=4, ge=0, le=100)
    no_show_grade: float = Field(default=3, ge=0, le=100)


class SubjectIn(BaseModel):
    career_id: int
    term_id: Optional[int] = None
    code: str = Field(default="", max_length=32)
    name: str = Field(min_length=1, max_length=200)
    ects: float = Field(default=6, gt=0, le=60)
    kind: SubjectKind = "obligatoria"
    plan_semester: Optional[int] = Field(default=None, ge=1, le=20)
    offered: Optional[SubjectOffered] = None
    planned_term: Optional[str] = Field(default=None, pattern=PLAN_TERM_PATTERN)
    track: Optional[str] = Field(default=None, max_length=64)
    status: SubjectStatus = "pending"
    final_grade: Grade = None
    attempt: int = Field(default=1, ge=1, le=10)
    price_per_credit: Optional[float] = Field(default=None, ge=0, le=10000)
    weekly_hours: Optional[float] = Field(default=None, ge=0, le=80)
    ai_policy: AiPolicy = "unknown"
    ai_policy_note: str = Field(default="", max_length=2000)
    eval_model: EvalModel = "weighted"
    eval_config: EvalConfig = Field(default_factory=EvalConfig)
    notes: str = Field(default="", max_length=10000)
    links: list[LinkItem] = Field(default_factory=list, max_length=30)


class SubjectOut(ORM, SubjectIn):
    id: int
    pack_ref: Optional[str]


class EvalGroupIn(BaseModel):
    subject_id: int
    name: str = Field(min_length=1, max_length=80)
    weight: float = Field(ge=0, le=100)
    min_grade: Grade = None
    role: Optional[GroupRole] = None
    position: int = Field(default=0, ge=0, le=100)


class EvalGroupOut(ORM, EvalGroupIn):
    id: int


class ActivityIn(BaseModel):
    subject_id: int
    group_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=160)
    kind: ActivityKind = "other"
    weight: float = Field(default=1, ge=0, le=100)
    grade: Optional[float] = Field(default=None, ge=0, le=100)
    max_grade: float = Field(default=10, gt=0, le=100)
    due_date: Optional[date] = None
    due_time: TimeStr = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    evaluable: bool = True
    done: bool = False
    kept_from_previous: bool = False
    estimated_hours: Optional[float] = Field(default=None, ge=0, le=500)
    notes: str = Field(default="", max_length=5000)


    @model_validator(mode="after")
    def _checks(self):
        if self.grade is not None and self.grade > self.max_grade:
            raise ValueError("La nota no puede superar la nota máxima")
        if self.window_start and self.window_end and self.window_end < self.window_start:
            raise ValueError("La ventana no puede acabar antes de empezar")
        return self


class ActivityOut(ORM, ActivityIn):
    id: int
    pack_ref: Optional[str]


class SimulateIn(BaseModel):
    """Notas hipotéticas por actividad (id → nota en la escala de la carrera) y nota objetivo
    (vacía = el aprobado). El máximo se comprueba contra la escala de la carrera."""

    hypothetical: dict[int, float] = Field(default_factory=dict)
    target: Optional[float] = Field(default=None, ge=0, le=100)

    @field_validator("hypothetical")
    @classmethod
    def _range(cls, v: dict[int, float]) -> dict[int, float]:
        if any(g < 0 or g > 100 for g in v.values()):
            raise ValueError("Nota hipotética fuera de rango")
        return v


# ---------- Agenda ----------

class EventIn(BaseModel):
    subject_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=200)
    kind: EventKind = "other"
    date: date
    end_date: Optional[date] = None
    start_time: TimeStr = None
    end_time: TimeStr = None
    url: UrlStr = ""
    notes: str = Field(default="", max_length=5000)
    done: bool = False


    @model_validator(mode="after")
    def _range(self):
        if self.end_date and self.end_date < self.date:
            raise ValueError("El evento no puede acabar antes de empezar")
        return self


class EventOut(ORM, EventIn):
    id: int


class HabitIn(BaseModel):
    subject_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=200)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    active: bool = True

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("Días de la semana entre 0 (lunes) y 6 (domingo)")
        return sorted(set(v))


class HabitOut(ORM, HabitIn):
    id: int


# ---------- Estudio ----------

class SessionIn(BaseModel):
    subject_id: Optional[int] = None
    date: date
    minutes: int = Field(ge=1, le=24 * 60)
    kind: SessionKind = "manual"
    note: str = Field(default="", max_length=300)


class SessionOut(ORM, SessionIn):
    id: int


class CardIn(BaseModel):
    subject_id: Optional[int] = None
    deck: str = Field(default="", max_length=160)
    question: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="", max_length=300)


class CardOut(ORM, CardIn):
    id: int
    box: int
    due_on: date
    last_reviewed: Optional[date]
    reviews: int
    lapses: int


class CardImportIn(BaseModel):
    subject_id: Optional[int] = None
    deck: str = Field(default="", max_length=160)
    source: str = Field(default="", max_length=300)
    markdown: str = Field(min_length=1, max_length=200_000)


class CardReviewIn(BaseModel):
    knew: bool


# ---------- Dinero y trámites ----------

class ExpenseIn(BaseModel):
    subject_id: Optional[int] = None
    term_id: Optional[int] = None
    date: date
    category: ExpenseCategory = "other"
    description: str = Field(default="", max_length=200)
    amount: float = Field(ge=-1_000_000, le=1_000_000)


class ExpenseOut(ORM, ExpenseIn):
    id: int


class GrantIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="", max_length=200)
    status: GrantStatus = "idea"
    amount: Optional[float] = Field(default=None, ge=0, le=1_000_000)
    deadline: Optional[date] = None
    decision_date: Optional[date] = None
    min_average: Optional[float] = Field(default=None, ge=0, le=100)
    income_threshold: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    url: UrlStr = ""
    notes: str = Field(default="", max_length=5000)



class GrantOut(ORM, GrantIn):
    id: int


class ProcedureIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: ProcedureCategory = "admin"
    status: ProcedureStatus = "todo"
    window_start: Optional[date] = None
    deadline: Optional[date] = None
    url: UrlStr = ""
    notes: str = Field(default="", max_length=5000)



class ProcedureOut(ORM, ProcedureIn):
    id: int


# ---------- Trayectoria ----------

class PathItemIn(BaseModel):
    kind: PathKind = "course"
    title: str = Field(min_length=1, max_length=200)
    organization: str = Field(default="", max_length=200)
    status: PathStatus = "planned"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    hours: Optional[float] = Field(default=None, ge=0, le=100_000)
    url: UrlStr = ""
    skills: list[str] = Field(default_factory=list, max_length=40)
    subject_id: Optional[int] = None
    notes: str = Field(default="", max_length=10000)


    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for s in v:
            s = s.strip()
            if not s:
                continue
            if len(s) > 60:
                raise ValueError("Cada competencia, 60 caracteres como máximo")
            if s.lower() not in (x.lower() for x in out):
                out.append(s)
        return out


class PathItemOut(ORM, PathItemIn):
    id: int
