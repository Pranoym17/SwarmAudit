import json
import re
from typing import Any

from pydantic import ValidationError

from app.schemas import AgentOutput


FENCED_JSON_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_json_object(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    text = raw.strip()
    fence_match = FENCED_JSON_PATTERN.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def parse_agent_output(raw: str | dict[str, Any], agent_name: str) -> AgentOutput:
    try:
        data = parse_json_object(raw)
        data.setdefault("agent_name", agent_name)
        return AgentOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return AgentOutput(
            agent_name=agent_name,
            findings=[],
            metadata={"parse_error": True},
        )
