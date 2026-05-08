import json

from app.schemas import AuditReport, Finding, Severity
from app.services.report_formatter import write_report_exports


def make_report() -> AuditReport:
    finding = Finding(
        title="Missing timeout",
        severity=Severity.medium,
        file_path="app.py",
        line_start=10,
        line_end=10,
        description="HTTP request has no timeout.",
        why_it_matters="Requests can hang indefinitely.",
        suggested_fix="Pass a timeout value.",
        agent_source="Performance Agent",
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
        hidden_findings_count=0,
        agent_finding_counts={"Performance Agent": 1},
        agents_run=["Performance Agent", "Synthesizer Agent"],
    )


def test_write_report_exports_creates_markdown_and_json(tmp_path):
    markdown_path, json_path = write_report_exports(make_report(), tmp_path)

    markdown = tmp_path.joinpath("swarm_audit_report.md").read_text(encoding="utf-8")
    data = json.loads(tmp_path.joinpath("swarm_audit_report.json").read_text(encoding="utf-8"))

    assert markdown_path.endswith("swarm_audit_report.md")
    assert json_path.endswith("swarm_audit_report.json")
    assert "# SwarmAudit Report" in markdown
    assert "Missing timeout" in markdown
    assert data["repo_url"] == "https://github.com/example/project"
    assert data["findings"][0]["severity"] == "MEDIUM"
    assert data["total_findings_count"] == 1
