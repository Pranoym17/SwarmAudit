import tempfile
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
        "## Severity Summary",
        "",
    ]

    for severity in [Severity.critical, Severity.high, Severity.medium, Severity.low]:
        lines.append(f"- **{severity.value}**: {report.severity_summary.get(severity, 0)}")

    if report.agent_finding_counts:
        lines.extend(["", "## Agent Summary", ""])
        for agent_name, count in report.agent_finding_counts.items():
            lines.append(f"- **{agent_name}**: {count}")

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


def write_report_exports(report: AuditReport, output_dir: Path | None = None) -> tuple[str, str]:
    export_dir = output_dir or Path(tempfile.mkdtemp(prefix="swarm_audit_export_"))
    export_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = export_dir / "swarm_audit_report.md"
    json_path = export_dir / "swarm_audit_report.json"

    markdown_path.write_text(format_report_markdown(report), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    return str(markdown_path), str(json_path)
