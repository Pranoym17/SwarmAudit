import json
from typing import Any

import httpx

from app.config import Settings


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
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
