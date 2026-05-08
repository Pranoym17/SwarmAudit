import runpy
from pathlib import Path

import pytest

from app.ui.gradio_app import (
    analyze_repo,
    build_app,
    choose_example,
    launch_app,
    render_workspace_header,
    run_benchmark,
    run_llm_diagnostics,
)


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
    assert "Multi-agent code review workspace" in html
    assert "vLLM" in html


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
async def test_run_llm_diagnostics_returns_provider_status():
    markdown = await run_llm_diagnostics()

    assert "LLM Diagnostics" in markdown
    assert "Provider: `mock`" in markdown
    assert "Status: `OK`" in markdown


@pytest.mark.anyio
async def test_run_benchmark_returns_mock_result():
    markdown = await run_benchmark()

    assert "LLM Benchmark" in markdown
    assert "Provider: `mock`" in markdown
    assert "Status: `OK`" in markdown


@pytest.mark.anyio
async def test_analyze_repo_empty_input_clears_report_exports():
    result = await anext(analyze_repo(" "))

    assert result == ("Paste a public GitHub repository URL to start.", "", None, None)


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
    assert updates[-1][1:] == ("", None, None)
