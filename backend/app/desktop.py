"""Modo escritorio (Windows/macOS, sin Docker): datos en la carpeta del usuario, frontend
empaquetado y servidor solo en 127.0.0.1. Lo llama desktop_launcher.py ANTES de importar
la app: config.py y database.py leen estas variables al importarse."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "Campus Pilot"
DESKTOP_HOST = "127.0.0.1"
DESKTOP_PORT = 17891


def base_dir() -> Path:
    local_app = os.getenv("LOCALAPPDATA")
    if local_app:
        return Path(local_app) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    return Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_DIR_NAME


def _bundle_root() -> Path:
    """Donde están los datos empaquetados (frozen) o el backend (desde el repo)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _first_dir(*candidates: Path) -> Optional[Path]:
    return next((c for c in candidates if c.is_dir()), None)


def configure(port: Optional[int] = None) -> dict[str, str]:
    data_dir = base_dir() / "data"
    logs_dir = base_dir() / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = _bundle_root()

    os.environ["CAMPUS_DESKTOP"] = "1"
    os.environ.setdefault("CAMPUS_DATA_DIR", str(data_dir))
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + (data_dir / "campus.db").resolve().as_posix())
    static = _first_dir(root / "desktop" / "static", Path(sys.executable).parent / "desktop" / "static")
    if static:
        os.environ.setdefault("CAMPUS_STATIC_DIR", str(static))
    packs = _first_dir(root / "packs", root.parent / "packs")
    if packs:
        os.environ.setdefault("CAMPUS_PACKS_DIR", str(packs))

    bind_port = str(port or int(os.getenv("CAMPUS_PORT", DESKTOP_PORT)))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(logs_dir / "campus-pilot.log", encoding="utf-8"), logging.StreamHandler()],
    )
    return {"data_dir": str(data_dir), "host": DESKTOP_HOST, "port": bind_port, "url": f"http://{DESKTOP_HOST}:{bind_port}"}
