import os
import warnings

import gradio as gr

from app.agents.graph import AuditGraph
from app.config import get_settings
from app.schemas import AuditReport, Severity
from app.services.llm_client import LLMClient
from app.services.benchmark import BenchmarkService
from app.services.report_formatter import (
    format_empty_finding_detail_html,
    format_finding_detail_html,
    format_report_overview_html,
    write_report_exports,
)


EXAMPLE_REPOS = {
    "Requests": "https://github.com/psf/requests",
    "ItsDangerous": "https://github.com/pallets/itsdangerous",
    "Flask": "https://github.com/pallets/flask",
}

AGENT_SWARM = [
    ("Crawler", "Fetch repository tree", "Crawler Agent", "mapped"),
    ("Chunker", "Tokenize and segment files", "Chunker", "created"),
    ("Security", "CVE and secret scanning", "Security Agent", "found"),
    ("Performance", "Hot-path and complexity", "Performance Agent", "found"),
    ("Quality", "Lint, types, smells", "Quality Agent", "found"),
    ("Docs", "Coverage and accuracy", "Docs Agent", "found"),
    ("Config", "Production config risk", "Config Agent", "found"),
    ("Dependency", "Manifest and CVE checks", "Dependency Agent", "found"),
    ("Errors", "Resilience paths", "Error Handling Agent", "found"),
    ("Observability", "Logs and health checks", "Observability Agent", "found"),
    ("ROCm", "CUDA portability", "CUDA-to-ROCm Agent", "found"),
    ("Synthesizer", "Merge findings into report", "Synthesizer Agent", "final report"),
]


APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --sa-bg: #0d1117;
    --sa-surface: #111820;
    --sa-panel: #161d26;
    --sa-panel-high: #1d2631;
    --sa-border: #2b3542;
    --sa-border-strong: #3d4a5c;
    --sa-text: #f2f5f8;
    --sa-muted: #99a6b8;
    --sa-primary: #9db2c7;
    --sa-primary-soft: #1b2733;
    --sa-blue: #7aaac2;
    --sa-orange: #c48a57;
    --sa-yellow: #c5aa55;
    --sa-red: #c86872;
    --sa-green: #8bbf9a;
    --sa-card-shadow: 0 18px 70px rgba(0, 0, 0, 0.2);
}

.gradio-container {
    background: #0d1117 !important;
    color: var(--sa-text) !important;
    font-family: Inter, system-ui, sans-serif !important;
}

#swarm-shell {
    max-width: 1440px;
    margin: 0 auto;
}

.swarm-topbar {
    border: 1px solid var(--sa-border);
    background: #111820;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
}

.swarm-brand-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 10px;
}

.swarm-brand {
    font-size: 18px;
    line-height: 24px;
    font-weight: 700;
    letter-spacing: 0;
}

.swarm-tagline {
    color: var(--sa-muted);
    font-size: 12px;
    line-height: 18px;
}

.swarm-status {
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    text-transform: uppercase;
}

.swarm-progressbar {
    height: 4px;
    border-radius: 999px;
    background: #22303c;
    overflow: hidden;
}

.swarm-progressbar span {
    display: block;
    width: 100%;
    height: 100%;
    background: var(--sa-primary);
}

.swarm-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
    margin: 12px 0;
}

.swarm-metric {
    border: 1px solid var(--sa-border);
    background: #111820;
    border-radius: 6px;
    padding: 12px;
}

.swarm-metric span {
    display: block;
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    text-transform: uppercase;
    letter-spacing: 0;
}

.swarm-metric strong {
    display: block;
    color: var(--sa-text);
    font-size: 22px;
    line-height: 28px;
    margin-top: 2px;
}

.metric-critical strong,
.metric-critical span {
    color: var(--sa-red);
}

.metric-high strong,
.metric-high span {
    color: var(--sa-orange);
}

.metric-medium strong,
.metric-medium span {
    color: var(--sa-yellow);
}

.metric-low strong,
.metric-low span {
    color: var(--sa-blue);
}

