import pytest

from app.agents.docs_agent import DocsAgent
from app.schemas import CodeChunk, Severity


@pytest.mark.anyio
async def test_docs_agent_flags_incomplete_readme():
    chunk = CodeChunk(
        file_path="README.md",
        language="Markdown",
        line_start=1,
        line_end=2,
        content="# Demo\nShort description only.",
    )

    output = await DocsAgent().analyze([chunk])

    titles = {finding.title for finding in output.findings}
    assert "README missing usage/setup guidance" in titles
    assert "README missing test instructions" in titles
    assert "README missing configuration notes" in titles


@pytest.mark.anyio
async def test_docs_agent_accepts_useful_readme():
    chunk = CodeChunk(
        file_path="README.md",
        language="Markdown",
        line_start=1,
        line_end=6,
        content="# Demo\n\n## Quick Start\nInstall and run it.\n## Tests\nRun pytest.\n## Configuration\nCopy .env.example.",
    )

    output = await DocsAgent().analyze([chunk])

    assert output.findings == []


@pytest.mark.anyio
async def test_docs_agent_flags_public_python_symbol_without_docstring():
    chunk = CodeChunk(
        file_path="service.py",
        language="Python",
        line_start=10,
        line_end=12,
        content="def run_audit():\n    return True",
    )

    output = await DocsAgent().analyze([chunk])

    assert output.findings[0].title == "Public Python symbol missing docstring"
    assert output.findings[0].severity == Severity.low
    assert output.findings[0].line_start == 10
