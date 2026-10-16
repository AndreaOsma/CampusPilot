"""Modelo de datos de Campus Pilot.

Núcleo genérico (vale para cualquier carrera): carreras, semestres, asignaturas con su
esquema de evaluación, agenda (actividades con fecha, eventos, hábitos), estudio (sesiones
y tarjetas de repaso), dinero y trámites, y trayectoria (cursos, proyectos, prácticas…).

Lo específico de unos estudios concretos (plan de estudios, reglas de evaluación,
calendario de un semestre) no vive en el código: llega instalando un *módulo de estudios*
(`packs/*.json`, ver packs.py). Las filas creadas por un módulo llevan `pack_ref` para
poder actualizarlas sin duplicar al reinstalarlo.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base

SUBJECT_KINDS = ("basica", "obligatoria", "optativa", "mencion", "practicas", "tfg", "otra")
# Periodo en que la asignatura tiene docencia: todos ("both") o solo uno: semestre s1/s2,
# trimestre t1–t3 o cuatrimestre/cuarto q1–q4, según el calendario de la carrera.
SUBJECT_OFFERED = ("both", "s1", "s2", "t1", "t2", "t3", "q1", "q2", "q3", "q4")
TERM_SYSTEMS = ("semesters", "trimesters", "quarters", "annual")
SUBJECT_STATUSES = ("pending", "enrolled", "passed", "failed", "convalidated", "dropped")
# Política de IA generativa en las actividades evaluables de la asignatura.
AI_POLICIES = ("unknown", "allowed", "limited", "forbidden")
EVAL_MODELS = ("weighted", "ec_pf")
GROUP_ROLES = ("ec", "pf")
ACTIVITY_KINDS = ("pec", "pr", "quiz", "video", "exam", "lab", "project", "other")
EVENT_KINDS = ("session", "class", "exam", "admin", "personal", "other")
SESSION_KINDS = ("focus", "manual")
EXPENSE_CATEGORIES = ("tuition", "materials", "books", "exam", "transport", "software", "other")
GRANT_STATUSES = ("idea", "preparing", "applied", "granted", "rejected", "paid")
PROCEDURE_CATEGORIES = ("enrollment", "recognition", "scholarship", "internship", "tfg", "admin", "other")
PROCEDURE_STATUSES = ("todo", "doing", "waiting", "done")
PATH_KINDS = ("course", "certification", "project", "internship", "job", "language", "volunteering", "award", "other")
PATH_STATUSES = ("idea", "planned", "in_progress", "done", "dropped")
INBOX_STATUSES = ("new", "read", "archived")
INBOX_KINDS = ("announcement", "grade", "video_check", "forum", "deadline", "admin", "other")
INBOX_CLASSIFY = ("pending", "running", "done", "error", "off")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(64), primary_key=True)
    value = Column(JSON, nullable=True)


class InstalledPack(Base):
    __tablename__ = "installed_packs"

    slug = Column(String(64), primary_key=True)
    name = Column(String(200), nullable=False)
    version = Column(String(32), nullable=False, default="1")
    installed_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    # Copia del JSON instalado: permite reaplicar un semestre sin volver a subir el archivo.
    content = Column(JSON, nullable=False)


class Career(Base):
    __tablename__ = "careers"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    institution = Column(String(200), nullable=False, default="")
    ects_goal = Column(Integer, nullable=False, default=240)
    pack_slug = Column(String(64), nullable=True)
    # Mención/itinerario elegido (id del track del módulo), si aplica.
    track = Column(String(64), nullable=True)
    # ECTS exigidos por tipo de asignatura ({"basica": 78, ...}); vacío = sin desglose.
    requirements = Column(JSON, nullable=False, default=dict)
    tracks = Column(JSON, nullable=False, default=list)
    # Reglas de la universidad: escala de notas, aprobado, créditos, calendario y nombres
    # (ver schemas.CareerConfig). Vacío = 0–10, aprobado 5, ECTS, semestres.
    config = Column(JSON, nullable=False, default=dict)
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)

    terms = relationship("Term", back_populates="career", cascade="all, delete-orphan", order_by="Term.start_date")
    subjects = relationship("Subject", back_populates="career", cascade="all, delete-orphan")


class Term(Base):
    __tablename__ = "terms"

    id = Column(Integer, primary_key=True)
    career_id = Column(Integer, ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(40), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    pack_ref = Column(String(160), nullable=True)

    career = relationship("Career", back_populates="terms")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    career_id = Column(Integer, ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    term_id = Column(Integer, ForeignKey("terms.id", ondelete="SET NULL"), nullable=True)
    pack_ref = Column(String(160), nullable=True)
    code = Column(String(32), nullable=False, default="")
    name = Column(String(200), nullable=False)
    ects = Column(Float, nullable=False, default=6)
    kind = Column(String(16), nullable=False, default="obligatoria")
    plan_semester = Column(Integer, nullable=True)
    offered = Column(String(4), nullable=True)
    # Semestre en que quien estudia planea cursarla ("2027S1"). Es suyo: los módulos de
    # estudios nunca lo tocan (plan_semester es solo la recomendación de la universidad).
    planned_term = Column(String(10), nullable=True)
    track = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="pending")
    # Nota oficial (acta / convalidación). Si está, manda sobre la calculada.
    final_grade = Column(Float, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    price_per_credit = Column(Float, nullable=True)
    weekly_hours = Column(Float, nullable=True)
    ai_policy = Column(String(16), nullable=False, default="unknown")
    ai_policy_note = Column(Text, nullable=False, default="")
    eval_model = Column(String(16), nullable=False, default="weighted")
    # Parámetros del modelo ec_pf: {"ec_pass": 5, "pf_min": 4, "no_show_grade": 3}.
    eval_config = Column(JSON, nullable=False, default=dict)
    notes = Column(Text, nullable=False, default="")
    links = Column(JSON, nullable=False, default=list)
    # Plan docente importado (ver syllabus.py): objetivos de aprendizaje, temario por módulos y
    # recursos, tal como los marca la universidad. {} si no hay.
    syllabus = Column(JSON, nullable=False, default=dict)

    career = relationship("Career", back_populates="subjects")
    term = relationship("Term")
    groups = relationship("EvalGroup", back_populates="subject", cascade="all, delete-orphan", order_by="EvalGroup.position")
    activities = relationship("Activity", back_populates="subject", cascade="all, delete-orphan")


class EvalGroup(Base):
    __tablename__ = "eval_groups"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(80), nullable=False)
    # Peso en la nota final, en %.
    weight = Column(Float, nullable=False, default=0)
    min_grade = Column(Float, nullable=True)
    role = Column(String(4), nullable=True)
    position = Column(Integer, nullable=False, default=0)

    subject = relationship("Subject", back_populates="groups")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("eval_groups.id", ondelete="SET NULL"), nullable=True)
    pack_ref = Column(String(160), nullable=True)
    name = Column(String(160), nullable=False)
    kind = Column(String(16), nullable=False, default="other")
    # Peso relativo dentro de su grupo.
    weight = Column(Float, nullable=False, default=1)
    grade = Column(Float, nullable=True)
    max_grade = Column(Float, nullable=False, default=10)
    due_date = Column(Date, nullable=True)
    due_time = Column(String(5), nullable=True)
    window_start = Column(Date, nullable=True)
    window_end = Column(Date, nullable=True)
    evaluable = Column(Boolean, nullable=False, default=True)
    done = Column(Boolean, nullable=False, default=False)
    # Nota conservada de una matrícula anterior (repetidores).
    kept_from_previous = Column(Boolean, nullable=False, default=False)
    estimated_hours = Column(Float, nullable=True)
    notes = Column(Text, nullable=False, default="")

    subject = relationship("Subject", back_populates="activities")
    group = relationship("EvalGroup")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    pack_ref = Column(String(160), nullable=True)
    title = Column(String(200), nullable=False)
    kind = Column(String(16), nullable=False, default="other")
    date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    start_time = Column(String(5), nullable=True)
    end_time = Column(String(5), nullable=True)
    url = Column(String(500), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    done = Column(Boolean, nullable=False, default=False)

    subject = relationship("Subject")


class Habit(Base):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    pack_ref = Column(String(160), nullable=True)
    title = Column(String(200), nullable=False)
    # Días de la semana en que toca (0 = lunes … 6 = domingo).
    weekdays = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True)

    subject = relationship("Subject")


class HabitCheck(Base):
    __tablename__ = "habit_checks"
    __table_args__ = (UniqueConstraint("habit_id", "date", name="uq_habit_check_day"),)

    id = Column(Integer, primary_key=True)
    habit_id = Column(Integer, ForeignKey("habits.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    minutes = Column(Integer, nullable=False)
    kind = Column(String(8), nullable=False, default="manual")
    note = Column(String(300), nullable=False, default="")


class ReviewCard(Base):
    """Pregunta de repaso (solo la pregunta: la respuesta la das tú, sin mirar)."""

    __tablename__ = "review_cards"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    deck = Column(String(160), nullable=False, default="")
    question = Column(Text, nullable=False)
    source = Column(String(300), nullable=False, default="")
    box = Column(Integer, nullable=False, default=1)
    due_on = Column(Date, nullable=False)
    last_reviewed = Column(Date, nullable=True)
    reviews = Column(Integer, nullable=False, default=0)
    lapses = Column(Integer, nullable=False, default=0)


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    term_id = Column(Integer, ForeignKey("terms.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    category = Column(String(16), nullable=False, default="other")
    description = Column(String(200), nullable=False, default="")
    amount = Column(Float, nullable=False)


class Grant(Base):
    __tablename__ = "grants"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    provider = Column(String(200), nullable=False, default="")
    status = Column(String(16), nullable=False, default="idea")
    amount = Column(Float, nullable=True)
    deadline = Column(Date, nullable=True)
    decision_date = Column(Date, nullable=True)
    min_average = Column(Float, nullable=True)
    income_threshold = Column(Float, nullable=True)
    url = Column(String(500), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")


class Procedure(Base):
    __tablename__ = "procedures"

    id = Column(Integer, primary_key=True)
    pack_ref = Column(String(160), nullable=True)
    title = Column(String(200), nullable=False)
    category = Column(String(16), nullable=False, default="admin")
    status = Column(String(16), nullable=False, default="todo")
    window_start = Column(Date, nullable=True)
    deadline = Column(Date, nullable=True)
    url = Column(String(500), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")


class PathItem(Base):
    """Trayectoria: todo lo que suma fuera (o además) del expediente."""

    __tablename__ = "path_items"

    id = Column(Integer, primary_key=True)
    kind = Column(String(16), nullable=False, default="course")
    title = Column(String(200), nullable=False)
    organization = Column(String(200), nullable=False, default="")
    status = Column(String(16), nullable=False, default="planned")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    hours = Column(Float, nullable=True)
    url = Column(String(500), nullable=False, default="")
    skills = Column(JSON, nullable=False, default=list)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=False, default="")


# ---------- Aprender (lecciones interactivas) ----------

STEP_KINDS = ("info", "choice", "truefalse", "numeric", "complex", "order", "param", "match")


class Course(Base):
    """Curso interactivo de una asignatura: uno por asignatura, al que se van sumando unidades
    (de un JSON importado o del generador). Su contenido es privado: no vive en el código ni en
    los módulos de estudios públicos."""

    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    slug = Column(String(64), nullable=False, unique=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, unique=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    source_note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=_now)

    units = relationship("CourseUnit", back_populates="course", cascade="all, delete-orphan", order_by="CourseUnit.position")
    subject = relationship("Subject")


class CourseUnit(Base):
    __tablename__ = "course_units"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    ref = Column(String(64), nullable=False)
    # De dónde vino la unidad (slug del JSON importado o "g<id>" del generador): reimportar
    # esa misma fuente solo reemplaza sus unidades, nunca las del resto.
    source = Column(String(64), nullable=False, default="")
    title = Column(String(200), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    chest_claimed = Column(Boolean, nullable=False, default=False)
    # Módulo del plan docente al que corresponde ("" = sin asignar).
    module_ref = Column(String(64), nullable=False, default="")

    course = relationship("Course", back_populates="units")
    lessons = relationship("Lesson", back_populates="unit", cascade="all, delete-orphan", order_by="Lesson.position")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("course_units.id", ondelete="CASCADE"), nullable=False)
    ref = Column(String(64), nullable=False)
    title = Column(String(200), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    # Teoría escrita por quien estudia (Markdown con $…$). El import nunca la pisa.
    theory = Column(Text, nullable=False, default="")
    theory_url = Column(String(500), nullable=False, default="")
    completed_at = Column(DateTime, nullable=True)
    best_ratio = Column(Float, nullable=True)
    runs = Column(Integer, nullable=False, default=0)

    unit = relationship("CourseUnit", back_populates="lessons")
    steps = relationship("LessonStep", back_populates="lesson", cascade="all, delete-orphan", order_by="LessonStep.position")


class LessonStep(Base):
    __tablename__ = "lesson_steps"

    id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    ref = Column(String(64), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    kind = Column(String(12), nullable=False)
    prompt = Column(Text, nullable=False)
    # Opciones y solución según el tipo (ver learn.py). Nunca se envía antes de responder.
    data = Column(JSON, nullable=False, default=dict)
    explanation = Column(Text, nullable=False, default="")
    # Origen en el material (p. ej. "Módulo 1, ejercicio de autoevaluación 16"). Obligatorio
    # salvo en las tarjetas informativas.
    source = Column(String(300), nullable=False, default="")
    hints = Column(JSON, nullable=False, default=list)
    concepts = Column(JSON, nullable=False, default=list)
    # Códigos de los objetivos de aprendizaje del plan docente que practica ("O3"…).
    objectives = Column(JSON, nullable=False, default=list)
    # Ejemplo resuelto (del material) que se enseña antes del paso solo la primera vez.
    worked = Column(Text, nullable=False, default="")
    # Repaso espaciado de lo fallado (Leitner, como las tarjetas de Estudio).
    box = Column(Integer, nullable=False, default=0)
    due_on = Column(Date, nullable=True)
    correct = Column(Integer, nullable=False, default=0)
    wrong = Column(Integer, nullable=False, default=0)
    confident_wrong = Column(Integer, nullable=False, default=0)

    lesson = relationship("Lesson", back_populates="steps")


class LearnDay(Base):
    """XP ganada por día: racha y meta diaria."""

    __tablename__ = "learn_days"

    date = Column(Date, primary_key=True)
    xp = Column(Integer, nullable=False, default=0)
    lessons = Column(Integer, nullable=False, default=0)
    # Para las misiones diarias.
    perfect_lessons = Column(Integer, nullable=False, default=0)
    best_combo = Column(Integer, nullable=False, default=0)
    correct = Column(Integer, nullable=False, default=0)
    claimed = Column(JSON, nullable=False, default=list)  # misiones cuya recompensa ya se cobró
    # Día salvado por un protector de racha (sin XP, pero no rompe la racha).
    frozen = Column(Boolean, nullable=False, default=False)


class LearnProfile(Base):
    """Estado de juego de Aprender (una sola fila): gemas y protectores de racha.
    Sin vidas a propósito: fallar no debe impedir seguir estudiando."""

    __tablename__ = "learn_profile"

    id = Column(Integer, primary_key=True)
    gems = Column(Integer, nullable=False, default=0)
    streak_freezes = Column(Integer, nullable=False, default=0)
    last_settled = Column(Date, nullable=True)


class GenerationJob(Base):
    """Generación de un borrador de curso a partir de materiales (Aprender → Generar)."""

    __tablename__ = "generation_jobs"

    id = Column(Integer, primary_key=True)
    status = Column(String(12), nullable=False, default="queued")  # queued|running|done|error
    created_at = Column(DateTime, nullable=False, default=_now)
    finished_at = Column(DateTime, nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    material_kind = Column(String(16), nullable=False, default="manual")
    title = Column(String(200), nullable=False, default="")
    filenames = Column(JSON, nullable=False, default=list)
    # Borrador: {"units": [...]} con el formato de curso + avisos por paso.
    draft = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=False, default=list)
    error = Column(Text, nullable=False, default="")
    cost_usd = Column(Float, nullable=True)


class InboxMessage(Base):
    """Correo de la universidad reenviado a la bandeja (ver inbox.py)."""

    __tablename__ = "inbox_messages"

    id = Column(Integer, primary_key=True)
    # Message-ID del correo: reenviar dos veces el mismo no lo duplica.
    message_id = Column(String(500), nullable=False, unique=True)
    received_at = Column(DateTime, nullable=False, default=_now)
    sender = Column(String(320), nullable=False, default="")
    recipient = Column(String(320), nullable=False, default="")
    title = Column(String(500), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    status = Column(String(16), nullable=False, default="new")
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String(16), nullable=False, default="other")
    summary = Column(Text, nullable=False, default="")
    # Fechas detectadas: [{"title", "date", "end_date", "time", "event_kind", "state", "event_id"}].
    # Nunca se añaden solas a la agenda: se aceptan o descartan una a una.
    proposals = Column(JSON, nullable=False, default=list)
    classify_status = Column(String(16), nullable=False, default="pending")
    classify_error = Column(Text, nullable=False, default="")

    subject = relationship("Subject")


class CalendarFeed(Base):
    """Enlace iCal del campus virtual que se sincroniza con la agenda (ver calendar_feeds.py)."""

    __tablename__ = "calendar_feeds"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, default="")
    # Suele llevar un token personal del campus: la API nunca lo devuelve entero.
    url = Column(String(1000), nullable=False)
    # Asignatura para lo que no se reconozca por código o nombre.
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    mode = Column(String(12), nullable=False, default="events")  # events | activities
    enabled = Column(Boolean, nullable=False, default=True)
    last_sync = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=False, default="")
    items = Column(Integer, nullable=False, default=0)


class Material(Base):
    """Material de estudio guardado (Aprender → Biblioteca): el texto para la IA y, si era un
    PDF, el archivo para abrirlo por la página que cita la teoría (ver materials.py)."""

    __tablename__ = "materials"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    module_ref = Column(String(64), nullable=False, default="")
    kind = Column(String(16), nullable=False, default="manual")
    filename = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    pages = Column(Integer, nullable=True)
    has_file = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)
