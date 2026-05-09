import tempfile
from html import escape
from pathlib import Path

from app.schemas import AuditReport, Severity


def format_report_markdown(report: AuditReport) -> str:
    lines = [
        "# SwarmAudit Report",
        "",
        f"Repository: `{report.repo_url}`",
        f"Files scanned: `{report.scanned_file_count}`",
        f"Files skipped: `{report.skipped_file_count}`",
        f"Findings shown: `{report.displayed_findings_count}` of `{report.total_findings_count}`",
        "",
        "## Readiness Scores",
        "",
        f"- **Security Score**: `{_score_label(report.security_score)}`",
        f"- **Production Readiness Score**: `{_score_label(report.production_score)}`",
        "",
        "## Severity Summary",
        "",
    ]

    for severity in [Severity.critical, Severity.high, Severity.medium, Severity.low]:
        lines.append(f"- **{severity.value}**: {report.severity_summary.get(severity, 0)}")

    if report.agent_finding_counts:
        lines.extend(["", "## Agent Summary", ""])
        for agent_name, count in report.agent_finding_counts.items():
            lines.append(f"- **{agent_name}**: {count}")

    if report.category_summary:
        lines.extend(["", "## Category Summary", ""])
        for category, count in report.category_summary.items():
            lines.append(f"- **{_label(category)}**: {count}")

    if report.remediation_roadmap:
        lines.extend(["", "## Remediation Roadmap", ""])
        for key, label in [
            ("this_week", "This Week"),
            ("next_sprint", "Next Sprint"),
            ("backlog", "Backlog"),
        ]:
            items = report.remediation_roadmap.get(key, [])
            lines.extend(["", f"### {label}", ""])
            if not items:
                lines.append("No items in this lane.")
                continue
            for item in items:
                lines.append(
                    f"- **[{item.get('severity', 'LOW')}] {item.get('title', 'Finding')}** "
                    f"({_label(item.get('category', 'general'))}) - "
                    f"`{item.get('file_path', 'unknown')}:{item.get('line_start', '?')}`"
                )

    if report.dependency_cves:
        lines.extend(["", "## Dependency CVEs", ""])
        for cve in report.dependency_cves:
            fixed_version = cve.get("fixed_version") or "a patched version"
            lines.append(
                f"- **[{cve.get('severity', 'LOW')}] {cve.get('id', 'UNKNOWN')}** "
                f"`{cve.get('package', 'package')}@{cve.get('version', 'unknown')}` "
                f"({cve.get('ecosystem', 'unknown')}) - upgrade to {fixed_version}"
            )

    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(["", "## Findings", ""])
    if not report.findings:
        lines.append("No findings detected by the current MVP agents.")
        return "\n".join(lines)

    for finding in report.findings:
        lines.extend(
            [
                f"### [{finding.severity.value}] {finding.title}",
                "",
                f"- File: `{finding.file_path}:{finding.line_start}-{finding.line_end}`",
                f"- Agent: `{finding.agent_source}`",
                "",
                finding.description,
                "",
                f"**Why it matters:** {finding.why_it_matters}",
                "",
                "**Suggested fix:**",
                "",
                "```text",
                finding.suggested_fix,
                "```",
                "",
            ]
        )

    return "\n".join(lines)


def format_report_html(report: AuditReport) -> str:
    findings = report.findings
    critical = report.severity_summary.get(Severity.critical, 0)
    high = report.severity_summary.get(Severity.high, 0)
    medium = report.severity_summary.get(Severity.medium, 0)
    low = report.severity_summary.get(Severity.low, 0)

    if not findings:
        return """
        <section class="audit-console">
            <div class="audit-console-header">
                <div class="audit-console-title">Audit report</div>
                <div class="audit-filter-row"><span class="filter-pill">All 0</span></div>
            </div>
            <div class="audit-empty">
                <h3>No findings detected</h3>
                <p>The current agent set did not raise findings for the displayed report.</p>
            </div>
        </section>
        """

    selected = findings[0]
    list_items = "\n".join(_finding_list_item(finding, index + 1) for index, finding in enumerate(findings[:12]))

    filter_items = _severity_filter_items(
        {
            Severity.critical: critical,
            Severity.high: high,
            Severity.medium: medium,
            Severity.low: low,
        }
    )

    return f"""
    <section class="audit-console">
        <div class="audit-console-header">
            <div class="audit-console-title">Audit report</div>
            <div class="audit-filter-row">
                <span class="filter-pill active">All {report.displayed_findings_count}</span>
                {filter_items}
            </div>
        </div>
        <div class="audit-console-body">
            <div class="finding-list">
                {list_items}
            </div>
            <div class="finding-detail">
                {_finding_detail(selected, 1)}
            </div>
        </div>
    </section>
    """


def format_empty_report_html() -> str:
    return """
    <section class="audit-console">
        <div class="audit-console-header">
            <div class="audit-console-title">Audit report</div>
            <div class="audit-filter-row"><span class="filter-pill active">All 0</span></div>
        </div>
        <div class="audit-empty">
            <h3>Run an audit to populate findings</h3>
            <p>The report panel will show ranked findings with file references and suggested fixes.</p>
        </div>
    </section>
    """


