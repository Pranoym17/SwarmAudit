import httpx
import pytest

from app.config import Settings
from app.services.llm_client import LLMClient


@pytest.mark.anyio
async def test_mock_llm_health_check_is_ok():
    health = await LLMClient(Settings(llm_provider="mock")).health_check()

    assert health.ok is True
    assert health.provider == "mock"
    assert health.completion_preview == "Mock LLM is active."


@pytest.mark.anyio
async def test_vllm_health_check_lists_models_and_tests_completion(monkeypatch):
    async def fake_get(self, url, headers):
        return httpx.Response(
            200,
            json={"data": [{"id": "Qwen/Qwen2.5-Coder-32B-Instruct"}]},
            request=httpx.Request("GET", url),
        )

    async def fake_post(self, url, json, headers):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "SwarmAudit LLM OK"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    health = await LLMClient(
        Settings(
            llm_provider="vllm",
            llm_base_url="http://amd.example:8000/v1",
            llm_api_key="token",
        )
    ).health_check()

    assert health.ok is True
    assert health.models == ["Qwen/Qwen2.5-Coder-32B-Instruct"]
    assert health.completion_preview == "SwarmAudit LLM OK"


@pytest.mark.anyio
async def test_vllm_health_check_reports_errors(monkeypatch):
    async def fake_get(self, url, headers):
        raise httpx.ConnectError("connection failed", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    health = await LLMClient(Settings(llm_provider="vllm")).health_check()

    assert health.ok is False
    assert "connection failed" in health.error
