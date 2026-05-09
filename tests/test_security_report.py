import pytest

from app.agents.security_agent import SecurityAgent
from app.agents.synthesizer_agent import SynthesizerAgent
from app.config import Settings
from app.schemas import CodeChunk, RepoScanResult, Severity
from app.services.llm_client import LLMClient


@pytest.mark.anyio
async def test_security_agent_and_synthesizer_return_structured_report():
    chunk = CodeChunk(
        file_path="app.py",
        language="Python",
        line_start=10,
        line_end=10,
        content="API_KEY = '1234567890abcdef'",
    )
    output = await SecurityAgent(LLMClient(Settings(enable_llm_enrichment=False))).analyze([chunk])
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, [output])

    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.high
    assert report.findings[0].file_path == "app.py"
    assert report.findings[0].line_start == 10
    assert report.severity_summary[Severity.high] == 1
    assert report.total_findings_count == 1
    assert report.displayed_findings_count == 1
    assert report.hidden_findings_count == 0


class FakeLLMClient(LLMClient):
    def __init__(self, settings: Settings, payload):
        super().__init__(settings)
        self.payload = payload
        self.calls = 0

    async def complete_json(self, system_prompt: str, user_prompt: str):
        self.calls += 1
        return self.payload


@pytest.mark.anyio
async def test_security_agent_does_not_call_llm_when_enrichment_disabled():
    llm_client = FakeLLMClient(Settings(enable_llm_enrichment=False), {"findings": []})
    chunk = CodeChunk(file_path="app.py", language="Python", line_start=1, line_end=1, content="print('ok')")

    output = await SecurityAgent(llm_client).analyze([chunk])

    assert llm_client.calls == 0
    assert output.metadata["llm_enrichment_enabled"] is False


@pytest.mark.anyio
async def test_security_agent_merges_valid_llm_findings_when_enabled():
    llm_client = FakeLLMClient(
        Settings(enable_llm_enrichment=True, max_llm_chunks=1),
        {
            "findings": [
                {
                    "title": "LLM detected command injection",
                    "severity": "HIGH",
                    "file_path": "app.py",
                    "line_start": 2,
                    "line_end": 2,
                    "description": "User input reaches a shell command.",
                    "why_it_matters": "Attackers could execute arbitrary commands.",
                    "suggested_fix": "Avoid shell=True and pass argument lists.",
                    "agent_source": "Security Agent",
                }
            ]
        },
    )
    chunk = CodeChunk(file_path="app.py", language="Python", line_start=1, line_end=2, content="run(user_input)")

    output = await SecurityAgent(llm_client).analyze([chunk])

    assert llm_client.calls == 1
    assert output.findings[0].title == "LLM detected command injection"
    assert output.metadata["llm_findings"] == 1


@pytest.mark.anyio
async def test_security_agent_survives_llm_failure_when_enabled():
    class FailingLLMClient(FakeLLMClient):
        async def complete_json(self, system_prompt: str, user_prompt: str):
            raise RuntimeError("vLLM unavailable")

    llm_client = FailingLLMClient(Settings(enable_llm_enrichment=True), {})
    chunk = CodeChunk(file_path="app.py", language="Python", line_start=1, line_end=1, content="print('ok')")

    output = await SecurityAgent(llm_client).analyze([chunk])

    assert output.findings == []
    assert "vLLM unavailable" in output.metadata["llm_error"]
