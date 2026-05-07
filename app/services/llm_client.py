import json
import time
from typing import Any

import httpx

from app.config import Settings
from app.schemas import LLMHealth


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self.settings.llm_provider == "mock":
            return {
                "findings": [],
                "note": "Mock LLM is active; static rules produced the demo findings.",
            }

        if self.settings.llm_provider != "vllm":
            raise ValueError(f"Unsupported LLM_PROVIDER={self.settings.llm_provider}")

        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        response = await self._client_post("/chat/completions", payload)
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    async def health_check(self) -> LLMHealth:
        if self.settings.llm_provider == "mock":
            return LLMHealth(
                provider=self.settings.llm_provider,
                model=self.settings.llm_model,
                base_url=self.settings.llm_base_url,
                ok=True,
                latency_ms=0,
                models=[self.settings.llm_model],
                completion_preview="Mock LLM is active.",
            )

        if self.settings.llm_provider != "vllm":
            return LLMHealth(
                provider=self.settings.llm_provider,
                model=self.settings.llm_model,
                base_url=self.settings.llm_base_url,
                ok=False,
                error=f"Unsupported LLM_PROVIDER={self.settings.llm_provider}",
            )

        start = time.perf_counter()
        try:
            models = await self.list_models()
            preview = await self.test_completion()
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return LLMHealth(
                provider=self.settings.llm_provider,
                model=self.settings.llm_model,
                base_url=self.settings.llm_base_url,
                ok=True,
                latency_ms=latency_ms,
                models=models,
                completion_preview=preview,
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return LLMHealth(
                provider=self.settings.llm_provider,
                model=self.settings.llm_model,
                base_url=self.settings.llm_base_url,
                ok=False,
                latency_ms=latency_ms,
                error=str(exc),
            )

    async def list_models(self) -> list[str]:
        if self.settings.llm_provider == "mock":
            return [self.settings.llm_model]

        response = await self._client_get("/models")
        data = response.json()
        return [model.get("id", "unknown") for model in data.get("data", [])]

    async def test_completion(self) -> str:
        if self.settings.llm_provider == "mock":
            return "Mock LLM is active."

        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": "You are a concise diagnostics assistant."},
                {"role": "user", "content": "Reply with exactly: SwarmAudit LLM OK"},
            ],
            "temperature": 0,
            "max_tokens": 16,
        }
        response = await self._client_post("/chat/completions", payload)
        return response.json()["choices"][0]["message"]["content"].strip()

    async def _client_get(self, path: str) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.settings.llm_base_url.rstrip('/')}{path}",
                headers=headers,
            )
            response.raise_for_status()
            return response

    async def _client_post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}{path}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response
