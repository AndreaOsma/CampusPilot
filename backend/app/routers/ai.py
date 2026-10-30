"""Ajustes → Inteligencia artificial. La clave se puede escribir o borrar, nunca leer.

«Conectar con OpenRouter» (OAuth con PKCE, sin registrar la app en ningún sitio): la persona
entra con su cuenta de OpenRouter, que redirige a Ajustes con un `code`, y aquí se cambia por
su clave (https://openrouter.ai/docs/use-cases/oauth-pkce). Desde ahí puede usar la IA que
prefiera de su catálogo (Claude, GPT, Gemini, modelos gratuitos…), pagando ella su uso.
"""
import base64
import hashlib
import secrets
import time
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import ai
from ..database import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AiSettingsIn(ai.AiSettings):
    # Vacío o ausente = no tocar la clave guardada.
    key: Optional[str] = Field(default=None, max_length=4000)


@router.get("")
def get_ai(db: Session = Depends(get_db)):
    return ai.public(db)


@router.put("")
def put_ai(payload: AiSettingsIn, db: Session = Depends(get_db)):
    ai.save(db, ai.AiSettings.model_validate(payload.model_dump(exclude={"key"})))
    if payload.key and payload.key.strip():
        ai.save_key(payload.key)
    return ai.public(db)


@router.delete("/key")
def delete_ai_key(db: Session = Depends(get_db)):
    ai.delete_key()
    return ai.public(db)


@router.post("/test")
async def test_ai(db: Session = Depends(get_db)):
    try:
        return await run_in_threadpool(ai.test, db)
    except ai.AiTimeout:
        raise HTTPException(status_code=504, detail="La IA tardó demasiado en responder")
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------- OpenRouter: OAuth con PKCE ----------

OPENROUTER_AUTH = "https://openrouter.ai/auth"
OPENROUTER_KEYS = "https://openrouter.ai/api/v1/auth/keys"
_PENDING_TTL_S = 15 * 60
# Un solo flujo pendiente a la vez (app de una persona): el verificador nunca sale del servidor.
_pending: dict[str, float | str] = {}


class OpenRouterStartIn(BaseModel):
    # A dónde vuelve OpenRouter: la pantalla de Ajustes de esta misma app (la manda el navegador).
    callback_url: str = Field(max_length=500)


class OpenRouterFinishIn(BaseModel):
    code: str = Field(min_length=8, max_length=500)


@router.post("/openrouter/start")
def openrouter_start(payload: OpenRouterStartIn):
    u = urlparse(payload.callback_url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise HTTPException(status_code=422, detail="Dirección de vuelta no válida")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _pending.clear()
    _pending.update(verifier=verifier, at=time.time())
    query = urlencode({"callback_url": payload.callback_url, "code_challenge": challenge, "code_challenge_method": "S256"})
    return {"url": f"{OPENROUTER_AUTH}?{query}"}


@router.post("/openrouter/finish")
def openrouter_finish(payload: OpenRouterFinishIn, db: Session = Depends(get_db)):
    verifier = _pending.get("verifier")
    if not verifier or time.time() - float(_pending.get("at", 0)) > _PENDING_TTL_S:
        _pending.clear()
        raise HTTPException(status_code=409, detail="La conexión con OpenRouter caducó: vuelve a pulsar «Conectar con OpenRouter»")
    try:
        with httpx.Client(timeout=20, transport=ai._TRANSPORT) as client:
            r = client.post(OPENROUTER_KEYS, json={"code": payload.code, "code_verifier": verifier, "code_challenge_method": "S256"})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo hablar con OpenRouter: revisa la conexión y vuelve a intentarlo")
    key = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("key") if r.is_success else None
    if not key:
        raise HTTPException(status_code=502, detail="OpenRouter no aceptó la conexión: vuelve a intentarlo desde el principio")
    _pending.clear()
    # Proveedor OpenRouter con sus modelos por defecto (enrutado automático); la persona puede
    # elegir otro modelo luego en esta misma pantalla.
    ai.save(db, ai.AiSettings(provider="openrouter"))
    ai.save_key(key)
    return ai.public(db)
