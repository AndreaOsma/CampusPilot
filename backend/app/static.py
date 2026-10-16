"""Sirve el build de Vite (Docker) con fallback SPA, después de registrar la API."""
from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

logger = logging.getLogger("campus.static")

# python:slim no trae /etc/mime.types con estas: sin ellas el manifest de la PWA sale como
# application/octet-stream.
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")


def resolve_static_dir() -> Optional[Path]:
    env = (os.getenv("CAMPUS_STATIC_DIR") or "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    return None


def mount_static(app, static_dir: Path) -> None:
    index_path = static_dir / "index.html"
    if not index_path.is_file():
        logger.warning("Static index missing at %s", index_path)
        return
    root = static_dir.resolve()

    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "ical/")) or full_path in ("api", "ical"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (static_dir / full_path).resolve()
        # Nada fuera de la carpeta estática (../../etc/passwd y similares).
        if candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index_path, media_type="text/html")
