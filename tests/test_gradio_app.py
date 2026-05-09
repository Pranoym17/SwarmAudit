import runpy
from pathlib import Path

import pytest

from app.ui.gradio_app import (
    analyze_repo,
    build_app,
    build_finding_choices,
    build_finding_rows,
    choose_example,
    launch_app,
    render_agent_swarm,
    render_empty_summary,
    render_report_toolbar,
    render_report_summary,
    render_workspace_header,
    run_benchmark,
    run_llm_diagnostics,
    select_finding,
)
from app.schemas import AuditReport, Finding, Severity


def test_choose_example_returns_repo_url():
    assert choose_example("Requests") == "https://github.com/psf/requests"


def test_choose_example_returns_empty_string_for_unknown_choice():
    assert choose_example("Unknown") == ""


def test_build_app_creates_gradio_blocks():
    demo = build_app()

    assert demo is not None


def test_render_workspace_header_contains_product_and_readiness_signals():
    html = render_workspace_header()

    assert "SwarmAudit" in html
    assert "production-readiness scanner" in html
    assert "vLLM" in html


def test_render_empty_summary_contains_placeholder_cards():
    html = render_empty_summary()

    assert "Files scanned" in html
    assert "<strong>-</strong>" in html


def test_render_agent_swarm_contains_current_agent_panel():
    html = render_agent_swarm()

    assert "Agent swarm" in html
    assert "Synthesizer" in html
    assert "idle" in html


def test_render_agent_swarm_tracks_running_and_done_states():
    html = render_agent_swarm(
        [
            "Crawler Agent: cloning and mapping repository...",
            "Crawler Agent: mapped 4 files and skipped 1.",
            "Chunker: filtering source files and creating chunks...",
        ]
    )

    assert "1/12 done" in html
    assert '<div class="agent-item done">' in html
    assert '<div class="agent-item running">' in html


def test_render_report_summary_uses_report_counts():
    report = AuditReport(
        repo_url="https://github.com/example/project",
        scanned_file_count=4,
        skipped_file_count=1,
        findings=[],
        severity_summary={
            Severity.critical: 1,
            Severity.high: 2,
            Severity.medium: 3,
            Severity.low: 4,
        },
        total_findings_count=10,
        security_score=76,
        production_score=84,
        category_summary={"security": 3},
        remediation_roadmap={"this_week": [], "next_sprint": [], "backlog": []},
        agents_run=["Synthesizer Agent"],
    )

    html = render_report_summary(report)

    assert "Files scanned" in html
    assert "<strong>4</strong>" in html
    assert "<strong>10</strong>" in html
    assert "metric-critical" in html


def test_render_report_toolbar_uses_actual_severity_counts():
    report = AuditReport(
        repo_url="https://github.com/example/project",
        scanned_file_count=4,
        skipped_file_count=1,
        findings=[],
        severity_summary={
            Severity.critical: 1,
            Severity.high: 2,
            Severity.medium: 0,
            Severity.low: 0,
        },
        displayed_findings_count=3,
        security_score=76,
        production_score=84,
        category_summary={"security": 3},
        remediation_roadmap={"this_week": [1], "next_sprint": [], "backlog": []},
        agents_run=["Synthesizer Agent"],
    )

    html = render_report_toolbar(report)

    assert "Audit report" in html
    assert "All 3" in html
    assert "Critical 1" in html
    assert "High 2" in html
    assert "Security Score" in html
    assert "76/100" in html
    assert "Production Readiness" in html
    assert "Security: 3" in html
    assert "This Week: 1" in html


def make_report_with_findings() -> AuditReport:
    finding = Finding(
        title="Missing timeout",
        severity=Severity.medium,
        file_path="app.py",
        line_start=10,
        line_end=10,
        description="HTTP request has no timeout.",
        why_it_matters="Requests can hang indefinitely.",
        suggested_fix="Pass timeout=10.",
        agent_source="Performance Agent",
        category="performance",
    )
    return AuditReport(
        repo_url="https://github.com/example/project",
        scanned_file_count=1,
        skipped_file_count=0,
        findings=[finding],
        severity_summary={
            Severity.critical: 0,
            Severity.high: 0,
            Severity.medium: 1,
            Severity.low: 0,
        },
        total_findings_count=1,
        displayed_findings_count=1,
        agents_run=["Performance Agent"],
    )


