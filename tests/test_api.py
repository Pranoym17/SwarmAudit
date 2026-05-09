from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings
from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "SwarmAudit"}


def test_llm_health_endpoint(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, llm_provider="mock"))

    response = TestClient(app).get("/llm/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["provider"] in {"mock", "vllm"}
