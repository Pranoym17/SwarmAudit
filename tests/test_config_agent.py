import pytest

from app.agents.config_agent import ConfigAgent
from app.schemas import CodeChunk, Severity


def make_chunk(content: str, file_path: str = "config.py") -> CodeChunk:
    return CodeChunk(
        file_path=file_path,
        language="Python",
        line_start=1,
        line_end=max(1, len(content.splitlines())),
        content=content,
    )


@pytest.mark.anyio
async def test_config_agent_detects_debug_mode():
    output = await ConfigAgent().analyze([make_chunk("DEBUG = True")])

    assert output.findings[0].title == "Debug mode enabled"
    assert output.findings[0].severity == Severity.high
    assert output.findings[0].category == "config"
    assert output.findings[0].confidence is not None


@pytest.mark.anyio
async def test_config_agent_detects_wildcard_cors():
    output = await ConfigAgent().analyze([make_chunk('allow_origins=["*"]')])

    assert output.findings[0].title == "Wildcard CORS origin"
    assert output.findings[0].severity == Severity.medium


@pytest.mark.anyio
async def test_config_agent_detects_disabled_tls_verification():
    output = await ConfigAgent().analyze([make_chunk("session.verify = False")])

    assert output.findings[0].title == "TLS verification disabled in configuration"
    assert output.findings[0].severity == Severity.high


@pytest.mark.anyio
async def test_config_agent_detects_weak_default_secret():
    output = await ConfigAgent().analyze([make_chunk("SECRET_KEY = 'django-insecure-demo'")])

    assert output.findings[0].title == "Weak default secret configured"
    assert output.findings[0].severity == Severity.high


@pytest.mark.anyio
async def test_config_agent_returns_empty_output_for_clean_config():
    output = await ConfigAgent().analyze([make_chunk("DEBUG = env.bool('DEBUG', default=False)")])

    assert output.findings == []
    assert output.metadata["mode"] == "static-rules"
