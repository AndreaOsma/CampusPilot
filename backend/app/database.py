"""SQLAlchemy engine, session factory y dependencia `get_db` de FastAPI."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./campus.db")

_is_memory_sqlite = DATABASE_URL == "sqlite:///:memory:"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if _is_memory_sqlite else None,
)


if DATABASE_URL.startswith("sqlite"):
    # SQLite ignora las claves foráneas (ON DELETE SET NULL/CASCADE) salvo que se activen por conexión.
    @event.listens_for(engine, "connect")
    def _sqlite_fk_on(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # Lecturas y escrituras a la vez (API, generador, bandeja y planificador): WAL y espera
        # en vez de "database is locked".
        cursor.execute("PRAGMA busy_timeout=5000")
        if not _is_memory_sqlite:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