def test_build_finding_rows_uses_actual_report_findings():
    rows = build_finding_rows(make_report_with_findings())

    assert rows == [["F-001", "MEDIUM", "Missing timeout", "app.py:10", "Performance Agent"]]


def test_build_finding_choices_uses_actual_report_findings():
    choices = build_finding_choices(make_report_with_findings())

    assert choices == ["F-001  [MEDIUM]  Missing timeout\napp.py:10  |  Performance Agent"]


def test_select_finding_renders_selected_actual_finding():
    choices = build_finding_choices(make_report_with_findings())

    html = select_finding(choices[0], make_report_with_findings())

    assert "Missing timeout" in html
    assert "Pass timeout=10." in html


def test_root_app_py_exposes_demo_for_spaces():
    namespace = runpy.run_path(str(Path(__file__).parents[1] / "app.py"))

    assert "demo" in namespace


def test_launch_app_uses_spaces_friendly_defaults(monkeypatch):
    calls = {}

    class FakeQueuedApp:
        def launch(self, **kwargs):
            calls.update(kwargs)

    class FakeApp:
        def queue(self):
            return FakeQueuedApp()

    monkeypatch.setattr("app.ui.gradio_app.build_app", lambda: FakeApp())
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("GRADIO_SERVER_PORT", raising=False)
    monkeypatch.delenv("GRADIO_SERVER_NAME", raising=False)

    launch_app()

    assert calls == {"server_name": "0.0.0.0", "server_port": 7860}


@pytest.mark.anyio
async def test_run_llm_diagnostics_returns_provider_status(monkeypatch):
    monkeypatch.setattr(
        "app.ui.gradio_app.get_settings",
        lambda: __import__("app.config").config.Settings(llm_provider="mock"),
    )

    markdown = await run_llm_diagnostics()

    assert "LLM Diagnostics" in markdown
    assert "Provider: `mock`" in markdown
    assert "Status: `OK`" in markdown


@pytest.mark.anyio
async def test_run_benchmark_returns_mock_result(monkeypatch):
    monkeypatch.setattr(
        "app.ui.gradio_app.get_settings",
        lambda: __import__("app.config").config.Settings(llm_provider="mock"),
    )

    markdown = await run_benchmark()

    assert "LLM Benchmark" in markdown
    assert "Provider: `mock`" in markdown
    assert "Status: `OK`" in markdown


@pytest.mark.anyio
async def test_analyze_repo_empty_input_clears_report_exports():
    result = await anext(analyze_repo(" "))

    assert result[0] == "Paste a public GitHub repository URL to start."
    assert "Agent swarm" in result[1]
    assert "Files scanned" in result[2]
    assert "Audit report" in result[3]
    assert result[4]["choices"] == []
    assert result[4]["value"] is None
    assert "Select a finding" in result[5]
    assert result[6:] == (None, None, None)


@pytest.mark.anyio
async def test_analyze_repo_failure_clears_report_exports(monkeypatch):
    class FakeAuditGraph:
        async def run_with_progress(self, repo_url: str):
            yield "Crawler Agent: cloning and mapping repository..."
            raise RuntimeError("clone failed")

    monkeypatch.setattr("app.ui.gradio_app.AuditGraph", FakeAuditGraph)

    updates = []
    async for update in analyze_repo("https://github.com/example/project"):
        updates.append(update)

    assert updates[-1][0].endswith("Audit failed: clone failed")
    assert "Agent swarm" in updates[-1][1]
    assert "Files scanned" in updates[-1][2]
    assert "Audit report" in updates[-1][3]
    assert updates[-1][4]["choices"] == []
    assert updates[-1][4]["value"] is None
    assert "Select a finding" in updates[-1][5]
    assert updates[-1][6:] == (None, None, None)
