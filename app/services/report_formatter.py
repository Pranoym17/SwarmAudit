from app.schemas import AuditReport, Severity


def format_report_markdown(report: AuditReport) -> str:
    lines = [
        "# SwarmAudit Report",
        "",
        f"Repository: `{report.repo_url}`",
        f"Files scanned: `{report.scanned_file_count}`",
        f"Files skipped: `{report.skipped_file_count}`",
        "",
        "## Severity Summary",
        "",
    ]

    for severity in [Severity.critical, Severity.high, Severity.medium, Severity.low]:
        lines.append(f"- **{severity.value}**: {report.severity_summary.get(severity, 0)}")

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
