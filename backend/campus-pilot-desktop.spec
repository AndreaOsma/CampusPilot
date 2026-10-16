# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: Campus Pilot de escritorio (carpeta en Windows, .app en macOS).

Lo usan los scripts compartidos de dev/lib/native-packaging (build-desktop-ci.sh con Wine
para Windows, build-desktop-mac-ci.sh en un Mac): copian el build de Vite a desktop/static
y ejecutan este spec desde una ruta limpia."""
import os
import sys
from pathlib import Path

backend = Path(SPECPATH)
static = backend / "desktop" / "static"
version_file = backend / "desktop" / "VERSION"
# Catálogo de módulos de estudios: los scripts de build lo dejan en desktop/packs (solo
# backend/ entra en la ruta limpia); desde el repo, ../packs.
packs = backend / "desktop" / "packs"
if not packs.is_dir():
    packs = backend.parent / "packs"

datas = [
    (str(backend / "alembic"), "alembic"),
    (str(backend / "alembic.ini"), "."),
]
if packs.is_dir():
    datas.append((str(packs), "packs"))
if version_file.is_file():
    datas.append((str(version_file), "desktop"))
if static.is_dir() and any(static.iterdir()):
    datas.append((str(static), os.path.join("desktop", "static")))

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "alembic",
    "alembic.config",
    "alembic.runtime.migration",
    "alembic.ddl.sqlite",
    "pypdf",
    "multipart",
    "anthropic",
    "tzdata",
]

a = Analysis(
    ["desktop_launcher.py"],
    pathex=[str(backend)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["psycopg2", "psycopg2_binary", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Campus Pilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name="Campus Pilot")

# Solo en macOS: envuelve la carpeta en Campus Pilot.app para el .dmg. Bajo Wine
# (sys.platform == "win32") se queda en la carpeta del instalador de Windows.
if sys.platform == "darwin":
    app = BUNDLE(coll, name="Campus Pilot.app", icon=None, bundle_identifier="com.andreaosma.campuspilot")
