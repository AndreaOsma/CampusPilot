"""Variables estándar de IA (AI_*), las mismas en todas las apps."""
from app import ai


def test_standard_env_variables(monkeypatch, tmp_path):
    for k in ("AI_PROVIDER", "AI_MODEL", "AI_MODEL_FAST", "AI_BASE_URL", "AI_API_KEY", "AI_API_KEY_FILE"):
        monkeypatch.delenv(k, raising=False)
    assert ai._env_resolved() is None
    secret = tmp_path / "k"
    secret.write_text("tok\n")
    monkeypatch.setenv("AI_PROVIDER", "LiteLLM")
    monkeypatch.setenv("AI_BASE_URL", "http://gw:4000/v1/")
    monkeypatch.setenv("AI_MODEL", "auto")
    monkeypatch.setenv("AI_API_KEY_FILE", str(secret))
    r = ai._env_resolved()
    assert (r.provider, r.base_url, r.models, r.key, r.source) == (
        "openai_compatible", "http://gw:4000/v1", {"generator": "auto", "inbox": "auto"}, "tok", "server")
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.delenv("AI_BASE_URL")
    monkeypatch.setenv("AI_MODEL_FAST", "qwen3:8b")
    r = ai._env_resolved()
    assert r.base_url == "http://localhost:11434" and r.models == {"generator": "auto", "inbox": "qwen3:8b"}
    monkeypatch.setenv("AI_PROVIDER", "inventado")
    assert ai._env_resolved() is None
