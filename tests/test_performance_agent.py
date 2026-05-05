import pytest

from app.agents.performance_agent import PerformanceAgent
from app.schemas import CodeChunk, Severity


@pytest.mark.anyio
async def test_performance_agent_flags_requests_without_timeout():
    chunk = CodeChunk(
        file_path="client.py",
        language="Python",
        line_start=1,
        line_end=1,
        content="response = requests.get(url)",
    )

    output = await PerformanceAgent().analyze([chunk])

    assert output.findings[0].title == "HTTP request without timeout"
    assert output.findings[0].severity == Severity.medium


@pytest.mark.anyio
async def test_performance_agent_flags_blocking_sleep_in_async_function():
    chunk = CodeChunk(
        file_path="worker.py",
        language="Python",
        line_start=20,
        line_end=22,
        content="async def run():\n    time.sleep(1)\n    return True",
    )

    output = await PerformanceAgent().analyze([chunk])

    assert output.findings[0].title == "Blocking sleep inside async function"
    assert output.findings[0].line_start == 21


@pytest.mark.anyio
async def test_performance_agent_flags_nested_loop():
    chunk = CodeChunk(
        file_path="search.py",
        language="Python",
        line_start=5,
        line_end=7,
        content="for user in users:\n    for order in orders:\n        match(user, order)",
    )

    output = await PerformanceAgent().analyze([chunk])

    assert output.findings[0].title == "Nested loop may become expensive"
    assert output.findings[0].line_start == 6
