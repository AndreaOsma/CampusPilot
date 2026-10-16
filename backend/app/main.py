"""Punto de entrada de FastAPI: migra el esquema, arranca el planificador (avisos +
snapshot), monta la API y sirve el frontend estático si lo encuentra (Docker)."""
import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, scheduler
from .routers import academic, agenda, ai, calendar, inbox, learn, materials, money, packs, path, settings, study, syllabus
from .security_headers import SecurityHeadersMiddleware
from .static import mount_static, resolve_static_dir


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(cfg, "head")


_run_migrations()

from . import generator  # noqa: E402

generator.fail_interrupted()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(scheduler.run_forever()) if scheduler.enabled() else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title=config.APP_NAME, lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)

if config.CORS_ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health():
    return {"status": "ok", "app": config.APP_NAME}


for _module in (academic, agenda, study, money, path):
    for _router in _module.routers:
        app.include_router(_router)
app.include_router(learn.router)
app.include_router(syllabus.router)
app.include_router(calendar.router)
app.include_router(materials.router)
app.include_router(ai.router)
app.include_router(packs.router)
app.include_router(settings.router)
app.include_router(inbox.public)
app.include_router(inbox.api)


_static_dir = resolve_static_dir()
if _static_dir:
    mount_static(app, _static_dir)
