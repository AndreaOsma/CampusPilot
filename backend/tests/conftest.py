import os
import tempfile
from pathlib import Path

import pytest

# La base y el directorio de datos se fijan ANTES de importar la app: main.py migra al importarse.
_TMP = Path(tempfile.mkdtemp(prefix="campus-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["CAMPUS_DATA_DIR"] = str(_TMP / "data")
os.environ["CAMPUS_SCHEDULER"] = "0"
os.environ["CAMPUS_ICAL_TOKEN"] = "test-token-123"
os.environ["CAMPUS_INBOX_TOKEN"] = "inbox-token-abc"
os.environ["CAMPUS_INBOX_EXPORT_TOKEN"] = "export-token-xyz"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.settings import BUNDLE_TABLES  # noqa: E402


@pytest.fixture()
def client():
    with SessionLocal() as db:
        for model in reversed(BUNDLE_TABLES):
            db.query(model).delete()
        db.commit()
    return TestClient(app)
