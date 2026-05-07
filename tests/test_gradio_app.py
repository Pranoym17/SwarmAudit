import runpy
from pathlib import Path

import pytest

from app.ui.gradio_app import build_app, choose_example, launch_app, run_benchmark, run_llm_diagnostics


def test_choose_example_returns_repo_url():
    assert choose_example("Requests") == "https://github.com/psf/requests"


def test_choose_example_returns_empty_string_for_unknown_choice():
    assert choose_example("Unknown") == ""


def test_build_app_creates_gradio_blocks():
    demo = build_app()

    assert demo is not None


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
