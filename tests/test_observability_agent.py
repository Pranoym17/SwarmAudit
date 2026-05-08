import pytest

from app.agents.observability_agent import ObservabilityAgent
from app.schemas import CodeChunk, Severity


def make_chunk(content: str, file_path: str = "app.py") -> CodeChunk:
    return CodeChunk(
        file_path=file_path,
        language="Python",
        line_start=1,
        line_end=max(1, len(content.splitlines())),
        content=content,
    )


@pytest.mark.anyio
async def test_observability_agent_detects_sensitive_logging():
    output = await ObservabilityAgent().analyze([make_chunk("print(f'password={password}')")])

    assert output.findings[0].title == "Sensitive value may be written to logs"
    assert output.findings[0].severity == Severity.high
    assert output.findings[0].category == "observability"


@pytest.mark.anyio
async def test_observability_agent_detects_print_overuse_without_logger():
    output = await ObservabilityAgent().analyze(
        [
            make_chunk(
                "print('start')\n"
                "print('middle')\n"
                "print('done')\n"
            )
        ]
    )

    assert output.findings[0].title == "Print statements used instead of structured logging"
    assert output.findings[0].severity == Severity.low


@pytest.mark.anyio
async def test_observability_agent_does_not_flag_prints_when_logger_exists():
    output = await ObservabilityAgent().analyze(
        [
            make_chunk("print('start')\nprint('middle')\nprint('done')\n"),
            make_chunk("logger.info('service started')", "logging_setup.py"),
        ]
    )

    assert output.findings == []


@pytest.mark.anyio
async def test_observability_agent_detects_missing_health_route():
    output = await ObservabilityAgent().analyze(
        [
            make_chunk(
                "@app.get('/users')\n"
                "def users():\n"
                "    return []\n"
            )
        ]
    )

    assert output.findings[0].title == "Web service has routes but no health endpoint detected"
    assert output.findings[0].severity == Severity.medium


@pytest.mark.anyio
async def test_observability_agent_accepts_existing_health_route():
    output = await ObservabilityAgent().analyze(
        [
            make_chunk(
                "@app.get('/users')\n"
                "def users():\n"
                "    return []\n"
                "@app.get('/health')\n"
                "def health():\n"
                "    return {'ok': True}\n"
            )
        ]
    )

    assert output.findings == []
