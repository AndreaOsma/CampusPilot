# GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""Textos del juego en español (clave) e inglés."""
from __future__ import annotations

EN: dict[str, str] = {
    "Esa misión no se puede cobrar": "That quest can't be claimed",
    "Puedes guardar {n} días libres como máximo": "You can save at most {n} days off",
    "No tienes chispas suficientes": "You don't have enough sparks",
    "Ya tienes la insignia de esta unidad": "You already have this unit's badge",
    "Termina todas las lecciones de la unidad para conseguir su insignia": "Finish every lesson in the unit to earn its badge",
}


def tr(language: str, text: str, **kw) -> str:
    out = EN.get(text, text) if language == "en" else text
    return out.format(**kw) if kw else out
