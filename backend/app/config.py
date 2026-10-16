"""Configuración leída de variables de entorno (pocas claves, ad-hoc como en Bitácora/Soberan)."""
import os
from pathlib import Path

APP_NAME = "Campus Pilot"

PORT = int(os.getenv("PORT", "8080"))

CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]

# Carpeta de datos (snapshots de SQLite). En Docker la fija el job de Nomad (/data).
DATA_DIR = Path(os.getenv("CAMPUS_DATA_DIR", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Catálogo de módulos de estudios (JSON). En Docker se copian a /app/packs; en dev se
# leen de ../packs junto al backend.
_default_packs = Path(__file__).resolve().parent.parent.parent / "packs"
PACKS_DIR = Path(os.getenv("CAMPUS_PACKS_DIR", str(_default_packs))).resolve()
MAX_PACK_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# Feed iCal para clientes de calendario que no pueden pasar por el SSO (opcional).
# Sin token configurado, /ical/* responde 404. Token por variable o por fichero.
ICAL_TOKEN = os.getenv("CAMPUS_ICAL_TOKEN", "").strip()
_ical_token_file = os.getenv("CAMPUS_ICAL_TOKEN_FILE", "").strip()
if not ICAL_TOKEN and _ical_token_file and Path(_ical_token_file).is_file():
    ICAL_TOKEN = Path(_ical_token_file).read_text(encoding="utf-8").strip()

# Avisos por ntfy (opcional). Sin CAMPUS_NTFY_URL quedan desactivados.
NTFY_URL = os.getenv("CAMPUS_NTFY_URL", "").strip()
NTFY_TOKEN = os.getenv("CAMPUS_NTFY_TOKEN", "").strip()
NTFY_AUTH_FILE = os.getenv("CAMPUS_NTFY_AUTH_FILE", "").strip()
PUBLIC_URL = os.getenv("CAMPUS_PUBLIC_URL", "").strip()
EXTERNAL_TIMEOUT_S = 10.0

# Generador de lecciones (Aprender). Ejecuta Claude Code en modo no interactivo sin
# herramientas. Credencial (la lee el propio CLI): CLAUDE_CODE_OAUTH_TOKEN —el token de
# `claude setup-token`, uso personal de tu suscripción— o ANTHROPIC_API_KEY. También por
# fichero (secreto montado): CAMPUS_CLAUDE_TOKEN_FILE.
CLAUDE_BIN = os.getenv("CAMPUS_CLAUDE_BIN", "claude").strip()
CLAUDE_MODEL = os.getenv("CAMPUS_CLAUDE_MODEL", "opus").strip()
CLAUDE_TOKEN_FILE = os.getenv("CAMPUS_CLAUDE_TOKEN_FILE", "").strip()
GENERATOR_TIMEOUT_S = int(os.getenv("CAMPUS_GENERATOR_TIMEOUT", "1200"))
MAX_MATERIAL_BYTES = 1_500_000  # texto total enviado al modelo
MAX_PDF_BYTES = 40 * 1024 * 1024
MAX_PDF_PAGES = 600

# Bandeja de la universidad: correos reenviados (Cloudflare Email Routing → Worker → /inbox/ingest) y
# copia diaria a un repositorio local (/inbox/export). Dos tokens distintos, por variable o
# por fichero; sin token, cada ruta responde 404. Son las únicas rutas fuera del SSO.
def _token(name: str) -> str:
    value = os.getenv(name, "").strip()
    path = os.getenv(f"{name}_FILE", "").strip()
    if not value and path and Path(path).is_file():
        value = Path(path).read_text(encoding="utf-8").strip()
    return value


INBOX_TOKEN = _token("CAMPUS_INBOX_TOKEN")
# Buzón del Worker de Cloudflare: la app va a buscar los correos (solo tráfico de salida;
# nada de fuera entra en la red). Sin URL o sin token, no se recoge nada.
INBOX_PULL_URL = os.getenv("CAMPUS_INBOX_PULL_URL", "").strip().rstrip("/")
INBOX_PULL_TOKEN = _token("CAMPUS_INBOX_PULL_TOKEN")
INBOX_EXPORT_TOKEN = _token("CAMPUS_INBOX_EXPORT_TOKEN")
MAX_INBOX_BYTES = 1_000_000
MAX_INBOX_TEXT = 200_000
# Clasificar un correo es una tarea pequeña: modelo rápido por defecto.
INBOX_CLAUDE_MODEL = os.getenv("CAMPUS_INBOX_MODEL", "haiku").strip()
INBOX_TIMEOUT_S = int(os.getenv("CAMPUS_INBOX_TIMEOUT", "180"))
