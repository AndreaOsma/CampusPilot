"""Ajustes → Inteligencia artificial. La clave se puede escribir o borrar, nunca leer."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import Field
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
