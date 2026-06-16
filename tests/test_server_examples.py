from types import SimpleNamespace

from fastapi.testclient import TestClient

from academic_pe.server import app


def test_refresh_examples_returns_cached_examples_when_generation_fails(monkeypatch):
    async def fail_generation():
        raise TimeoutError("provider timeout")

    async def load_cached_examples(lang):
        return [{"topic": "Cached", "instructions": f"Use cached examples in {lang}."}]

    monkeypatch.setattr(
        "academic_pe.server.load_config",
        lambda path: SimpleNamespace(
            ui=SimpleNamespace(language="en"),
            dynamic_examples_interval_mins=7,
        ),
    )
    monkeypatch.setattr("academic_pe.core.dynamic_examples.generate_new_examples", fail_generation)
    monkeypatch.setattr("academic_pe.core.dynamic_examples.load_cached_examples", load_cached_examples)
    monkeypatch.setattr("academic_pe.core.dynamic_examples.last_generated_at", 123.0)

    client = TestClient(app)
    response = client.post("/api/examples/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body["examples"] == [
        {"topic": "Cached", "instructions": "Use cached examples in en."}
    ]
    assert body["refreshed"] is False
    assert body["dynamic"] is True
    assert body["last_generated"] == 123000
    assert body["ttl"] == 420
    assert "provider timeout" in body["error"]
