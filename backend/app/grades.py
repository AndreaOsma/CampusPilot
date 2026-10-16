"""Cálculo de notas: funciones puras (sin base de datos) para poder probarlas a fondo.

Dos modelos de evaluación:

- ``weighted``: nota final = suma ponderada de grupos (p. ej. 30 % PEC + 70 % PR), cada
  grupo con su mínimo opcional. Si un grupo terminado no llega a su mínimo, no se supera.
- ``ec_pf``: evaluación continua + prueba final con notas mínimas (habitual en la enseñanza a distancia):
  EC suspendida → nota final = EC; PF por debajo del mínimo → nota final = PF; si no,
  ponderación de las dos. (``no_show_grade`` = nota si no te presentas a la PF con la EC
  aprobada; se guarda para mostrarla, no entra en el cálculo.)

Todo va en la escala de la carrera (``scale``: 10, 20, 100…) con su aprobado (``pass_grade``).
Dentro de un grupo, la nota es la media ponderada de sus actividades, normalizadas a esa escala.
Un grupo sin actividades cuenta como una única pieza pendiente (típico de la PF antes de
que se conozca su estructura).

"¿Cuánto necesito?" = la nota mínima *uniforme* en todo lo pendiente para llegar al
objetivo cumpliendo todos los mínimos. El predicado "aprueba con x" es monótono en x, así
que basta una búsqueda binaria.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

PASS_GRADE = 5.0  # aprobado por defecto (escala 0–10)


@dataclass
class ActivityData:
    id: int
    group_id: Optional[int]
    weight: float = 1.0
    grade: Optional[float] = None
    max_grade: float = 10.0
    evaluable: bool = True

    def scaled(self, hypothetical: dict[int, float], scale: float) -> Optional[float]:
        if self.grade is not None:
            return max(0.0, min(scale, self.grade / self.max_grade * scale))
        return hypothetical.get(self.id)


@dataclass
class GroupData:
    id: int
    name: str
    weight: float
    min_grade: Optional[float] = None
    role: Optional[str] = None


@dataclass
class EvalData:
    model: str = "weighted"
    groups: list[GroupData] = field(default_factory=list)
    activities: list[ActivityData] = field(default_factory=list)
    ec_pass: float = 5.0
    pf_min: float = 4.0
    no_show_grade: float = 3.0
    scale: float = 10.0
    pass_grade: float = PASS_GRADE


@dataclass
class GroupResult:
    id: int
    name: str
    weight: float
    min_grade: Optional[float]
    grade: Optional[float]  # media de lo calificado (o simulado) hasta ahora
    complete: bool
    pending: int
    meets_min: Optional[bool]  # None = aún no se sabe


@dataclass
class EvalResult:
    groups: list[GroupResult]
    current: Optional[float]  # media ponderada de lo que ya tiene nota
    final: Optional[float]  # solo cuando todo está calificado
    passed: Optional[bool]
    reasons: list[str]
    pending: int
    needed: Optional[float]  # nota uniforme necesaria en lo pendiente
    achievable: bool


def _group_acts(data: EvalData, group: GroupData) -> list[ActivityData]:
    return [a for a in data.activities if a.group_id == group.id and a.evaluable and a.weight > 0]


def _group_grade(
    data: EvalData, group: GroupData, hypothetical: dict[int, float], fill: Optional[float]
) -> tuple[Optional[float], bool, int]:
    """(nota del grupo sobre lo calificado, ¿completo?, piezas pendientes)."""
    acts = _group_acts(data, group)
    if not acts:
        if fill is not None:
            return fill, True, 0
        return None, False, 1
    total_w = 0.0
    acc = 0.0
    pending = 0
    for act in acts:
        g = act.scaled(hypothetical, data.scale)
        if g is None and fill is not None:
            g = fill
        if g is None:
            pending += 1
            continue
        total_w += act.weight
        acc += act.weight * g
    grade = acc / total_w if total_w > 0 else None
    return grade, pending == 0, pending


def _weighted(parts: list[tuple[float, Optional[float]]]) -> Optional[float]:
    total = sum(w for w, g in parts if g is not None)
    if total <= 0:
        return None
    return sum(w * g for w, g in parts if g is not None) / total


def _evaluate(data: EvalData, hypothetical: dict[int, float], fill: Optional[float]):
    """Devuelve (resultados por grupo, media actual, final, aprobado, motivos)."""
    groups = [g for g in data.groups if g.weight > 0]
    results: list[GroupResult] = []
    for g in groups:
        grade, complete, pending = _group_grade(data, g, hypothetical, fill)
        meets = None
        if complete and grade is not None and g.min_grade is not None:
            meets = grade >= g.min_grade - 1e-9
        results.append(GroupResult(g.id, g.name, g.weight, g.min_grade, grade, complete, pending, meets))

    current = _weighted([(r.weight, r.grade) for r in results])
    all_complete = bool(results) and all(r.complete for r in results)
    reasons: list[str] = []
    final: Optional[float] = None
    passed: Optional[bool] = None

    if data.model == "ec_pf":
        ec_res = [r for r, g in zip(results, groups) if g.role == "ec"]
        pf_res = [r for r, g in zip(results, groups) if g.role == "pf"]
        ec_grade = _weighted([(r.weight, r.grade) for r in ec_res])
        ec_done = bool(ec_res) and all(r.complete for r in ec_res)
        pf_grade = _weighted([(r.weight, r.grade) for r in pf_res])
        pf_done = bool(pf_res) and all(r.complete for r in pf_res)
        w_ec = sum(r.weight for r in ec_res)
        w_pf = sum(r.weight for r in pf_res)
        if ec_done and ec_grade is not None and ec_grade < data.ec_pass:
            final, passed = ec_grade, False
            reasons.append(f"EC por debajo de {data.ec_pass:g}: la nota final es la de la EC")
        elif ec_done and pf_done and ec_grade is not None and pf_grade is not None:
            if pf_grade < data.pf_min:
                final, passed = pf_grade, False
                reasons.append(f"PF por debajo de {data.pf_min:g}: la nota final es la de la PF")
            else:
                final = (w_ec * ec_grade + w_pf * pf_grade) / (w_ec + w_pf) if (w_ec + w_pf) > 0 else None
                passed = final is not None and final >= data.pass_grade - 1e-9
    elif all_complete:
        final = current
        failed = [r for r in results if r.meets_min is False]
        if failed:
            passed = False
            for r in failed:
                reasons.append(f"{r.name}: {r.grade:.2f} no llega al mínimo de {r.min_grade:g}")
        else:
            passed = final is not None and final >= data.pass_grade - 1e-9

    return results, current, final, passed, reasons


def evaluate(data: EvalData, hypothetical: Optional[dict[int, float]] = None, target: Optional[float] = None) -> EvalResult:
    hypothetical = hypothetical or {}
    target = data.pass_grade if target is None else target
    top = data.scale
    results, current, final, passed, reasons = _evaluate(data, hypothetical, None)
    pending = sum(r.pending for r in results)

    needed: Optional[float] = None
    achievable = True
    if pending and results:
        def ok(x: float) -> bool:
            _, _, f, p, _ = _evaluate(data, hypothetical, x)
            return bool(p) and f is not None and f >= target - 1e-9

        if not ok(top):
            achievable = False
        elif ok(0.0):
            needed = 0.0
        else:
            lo, hi = 0.0, top
            for _ in range(40):
                mid = (lo + hi) / 2
                if ok(mid):
                    hi = mid
                else:
                    lo = mid
            # Hacia arriba a la centésima, con tolerancia para que 5.0000001 no salga 5.01.
            needed = min(top, math.ceil(hi * 100 - 1e-6) / 100)

    return EvalResult(results, current, final, passed, reasons, pending, needed, achievable)


def career_average(rows: list[tuple[float, Optional[float]]]) -> Optional[float]:
    """Media ponderada por créditos de (créditos, nota); ignora las que no tienen nota."""
    total = sum(e for e, g in rows if g is not None)
    if total <= 0:
        return None
    return sum(e * g for e, g in rows if g is not None) / total
