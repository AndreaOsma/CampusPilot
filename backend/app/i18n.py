"""Textos que genera el servidor y se ven en pantalla (misiones, «Hoy toca», riesgo, estado de
la IA), en el idioma de Ajustes. Clave = texto en español; lo no traducido sale en español."""
from __future__ import annotations

from sqlalchemy.orm import Session

EN: dict[str, str] = {
    # Misiones
    "Gana {n} XP": "Earn {n} XP",
    "Completa 2 lecciones": "Complete 2 lessons",
    "Consigue 5 aciertos seguidos": "Get 5 right in a row",
    "Termina una lección sin fallos": "Finish a lesson with no mistakes",
    "Acierta 15 ejercicios": "Get 15 exercises right",
    # Hoy toca
    "Avanza «{name}»": "Work on “{name}”",
    "{subject} · vence {when}": "{subject} · due {when}",
    "hoy": "today",
    "mañana": "tomorrow",
    "en {n} días": "in {n} days",
    "Estudia {name}": "Study {name}",
    "Vas {h} h por detrás esta semana": "You're {h} h behind this week",
    " · siguiente lección: {title}": " · next lesson: {title}",
    "Repasa {n} tarjeta": "Review {n} card",
    "Repasa {n} tarjetas": "Review {n} cards",
    "Repaso espaciado pendiente": "Spaced review due",
    "Una lección de {name}": "A lesson of {name}",
    # Riesgo
    "Ya no llega al aprobado": "Can no longer pass",
    "Por debajo del mínimo en {groups}": "Below the minimum in {groups}",
    "Necesitas {n} de media en lo que queda": "You need an average of {n} in what's left",
    # IA
    "Claude Code no está instalado en el servidor": "Claude Code isn't installed on the server",
    "Falta el token de Claude Code (claude setup-token)": "The Claude Code token is missing (claude setup-token)",
    "Falta la clave de API de Claude": "The Claude API key is missing",
    "Falta la URL del servidor": "The server URL is missing",
    "Falta el nombre del modelo": "The model name is missing",
    "Elige tu IA en Ajustes: una clave de Claude, Gemini u OpenRouter, o un servidor Ollama": "Choose your AI in Settings: a Claude, Gemini or OpenRouter key, or an Ollama server",
    # Generador
    "Manual o módulo": "Textbook or module",
    "Mis apuntes": "My notes",
    "Vídeo resumen (transcripción)": "Summary video (transcript)",
    "Otro material": "Other material",
}


def lang(db: Session) -> str:
    from .settings_store import load_settings

    try:
        return load_settings(db).language
    except Exception:  # noqa: BLE001 — sin ajustes: español
        return "es"


def tr(language: str, text: str, **kw) -> str:
    out = EN.get(text, text) if language == "en" else text
    return out.format(**kw) if kw else out


# Idioma en que la IA escribe lo que genera (teoría, ejercicios, plan docente): el de Ajustes.
PROMPT_LANGUAGES = {"es": "español", "en": "English (write everything in English, even if the material is in another language)"}


def prompt_lang(db: Session, instructions: str) -> str:
    return instructions.replace("{LANG}", PROMPT_LANGUAGES.get(lang(db), PROMPT_LANGUAGES["es"]))
