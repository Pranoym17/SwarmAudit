import pytest

from app.agents.docs_agent import DocsAgent
from app.agents.performance_agent import PerformanceAgent
from app.agents.quality_agent import QualityAgent
from app.config import Settings
from app.schemas import CodeChunk
from app.services.llm_client import LLMClient


class FakeLLMClient(LLMClient):
    def __init__(self, settings: Settings, payload=None, should_fail: bool = False):
        super().__init__(settings)
        self.payload = payload or {"findings": []}
        self.should_fail = should_fail
        self.calls = 0

    async def complete_json(self, system_prompt: str, user_prompt: str):
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("vLLM unavailable")
        return self.payload


def make_chunk() -> CodeChunk:
    return CodeChunk(
        file_path="app.py",
        language="Python",
        line_start=1,
        line_end=2,
        content="def work():\n    return True",
    )


def make_payload(agent_name: str):
    return {
        "findings": [
            {
                "title": f"{agent_name} LLM finding",
                "severity": "LOW",
                "file_path": "app.py",
                "line_start": 1,
                "line_end": 1,
                "description": "LLM detected an issue.",
                "why_it_matters": "It affects maintainability or runtime behavior.",
                "suggested_fix": "Review and improve the implementation.",
                "agent_source": agent_name,
            }
        ]
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("agent_cls", "agent_name"),
    [
        (PerformanceAgent, "Performance Agent"),
        (QualityAgent, "Quality Agent"),
        (DocsAgent, "Docs Agent"),
    ],
)
async def test_agent_enrichment_disabled_does_not_call_llm(agent_cls, agent_name):
    llm_client = FakeLLMClient(Settings(enable_llm_enrichment=False))
    output = await agent_cls(llm_client).analyze([make_chunk()])

    assert llm_client.calls == 0
    assert output.metadata["llm_enrichment_enabled"] is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("agent_cls", "agent_name"),
    [
        (PerformanceAgent, "Performance Agent"),
        (QualityAgent, "Quality Agent"),
        (DocsAgent, "Docs Agent"),
    ],
)
async def test_agent_enrichment_merges_valid_llm_findings(agent_cls, agent_name):
    llm_client = FakeLLMClient(
        Settings(enable_llm_enrichment=True, max_llm_chunks=1),
        make_payload(agent_name),
    )
    output = await agent_cls(llm_client).analyze([make_chunk()])

    assert llm_client.calls == 1
    assert any(finding.title == f"{agent_name} LLM finding" for finding in output.findings)
    assert output.metadata["llm_findings"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("agent_cls", "agent_name"),
    [
        (PerformanceAgent, "Performance Agent"),
        (QualityAgent, "Quality Agent"),
        (DocsAgent, "Docs Agent"),
    ],
)
async def test_agent_enrichment_failure_is_metadata_not_exception(agent_cls, agent_name):
    llm_client = FakeLLMClient(Settings(enable_llm_enrichment=True), should_fail=True)
    output = await agent_cls(llm_client).analyze([make_chunk()])

    assert "vLLM unavailable" in output.metadata["llm_error"]
