# GENERADO desde dev/lib/agent-api (Homelab): no lo edites aquí, edita la librería y ejecuta su sync.mjs
"""API para asistentes (ágora en Matrix u otro): cada app declara sus herramientas y un asistente
con el token de la app las descubre (manifiesto con esquema JSON) y las llama.

    from .agent_api import AgentRegistry, AgentError
    agent = AgentRegistry("home-inventory", "Home Inventory", "Qué hay en casa y dónde está",
                          token_env="HOME_INVENTORY_AGENT_TOKEN")

    class WhereIn(BaseModel):
        q: str = Field(min_length=1, max_length=120)

    @agent.tool("donde_esta", "Busca un objeto y devuelve dónde está")
    def where(db, p: WhereIn): ...

    @agent.tool("anadir_objeto", "Añade un objeto", write=True)
    def add(db, p: AddIn): ...

Seguridad:
- Cerrada por defecto: sin token configurado (variable de entorno) la API no existe (404).
- Token comparado en tiempo constante (Authorization: Bearer <token>).
- Los parámetros se validan con pydantic antes de llamar a la herramienta.
- `write=True` marca lo que cambia datos. Quien llama (el asistente) debe pedir confirmación a
  la persona antes de ejecutarlo; /validate permite comprobar los parámetros sin ejecutar nada.
- `preview=fn(ctx, params) -> str` (opcional, solo lectura): la frase que verá la persona al
  confirmar, generada por la app a partir de los parámetros exactos («Prestar «Taladro Bosch»
  a Luis hasta el 23/10» en vez de «objeto_id: 1»). /validate la devuelve; si falla (p. ej. el
  objeto no existe) la validación falla antes de proponer nada.

Los adaptadores para FastAPI y Flask están en agent_api.fastapi y agent_api.flask.
"""
from __future__ import annotations

import dataclasses
import enum
import hmac
import inspect
import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Callable, Optional

from pydantic import BaseModel, ValidationError

API_VERSION = 1
MAX_ITEMS = 200  # tope de elementos en una lista devuelta (el contexto del asistente es finito)


class AgentError(Exception):
    """Error que se devuelve tal cual al asistente (mensaje claro, en español)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[..., Any]
    params: Optional[type[BaseModel]] = None
    write: bool = False
    preview: Optional[Callable[..., str]] = None

    def schema(self) -> dict:
        if self.params is None:
            return {"type": "object", "properties": {}}
        s = self.params.model_json_schema()
        s.pop("title", None)
        return s


def jsonable(value: Any) -> Any:
    """Lo que devuelve una herramienta → JSON (fechas ISO, modelos pydantic, filas ORM sencillas)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return jsonable(value.value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        out = [jsonable(v) for v in items[:MAX_ITEMS]]
        if len(items) > MAX_ITEMS:
            out.append({"_truncado": f"{len(items) - MAX_ITEMS} más; afina la búsqueda"})
        return out
    table = getattr(value, "__table__", None)  # fila de SQLAlchemy: solo sus columnas
    if table is not None:
        return {c.name: jsonable(getattr(value, c.name)) for c in table.columns}
    return str(value)


class AgentRegistry:
    def __init__(self, app: str, title: str, description: str, *, token_env: str):
        self.app = app
        self.title = title
        self.description = description
        self.token_env = token_env
        self.tools: dict[str, Tool] = {}

    # ---------- Declarar ----------

    def tool(self, name: str, description: str, *, write: bool = False, preview: Optional[Callable[..., str]] = None):
        """Decorador. La función recibe (ctx, params) — ctx es lo que inyecte el adaptador (la
        sesión de base de datos, normalmente) y params la instancia validada del modelo pydantic
        anotado en el segundo argumento (o nada si la herramienta no tiene parámetros)."""

        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            if name in self.tools:
                raise ValueError(f"Herramienta duplicada: {name}")
            sig = list(inspect.signature(fn).parameters.values())
            params = None
            if len(sig) >= 2:
                ann = sig[1].annotation
                if isinstance(ann, str):  # from __future__ import annotations
                    ann = fn.__globals__.get(ann, ann)
                if not (isinstance(ann, type) and issubclass(ann, BaseModel)):
                    raise TypeError(f"{name}: el segundo argumento debe anotarse con un modelo pydantic")
                params = ann
            self.tools[name] = Tool(name=name, description=description, handler=fn, params=params, write=write, preview=preview)
            return fn

        return deco

    # ---------- Seguridad ----------

    def token(self) -> str:
        return os.getenv(self.token_env, "").strip()

    @property
    def enabled(self) -> bool:
        return len(self.token()) >= 16

    def check(self, authorization: Optional[str]) -> None:
        """Lanza AgentError(404) si la API está apagada y AgentError(401) si el token no vale."""
        expected = self.token()
        if len(expected) < 16:
            raise AgentError("La API para asistentes no está activada en esta instalación.", 404)
        provided = (authorization or "").strip()
        if provided.lower().startswith("bearer "):
            provided = provided[7:].strip()
        if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
            raise AgentError("Token del asistente inválido o ausente (Authorization: Bearer <token>).", 401)

    # ---------- Usar ----------

    def manifest(self) -> dict:
        return {
            "api": API_VERSION,
            "app": self.app,
            "title": self.title,
            "description": self.description,
            "tools": [
                {"name": t.name, "description": t.description, "write": t.write, "parameters": t.schema()}
                for t in self.tools.values()
            ],
        }

    def _get(self, name: str) -> Tool:
        tool = self.tools.get(name)
        if tool is None:
            raise AgentError(f"No existe la herramienta «{name}». Pide el manifiesto para ver las que hay.", 404)
        return tool

    def _parse(self, tool: Tool, args: Any) -> Optional[BaseModel]:
        if tool.params is None:
            return None
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise AgentError("Los parámetros tienen que ser un objeto JSON.", 422)
        try:
            return tool.params.model_validate(args)
        except ValidationError as e:
            errs = "; ".join(f"{'.'.join(str(x) for x in err['loc']) or 'parámetros'}: {err['msg']}" for err in e.errors()[:5])
            raise AgentError(f"Parámetros no válidos — {errs}", 422) from None

    def validate(self, name: str, args: Any, ctx: Any = None) -> dict:
        tool = self._get(name)
        parsed = self._parse(tool, args)
        out = {"ok": True, "tool": name, "write": tool.write, "parameters": parsed.model_dump(mode="json") if parsed else {}}
        if tool.preview is not None:
            text = tool.preview(ctx, parsed) if tool.params is not None else tool.preview(ctx)
            out["preview"] = str(text)[:1000]
        return out

    def call(self, name: str, args: Any, ctx: Any) -> dict:
        tool = self._get(name)
        parsed = self._parse(tool, args)
        result = tool.handler(ctx, parsed) if tool.params is not None else tool.handler(ctx)
        return {"ok": True, "tool": name, "result": jsonable(result)}
