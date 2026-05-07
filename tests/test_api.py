from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "SwarmAudit"}


def test_llm_health_endpoint():
    response = TestClient(app).get("/llm/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["provider"] == "mock"
