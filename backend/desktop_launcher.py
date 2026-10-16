"""Campus Pilot de escritorio: arranca la API + el frontend en 127.0.0.1 y abre una ventana
nativa (pywebview). Los datos quedan en la carpeta del usuario (ver app/desktop.py)."""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app import desktop  # noqa: E402 — antes que nada de la app: fija las variables de entorno


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    """Espera a que la API acepte conexiones: abrir la ventana antes enseña la página de error
    del WebView en vez de la app (la primera vez migra la base de datos)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_in_use(host, port):
            return True
        time.sleep(0.15)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Campus Pilot (escritorio)")
    parser.add_argument("--no-window", action="store_true", help="Solo el servidor, sin ventana")
    parser.add_argument("--port", type=int, default=None, help=f"Puerto local (por defecto {desktop.DESKTOP_PORT})")
    args = parser.parse_args()

    info = desktop.configure(args.port)
    host, port, url = info["host"], int(info["port"]), info["url"]
    if _port_in_use(host, port):
        # Ya hay una abierta: se enseña esa en vez de arrancar otra sobre la misma base de datos.
        print(f"Campus Pilot ya está abierto en {url}", file=sys.stderr)
        if not args.no_window:
            webbrowser.open(url)
        return 0

    import uvicorn  # noqa: E402
    from app.main import app  # noqa: E402 — migra la base de datos al importarse

    print(f"Campus Pilot en {url} · datos en {info['data_dir']}")
    if args.no_window:
        uvicorn.run(app, host=host, port=port, log_level="info")
        return 0

    # La ventana necesita el hilo principal (obligatorio en macOS): el servidor va en otro.
    threading.Thread(target=uvicorn.run, kwargs={"app": app, "host": host, "port": port, "log_level": "info"}, daemon=True).start()
    if not _wait_for_port(host, port):
        print("La API no respondió a tiempo: se abre la ventana igualmente.", file=sys.stderr)
    import webview  # noqa: E402

    webview.create_window("Campus Pilot", url, width=1280, height=860, min_size=(380, 560))
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
