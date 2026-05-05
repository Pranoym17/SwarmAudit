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
    output = await SecurityAgent(LLMClient(Settings())).analyze([chunk])
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, [output])

    assert len(report.findings) == 1
    assert report.findings[0].severity == Severity.high
    assert report.findings[0].file_path == "app.py"
    assert report.findings[0].line_start == 10
    assert report.severity_summary[Severity.high] == 1
