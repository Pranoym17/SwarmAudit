import json

import pytest
from pydantic import ValidationError

from app.schemas import AuditReport, Finding, Severity
from app.services.report_formatter import write_report_exports


def make_finding(**overrides) -> Finding:
    data = {
        "title": "Finding",
        "severity": Severity.low,
        "file_path": "app.py",
        "line_start": 1,
        "line_end": 1,
        "description": "Description",
        "why_it_matters": "Why",
        "suggested_fix": "Fix",
        "agent_source": "Quality Agent",
    }
    data.update(overrides)
    return Finding(**data)


def make_report(**overrides) -> AuditReport:
    data = {
        "repo_url": "https://github.com/example/project",
        "scanned_file_count": 1,
        "skipped_file_count": 0,
        "findings": [make_finding()],
        "severity_summary": {
            Severity.critical: 0,
            Severity.high: 0,
            Severity.medium: 0,
            Severity.low: 1,
        },
        "agents_run": ["Quality Agent"],
    }
    data.update(overrides)
    return AuditReport(**data)


def test_finding_keeps_legacy_fields_optional_for_v2_metadata():
    finding = make_finding()

    assert finding.category is None
    assert finding.confidence is None


def test_finding_accepts_v2_category_and_confidence():
    finding = make_finding(category="observability", confidence=0.91)

    assert finding.category == "observability"
    assert finding.confidence == 0.91


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_finding_rejects_invalid_confidence(confidence):
    with pytest.raises(ValidationError):
        make_finding(confidence=confidence)


def test_audit_report_defaults_v2_fields_without_breaking_legacy_reports():
    report = make_report()

    assert report.category_summary == {}
    assert report.security_score is None
    assert report.production_score is None
    assert report.remediation_roadmap == {}
    assert report.dependency_cves == []


def test_audit_report_exports_v2_fields_to_json(tmp_path):
    report = make_report(
        findings=[make_finding(category="config", confidence=0.8)],
        category_summary={"config": 1},
        security_score=88,
        production_score=92,
        remediation_roadmap={"this_week": [], "next_sprint": [], "backlog": []},
        dependency_cves=[{"id": "GHSA-test", "package": "demo", "severity": "LOW"}],
    )

    _, json_path = write_report_exports(report, tmp_path)
    data = json.loads(tmp_path.joinpath("swarm_audit_report.json").read_text(encoding="utf-8"))

    assert json_path.endswith("swarm_audit_report.json")
    assert data["findings"][0]["category"] == "config"
    assert data["findings"][0]["confidence"] == 0.8
    assert data["category_summary"] == {"config": 1}
    assert data["security_score"] == 88
    assert data["production_score"] == 92
    assert data["dependency_cves"][0]["id"] == "GHSA-test"
