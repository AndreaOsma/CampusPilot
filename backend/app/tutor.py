"""Tutor: preguntas sobre la teoría, respondidas solo con tu material (Aprender → Pregunta).

Usa la IA de Ajustes con los materiales de la biblioteca de la asignatura (los del módulo
elegido primero) y responde citando de dónde sale cada cosa. Si no está en el material, lo
dice en vez de inventar. Barreras en el código, igual que el generador: no contesta nada que
parezca una actividad evaluable (enunciados, PEC, prácticas, exámenes…) y, en asignaturas con
la IA prohibida en las evaluables, solo explica la teoría y los ejemplos resueltos del
material: no resuelve problemas nuevos.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from . import ai, config, generator, i18n, materials, models

TIMEOUT_S = 240
MAX_HISTORY = 6

# Peticiones de resolver una actividad evaluable (además de las frases de generator._EVALUABLE_TEXT).
_EVALUABLE_ASK = re.compile(
    r"\b(pec|pac|pr\s*\d|pr[aá]ctica\s*\d|reto\s*\d|cuestionario\s*\d|examen|prueba de s[ií]ntesis|enunciado|"
    r"assignment|homework|quiz\s*\d|exam\b|graded)\b",
    re.IGNORECASE,
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "in_material": {"type": "boolean"},
        "citations": {"type": "array", "items": {"type": "object", "properties": {
            "material": {"type": "string"}, "page": {"type": ["integer", "null"]}, "section": {"type": "string"},
        }, "required": ["material", "section"]}},
    },
    "required": ["answer", "in_material", "citations"],
}

INSTRUCTIONS = """Eres el tutor de Campus Pilot. Recibes material de estudio de una asignatura universitaria (cada uno con su cabecera «===== MATERIAL: nombre =====» y marcas <!-- página N -->), la conversación y una pregunta. Devuelve SOLO el JSON del esquema.

Reglas (obligatorias):
1. Responde solo con lo que dice el material. Si la respuesta no está en él, "in_material": false y dilo en "answer" (puedes indicar qué apartado se acerca más); no la completes con conocimiento propio.
2. Explica como un buen profesor: claro, paso a paso, con un ejemplo del propio material si lo hay. "answer" en Markdown (listas, **negrita**, fórmulas $…$), como mucho unas 250 palabras.
3. "citations": de dónde sale (nombre del material, "page" si hay marca de página, "section" = apartado).
4. Si la pregunta es el enunciado de una actividad evaluable (PEC, práctica, reto, cuestionario, examen…) o pide resolver un problema que podría serlo, no lo resuelvas: explica la teoría que hace falta y sugiere preguntarlo en el foro del aula.
{FORBIDDEN}5. Idioma: {LANG}.
"""
FORBIDDEN_RULE = "4b. En esta asignatura la IA está prohibida en las actividades evaluables: explica solo la teoría y los ejemplos ya resueltos del material; no resuelvas ningún problema o ejercicio nuevo, aunque lo pidan.\n"


class Refused(ValueError):
    pass


def check_question(question: str) -> None:
    if _EVALUABLE_ASK.search(question) or generator._EVALUABLE_TEXT.search(question):
        raise Refused("Eso parece una actividad evaluable: el tutor no la trabaja. Pregúntalo en el foro del aula; aquí puedes preguntar por la teoría que hay detrás.")


def pick_materials(db: Session, subject: models.Subject, module_ref: str, ids: list[int]) -> list[models.Material]:
    rows = db.query(models.Material).filter_by(subject_id=subject.id).all()
    if ids:
        rows = [m for m in rows if m.id in set(ids)]
    # Los del módulo primero; se corta al llegar al máximo de texto.
    rows.sort(key=lambda m: (m.module_ref != module_ref, m.id))
    out, total = [], 0
    for m in rows:
        size = len(m.text.encode("utf-8"))
        if total + size > config.MAX_MATERIAL_BYTES:
            continue
        try:
            materials.check(m, subject)
        except ValueError:
            continue
        out.append(m)
        total += size
    return out


def ask(db: Session, subject: models.Subject, question: str, history: list[dict], module_ref: str = "", ids: Optional[list[int]] = None) -> dict:
    check_question(question)
    chosen = pick_materials(db, subject, module_ref, ids or [])
    if not chosen:
        raise ValueError("Esta asignatura aún no tiene materiales en la biblioteca: sube el manual o tus apuntes.")
    convo = "\n".join(f"{'Estudiante' if h.get('role') == 'user' else 'Tutor'}: {str(h.get('text', ''))[:2000]}" for h in history[-MAX_HISTORY:])
    text = "\n\n".join([*(materials.as_part(m) for m in chosen), "===== CONVERSACIÓN =====", convo or "(empieza ahora)", "===== PREGUNTA =====", question])
    rules = INSTRUCTIONS.replace("{FORBIDDEN}", FORBIDDEN_RULE if subject.ai_policy == "forbidden" else "")
    payload, _ = ai.complete_json(ai.resolve(db), i18n.prompt_lang(db, rules), SCHEMA, text, "generator", TIMEOUT_S)
    by_name = {m.filename: m for m in chosen}
    citations = []
    for c in payload.get("citations") or []:
        m = by_name.get(str((c or {}).get("material") or ""))
        page = c.get("page") if isinstance(c.get("page"), int) and c.get("page") > 0 else None
        citations.append({"material": str(c.get("material") or "")[:200], "section": str(c.get("section") or "")[:200], "page": page,
                          "material_id": m.id if m else None, "has_file": bool(m and m.has_file)})
    return {"answer": str(payload.get("answer") or "")[:6000], "in_material": bool(payload.get("in_material")), "citations": citations[:8],
            "materials": [m.filename for m in chosen]}
