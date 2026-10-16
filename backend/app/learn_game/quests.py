# GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""Misiones del día: unas fijas y una que rota según el día, todas con su recompensa en chispas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class QuestDef:
    id: str
    title: str  # ya traducido; puede llevar el objetivo dentro
    counter: str  # clave del contador del día que mide el progreso
    target: int
    gems: int


def build(today: date, fixed: list[QuestDef], rotating: list[QuestDef], counters: dict[str, int], claimed: set[str]) -> list[dict]:
    chosen = list(fixed) + ([rotating[today.toordinal() % len(rotating)]] if rotating else [])
    out = []
    for q in chosen:
        progress = min(int(counters.get(q.counter, 0)), q.target)
        out.append({
            "id": q.id, "title": q.title, "progress": progress, "target": q.target, "gems": q.gems,
            "done": progress >= q.target, "claimed": q.id in claimed,
        })
    return out


def claimable(quests: list[dict], quest_id: str) -> dict:
    q = next((x for x in quests if x["id"] == quest_id), None)
    if q is None or not q["done"] or q["claimed"]:
        raise ValueError("Esa misión no se puede cobrar")
    return q
