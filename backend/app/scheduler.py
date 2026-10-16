"""Tareas periódicas dentro del propio proceso (una sola réplica, no hace falta más):

- Resumen diario por ntfy: entregas que se acercan, ventanas que abren o cierran, semana
  cargada (▲, los lunes), hábitos del día, tarjetas de repaso y plazos de trámites/becas.
- Snapshot consistente de SQLite (`VACUUM INTO`) para que la copia nocturna de tu servidor (restic, borg…) se lleve una base coherente.
- Bandeja de la universidad: recoge los correos que guarda el Worker de Cloudflare, los clasifica y avisa.

El estado (qué se envió/copió hoy) vive en la tabla settings bajo una clave interna.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from . import agenda, calendar_feeds, clock, config, inbox, models
from .database import DATABASE_URL, SessionLocal, engine
from .settings_store import load_settings

logger = logging.getLogger("campus.scheduler")

TZ = clock.TZ
TICK_SECONDS = 300
SNAPSHOT_HOUR = 2  # antes del restic de las 03:00
STATE_KEY = "_scheduler_state"


def _get_state(db: Session) -> dict:
    row = db.get(models.Setting, STATE_KEY)
    return dict(row.value or {}) if row else {}


def _set_state(db: Session, **values) -> None:
    row = db.get(models.Setting, STATE_KEY)
    state = dict(row.value or {}) if row else {}
    state.update(values)
    if row is None:
        db.add(models.Setting(key=STATE_KEY, value=state))
    else:
        row.value = state
    db.commit()


# ---------- ntfy ----------

def ntfy_configured() -> bool:
    return bool(config.NTFY_URL)


def _ntfy_auth() -> dict:
    if config.NTFY_TOKEN:
        return {"headers": {"Authorization": f"Bearer {config.NTFY_TOKEN}"}}
    if config.NTFY_AUTH_FILE and Path(config.NTFY_AUTH_FILE).is_file():
        user, _, password = Path(config.NTFY_AUTH_FILE).read_text(encoding="utf-8").strip().partition(":")
        return {"auth": (user, password)}
    return {}


def _header_safe(value: str) -> str:
    if value.isascii():
        return value
    return "=?UTF-8?B?" + base64.b64encode(value.encode("utf-8")).decode("ascii") + "?="


def send_ntfy(topic: str, title: str, message: str, tags: str = "mortar_board", priority: str = "default") -> None:
    if not ntfy_configured():
        raise RuntimeError("ntfy no está configurado en el servidor (CAMPUS_NTFY_URL)")
    auth = _ntfy_auth()
    headers = {"Title": _header_safe(title), "Tags": tags, "Priority": priority, **auth.get("headers", {})}
    if config.PUBLIC_URL:
        headers["Click"] = config.PUBLIC_URL
    resp = httpx.post(
        f"{config.NTFY_URL.rstrip('/')}/{topic}",
        content=message.encode("utf-8"),
        headers=headers,
        auth=auth.get("auth"),
        timeout=config.EXTERNAL_TIMEOUT_S,
    )
    resp.raise_for_status()


# ---------- Resumen ----------

def _in_days(n: int) -> str:
    return {0: "hoy", 1: "mañana"}.get(n, f"en {n} días")


def build_digest(db: Session, today: date) -> list[str]:
    """Líneas del resumen diario; lista vacía = nada que contar hoy."""
    settings = load_settings(db)
    milestones = set(settings.notifications.days_before)
    horizon = max(milestones | {0})
    lines: list[str] = []
    items = agenda.build(db, today, today + timedelta(days=max(horizon, 7)))

    for it in items:
        if it.done:
            continue
        subject = f" · {it.subject_name}" if it.subject_name else ""
        if it.type == "window":
            if it.date == today:
                lines.append(f"🪟 Abre hoy: {it.title}{subject} (hasta el {it.end_date:%d/%m})")
            elif it.end_date and it.date < today and (it.end_date - today).days in (1, 0):
                lines.append(f"⏳ Cierra {_in_days((it.end_date - today).days)}: {it.title}{subject}")
            continue
        days = (it.date - today).days
        if days not in milestones:
            continue
        if it.type == "activity":
            icon = "🚫🤖 " if it.ai_forbidden and it.evaluable else ""
            hour = f" a las {it.time}" if it.time else ""
            lines.append(f"📌 {icon}{it.title}{subject}: {_in_days(days)}{hour}")
        elif it.type == "event" and days == 0:
            hour = f" {it.time}" if it.time else ""
            lines.append(f"📅 Hoy{hour}: {it.title}{subject}")
        elif it.type in ("procedure", "grant"):
            lines.append(f"📋 {it.title}: plazo {_in_days(days)}")

    if today.weekday() == 0:
        week = agenda.week_start(today)
        heavy = agenda.heavy_weeks(
            agenda.build(db, week, week + timedelta(days=6)), settings.heavy_week_subjects
        )
        if week in heavy:
            lines.append(f"▲ Semana cargada: entregas de {', '.join(heavy[week])}")

    if settings.modules.get("semestre", True):
        checked = {c.habit_id for c in db.query(models.HabitCheck).filter_by(date=today)}
        for h in db.query(models.Habit).filter_by(active=True):
            if today.weekday() in (h.weekdays or []) and h.id not in checked:
                lines.append(f"🔁 {h.title}")

    if settings.modules.get("aprender", True) and db.query(models.Course).count():
        from . import learn

        due_steps = db.query(models.LessonStep).filter(models.LessonStep.box > 0, models.LessonStep.due_on <= today).count()
        current = learn.streak(db, today)
        if due_steps:
            lines.append(f"🎯 {due_steps} ejercicio{'s' if due_steps != 1 else ''} fallado{'s' if due_steps != 1 else ''} para repasar en Aprender")
        elif current and not db.get(models.LearnDay, today):
            lines.append(f"🔥 Racha de {current} día{'s' if current != 1 else ''}: una lección hoy para no perderla")

    if settings.modules.get("estudio", True):
        due = db.query(models.ReviewCard).filter(models.ReviewCard.due_on <= today).count()
        if due:
            lines.append(f"🧠 {due} pregunta{'s' if due != 1 else ''} de repaso para hoy")
    return lines


# ---------- Snapshot ----------

def _sqlite_path() -> Optional[Path]:
    prefix = "sqlite:///"
    if not DATABASE_URL.startswith(prefix) or DATABASE_URL.endswith(":memory:"):
        return None
    return Path(DATABASE_URL[len(prefix):])


def snapshot_sqlite() -> Optional[Path]:
    db_path = _sqlite_path()
    if db_path is None:
        return None
    target_dir = config.DATA_DIR / "snapshots"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{db_path.stem}.snapshot.db"
    tmp = target.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    with engine.connect() as conn:
        # VACUUM INTO no admite parámetros enlazados; la ruta la construimos nosotros.
        conn.exec_driver_sql(f"VACUUM INTO '{tmp.as_posix()}'")
    os.replace(tmp, target)
    return target


# ---------- Bucle ----------

def tick(now: Optional[datetime] = None) -> None:
    now = now or datetime.now(TZ)
    today = now.date()
    with SessionLocal() as db:
        state = _get_state(db)

        if now.hour >= SNAPSHOT_HOUR and state.get("last_snapshot") != today.isoformat():
            try:
                path = snapshot_sqlite()
                if path:
                    logger.info("SQLite snapshot written to %s", path)
                _set_state(db, last_snapshot=today.isoformat())
            except Exception:  # noqa: BLE001 — un fallo aquí no debe tumbar la app
                logger.exception("SQLite snapshot failed")

        notif = load_settings(db).notifications
        if notif.enabled and now.hour >= notif.hour and state.get("last_digest") != today.isoformat():
            lines = build_digest(db, today)
            try:
                if lines and ntfy_configured():
                    send_ntfy(notif.topic, "Campus Pilot", "\n".join(lines))
                _set_state(db, last_digest=today.isoformat())
            except Exception:  # noqa: BLE001
                logger.exception("ntfy digest failed")

    with SessionLocal() as db:
        calendar_feeds.sync_due(db)

    if config.INBOX_PULL_URL:
        try:
            new_ids = inbox.pull_remote()
        except Exception:  # noqa: BLE001 — sin conexión con el Worker: se reintenta en el siguiente tick
            logger.exception("inbox pull failed")
            new_ids = []
        if new_ids and ntfy_configured():
            with SessionLocal() as db:
                notif = load_settings(db).notifications
                lines, urgent = inbox.notification_lines(db, new_ids)
            if notif.enabled and lines:
                try:
                    send_ntfy(notif.topic, " · ".join(x for x in ("Bandeja", inbox.institution(db)) if x), "\n".join(lines), tags="inbox_tray", priority="high" if urgent else "default")
                except Exception:  # noqa: BLE001
                    logger.exception("ntfy inbox notice failed")


async def run_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler tick failed")
        await asyncio.sleep(TICK_SECONDS)


def enabled() -> bool:
    return os.getenv("CAMPUS_SCHEDULER", "1").strip() not in ("0", "false", "no")
