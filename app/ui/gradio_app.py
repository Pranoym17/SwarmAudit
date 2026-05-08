import os

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
    with gr.Blocks(title="SwarmAudit") as demo:
        gr.Markdown(
            "# SwarmAudit\n"
            "Paste a public GitHub URL and get a structured multi-agent audit report."
        )

        with gr.Tab("Audit"):
            with gr.Row():
                repo_url = gr.Textbox(
                    label="GitHub Repository URL",
                    placeholder="https://github.com/owner/repo",
                    scale=4,
                )
                analyze = gr.Button("Analyze", variant="primary", scale=1)

            example = gr.Dropdown(
                label="Example repos",
                choices=list(EXAMPLE_REPOS.keys()),
                value=None,
                interactive=True,
            )
            example.change(choose_example, inputs=example, outputs=repo_url)

            with gr.Row():
                progress_output = gr.Textbox(
                    label="Agent Progress",
                    lines=10,
                    interactive=False,
                )
                report_output = gr.Markdown(label="Audit Report")

            with gr.Row():
                markdown_export = gr.File(label="Download Markdown Report")
                json_export = gr.File(label="Download JSON Report")

            analyze.click(
                analyze_repo,
                inputs=repo_url,
                outputs=[progress_output, report_output, markdown_export, json_export],
            )

        with gr.Tab("Diagnostics"):
            gr.Markdown("Check the configured LLM backend before switching from mock mode to vLLM.")
            diagnostics_button = gr.Button("Test LLM Connection", variant="primary")
            diagnostics_output = gr.Markdown()
            diagnostics_button.click(run_llm_diagnostics, outputs=diagnostics_output)

        with gr.Tab("Benchmark"):
            gr.Markdown("Run a small LLM timing probe. In mock mode this validates the benchmark UI; in vLLM mode it measures endpoint latency.")
            benchmark_button = gr.Button("Run Benchmark", variant="primary")
            benchmark_output = gr.Markdown()
            benchmark_button.click(run_benchmark, outputs=benchmark_output)
    return demo


def launch_app() -> None:
    server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
    server_port = int(os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "7860")))
    build_app().queue().launch(server_name=server_name, server_port=server_port)


if __name__ == "__main__":
    launch_app()
