"""Evaluador de expresiones matemáticas seguro (sin `eval`): recorre el AST y solo admite
números, variables dadas, operadores aritméticos y unas pocas funciones matemáticas.

Lo usan los ejercicios con números aleatorios (`param`) para calcular la solución, y el
generador para recalcular las respuestas que propone el modelo.
"""
from __future__ import annotations

import ast
import math
import operator
from typing import Callable, Mapping

FUNCS: dict[str, Callable[..., float]] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "exp": math.exp,
    "log": math.log,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "hypot": math.hypot,
    "min": min,
    "max": max,
}
CONSTS = {"pi": math.pi, "e": math.e}
BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
MAX_LEN = 300
MAX_POW = 64


class MathError(ValueError):
    pass


def evaluate(expr: str, variables: Mapping[str, float] | None = None) -> float:
    if not isinstance(expr, str) or not expr.strip():
        raise MathError("Expresión vacía")
    if len(expr) > MAX_LEN:
        raise MathError("Expresión demasiado larga")
    try:
        tree = ast.parse(expr.replace("^", "**"), mode="eval")
    except SyntaxError:
        raise MathError(f"Expresión no válida: {expr}")
    variables = dict(variables or {})

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in variables:
                return float(variables[node.id])
            if node.id in CONSTS:
                return CONSTS[node.id]
            raise MathError(f"Variable desconocida: {node.id}")
        if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > MAX_POW:
                raise MathError("Exponente demasiado grande")
            try:
                return float(BINOPS[type(node.op)](left, right))
            except (ZeroDivisionError, OverflowError, ValueError) as exc:
                raise MathError(str(exc))
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
            return float(UNARY[type(node.op)](ev(node.operand)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
            args = [ev(a) for a in node.args]
            try:
                return float(FUNCS[node.func.id](*args))
            except (ValueError, TypeError, OverflowError, ZeroDivisionError) as exc:
                raise MathError(str(exc))
        raise MathError("Operación no permitida en la expresión")

    value = ev(tree)
    if not math.isfinite(value):
        raise MathError("Resultado no finito")
    return value


def names_in(expr: str) -> set[str]:
    try:
        tree = ast.parse(expr.replace("^", "**"), mode="eval")
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - set(FUNCS) - set(CONSTS)
