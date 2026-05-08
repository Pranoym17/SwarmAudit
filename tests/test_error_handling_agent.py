import pytest

from app.agents.error_handling_agent import ErrorHandlingAgent
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
async def test_error_handling_agent_detects_bare_except_and_swallow():
    output = await ErrorHandlingAgent().analyze(
        [
            make_chunk(
                "try:\n"
                "    work()\n"
                "except:\n"
                "    pass\n"
            )
        ]
    )

    titles = {finding.title for finding in output.findings}
    assert "Broad exception handler" in titles
    assert "Exception swallowed without recovery" in titles
    assert all(finding.category == "error_handling" for finding in output.findings)


@pytest.mark.anyio
async def test_error_handling_agent_detects_return_none_swallow():
    output = await ErrorHandlingAgent().analyze(
        [
            make_chunk(
                "try:\n"
                "    return load_user()\n"
                "except ValueError:\n"
                "    return None\n"
            )
        ]
    )

    assert output.findings[0].title == "Exception swallowed without recovery"
    assert output.findings[0].severity == Severity.high


@pytest.mark.anyio
async def test_error_handling_agent_does_not_flag_logged_specific_exception():
    output = await ErrorHandlingAgent().analyze(
        [
            make_chunk(
                "try:\n"
                "    return load_user()\n"
                "except ValueError:\n"
                "    logger.exception('load failed')\n"
                "    raise\n"
            )
        ]
    )

    assert output.findings == []


@pytest.mark.anyio
async def test_error_handling_agent_detects_request_without_timeout():
    output = await ErrorHandlingAgent().analyze([make_chunk("response = requests.get(url)")])

    assert output.findings[0].title == "External HTTP call without timeout"
    assert output.findings[0].severity == Severity.medium


@pytest.mark.anyio
async def test_error_handling_agent_ignores_request_with_timeout():
    output = await ErrorHandlingAgent().analyze([make_chunk("response = requests.get(url, timeout=10)")])

    assert output.findings == []
