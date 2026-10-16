import os

from app import desktop


def test_desktop_configure_uses_user_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # setenv + delenv: así monkeypatch las registra (aunque no existieran) y al acabar deja el
    # entorno como estaba; configure() escribe directamente en os.environ.
    for key in ("CAMPUS_DESKTOP", "CAMPUS_DATA_DIR", "CAMPUS_PORT", "CAMPUS_PACKS_DIR", "CAMPUS_STATIC_DIR"):
        monkeypatch.setenv(key, "x")
        monkeypatch.delenv(key)
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", ""))  # la de los tests manda (setdefault)
    info = desktop.configure(port=18000)
    assert info["url"] == "http://127.0.0.1:18000" and info["host"] == "127.0.0.1"
    assert os.environ["CAMPUS_DESKTOP"] == "1"
    assert os.environ["CAMPUS_DATA_DIR"] == str(tmp_path / "Campus Pilot" / "data")
    assert (tmp_path / "Campus Pilot" / "logs").is_dir()
    assert os.environ["CAMPUS_PACKS_DIR"].endswith("packs")  # desde el repo: ../packs


def test_desktop_asks_to_choose_ai(client, monkeypatch):
    monkeypatch.setenv("CAMPUS_DESKTOP", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    st = client.get("/api/learn/generator/status").json()
    assert st["enabled"] is False and "Ajustes" in st["reason"]


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer" and "content-security-policy" not in r.headers  # JSON: sin CSP
    from app.security_headers import CSP
    from fastapi.responses import HTMLResponse

    from app.main import app

    @app.get("/__csp_probe", include_in_schema=False)
    def probe():
        return HTMLResponse("<p>x</p>")

    assert client.get("/__csp_probe").headers["content-security-policy"] == CSP
    assert "frame-ancestors 'none'" in CSP and "script-src 'self'" in CSP
