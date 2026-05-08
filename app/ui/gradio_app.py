import os
import warnings

import gradio as gr

from app.agents.graph import AuditGraph
from app.config import get_settings
from app.schemas import AuditReport
from app.services.llm_client import LLMClient
from app.services.benchmark import BenchmarkService
from app.services.report_formatter import format_report_markdown, write_report_exports


EXAMPLE_REPOS = {
    "Requests": "https://github.com/psf/requests",
    "ItsDangerous": "https://github.com/pallets/itsdangerous",
    "Flask": "https://github.com/pallets/flask",
}


APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --sa-bg: #0f1218;
    --sa-surface: #151922;
    --sa-panel: #1a1f2a;
    --sa-panel-high: #222938;
    --sa-border: #303848;
    --sa-border-strong: #465266;
    --sa-text: #eef1f7;
    --sa-muted: #9ea8ba;
    --sa-primary: #b8cdf7;
    --sa-primary-strong: #7fa6eb;
    --sa-accent: #9ac7d8;
    --sa-orange: #e9ad72;
    --sa-red: #e98a84;
    --sa-green: #8fd6a6;
}

.gradio-container {
    background: linear-gradient(180deg, #10141b 0%, #0f1218 100%) !important;
    color: var(--sa-text) !important;
    font-family: Inter, system-ui, sans-serif !important;
}

#swarm-shell {
    max-width: 1420px;
    margin: 0 auto;
}

.swarm-hero {
    border: 1px solid var(--sa-border);
    background: linear-gradient(135deg, rgba(26, 31, 42, 0.98), rgba(18, 22, 30, 0.98));
    border-radius: 8px;
    padding: 20px 22px;
    margin-bottom: 14px;
    box-shadow: 0 12px 42px rgba(0, 0, 0, 0.22);
}

.swarm-kicker {
    color: var(--sa-accent);
    font: 600 12px/18px JetBrains Mono, monospace;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.swarm-title {
    font-size: 30px;
    line-height: 38px;
    font-weight: 700;
    margin: 0;
}

.swarm-subtitle {
    color: var(--sa-muted);
    max-width: 760px;
    margin: 8px 0 0;
    font-size: 14px;
    line-height: 22px;
}

.swarm-metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-top: 18px;
}

.swarm-metric {
    border: 1px solid var(--sa-border);
    background: rgba(21, 25, 34, 0.92);
    border-radius: 6px;
    padding: 12px;
}

.swarm-metric span {
    display: block;
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    text-transform: uppercase;
}

.swarm-metric strong {
    display: block;
    color: var(--sa-text);
    font-size: 18px;
    line-height: 26px;
    margin-top: 2px;
}

.swarm-card,
.swarm-panel,
.swarm-export {
    border: 1px solid var(--sa-border) !important;
    background: rgba(21, 25, 34, 0.94) !important;
    border-radius: 8px !important;
    box-shadow: 0 10px 34px rgba(0, 0, 0, 0.16);
}

.swarm-card textarea,
.swarm-card input,
.swarm-card select {
    font-family: JetBrains Mono, monospace !important;
}

.swarm-progress textarea {
    min-height: 360px !important;
    font-family: JetBrains Mono, monospace !important;
    font-size: 12px !important;
    line-height: 20px !important;
    color: #dce3f1 !important;
}

.swarm-report {
    min-height: 520px;
}

.swarm-report h1,
.swarm-report h2,
.swarm-report h3 {
    color: var(--sa-text) !important;
}

.swarm-report code,
.swarm-report pre {
    font-family: JetBrains Mono, monospace !important;
}

.swarm-export {
    padding: 12px !important;
}

button.primary,
.gradio-button.primary {
    background: #d7e4ff !important;
    color: #121824 !important;
    border: 0 !important;
    font-weight: 700 !important;
    box-shadow: 0 8px 20px rgba(127, 166, 235, 0.16);
}

.tabs {
    border: 1px solid var(--sa-border) !important;
    border-radius: 8px !important;
    background: rgba(15, 18, 24, 0.72) !important;
    padding: 8px !important;
}

.tab-nav button {
    border-radius: 7px !important;
    font-weight: 600 !important;
}

.swarm-note {
    color: var(--sa-muted);
    font-size: 13px;
    line-height: 20px;
    margin: 0 0 10px;
}

.swarm-report a {
    color: var(--sa-primary) !important;
}

.swarm-report blockquote {
    border-left: 3px solid var(--sa-border-strong) !important;
    color: var(--sa-muted) !important;
}

