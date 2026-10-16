"""Exportar a Anki (Archivo → Importar): texto separado por tabuladores con las cabeceras que
Anki entiende (#separator, #html, #deck, #tags column). Sin dependencias ni .apkg.

Anverso = enunciado (y opciones); reverso = solución + explicación + fuente. Fórmulas $…$ →
\\(…\\) (MathJax de Anki). Los pasos con números nuevos cada vez (param) no se exportan: en
una tarjeta fija perderían la gracia.
"""
from __future__ import annotations

import html
import re

from . import models

_MATH = re.compile(r"\$([^$]+)\$")


def _html(text: str) -> str:
    """Markdown ligero → HTML seguro para Anki, en una sola línea (sin tabuladores)."""
    maths: list[str] = []

    def keep(m: re.Match) -> str:
        maths.append(m.group(1))
        return f"\x00{len(maths) - 1}\x00"

    out = html.escape(_MATH.sub(keep, text or ""), quote=False)
    out = re.sub(r"```(?:\w+)?\n?(.*?)```", lambda m: f"<pre>{m.group(1)}</pre>", out, flags=re.S)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"^\s*-\s+", "• ", out, flags=re.M)
    out = re.sub(r"\x00(\d+)\x00", lambda m: f"\\({html.escape(maths[int(m.group(1))], quote=False)}\\)", out)
    return out.replace("\t", " ").replace("\r", "").replace("\n", "<br>")


def _card(step: models.LessonStep) -> tuple[str, str] | None:
    d = step.data or {}
    front, back = _html(step.prompt), ""
    if step.kind == "info":
        back = _html(step.explanation)
        front = f"<b>{front}</b>"
    elif step.kind == "choice":
        opts = d.get("options") or []
        front += "<br>" + "<br>".join(f"{chr(65 + i)}) {_html(o)}" for i, o in enumerate(opts))
        back = " · ".join(f"{chr(65 + i)}) {_html(opts[i])}" for i in d.get("correct", []) if i < len(opts))
    elif step.kind == "truefalse":
        back = "Verdadero" if d.get("answer") else "Falso"
    elif step.kind == "numeric":
        back = f"{d.get('answer')}{(' ' + str(d['unit'])) if d.get('unit') else ''}"
    elif step.kind == "complex":
        back = f"{d.get('re')} + {d.get('im')}i"
    elif step.kind == "order":
        back = " → ".join(_html(i) for i in d.get("items") or [])
    elif step.kind == "match":
        back = "<br>".join(f"{_html(a)} ↔ {_html(b)}" for a, b in d.get("pairs") or [])
    else:
        return None
    if step.kind != "info" and step.explanation:
        back += f"<br><br>{_html(step.explanation)}"
    if step.source:
        back += f"<br><small>📖 {_html(step.source)}</small>"
    return front, back


def _tag(text: str) -> str:
    return re.sub(r"[^\w.-]+", "_", text.strip().lower())[:60] or "x"


def export_course(course: models.Course, only_missed: bool = False, with_theory: bool = True) -> str:
    deck = f"Campus Pilot::{course.title}".replace("\t", " ").replace("\n", " ")
    lines = ["#separator:tab", "#html:true", f"#deck:{deck}", "#tags column:3", "#notetype:Basic"]
    for unit in course.units:
        for lesson in unit.lessons:
            for step in lesson.steps:
                if step.kind == "info" and not with_theory:
                    continue
                if only_missed and (step.kind == "info" or not step.wrong):
                    continue
                card = _card(step)
                if card is None:
                    continue
                tags = " ".join(sorted({_tag(unit.title), *(_tag(c) for c in step.concepts or []), *(step.objectives or [])}))
                lines.append(f"{card[0]}\t{card[1]}\t{tags}")
    return "\n".join(lines) + "\n"
