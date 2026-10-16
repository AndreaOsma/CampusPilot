# GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""Racha: días seguidos con actividad, que un día libre guardado puede cubrir."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional


def days_to_freeze(today: date, last_active: Optional[date], freezes: int) -> list[date]:
    """Días perdidos entre el último activo y ayer que se cubren con días libres (si alcanzan
    para todos; si no, ninguno: la racha se rompe y los días libres se conservan)."""
    if last_active is None:
        return []
    missing = [last_active + timedelta(days=i) for i in range(1, (today - last_active).days)]
    return missing if missing and len(missing) <= freezes else []


def streak(today: date, active: Iterable[date]) -> int:
    """Días seguidos hasta hoy (o hasta ayer, si hoy aún no hay actividad)."""
    days = set(active)
    cur = today if today in days else today - timedelta(days=1)
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def week(today: date, rows: dict[date, dict]) -> list[dict]:
    """Lunes a domingo de esta semana. `rows[d]` = {"xp", "frozen", "active"} (active: hubo
    actividad aunque no diera XP, p. ej. un vuelo en Bitácora)."""
    monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        r = rows.get(d) or {}
        out.append({
            "date": d.isoformat(),
            "xp": int(r.get("xp", 0)),
            "frozen": bool(r.get("frozen")),
            "active": bool(r.get("active")) or int(r.get("xp", 0)) > 0,
            "future": d > today,
        })
    return out
