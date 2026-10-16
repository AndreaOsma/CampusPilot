import json
from types import SimpleNamespace

import httpx
import pytest

from app import ai, config

SECRET = "sk-test-secreto-123456"


@pytest.fixture(autouse=True)
def clean_key():
    ai.delete_key()
    yield
    ai.delete_key()
    ai._TRANSPORT = None


def mock(handler):
    ai._TRANSPORT = httpx.MockTransport(handler)


def test_default_is_server_claude_code(client, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    data = client.get("/api/ai").json()
    assert data["provider"] is None and data["has_key"] is False
    assert data["status"]["provider"] == "claude_code" and data["status"]["source"] == "server"
    assert data["status"]["enabled"] is False and data["status"]["reason"]


def test_ollama_end_to_end(client):
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        body = json.loads(request.content)
        seen["format"] = body["format"]
        return httpx.Response(200, json={"message": {"content": json.dumps({"ok": True, "saludo": "hola"})}})

    mock(handler)
    r = client.put("/api/ai", json={"provider": "ollama", "base_url": "http://ollama.local:11434/", "model_inbox": "qwen3:8b"})
    assert r.status_code == 200 and r.json()["status"]["enabled"] is True
    t = client.post("/api/ai/test")
    assert t.status_code == 200, t.text
    assert seen["url"] == "http://ollama.local:11434/api/chat" and seen["format"] == ai.TEST_SCHEMA


def test_openai_compatible_key_is_write_only_and_encrypted(client):
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "```json\n{\"ok\": true, \"saludo\": \"hola\"}\n```"}}]})

    mock(handler)
    r = client.put("/api/ai", json={"provider": "openai_compatible", "base_url": "https://llm.example/v1", "model_generator": "m", "model_inbox": "m", "key": SECRET})
    body = r.json()
    assert body["has_key"] is True and SECRET not in json.dumps(body)
    assert SECRET.encode() not in (config.DATA_DIR / "ai-key.enc").read_bytes()
    assert client.post("/api/ai/test").status_code == 200 and seen["auth"] == f"Bearer {SECRET}"
    # Guardar sin clave no la borra; el backup no la lleva.
    client.put("/api/ai", json={"provider": "openai_compatible", "base_url": "https://llm.example/v1", "model_generator": "m2"})
    assert ai.stored_key() == SECRET
    assert SECRET not in client.get("/api/backup").text
    assert client.delete("/api/ai/key").json()["has_key"] is False


def test_errors_are_readable(client):
    mock(lambda request: httpx.Response(401, json={"error": "no"}))
    client.put("/api/ai", json={"provider": "openai_compatible", "base_url": "https://llm.example/v1", "model_generator": "m", "key": "x"})
    r = client.post("/api/ai/test")
    assert r.status_code == 502 and "clave" in r.json()["detail"]
    assert client.put("/api/ai", json={"provider": "ollama", "base_url": "file:///etc/passwd"}).status_code == 422
    assert client.put("/api/ai", json={"provider": "ollama", "model_generator": "bad model; rm"}).status_code == 422


def test_anthropic_uses_structured_output(client, monkeypatch):
    calls = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"ok": true, "saludo": "hola"}')])

    class Messages:
        def stream(self, **kwargs):
            calls.update(kwargs)
            return Stream()

    monkeypatch.setattr(ai, "_anthropic_client", lambda key, timeout: (calls.setdefault("key", key), SimpleNamespace(messages=Messages()))[1])
    client.put("/api/ai", json={"provider": "anthropic", "key": SECRET})
    assert client.post("/api/ai/test").status_code == 200
    assert calls["key"] == SECRET and calls["model"] == "claude-haiku-4-5-20251001"
    assert calls["output_config"]["format"]["type"] == "json_schema"


def test_generator_status_follows_settings(client):
    client.put("/api/ai", json={"provider": "anthropic"})
    st = client.get("/api/learn/generator/status").json()
    assert st["enabled"] is False and "clave" in st["reason"] and "manual" in st["kinds"]


@pytest.mark.parametrize("provider,url", [
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions"),
])
def test_gemini_and_openrouter_need_the_user_key_and_use_their_url(client, provider, url):
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": true}"}}]})

    mock(handler)
    sin_clave = client.put("/api/ai", json={"provider": provider}).json()
    assert sin_clave["status"]["enabled"] is False and "clave" in sin_clave["status"]["reason"]
    con_clave = client.put("/api/ai", json={"provider": provider, "key": SECRET}).json()
    assert con_clave["status"]["enabled"] is True and con_clave["status"]["source"] == "settings"
    assert client.post("/api/ai/test").status_code == 200
    assert seen["url"] == url and seen["auth"] == f"Bearer {SECRET}"
