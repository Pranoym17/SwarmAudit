import pytest

from app.agents.quality_agent import QualityAgent
from app.schemas import CodeChunk, Severity


@pytest.mark.anyio
async def test_quality_agent_flags_todo_comments():
    chunk = CodeChunk(
        file_path="service.py",
        language="Python",
        line_start=12,
        line_end=12,
        content="# TODO: handle retry failures",
    )

    output = await QualityAgent().analyze([chunk])

    assert output.findings[0].title == "Unresolved maintenance comment"
    assert output.findings[0].severity == Severity.low
    assert output.findings[0].line_start == 12


@pytest.mark.anyio
async def test_quality_agent_flags_high_branch_density():
    lines = [f"if condition_{index}:" for index in range(30)]
    chunk = CodeChunk(
        file_path="rules.py",
        language="Python",
        line_start=1,
        line_end=len(lines),
        content="\n".join(lines),
    )

    output = await QualityAgent().analyze([chunk])

    assert output.findings[0].title == "High branching complexity"
    assert output.findings[0].severity == Severity.medium


@pytest.mark.anyio
async def test_quality_agent_flags_long_function():
    lines = ["def process_everything():"]
    lines.extend(f"    value_{index} = {index}" for index in range(85))
    chunk = CodeChunk(
        file_path="processor.py",
        language="Python",
        line_start=30,
        line_end=30 + len(lines) - 1,
        content="\n".join(lines),
    )

    output = await QualityAgent().analyze([chunk])

    assert output.findings[0].title == "Long function or class body"
    assert output.findings[0].severity == Severity.medium
    assert output.findings[0].line_start == 30
