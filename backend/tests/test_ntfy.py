"""Avisos por ntfy: el servidor se pone en Ajustes o, para toda la instalación, por variable."""
import io
import json

from app import scheduler


def _capture(monkeypatch) -> dict:
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

    def fake_post(url, content, headers, auth, timeout):
        sent.update(url=url, headers=headers, auth=auth)
        return Resp()

    monkeypatch.setattr(scheduler.httpx, "post", fake_post)
    monkeypatch.setattr(scheduler.config, "PUBLIC_URL", "")
    return sent


def test_without_any_server(client, monkeypatch):
    monkeypatch.setattr(scheduler.config, "NTFY_URL", "")
    assert client.get("/api/notifications/status").json() == {"configured": False, "server": None, "installation_default": False, "has_token": False}
    assert client.post("/api/notifications/test").status_code == 503


def test_settings_server_wins_and_never_gets_installation_credentials(client, monkeypatch):
    sent = _capture(monkeypatch)
    monkeypatch.setattr(scheduler.config, "NTFY_URL", "https://ntfy.instalacion.example")
    monkeypatch.setattr(scheduler.config, "NTFY_TOKEN", "tk_de_la_instalacion")
    st = client.get("/api/notifications/status").json()
    assert st == {"configured": True, "server": None, "installation_default": True, "has_token": False}  # su URL no se enseña
    assert client.post("/api/notifications/test").status_code == 200
    assert sent["url"].startswith("https://ntfy.instalacion.example/") and sent["headers"]["Authorization"] == "Bearer tk_de_la_instalacion"
    settings = client.get("/api/settings").json()
    settings["notifications"]["server"] = "https://ntfy.sh"
    assert client.put("/api/settings", json=settings).status_code == 200
    sent.clear()
    assert client.post("/api/notifications/test").status_code == 200
    assert sent["url"].startswith("https://ntfy.sh/") and "Authorization" not in sent["headers"] and sent["auth"] is None
    assert client.put("/api/notifications/token", json={"token": "yo:secreto"}).status_code == 204
    assert client.get("/api/notifications/status").json()["has_token"] is True
    assert "secreto" not in str(client.get("/api/settings").json())
    sent.clear()
    client.post("/api/notifications/test")
    assert sent["auth"] == ("yo", "secreto")
    settings["notifications"]["server"] = "file:///etc/passwd"
    assert client.put("/api/settings", json=settings).status_code == 422


def test_token_stays_out_of_backups_and_survives_restore(client):
    client.put("/api/notifications/token", json={"token": "tk_privado"})
    bundle = client.get("/api/backup").json()
    assert "tk_privado" not in json.dumps(bundle)
    r = client.post("/api/backup/restore", files={"file": ("b.json", io.BytesIO(json.dumps(bundle).encode()), "application/json")})
    assert r.status_code == 200, r.text
    assert client.get("/api/notifications/status").json()["has_token"] is True