.swarm-card,
.swarm-panel,
.swarm-export {
    border: 1px solid var(--sa-border) !important;
    background: #111820 !important;
    border-radius: 7px !important;
    box-shadow: none;
}

.agent-card {
    border: 1px solid var(--sa-border);
    background: #111820;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 12px;
}

.agent-card-header,
.audit-console-header {
    min-height: 42px;
    border-bottom: 1px solid var(--sa-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
}

.agent-card-title,
.audit-console-title {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 18px;
    font-weight: 700;
}

.agent-card-count,
.audit-filter-row {
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
}

.agent-list {
    padding: 12px 14px 14px;
}

.agent-item {
    display: grid;
    grid-template-columns: 28px 1fr auto;
    gap: 10px;
    align-items: center;
    padding: 8px 0;
}

.agent-icon {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: 1px solid var(--sa-border);
    background: #1b2430;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--sa-muted);
    font: 700 11px/16px JetBrains Mono, monospace;
}

.agent-name {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 18px;
    font-weight: 700;
}

.agent-desc {
    color: var(--sa-muted);
    font-size: 11px;
    line-height: 16px;
}

.agent-status {
    font: 600 11px/16px JetBrains Mono, monospace;
}

.agent-status.done {
    color: var(--sa-green);
}

.agent-status.running {
    color: var(--sa-primary);
}

.agent-status.idle {
    color: var(--sa-muted);
}

.agent-item.running {
    background: #17212b;
    border: 1px solid var(--sa-border);
    border-radius: 7px;
    margin: 2px -6px;
    padding: 8px 6px;
}

.swarm-card textarea,
.swarm-card input,
.swarm-card select {
    font-family: JetBrains Mono, monospace !important;
}

.swarm-progress textarea {
    min-height: 285px !important;
    font-family: JetBrains Mono, monospace !important;
    font-size: 12px !important;
    line-height: 20px !important;
    color: #d8e3ef !important;
    background: #0d1117 !important;
}

.swarm-report {
    min-height: 560px;
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

.audit-actionbar {
    border: 1px solid var(--sa-border) !important;
    background: #111820 !important;
    border-radius: 8px !important;
    padding: 6px 8px !important;
    margin-bottom: 12px !important;
}

.audit-actionbar .form,
.audit-actionbar .block {
    min-height: 0 !important;
}

.audit-actionbar label {
    color: var(--sa-muted) !important;
    font: 600 11px/16px JetBrains Mono, monospace !important;
    text-transform: lowercase !important;
}

.audit-actionbar input {
    background: #0f151d !important;
    border: 1px solid var(--sa-border) !important;
    border-radius: 6px !important;
    color: var(--sa-text) !important;
    font-family: JetBrains Mono, monospace !important;
    min-height: 34px !important;
    height: 34px !important;
    padding: 6px 10px !important;
}

.example-label {
    display: flex;
    align-items: center;
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    height: 34px;
    padding: 0 2px;
}

.example-chip button {
    background: #151d27 !important;
    border: 1px solid var(--sa-border) !important;
    border-radius: 6px !important;
    color: var(--sa-muted) !important;
    font: 600 11px/16px JetBrains Mono, monospace !important;
    min-width: 0 !important;
    height: 34px !important;
    min-height: 34px !important;
    padding: 0 10px !important;
    margin: 0 !important;
}

.example-chip button:hover {
    background: #1b2430 !important;
    color: var(--sa-text) !important;
}

button.primary,
.gradio-button.primary {
    background: #d7dee7 !important;
    color: #111820 !important;
    border: 0 !important;
    font-weight: 700 !important;
    box-shadow: none;
    min-height: 34px !important;
    height: 34px !important;
    padding: 0 14px !important;
}

.tabs {
    border: 1px solid var(--sa-border) !important;
    border-radius: 8px !important;
    background: #0d1117 !important;
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

.audit-console {
    border: 1px solid var(--sa-border);
    background: #111820;
    border-radius: 8px;
    overflow: hidden;
    min-height: 700px;
}

.findings-list-radio,
.finding-detail-panel {
    border: 1px solid var(--sa-border);
    background: #111820;
    border-radius: 0;
    overflow: hidden;
}

.findings-list-radio {
    height: 540px;
    max-height: 540px;
    overflow-y: auto !important;
    border-right: 0;
    border-radius: 0 0 0 8px;
}

.report-toolbar {
    min-height: 41px;
    border: 1px solid var(--sa-border);
    border-bottom: 0;
    background: #111820;
    border-radius: 8px 8px 0 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 13px;
}

.report-overview {
    border: 1px solid var(--sa-border);
    border-top: 0;
    background: #111820;
    display: grid;
    grid-template-columns: repeat(2, minmax(120px, 0.7fr)) repeat(2, minmax(170px, 1fr));
    gap: 0;
}

.overview-column {
    border-right: 1px solid var(--sa-border);
    padding: 10px 12px;
}

.overview-column:last-child {
    border-right: 0;
}

.overview-column span {
    color: var(--sa-muted);
    font: 600 10px/15px JetBrains Mono, monospace;
    text-transform: uppercase;
}

.overview-column strong {
    display: block;
    color: var(--sa-text);
    font-size: 18px;
    line-height: 24px;
    margin-top: 2px;
}

.overview-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 4px;
}

.overview-tags span {
    border: 1px solid var(--sa-border);
    border-radius: 5px;
    background: #151d27;
    color: #cbd5e1;
    padding: 3px 6px;
    text-transform: none;
}

.report-body {
    border: 1px solid var(--sa-border) !important;
    border-top: 0 !important;
    background: #111820 !important;
    border-radius: 0 0 8px 8px !important;
    overflow: hidden !important;
}

.report-body > .form {
    gap: 0 !important;
}

.report-title {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 18px;
    font-weight: 700;
}

.report-title span {
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    margin-right: 6px;
}

.findings-list-radio .wrap,
.findings-list-radio .block,
.findings-list-radio fieldset {
    background: #111820 !important;
    border: 0 !important;
    padding: 0 !important;
}

.findings-list-radio label {
    border-bottom: 1px solid var(--sa-border) !important;
    background: #111820 !important;
    padding: 11px 13px !important;
    margin: 0 !important;
    align-items: flex-start !important;
    cursor: pointer !important;
}

.findings-list-radio label:hover {
    background: #161f29 !important;
}

.findings-list-radio input:checked + span,
.findings-list-radio label:has(input:checked) {
    background: #1b232d !important;
}

.findings-list-radio span {
    color: #dce4ee !important;
    font: 600 12px/18px Inter, system-ui, sans-serif !important;
    white-space: pre-wrap !important;
}

.findings-list-radio input {
    margin-top: 4px !important;
    accent-color: var(--sa-primary) !important;
}

.finding-detail-panel {
    height: 540px;
    max-height: 540px;
    overflow-y: auto;
    border-radius: 0 0 8px 0;
}

.audit-filter-row {
    display: flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
}

.filter-pill {
    background: #202a36;
    border-radius: 6px;
    padding: 5px 10px;
    color: var(--sa-muted);
}

.filter-pill.active {
    color: var(--sa-text);
}

.filter-dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    display: inline-block;
}

.dot-critical { background: var(--sa-red); }
.dot-high { background: var(--sa-orange); }
.dot-medium { background: var(--sa-yellow); }
.dot-low { background: var(--sa-blue); }

.audit-console-body {
    display: grid;
    grid-template-columns: minmax(280px, 42%) 1fr;
    min-height: 657px;
}

.finding-list {
    border-right: 1px solid var(--sa-border);
    background: #121922;
}

.finding-row {
    padding: 14px 16px;
    border-bottom: 1px solid var(--sa-border);
    background: #121922;
}

.finding-row:first-child {
    background: #1b232d;
}

.finding-row-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
    margin-bottom: 7px;
}

