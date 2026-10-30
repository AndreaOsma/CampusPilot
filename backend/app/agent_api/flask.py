# GENERADO desde dev/lib/agent-api (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""Adaptador Flask (mismas rutas que el de FastAPI).

    app.register_blueprint(create_agent_blueprint(agent, ctx_factory))

`ctx_factory(token)` da el contexto de cada llamada (p. ej. el usuario dueño del token); si
devuelve None la petición se rechaza con 401. Con `ctx_factory=None` se usa el token único de
`agent.token_env`.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from flask import Blueprint, jsonify, request

from . import AgentError, AgentRegistry

MAX_BODY = 256 * 1024


def create_agent_blueprint(agent: AgentRegistry, ctx_factory: Optional[Callable[[str], Any]] = None,
                           prefix: str = "/agent/v1", name: str = "agent_api") -> Blueprint:
    bp = Blueprint(name, __name__, url_prefix=prefix)

    def _ctx() -> Any:
        header = (request.headers.get("Authorization") or "").strip()
        token = header[7:].strip() if header.lower().startswith("bearer ") else header
        if ctx_factory is None:
            agent.check(header)
            return None
        if not token:
            raise AgentError("Token del asistente ausente (Authorization: Bearer <token>).", 401)
        ctx = ctx_factory(token)
        if ctx is None:
            raise AgentError("Token del asistente inválido o revocado.", 401)
        return ctx

    def _args() -> Any:
        if (request.content_length or 0) > MAX_BODY:
            raise AgentError("Petición demasiado grande.", 413)
        if not request.get_data():
            return {}
        data = request.get_json(silent=True)
        if data is None:
            raise AgentError("El cuerpo tiene que ser JSON.", 422)
        return data

    @bp.errorhandler(AgentError)
    def _err(e: AgentError):
        return jsonify({"ok": False, "error": e.message}), e.status

    @bp.get("/manifest")
    def manifest():
        _ctx()
        return jsonify(agent.manifest())

    @bp.post("/validate/<tool>")
    def validate(tool: str):
        ctx = _ctx()
        return jsonify(agent.validate(tool, _args(), ctx))

    @bp.post("/call/<tool>")
    def call(tool: str):
        ctx = _ctx()
        return jsonify(agent.call(tool, _args(), ctx))

    return bp
