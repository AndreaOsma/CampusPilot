# GENERADO desde dev/lib/agent-api (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""Adaptador FastAPI: GET /agent/v1/manifest · POST /agent/v1/validate/{tool} · POST /agent/v1/call/{tool}

    app.include_router(create_agent_router(agent, get_db))

`get_db` es la dependencia de la app (generador que da la sesión); su valor llega a cada
herramienta como primer argumento.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from . import AgentError, AgentRegistry

MAX_BODY = 256 * 1024


def create_agent_router(agent: AgentRegistry, get_db: Optional[Callable[..., Any]] = None, prefix: str = "/agent/v1") -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["agent"], include_in_schema=False)

    def _no_db():
        return None

    db_dep = get_db or _no_db

    def _error(e: AgentError) -> JSONResponse:
        return JSONResponse({"ok": False, "error": e.message}, status_code=e.status)

    async def _args(request: Request) -> Any:
        raw = await request.body()
        if len(raw) > MAX_BODY:
            raise AgentError("Petición demasiado grande.", 413)
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            raise AgentError("El cuerpo tiene que ser JSON.", 422) from None

    @router.get("/manifest")
    def manifest(authorization: Optional[str] = Header(None)):
        try:
            agent.check(authorization)
        except AgentError as e:
            return _error(e)
        return agent.manifest()

    @router.post("/validate/{tool}")
    async def validate(tool: str, request: Request, authorization: Optional[str] = Header(None), db=Depends(db_dep)):
        try:
            agent.check(authorization)
            args = await _args(request)
            return await run_in_threadpool(agent.validate, tool, args, db)
        except AgentError as e:
            return _error(e)

    @router.post("/call/{tool}")
    async def call(tool: str, request: Request, authorization: Optional[str] = Header(None), db=Depends(db_dep)):
        try:
            agent.check(authorization)
            args = await _args(request)
            # Las herramientas son síncronas (SQLAlchemy): fuera del bucle de eventos.
            return await run_in_threadpool(agent.call, tool, args, db)
        except AgentError as e:
            if db is not None and hasattr(db, "rollback"):
                db.rollback()
            return _error(e)

    return router
