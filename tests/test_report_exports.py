import json
from pathlib import Path

from app.schemas import AuditReport, Finding, Severity
from app.services.report_formatter import (
    format_empty_report_html,
    format_finding_detail_html,
    format_report_html,
    write_report_exports,
)


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
        category_summary={"performance": 1},
        security_score=100,
        production_score=96,
        remediation_roadmap={
            "this_week": [],
            "next_sprint": [
                {
                    "title": "Missing timeout",
                    "severity": "MEDIUM",
                    "category": "performance",
                    "file_path": "app.py",
                    "line_start": "10",
                    "agent_source": "Performance Agent",
                }
            ],
            "backlog": [],
        },
        dependency_cves=[
            {
                "id": "GHSA-test",
                "package": "requests",
                "version": "2.28.0",
                "ecosystem": "PyPI",
                "severity": "HIGH",
                "fixed_version": "2.32.0",
            }
        ],
        agents_run=["Performance Agent", "Synthesizer Agent"],
    )


def test_write_report_exports_creates_markdown_and_json():
    output_dir = Path.cwd() / ".tmp_test_exports" / "report_export"
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path, json_path = write_report_exports(make_report(), output_dir)

    markdown = output_dir.joinpath("swarm_audit_report.md").read_text(encoding="utf-8")
    data = json.loads(output_dir.joinpath("swarm_audit_report.json").read_text(encoding="utf-8"))

    assert markdown_path.endswith("swarm_audit_report.md")
    assert json_path.endswith("swarm_audit_report.json")
    assert "# SwarmAudit Report" in markdown
    assert "Security Score" in markdown
    assert "Production Readiness Score" in markdown
    assert "Category Summary" in markdown
    assert "Remediation Roadmap" in markdown
    assert "Dependency CVEs" in markdown
    assert "GHSA-test" in markdown
    assert "Missing timeout" in markdown
    assert data["repo_url"] == "https://github.com/example/project"
    assert data["findings"][0]["severity"] == "MEDIUM"
    assert data["total_findings_count"] == 1


def test_format_report_html_renders_console_and_escapes_content():
    report = make_report()
    report.findings[0].title = "<script>alert('x')</script>"

    html = format_report_html(report)

    assert "audit-console" in html
    assert "finding-list" in html
    assert "finding-detail" in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html


def test_format_report_html_hides_zero_count_severity_filters():
    report = make_report()

    html = format_report_html(report)

    assert "Medium 1" in html
    assert "Critical 0" not in html
    assert "High 0" not in html
    assert "Low 0" not in html


def test_format_empty_report_html_renders_placeholder():
    html = format_empty_report_html()

    assert "Run an audit to populate findings" in html
    assert "audit-console" in html


def test_format_finding_detail_links_to_github_file_reference():
    html = format_finding_detail_html(make_report(), 0)

    assert 'href="https://github.com/example/project/blob/HEAD/app.py#L10"' in html
    assert 'target="_blank"' in html
