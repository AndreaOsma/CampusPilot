# GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""Chispas y canje: días libres (protegen la racha) e insignias de unidad."""
from __future__ import annotations

PRICE_FREEZE = 100
MAX_FREEZES = 2
BADGE_GEMS = 20
PERFECT_BONUS_XP = 5


def buy_freeze(gems: int, freezes: int, price: int = PRICE_FREEZE, maximum: int = MAX_FREEZES) -> tuple[int, int]:
    """(chispas, días libres) tras comprar uno. ValueError si no se puede."""
    if freezes >= maximum:
        # Clave de traducción con {n}: quien la muestre la formatea (i18n.tr(..., n=maximum)).
        raise ValueError("Puedes guardar {n} días libres como máximo")
    if gems < price:
        raise ValueError("No tienes chispas suficientes")
    return gems - price, freezes + 1


def badge(already: bool, unit_done: bool) -> int:
    """Chispas por la insignia de una unidad terminada. ValueError si no toca."""
    if already:
        raise ValueError("Ya tienes la insignia de esta unidad")
    if not unit_done:
        raise ValueError("Termina todas las lecciones de la unidad para conseguir su insignia")
    return BADGE_GEMS