.severity-badge {
    border: 1px solid currentColor;
    border-radius: 4px;
    padding: 2px 6px;
    font: 700 10px/14px JetBrains Mono, monospace;
    color: var(--sa-muted);
}

.severity-critical .severity-badge,
.severity-badge.severity-critical { color: var(--sa-red); }
.severity-high .severity-badge,
.severity-badge.severity-high { color: var(--sa-orange); }
.severity-medium .severity-badge,
.severity-badge.severity-medium { color: var(--sa-yellow); }
.severity-low .severity-badge,
.severity-badge.severity-low { color: var(--sa-blue); }

.finding-row-title {
    color: var(--sa-text);
    font-size: 13px;
    line-height: 19px;
    font-weight: 700;
}

.finding-row-path {
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
    margin-top: 3px;
}

.finding-detail {
    padding: 22px 22px 26px;
    background: #111820;
}

.finding-detail-meta {
    display: flex;
    gap: 8px;
    color: var(--sa-muted);
    font: 500 11px/16px JetBrains Mono, monospace;
    margin-bottom: 12px;
}

.finding-detail-title {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 22px;
}

.finding-detail-title h3 {
    margin: 0;
    color: var(--sa-text);
    font-size: 18px;
    line-height: 26px;
}

.detail-section {
    margin-bottom: 20px;
}

