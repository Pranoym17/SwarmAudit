import gradio as gr

from app.agents.graph import AuditGraph
from app.schemas import AuditReport
from app.services.report_formatter import format_report_markdown


async def analyze_repo(repo_url: str):
    if not repo_url.strip():
        yield "Paste a public GitHub repository URL to start."
        return

    transcript: list[str] = []
    try:
        async for event in AuditGraph().run_with_progress(repo_url.strip()):
            if isinstance(event, AuditReport):
                transcript.append("")
                transcript.append(format_report_markdown(event))
            else:
                transcript.append(event)
            yield "\n".join(transcript)
    except Exception as exc:
        transcript.append(f"Audit failed: {exc}")
        yield "\n".join(transcript)


def build_app() -> gr.Blocks:
    with gr.Blocks(title="SwarmAudit") as demo:
        gr.Markdown("# SwarmAudit")
        gr.Markdown("Paste any public GitHub URL. Get a structured AI code review in minutes.")
        repo_url = gr.Textbox(
            label="GitHub Repository URL",
            placeholder="https://github.com/owner/repo",
        )
        analyze = gr.Button("Analyze")
        output = gr.Markdown(label="Audit Report")
        analyze.click(analyze_repo, inputs=repo_url, outputs=output)
    return demo


if __name__ == "__main__":
    build_app().queue().launch()
