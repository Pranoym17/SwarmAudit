from pathlib import Path

import pytest

from app.agents.graph import AuditGraph
from app.config import Settings
from app.schemas import AuditReport


def test_audit_graph_exposes_current_agents_through_registry():
    graph = AuditGraph(Settings())

    assert [spec.node_name for spec in graph.analysis_agents] == ["security", "performance", "quality", "docs", "config"]
    assert [spec.state_key for spec in graph.analysis_agents] == [
        "security_output",
        "performance_output",
        "quality_output",
        "docs_output",
        "config_output",
    ]
    assert [spec.agent.name for spec in graph.analysis_agents] == [
        "Security Agent",
        "Performance Agent",
        "Quality Agent",
        "Docs Agent",
        "Config Agent",
    ]


@pytest.mark.anyio
async def test_run_with_progress_yields_real_stages_and_report(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("API_KEY = '1234567890abcdef'\nresponse = requests.get(url)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# Demo\n\n## Quick Start\nInstall and run it.\n## Tests\nRun pytest.\n## Configuration\nCopy .env.example.",
        encoding="utf-8",
    )
    graph = AuditGraph(Settings(max_files=10, max_file_size_kb=10, max_chars_per_chunk=1000))

    graph.crawler.clone_and_scan = lambda repo_url: graph.crawler.scan_local_repo(repo_url, tmp_path)
    graph.crawler.cleanup = lambda scan_result: None

    events = []
    async for event in graph.run_with_progress("https://github.com/example/project"):
        events.append(event)

    assert any("Crawler Agent" in event for event in events if isinstance(event, str))
    assert any("Security Agent" in event for event in events if isinstance(event, str))
    assert any("Performance Agent" in event for event in events if isinstance(event, str))
    assert any("Quality Agent" in event for event in events if isinstance(event, str))
    assert any("Docs Agent" in event for event in events if isinstance(event, str))
    assert any("Config Agent" in event for event in events if isinstance(event, str))
    assert isinstance(events[-1], AuditReport)
    assert len(events[-1].findings) == 2
    assert "Security Agent" in events[-1].agents_run
    assert "Performance Agent" in events[-1].agents_run
    assert "Quality Agent" in events[-1].agents_run
    assert "Docs Agent" in events[-1].agents_run
    assert "Config Agent" in events[-1].agents_run
