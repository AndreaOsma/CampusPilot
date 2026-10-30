# GENERADO desde dev/lib/learn-game (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""Repaso mixto: preguntas al azar de asignaturas al azar (práctica intercalada).

Solo entra lo que ya se ha visto (cada app decide qué es «visto» al construir los candidatos).
Primero se sortea la asignatura —todas con la misma probabilidad, así una enorme no se come a
las demás— y nunca la misma dos veces seguidas si hay otra; luego, dentro de ella, una pregunta
con más peso para lo flojo (pendiente de repaso, fallado, fallado con seguridad) sin dejar fuera
lo que ya se domina, para que no se oxide."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Hashable, Optional

DEFAULT_N = 10
MAX_N = 30


@dataclass(frozen=True)
class Candidate:
    id: Any
    group: Hashable  # asignatura, curso o materia
    correct: int = 0
    wrong: int = 0
    confident_wrong: int = 0
    due: bool = False  # su repaso espaciado toca hoy o antes


def weight(c: Candidate) -> float:
    """1 para lo dominado; hasta ~9 para lo que toca repasar y se falló con seguridad."""
    w = 1.0
    tries = c.correct + c.wrong
    if tries:
        w += 3 * c.wrong / tries
    if c.due:
        w += 3
    w += min(c.confident_wrong, 2)
    return w


def pick(candidates: list[Candidate], n: int = DEFAULT_N, rng: Optional[random.Random] = None) -> list[Candidate]:
    """Hasta `n` candidatos sin repetir, intercalando asignaturas."""
    rng = rng or random.Random()
    n = max(1, min(int(n), MAX_N))
    pools: dict[Hashable, list[Candidate]] = {}
    for c in candidates:
        pools.setdefault(c.group, []).append(c)
    out: list[Candidate] = []
    last: Hashable = object()
    while len(out) < n and pools:
        groups = [g for g in pools if g != last] or list(pools)
        g = rng.choice(groups)
        pool = pools[g]
        c = rng.choices(pool, weights=[weight(x) for x in pool])[0]
        pool.remove(c)
        if not pool:
            del pools[g]
        out.append(c)
        last = g
    return out
