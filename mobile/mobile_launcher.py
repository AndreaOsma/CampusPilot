"""Android (Chaquopy): Campus Pilot entero dentro del móvil, con SQLite local y uvicorn en
127.0.0.1:PORT. Es el mismo despliegue de un solo proceso que el modo escritorio
(app/desktop.py), pero con los datos en el almacenamiento privado de la app.

Lo llama MainApplication.onCreate() con Context.getFilesDir(). Sin consola: el log va a
<datos>/logs/campus-pilot.log para poder diagnosticar.
"""
import logging
import os
import threading

PORT = 17892
HOST = "127.0.0.1"

_started = False


def start(files_dir: str) -> str:
    global _started
    url = f"http://{HOST}:{PORT}"
    if _started:
        return url
    _started = True

    base = os.path.join(files_dir, "campus-pilot")
    data_dir = os.path.join(base, "data")
    logs_dir = os.path.join(base, "logs")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(os.path.join(logs_dir, "campus-pilot.log"), encoding="utf-8")],
    )
    log = logging.getLogger("campus.mobile")

    os.environ["CAMPUS_DESKTOP"] = "1"
    os.environ.setdefault("CAMPUS_DATA_DIR", data_dir)
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(data_dir, "campus.db"))
    # El WebView de Capacitor carga la app desde https://localhost y llama a la API en
    # http://127.0.0.1:PORT: otro origen, así que hay que permitirlo.
    os.environ["CORS_ALLOW_ORIGINS"] = "https://localhost,capacitor://localhost"
    # En el móvil no hay programador de tareas de servidor ni Worker de correo.
    os.environ.setdefault("CAMPUS_SCHEDULER", "0")

    def _run():
        try:
            import uvicorn
            from app.main import app  # el import crea el esquema y aplica las migraciones

            log.info("Campus Pilot backend en %s (datos en %s)", url, data_dir)
            uvicorn.run(app, host=HOST, port=PORT, log_level="info")
        except Exception:
            log.exception("El backend de Campus Pilot no pudo arrancar")

    threading.Thread(target=_run, daemon=True, name="campus-backend").start()
    return url