@media (max-width: 900px) {
    .swarm-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .swarm-title {
        font-size: 26px;
        line-height: 34px;
    }
}
"""


def render_workspace_header() -> str:
    return """
    <section class="swarm-hero">
        <div class="swarm-kicker">Multi-agent code review workspace</div>
        <h1 class="swarm-title">SwarmAudit</h1>
        <p class="swarm-subtitle">
            Paste a public GitHub repository and launch a coordinated audit across security,
            performance, quality, documentation, and synthesis agents. Built for a mock-first
            demo path, with a vLLM/Qwen endpoint ready for AMD MI300X.
        </p>
        <div class="swarm-metrics">
            <div class="swarm-metric"><span>Mode</span><strong>Mock-first</strong></div>
            <div class="swarm-metric"><span>Agents</span><strong>5 active</strong></div>
            <div class="swarm-metric"><span>Output</span><strong>MD + JSON</strong></div>
            <div class="swarm-metric"><span>vLLM</span><strong>Ready</strong></div>
        </div>
    </section>
    """


async def analyze_repo(repo_url: str):
    if not repo_url.strip():
        yield "Paste a public GitHub repository URL to start.", "", None, None
        return

    progress: list[str] = []
    report_markdown = ""
    markdown_export = None
    json_export = None
    try:
        async for event in AuditGraph().run_with_progress(repo_url.strip()):
            if isinstance(event, AuditReport):
                report_markdown = format_report_markdown(event)
                markdown_export, json_export = write_report_exports(event)
            else:
                progress.append(event)
            yield "\n".join(progress), report_markdown, markdown_export, json_export
    except Exception as exc:
        progress.append(f"Audit failed: {exc}")
        yield "\n".join(progress), "", None, None


def choose_example(example_name: str) -> str:
    return EXAMPLE_REPOS.get(example_name, "")


async def run_llm_diagnostics() -> str:
    health = await LLMClient(get_settings()).health_check()
    lines = [
        "# LLM Diagnostics",
        "",
        f"- Provider: `{health.provider}`",
        f"- Model: `{health.model}`",
        f"- Base URL: `{health.base_url}`",
        f"- Status: `{'OK' if health.ok else 'FAILED'}`",
    ]

    if health.latency_ms is not None:
        lines.append(f"- Latency: `{health.latency_ms} ms`")
    if health.models:
        lines.extend(["", "## Models", ""])
        lines.extend(f"- `{model}`" for model in health.models)
    if health.completion_preview:
        lines.extend(["", "## Completion Preview", "", health.completion_preview])
    if health.error:
        lines.extend(["", "## Error", "", f"```text\n{health.error}\n```"])

    return "\n".join(lines)


async def run_benchmark() -> str:
    result = await BenchmarkService(get_settings()).run_llm_benchmark()
    lines = [
        "# LLM Benchmark",
        "",
        f"- Provider: `{result.provider}`",
        f"- Backend: `{result.backend}`",
        f"- Model: `{result.model}`",
        f"- Hardware: `{result.hardware}`",
        f"- Status: `{'OK' if result.ok else 'FAILED'}`",
        f"- Prompt chars: `{result.prompt_chars}`",
        f"- Completion chars: `{result.completion_chars}`",
    ]

    if result.latency_ms is not None:
        lines.append(f"- Latency: `{result.latency_ms} ms`")
    if result.chars_per_second is not None:
        lines.append(f"- Approx chars/sec: `{result.chars_per_second}`")
    if result.completion_preview:
        lines.extend(["", "## Completion Preview", "", result.completion_preview])
    if result.error:
        lines.extend(["", "## Error", "", f"```text\n{result.error}\n```"])

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This scaffold uses character counts until a real vLLM endpoint exposes token usage. "
            "When running on AMD MI300X, record latency/tokens-per-second here for the final demo.",
        ]
    )
    return "\n".join(lines)


def build_app() -> gr.Blocks:
    theme = gr.themes.Base(
        primary_hue="blue",
        secondary_hue="cyan",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
        font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "monospace"],
    )

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The parameters have been moved from the Blocks constructor to the launch.*",
            category=UserWarning,
        )
        with gr.Blocks(title="SwarmAudit", theme=theme, css=APP_CSS, elem_id="swarm-shell") as demo:
            gr.HTML(render_workspace_header())

            with gr.Tab("Audit"):
                gr.Markdown(
                    "Run a repository audit and export the final report for your demo package.",
                    elem_classes=["swarm-note"],
                )
                with gr.Row(elem_classes=["swarm-card"]):
                    repo_url = gr.Textbox(
                        label="GitHub Repository URL",
                        placeholder="https://github.com/owner/repo",
                        scale=4,
                    )
                    analyze = gr.Button("Analyze", variant="primary", scale=1)

                example = gr.Radio(
                    label="Fast demo repos",
                    choices=list(EXAMPLE_REPOS.keys()),
                    value=None,
                    interactive=True,
                    elem_classes=["swarm-card"],
                )
                example.change(choose_example, inputs=example, outputs=repo_url)

                with gr.Row():
                    with gr.Column(scale=1):
                        progress_output = gr.Textbox(
                            label="Agent Mesh Progress",
                            lines=16,
                            interactive=False,
                            elem_classes=["swarm-panel", "swarm-progress"],
                        )
                    with gr.Column(scale=2):
                        report_output = gr.Markdown(
                            label="Audit Report",
                            elem_classes=["swarm-panel", "swarm-report"],
                        )

                with gr.Row(elem_classes=["swarm-export"]):
                    markdown_export = gr.File(label="Markdown Report")
                    json_export = gr.File(label="JSON Report")

                analyze.click(
                    analyze_repo,
                    inputs=repo_url,
                    outputs=[progress_output, report_output, markdown_export, json_export],
                )

            with gr.Tab("Diagnostics"):
                gr.Markdown(
                    "Verify the configured LLM backend before switching from mock mode to AMD/vLLM enrichment.",
                    elem_classes=["swarm-note"],
                )
                diagnostics_button = gr.Button("Test LLM Connection", variant="primary")
                diagnostics_output = gr.Markdown(elem_classes=["swarm-panel"])
                diagnostics_button.click(run_llm_diagnostics, outputs=diagnostics_output)

            with gr.Tab("Benchmark"):
                gr.Markdown(
                    "Run a small timing probe. Mock mode validates the UI path; vLLM mode records MI300X demo numbers.",
                    elem_classes=["swarm-note"],
                )
                benchmark_button = gr.Button("Run Benchmark", variant="primary")
                benchmark_output = gr.Markdown(elem_classes=["swarm-panel"])
                benchmark_button.click(run_benchmark, outputs=benchmark_output)
    return demo


def launch_app() -> None:
    server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
    server_port = int(os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "7860")))
    build_app().queue().launch(server_name=server_name, server_port=server_port)


if __name__ == "__main__":
    launch_app()
