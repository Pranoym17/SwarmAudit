import pytest

from app.agents.synthesizer_agent import SynthesizerAgent
from app.schemas import AgentOutput, Finding, RepoScanResult, Severity


def make_finding(index: int, agent: str = "Docs Agent", severity: Severity = Severity.low) -> Finding:
    return Finding(
        title=f"Finding {index}",
        severity=severity,
        file_path=f"file_{index}.py",
        line_start=1,
        line_end=1,
        description="Description",
        why_it_matters="Why",
        suggested_fix="Fix",
        agent_source=agent,
    )


@pytest.mark.anyio
async def test_synthesizer_preserves_totals_when_display_is_truncated():
    output = AgentOutput(
        agent_name="Docs Agent",
        findings=[make_finding(index) for index in range(20)],
    )
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, [output])

    assert report.total_findings_count == 20
    assert report.displayed_findings_count == 12
    assert report.hidden_findings_count == 8
    assert report.agent_finding_counts["Docs Agent"] == 20
    assert any("displaying 12 of 20" in warning for warning in report.warnings)


@pytest.mark.anyio
async def test_synthesizer_keeps_high_severity_before_low_findings():
    outputs = [
        AgentOutput(agent_name="Docs Agent", findings=[make_finding(1, severity=Severity.low)]),
        AgentOutput(agent_name="Security Agent", findings=[make_finding(2, "Security Agent", Severity.high)]),
    ]
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, outputs)

    assert report.findings[0].severity == Severity.high


@pytest.mark.anyio
async def test_synthesizer_keeps_low_findings_visible_when_report_is_noisy():
    outputs = [
        AgentOutput(
            agent_name="Performance Agent",
            findings=[make_finding(index, "Performance Agent", Severity.high) for index in range(45)],
        ),
        AgentOutput(
            agent_name="Docs Agent",
            findings=[make_finding(index + 100, "Docs Agent", Severity.low) for index in range(20)],
        ),
    ]
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, outputs)

    assert any(finding.severity == Severity.low for finding in report.findings)
    assert sum(1 for finding in report.findings if finding.severity == Severity.low) <= 12


@pytest.mark.anyio
async def test_synthesizer_populates_scores_categories_and_roadmap():
    outputs = [
        AgentOutput(
            agent_name="Security Agent",
            findings=[make_finding(1, "Security Agent", Severity.high)],
        ),
        AgentOutput(
            agent_name="Performance Agent",
            findings=[make_finding(2, "Performance Agent", Severity.medium)],
        ),
        AgentOutput(
            agent_name="Error Handling Agent",
            findings=[make_finding(3, "Error Handling Agent", Severity.low)],
        ),
    ]
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, outputs)

    assert report.security_score == 89
    assert report.production_score == 95
    assert report.category_summary == {"error_handling": 1, "performance": 1, "security": 1}
    assert report.remediation_roadmap["this_week"][0]["category"] == "security"
    assert report.remediation_roadmap["next_sprint"][0]["category"] == "performance"
    assert report.remediation_roadmap["backlog"][0]["category"] == "error_handling"


@pytest.mark.anyio
async def test_synthesizer_carries_dependency_cves_and_warnings():
    outputs = [
        AgentOutput(
            agent_name="Dependency Agent",
            findings=[],
            metadata={
                "dependency_cves": [{"id": "GHSA-test", "package": "requests", "severity": "HIGH"}],
                "warnings": ["Dependency CVE lookup failed gracefully: timeout"],
            },
        )
    ]
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, outputs)

    assert report.dependency_cves == [{"id": "GHSA-test", "package": "requests", "severity": "HIGH"}]
    assert "timeout" in report.warnings[0]


@pytest.mark.anyio
async def test_synthesizer_caps_score_penalties_for_noisy_repos():
    outputs = [
        AgentOutput(
            agent_name="Performance Agent",
            findings=[make_finding(index, "Performance Agent", Severity.medium) for index in range(120)],
        ),
        AgentOutput(
            agent_name="Docs Agent",
            findings=[make_finding(index + 200, "Docs Agent", Severity.low) for index in range(80)],
        ),
        AgentOutput(
            agent_name="Error Handling Agent",
            findings=[make_finding(index + 400, "Error Handling Agent", Severity.high) for index in range(20)],
        ),
    ]
    repo = RepoScanResult(repo_url="https://github.com/example/project", local_path=".", files=[], skipped_files=0)

    report = await SynthesizerAgent().synthesize(repo, outputs)

    assert report.production_score == 54
