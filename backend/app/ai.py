"""Proveedor de IA configurable desde Ajustes: cada instalación pone el suyo.

Lo usan el generador de lecciones y el clasificador de la bandeja, siempre con la misma
interfaz: instrucciones + texto de entrada → objeto JSON que cumple un esquema. Nada de
herramientas ni acceso a ficheros: solo texto de entrada y JSON validado de salida.

Proveedores:
- ``claude_code``: el CLI de Claude Code (``claude -p``) con el token de ``claude setup-token``.
  Pensado para quien se instala su propia app con su propia suscripción.
- ``anthropic``: la API de Claude con una clave de API (SDK oficial).
- ``ollama``: un servidor Ollama (local o en tu red).
- ``gemini``: Gemini con una clave de Google AI Studio (su API compatible con OpenAI).
- ``openrouter``: OpenRouter con su clave (cualquier modelo de su catálogo).
- ``openai_compatible``: cualquier otro endpoint ``/chat/completions`` compatible (LM Studio,
  vLLM…).

La clave/token se guarda **cifrada** (Fernet) en ``DATA_DIR/ai-key.enc``, fuera de la base de
datos y por tanto fuera de los backups; la clave de cifrado sale de ``CAMPUS_SECRET_KEY`` o de
``DATA_DIR/secret.key`` (0600, se crea la primera vez). La API nunca la devuelve.

Si no hay nada configurado, se usa lo que el servidor traiga por entorno (Claude Code con
``CAMPUS_CLAUDE_TOKEN_FILE`` / ``CLAUDE_CODE_OAUTH_TOKEN``), como hasta ahora.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from . import config, i18n, models

Provider = Literal["claude_code", "anthropic", "gemini", "openrouter", "ollama", "openai_compatible"]
Feature = Literal["generator", "inbox"]
SETTING_KEY = "ai"

PROVIDERS: dict[str, dict[str, Any]] = {
    "claude_code": {"label": "Claude Code (tu suscripción)", "needs_key": True, "needs_url": False,
                    "models": {"generator": "opus", "inbox": "haiku"}},
    "anthropic": {"label": "Claude · clave de API", "needs_key": True, "needs_url": False,
                  "models": {"generator": "claude-opus-5-5", "inbox": "claude-haiku-4-5-20251001"}},
    "gemini": {"label": "Gemini · clave de API", "needs_key": True, "needs_url": False,
               "default_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "models": {"generator": "gemini-2.5-pro", "inbox": "gemini-2.5-flash"}},
    "openrouter": {"label": "OpenRouter", "needs_key": True, "needs_url": False, "default_url": "https://openrouter.ai/api/v1",
                   "models": {"generator": "openrouter/auto", "inbox": "openrouter/auto"}},
    "ollama": {"label": "Ollama", "needs_key": False, "needs_url": True, "default_url": "http://localhost:11434",
               "models": {"generator": "qwen3:14b", "inbox": "qwen3:8b"}},
    "openai_compatible": {"label": "Compatible con OpenAI", "needs_key": False, "needs_url": True,
                          "default_url": "https://openrouter.ai/api/v1", "models": {"generator": "", "inbox": ""}},
}
MAX_TOKENS: dict[str, int] = {"generator": 32000, "inbox": 4000}

# En los tests se sustituye por un httpx.MockTransport.
_TRANSPORT: Optional[httpx.BaseTransport] = None


class AiTimeout(RuntimeError):
    pass


class AiSettings(BaseModel):
    provider: Optional[Provider] = None  # None = lo que traiga el servidor por entorno
    base_url: str = Field(default="", max_length=500)
    model_generator: str = Field(default="", max_length=200)
    model_inbox: str = Field(default="", max_length=200)

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v:
            u = urlparse(v)
            if u.scheme not in ("http", "https") or not u.netloc:
                raise ValueError("La URL debe empezar por http:// o https://")
        return v

    @field_validator("model_generator", "model_inbox")
    @classmethod
    def _model(cls, v: str) -> str:
        v = v.strip()
        if v and not re.fullmatch(r"[\w.:/@+-]{1,200}", v):
            raise ValueError("Nombre de modelo no válido")
        return v


# ---------- Clave cifrada ----------

def _fernet() -> Fernet:
    env = os.getenv("CAMPUS_SECRET_KEY", "").strip()
    if env:
        return Fernet(env.encode())
    path = config.DATA_DIR / "secret.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(Fernet.generate_key())
    return Fernet(path.read_bytes().strip())


def _key_path() -> Path:
    return config.DATA_DIR / "ai-key.enc"


def save_key(secret: str) -> None:
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(_fernet().encrypt(secret.strip().encode()))
    tmp.replace(path)


def delete_key() -> None:
    _key_path().unlink(missing_ok=True)


def stored_key() -> Optional[str]:
    path = _key_path()
    if not path.is_file():
        return None
    try:
        return _fernet().decrypt(path.read_bytes()).decode() or None
    except (InvalidToken, ValueError):
        return None


# ---------- Configuración efectiva ----------

def load(db: Session) -> AiSettings:
    row = db.get(models.Setting, SETTING_KEY)
    try:
        return AiSettings.model_validate(row.value if row and isinstance(row.value, dict) else {})
    except ValueError:
        return AiSettings()


def save(db: Session, s: AiSettings) -> None:
    row = db.get(models.Setting, SETTING_KEY)
    if row is None:
        db.add(models.Setting(key=SETTING_KEY, value=s.model_dump()))
    else:
        row.value = s.model_dump()
    db.commit()


def _env_token() -> Optional[str]:
    if config.CLAUDE_TOKEN_FILE and Path(config.CLAUDE_TOKEN_FILE).is_file():
        tok = Path(config.CLAUDE_TOKEN_FILE).read_text(encoding="utf-8").strip()
        if tok:
            return tok
    return os.getenv("CLAUDE_CODE_OAUTH_TOKEN") or None


class Resolved(BaseModel):
    provider: Provider
    base_url: str
    models: dict[str, str]
    key: Optional[str] = None
    source: Literal["settings", "server"]


def resolve(db: Session) -> Resolved:
    s = load(db)
    if s.provider is None:
        # Sin configurar: lo que traiga el servidor (Claude Code con token o clave por entorno).
        defaults = PROVIDERS["claude_code"]["models"]
        return Resolved(provider="claude_code", base_url="", source="server", key=_env_token(),
                        models={"generator": config.CLAUDE_MODEL or defaults["generator"], "inbox": config.INBOX_CLAUDE_MODEL or defaults["inbox"]})
    meta = PROVIDERS[s.provider]
    return Resolved(
        provider=s.provider,
        base_url=s.base_url or meta.get("default_url", ""),
        models={"generator": s.model_generator or meta["models"]["generator"], "inbox": s.model_inbox or meta["models"]["inbox"]},
        key=stored_key(),
        source="settings",
    )


def status(db: Session) -> dict:
    r = resolve(db)
    reason = ""
    if r.source == "server" and os.getenv("CAMPUS_DESKTOP") == "1" and not os.getenv("ANTHROPIC_API_KEY"):
        # En la app de escritorio no hay «servidor» que traiga IA: cada cual pone la suya.
        reason = "Elige tu IA en Ajustes: una clave de Claude, Gemini u OpenRouter, o un servidor Ollama"
    elif r.provider == "claude_code":
        if not shutil.which(config.CLAUDE_BIN):
            reason = "Claude Code no está instalado en el servidor"
        elif not (r.key or os.getenv("ANTHROPIC_API_KEY")):
            reason = "Falta el token de Claude Code (claude setup-token)"
    elif r.provider == "anthropic" and not r.key:
        reason = "Falta la clave de API de Claude"
    elif r.provider in ("gemini", "openrouter") and not r.key:
        reason = "Falta la clave de API"
    elif r.provider in ("ollama", "openai_compatible"):
        if not r.base_url:
            reason = "Falta la URL del servidor"
        elif not r.models["generator"]:
            reason = "Falta el nombre del modelo"
    return {"enabled": not reason, "provider": r.provider, "source": r.source, "model": r.models["generator"],
            "reason": i18n.tr(i18n.lang(db), reason) if reason else ""}


def public(db: Session) -> dict:
    s = load(db)
    return {
        **s.model_dump(),
        "has_key": _key_path().is_file(),
        "status": status(db),
        "providers": {k: {kk: vv for kk, vv in v.items()} for k, v in PROVIDERS.items()},
    }


# ---------- Llamada ----------

def _parse_json(text: str) -> dict:
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        payload = json.loads(text)
    except ValueError:
        raise RuntimeError("La respuesta no es el JSON esperado")
    if not isinstance(payload, dict):
        raise RuntimeError("La respuesta no es un objeto JSON")
    return payload


def complete_json(r: Resolved, instructions: str, schema: dict, text: str, feature: Feature, timeout: int) -> tuple[dict, Optional[float]]:
    """Devuelve (objeto JSON, coste en USD si el proveedor lo da). Lanza AiTimeout o RuntimeError."""
    model = r.models[feature]
    if r.provider == "claude_code":
        return _claude_code(instructions, schema, text, model, timeout, r.key)
    if r.provider == "anthropic":
        if not r.key:
            raise RuntimeError("Falta la clave de API de Claude")
        return _anthropic(instructions, schema, text, model, timeout, r.key, MAX_TOKENS[feature]), None
    if r.provider == "ollama":
        return _ollama(instructions, schema, text, model, timeout, r.base_url), None
    return _openai_compatible(instructions, schema, text, model, timeout, r.base_url, r.key), None


def _claude_code(instructions: str, schema: dict, stdin: str, model: str, timeout: int, token: Optional[str]) -> tuple[dict, Optional[float]]:
    binary = shutil.which(config.CLAUDE_BIN)
    if not binary:
        raise RuntimeError("Claude Code no está instalado en el servidor")
    home = config.DATA_DIR / "claude-home"
    home.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    for key in ("ANTHROPIC_API_KEY", "SSL_CERT_FILE", "HTTPS_PROXY", "NO_PROXY"):
        if os.getenv(key):
            env[key] = os.environ[key]
    if token and "ANTHROPIC_API_KEY" not in env:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    cmd = [
        binary, "-p", instructions,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--tools", "",
        "--model", model,
        "--no-session-persistence",
        "--strict-mcp-config",
        "--permission-mode", "dontAsk",
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="campus-ai-") as cwd:
            proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AiTimeout("La IA tardó demasiado")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-600:]
        raise RuntimeError(f"Claude Code terminó con error ({proc.returncode}): {tail}")
    try:
        outer = json.loads(proc.stdout)
    except ValueError:
        raise RuntimeError("Claude Code no devolvió JSON")
    if outer.get("is_error"):
        raise RuntimeError(str(outer.get("result") or "Error de Claude Code")[:600])
    payload = outer.get("structured_output")
    if payload is None:
        payload = _parse_json(str(outer.get("result") or ""))
    if not isinstance(payload, dict):
        raise RuntimeError("La respuesta no es un objeto JSON")
    return payload, outer.get("total_cost_usd")


def _anthropic_client(key: str, timeout: int):
    import anthropic

    return anthropic.Anthropic(api_key=key, timeout=float(timeout), max_retries=2)


def _anthropic(instructions: str, schema: dict, text: str, model: str, timeout: int, key: str, max_tokens: int) -> dict:
    import anthropic

    client = _anthropic_client(key, timeout)
    try:
        # Streaming: la generación puede ser larga y así no hay timeouts de petición.
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=instructions,
            messages=[{"role": "user", "content": text}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            message = stream.get_final_message()
    except anthropic.APITimeoutError:
        raise AiTimeout("La IA tardó demasiado")
    except anthropic.AuthenticationError:
        raise RuntimeError("La clave de API de Claude no es válida")
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"La API de Claude respondió con error {exc.status_code}")
    except anthropic.APIConnectionError:
        raise RuntimeError("No se pudo conectar con la API de Claude")
    if message.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó la petición")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("La respuesta se cortó por longitud: prueba con menos material")
    return _parse_json(next((b.text for b in message.content if b.type == "text"), ""))


def _http(timeout: int) -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(float(timeout), connect=10.0), transport=_TRANSPORT, follow_redirects=False)


def _ollama(instructions: str, schema: dict, text: str, model: str, timeout: int, base_url: str) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": text}],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        with _http(timeout) as client:
            resp = client.post(f"{base_url}/api/chat", json=body)
    except httpx.TimeoutException:
        raise AiTimeout("La IA tardó demasiado")
    except httpx.HTTPError:
        raise RuntimeError(f"No se pudo conectar con Ollama en {base_url}")
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama respondió con error {resp.status_code}: {resp.text[:300]}")
    try:
        content = resp.json()["message"]["content"]
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Respuesta de Ollama inesperada")
    return _parse_json(str(content))


def _openai_compatible(instructions: str, schema: dict, text: str, model: str, timeout: int, base_url: str, key: Optional[str]) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": text}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "respuesta", "schema": schema}},
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        with _http(timeout) as client:
            resp = client.post(f"{base_url}/chat/completions", json=body, headers=headers)
    except httpx.TimeoutException:
        raise AiTimeout("La IA tardó demasiado")
    except httpx.HTTPError:
        raise RuntimeError(f"No se pudo conectar con {base_url}")
    if resp.status_code in (401, 403):
        raise RuntimeError("La clave no es válida para ese servidor")
    if resp.status_code != 200:
        raise RuntimeError(f"El servidor respondió con error {resp.status_code}: {resp.text[:300]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise RuntimeError("Respuesta del servidor inesperada")
    return _parse_json(str(content or ""))


TEST_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "saludo": {"type": "string"}},
    "required": ["ok", "saludo"],
    "additionalProperties": False,
}


def test(db: Session) -> dict:
    st = status(db)
    if not st["enabled"]:
        raise RuntimeError(st["reason"])
    payload, _ = complete_json(resolve(db), "Responde solo con el JSON pedido.", TEST_SCHEMA,
                               'Devuelve {"ok": true, "saludo": "hola"}.', "inbox", 60)
    if payload.get("ok") is not True:
        raise RuntimeError("El modelo respondió, pero no con lo esperado")
    return {"ok": True, "provider": st["provider"], "model": resolve(db).models["inbox"]}