def format_report_overview_html(report: AuditReport | None) -> str:
    if report is None:
        return """
        <section class="report-overview">
            <div class="overview-column">
                <span>Security Score</span>
                <strong>-</strong>
            </div>
            <div class="overview-column">
                <span>Production Readiness</span>
                <strong>-</strong>
            </div>
        </section>
        """

    categories = "".join(
        f"<span>{escape(_label(category))}: {count}</span>"
        for category, count in list(report.category_summary.items())[:6]
    )
    roadmap = report.remediation_roadmap or {}
    return f"""
    <section class="report-overview">
        <div class="overview-column">
            <span>Security Score</span>
            <strong>{_score_label(report.security_score)}</strong>
        </div>
        <div class="overview-column">
            <span>Production Readiness</span>
            <strong>{_score_label(report.production_score)}</strong>
        </div>
        <div class="overview-column overview-wide">
            <span>Category Summary</span>
            <div class="overview-tags">{categories or "<span>No categories raised</span>"}</div>
        </div>
        <div class="overview-column overview-wide">
            <span>Roadmap</span>
            <div class="overview-tags">
                <span>This Week: {len(roadmap.get("this_week", []))}</span>
                <span>Next Sprint: {len(roadmap.get("next_sprint", []))}</span>
                <span>Backlog: {len(roadmap.get("backlog", []))}</span>
            </div>
        </div>
    </section>
    """


def format_finding_detail_html(report: AuditReport | None, index: int = 0) -> str:
    if report is None or not report.findings:
        return format_empty_finding_detail_html()

    safe_index = min(max(index, 0), len(report.findings) - 1)
    return f"""
    <section class="finding-detail-panel">
        {_finding_detail(report.findings[safe_index], safe_index + 1)}
    </section>
    """


def format_empty_finding_detail_html() -> str:
    return """
    <section class="finding-detail-panel empty-detail">
        <div class="audit-empty">
            <h3>Select a finding</h3>
            <p>Run an audit, then click any row in the findings list to inspect its explanation and suggested fix.</p>
        </div>
    </section>
    """


def _finding_list_item(finding, index: int) -> str:
    severity = finding.severity.value
    severity_class = severity.lower()
    reference = f"{finding.file_path}:{finding.line_start}"
    return f"""
    <article class="finding-row severity-{severity_class}">
        <div class="finding-row-meta">
            <span class="severity-badge">{escape(severity)}</span>
            <span>F-{index:03d}</span>
        </div>
        <div class="finding-row-title">{escape(finding.title)}</div>
        <div class="finding-row-path">{escape(reference)}</div>
    </article>
    """


def _severity_filter_items(counts: dict[Severity, int]) -> str:
    items: list[str] = []
    for severity, css_class, label in [
        (Severity.critical, "dot-critical", "Critical"),
        (Severity.high, "dot-high", "High"),
        (Severity.medium, "dot-medium", "Medium"),
        (Severity.low, "dot-low", "Low"),
    ]:
        count = counts.get(severity, 0)
        if count <= 0:
            continue
        items.append(f'<span class="filter-dot {css_class}"></span><span>{label} {count}</span>')
    return "\n".join(items)


def _finding_detail(finding, index: int) -> str:
    severity = finding.severity.value
    severity_class = severity.lower()
    reference = f"{finding.file_path}:{finding.line_start}-{finding.line_end}"
    category = finding.category or finding.agent_source.replace(" Agent", "").lower()
    return f"""
    <div class="finding-detail-meta">
        <span>F-{index:03d}</span>
        <span>></span>
        <span>{escape(category.upper())}</span>
        <span>></span>
        <span>{escape(reference)}</span>
    </div>
    <div class="finding-detail-title">
        <span class="severity-badge severity-{severity_class}">{escape(severity)}</span>
        <h3>{escape(finding.title)}</h3>
    </div>
    <div class="detail-section">
        <span>Explanation</span>
        <p>{escape(finding.description)}</p>
    </div>
    <div class="detail-section">
        <span>Why it matters</span>
        <p>{escape(finding.why_it_matters)}</p>
    </div>
    <div class="detail-section">
        <span>Suggested fix</span>
        <pre>{escape(finding.suggested_fix)}</pre>
    </div>
    <div class="reference-card">
        <code>{escape(reference)}</code>
        <span>open -></span>
    </div>
    """


def write_report_exports(report: AuditReport, output_dir: Path | None = None) -> tuple[str, str]:
    export_dir = output_dir or Path(tempfile.mkdtemp(prefix="swarm_audit_export_"))
    export_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = export_dir / "swarm_audit_report.md"
    json_path = export_dir / "swarm_audit_report.json"

    markdown_path.write_text(format_report_markdown(report), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    return str(markdown_path), str(json_path)


def _score_label(score: int | None) -> str:
    if score is None:
        return "-"
    return f"{score}/100"


def _label(value: str | None) -> str:
    if not value:
        return "General"
    return value.replace("_", " ").replace("-", " ").title()