.detail-section span {
    display: block;
    color: var(--sa-muted);
    font: 600 11px/16px JetBrains Mono, monospace;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.detail-section p {
    color: #dce4ee;
    font-size: 13px;
    line-height: 21px;
    margin: 0;
}

.detail-section pre,
.reference-card {
    border: 1px solid var(--sa-border);
    background: #1b232d;
    border-radius: 6px;
}

.detail-section pre {
    color: #f1f5f9;
    white-space: pre-wrap;
    font: 500 12px/20px JetBrains Mono, monospace;
    padding: 14px;
}

.reference-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    color: var(--sa-muted);
}

.reference-card code {
    color: #dce4ee;
    font: 600 12px/18px JetBrains Mono, monospace;
}

.audit-empty {
    padding: 72px 24px;
    text-align: center;
    color: var(--sa-muted);
}

.audit-empty h3 {
    color: var(--sa-text);
    margin: 0 0 8px;
}

@media (max-width: 900px) {
    .swarm-summary-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .audit-console-body {
        grid-template-columns: 1fr;
    }
    .finding-list {
        border-right: 0;
    }
    .report-overview {
        grid-template-columns: 1fr 1fr;
    }
}
"""


def render_workspace_header() -> str:
    return """
    <section class="swarm-topbar">
        <div class="swarm-brand-row">
            <div>
                <div class="swarm-brand">SwarmAudit</div>
                <div class="swarm-tagline">AI-generated code production-readiness scanner</div>
            </div>
            <div class="swarm-status">mock-first / vLLM-ready</div>
        </div>
        <div class="swarm-progressbar"><span></span></div>
    </section>
    """


def render_agent_swarm(progress: list[str] | None = None) -> str:
    progress = progress or []
    done_count = sum(1 for _, _, token, done_token in AGENT_SWARM if _agent_status(progress, token, done_token) == "done")
    items = "\n".join(
        f"""
        <div class="agent-item {status}">
            <div class="agent-icon">{name[:2].upper()}</div>
            <div>
                <div class="agent-name">{name}</div>
                <div class="agent-desc">{desc}</div>
            </div>
            <div class="agent-status {status}">{status}</div>
        </div>
        """
        for name, desc, token, done_token in AGENT_SWARM
        for status in [_agent_status(progress, token, done_token)]
    )
    return f"""
    <section class="agent-card">
        <div class="agent-card-header">
            <div class="agent-card-title">Agent swarm</div>
            <div class="agent-card-count">{done_count}/{len(AGENT_SWARM)} done</div>
        </div>
        <div class="agent-list">{items}</div>
    </section>
    """


def _agent_status(progress: list[str], token: str, done_token: str) -> str:
    matching_events = [event for event in progress if token in event]
    if any(done_token in event for event in matching_events):
        return "done"
    if matching_events:
        return "running"
    return "idle"


def render_empty_summary() -> str:
    return render_summary_cards(
        files_scanned="-",
        total_findings="-",
        severity_counts={},
    )


def render_report_summary(report: AuditReport) -> str:
    return render_summary_cards(
        files_scanned=str(report.scanned_file_count),
        total_findings=str(report.total_findings_count),
        severity_counts={
            Severity.critical: report.severity_summary.get(Severity.critical, 0),
            Severity.high: report.severity_summary.get(Severity.high, 0),
            Severity.medium: report.severity_summary.get(Severity.medium, 0),
            Severity.low: report.severity_summary.get(Severity.low, 0),
        },
    )


def render_report_toolbar(report: AuditReport | None) -> str:
    if report is None:
        counts: dict[Severity, int] = {}
        total = 0
    else:
        counts = report.severity_summary
        total = report.displayed_findings_count

    filter_items = []
    for severity, css_class, label in [
        (Severity.critical, "dot-critical", "Critical"),
        (Severity.high, "dot-high", "High"),
        (Severity.medium, "dot-medium", "Medium"),
        (Severity.low, "dot-low", "Low"),
    ]:
        count = counts.get(severity, 0)
        if count <= 0:
            continue
        filter_items.append(f'<span class="filter-dot {css_class}"></span><span>{label} {count}</span>')

    filters_html = "\n".join(filter_items)
    return f"""
    <section class="report-toolbar">
        <div class="report-title"><span>DOC</span>Audit report</div>
        <div class="audit-filter-row">
            <span class="filter-pill active">All {total}</span>
            {filters_html}
        </div>
    </section>
    {format_report_overview_html(report)}
    """


def render_summary_cards(
    files_scanned: str,
    total_findings: str,
    severity_counts: dict[Severity, int],
) -> str:
    severity_cards = []
    for severity, css_class in [
        (Severity.critical, "metric-critical"),
        (Severity.high, "metric-high"),
        (Severity.medium, "metric-medium"),
        (Severity.low, "metric-low"),
    ]:
        count = severity_counts.get(severity, 0)
        if count <= 0:
            continue
        severity_cards.append(
            f'<div class="swarm-metric {css_class}"><span>{severity.value.title()}</span><strong>{count}</strong></div>'
        )

    severity_html = "\n".join(severity_cards)
    return f"""
    <section class="swarm-summary-grid">
        <div class="swarm-metric"><span>Files scanned</span><strong>{files_scanned}</strong></div>
        <div class="swarm-metric"><span>Findings</span><strong>{total_findings}</strong></div>
        {severity_html}
    </section>
    """


async def analyze_repo(repo_url: str):
    if not repo_url.strip():
        yield (
            "Paste a public GitHub repository URL to start.",
            render_agent_swarm(),
            render_empty_summary(),
            render_report_toolbar(None),
            gr.update(choices=[], value=None),
            format_empty_finding_detail_html(),
            None,
            None,
            None,
        )
        return

    progress: list[str] = []
    agent_html = render_agent_swarm(progress)
    summary_html = render_empty_summary()
    report_toolbar_html = render_report_toolbar(None)
    finding_choice_update = gr.update(choices=[], value=None)
    finding_detail_html = format_empty_finding_detail_html()
    markdown_export = None
    json_export = None
    report_state = None
    try:
        async for event in AuditGraph().run_with_progress(repo_url.strip()):
            if isinstance(event, AuditReport):
                report_state = event
                finding_choices = build_finding_choices(event)
                finding_choice_update = gr.update(
                    choices=finding_choices,
                    value=finding_choices[0] if finding_choices else None,
                )
                finding_detail_html = format_finding_detail_html(event, 0)
                summary_html = render_report_summary(event)
                report_toolbar_html = render_report_toolbar(event)
                markdown_export, json_export = write_report_exports(event)
            else:
                progress.append(event)
                agent_html = render_agent_swarm(progress)
            yield (
                "\n".join(progress),
                agent_html,
                summary_html,
                report_toolbar_html,
                finding_choice_update,
                finding_detail_html,
                markdown_export,
                json_export,
                report_state,
            )
    except Exception as exc:
        progress.append(f"Audit failed: {exc}")
        yield (
            "\n".join(progress),
            render_agent_swarm(progress),
            render_empty_summary(),
            render_report_toolbar(None),
            gr.update(choices=[], value=None),
            format_empty_finding_detail_html(),
            None,
            None,
            None,
        )


def build_finding_rows(report: AuditReport | None) -> list[list[str]]:
    if report is None:
        return []

    rows: list[list[str]] = []
    for index, finding in enumerate(report.findings, start=1):
        rows.append(
            [
                f"F-{index:03d}",
                finding.severity.value,
                finding.title,
                f"{finding.file_path}:{finding.line_start}",
                finding.agent_source,
            ]
        )
    return rows


def build_finding_choices(report: AuditReport | None) -> list[str]:
    if report is None:
        return []

    choices: list[str] = []
    for index, finding in enumerate(report.findings, start=1):
        choices.append(
            f"F-{index:03d}  [{finding.severity.value}]  {finding.title}\n"
            f"{finding.file_path}:{finding.line_start}  |  {finding.agent_source}"
        )
    return choices


def select_finding(choice: str | None, report: AuditReport | None) -> str:
    if report is None or not report.findings:
        return format_empty_finding_detail_html()

    row_index = 0
    if choice:
        first_token = choice.split(maxsplit=1)[0]
        if first_token.startswith("F-"):
            try:
                row_index = int(first_token.removeprefix("F-")) - 1
            except ValueError:
                row_index = 0

    return format_finding_detail_html(report, row_index)


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
                with gr.Group(elem_classes=["audit-actionbar"]):
                    with gr.Row(equal_height=False):
                        repo_url = gr.Textbox(
                            label="",
                            placeholder="repo  https://github.com/owner/repo",
                            scale=5,
                            show_label=False,
                            elem_classes=["repo-input"],
                        )
                        analyze = gr.Button("Analyze", variant="primary", scale=1)
                        gr.HTML('<div class="example-label">Examples</div>', scale=0)
                        for example_name, example_url in EXAMPLE_REPOS.items():
                            example_button = gr.Button(example_name, scale=1, elem_classes=["example-chip"])
                            example_button.click(lambda url=example_url: url, outputs=repo_url)

                summary_output = gr.HTML(render_empty_summary())
                report_state = gr.State(None)

                with gr.Row():
                    with gr.Column(scale=1):
                        agent_output = gr.HTML(render_agent_swarm())
                        progress_output = gr.Textbox(
                            label="Activity log",
                            lines=12,
                            interactive=False,
                            elem_classes=["swarm-panel", "swarm-progress"],
                        )
                    with gr.Column(scale=3):
                        report_toolbar = gr.HTML(render_report_toolbar(None))
                        with gr.Row(equal_height=True, elem_classes=["report-body"]):
                            with gr.Column(scale=1):
                                finding_selector = gr.Radio(
                                    choices=[],
                                    value=None,
                                    interactive=True,
                                    show_label=False,
                                    elem_classes=["findings-list-radio"],
                                )
                            with gr.Column(scale=1):
                                finding_detail = gr.HTML(
                                    format_empty_finding_detail_html(),
                                    elem_classes=["swarm-panel", "swarm-report"],
                                )

                with gr.Row(elem_classes=["swarm-export"]):
                    markdown_export = gr.File(label="Markdown Report")
                    json_export = gr.File(label="JSON Report")

                analyze.click(
                    analyze_repo,
                    inputs=repo_url,
                    outputs=[
                        progress_output,
                        agent_output,
                        summary_output,
                        report_toolbar,
                        finding_selector,
                        finding_detail,
                        markdown_export,
                        json_export,
                        report_state,
                    ],
                )
                finding_selector.change(select_finding, inputs=[finding_selector, report_state], outputs=finding_detail)

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
