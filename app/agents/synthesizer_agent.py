from app.schemas import AgentOutput, AuditReport, Finding, RepoScanResult, Severity


SEVERITY_ORDER = {
    Severity.critical: 0,
    Severity.high: 1,
    Severity.medium: 2,
    Severity.low: 3,
}

MAX_DISPLAY_FINDINGS = 40
MAX_DISPLAY_FINDINGS_BY_AGENT = {
    "Security Agent": 20,
    "Performance Agent": 12,
    "Quality Agent": 10,
    "Docs Agent": 8,
}

SECURITY_CATEGORIES = {
    "security",
    "config",
    "dependency",
    "cuda_migration",
}

PRODUCTION_CATEGORIES = {
    "performance",
    "quality",
    "docs",
    "error_handling",
    "observability",
}

AGENT_CATEGORY_DEFAULTS = {
    "Security Agent": "security",
    "Config Agent": "config",
    "Dependency Agent": "dependency",
    "CUDA-to-ROCm Agent": "cuda_migration",
    "Performance Agent": "performance",
    "Quality Agent": "quality",
    "Docs Agent": "docs",
    "Error Handling Agent": "error_handling",
    "Observability Agent": "observability",
}

SECURITY_WEIGHTS = {
    Severity.critical: 24,
    Severity.high: 12,
    Severity.medium: 5,
    Severity.low: 1,
}

PRODUCTION_WEIGHTS = {
    Severity.critical: 16,
    Severity.high: 9,
    Severity.medium: 4,
    Severity.low: 1,
}


class SynthesizerAgent:
    name = "Synthesizer Agent"

    async def synthesize(self, repo: RepoScanResult, outputs: list[AgentOutput]) -> AuditReport:
        all_findings = self._dedupe([finding for output in outputs for finding in output.findings])
        all_findings.sort(key=self._sort_key)

        summary = {severity: 0 for severity in Severity}
        for finding in all_findings:
            summary[finding.severity] += 1

        agent_counts = {output.agent_name: len(output.findings) for output in outputs}
        display_findings, hidden_count, warnings = self._select_display_findings(all_findings, agent_counts)
        category_summary = self._category_summary(all_findings)
        security_score, production_score = self._compute_scores(all_findings)
        roadmap = self._build_roadmap(all_findings)

        return AuditReport(
            repo_url=repo.repo_url,
            scanned_file_count=len(repo.files),
            skipped_file_count=repo.skipped_files,
            findings=display_findings,
            severity_summary=summary,
            total_findings_count=len(all_findings),
            displayed_findings_count=len(display_findings),
            hidden_findings_count=hidden_count,
            agent_finding_counts=agent_counts,
            category_summary=category_summary,
            security_score=security_score,
            production_score=production_score,
            remediation_roadmap=roadmap,
            agents_run=[output.agent_name for output in outputs] + [self.name],
            warnings=repo.warnings + warnings,
        )

    def _dedupe(self, findings: list[Finding]) -> list[Finding]:
        seen: set[tuple[str, int, str, str]] = set()
        unique: list[Finding] = []
        for finding in findings:
            key = (finding.file_path, finding.line_start, finding.title, finding.agent_source)
            if key in seen:
                continue
            seen.add(key)
            unique.append(finding)
        return unique

    def _select_display_findings(
        self,
        findings: list[Finding],
        agent_counts: dict[str, int],
    ) -> tuple[list[Finding], int, list[str]]:
        selected: list[Finding] = []
        selected_by_agent = {agent_name: 0 for agent_name in agent_counts}

        for finding in findings:
            agent_limit = MAX_DISPLAY_FINDINGS_BY_AGENT.get(finding.agent_source, MAX_DISPLAY_FINDINGS)
            if selected_by_agent.get(finding.agent_source, 0) >= agent_limit:
                continue
            if len(selected) >= MAX_DISPLAY_FINDINGS:
                break
            selected.append(finding)
            selected_by_agent[finding.agent_source] = selected_by_agent.get(finding.agent_source, 0) + 1

        hidden_count = max(0, len(findings) - len(selected))
        warnings: list[str] = []
        if hidden_count:
            warnings.append(
                f"Report display prioritized {len(selected)} of {len(findings)} findings; "
                f"{hidden_count} lower-priority findings are hidden from the demo report."
            )

        for agent_name, total_count in agent_counts.items():
            displayed_count = selected_by_agent.get(agent_name, 0)
            hidden_for_agent = total_count - displayed_count
            if hidden_for_agent > 0:
                warnings.append(f"{agent_name}: displaying {displayed_count} of {total_count} findings.")

        return selected, hidden_count, warnings

    def _sort_key(self, finding: Finding) -> tuple[int, int, str, int]:
        test_file_penalty = 1 if self._is_test_file(finding.file_path) and finding.severity != Severity.critical else 0
        return (SEVERITY_ORDER[finding.severity], test_file_penalty, finding.file_path, finding.line_start)

    def _is_test_file(self, file_path: str) -> bool:
        normalized = file_path.lower().replace("\\", "/")
        return "/test" in normalized or normalized.startswith("test") or "_test." in normalized

    def _category_for(self, finding: Finding) -> str:
        if finding.category:
            return finding.category
        return AGENT_CATEGORY_DEFAULTS.get(finding.agent_source, finding.agent_source.replace(" Agent", "").lower())

    def _category_summary(self, findings: list[Finding]) -> dict[str, int]:
        summary: dict[str, int] = {}
        for finding in findings:
            category = self._category_for(finding)
            summary[category] = summary.get(category, 0) + 1
        return dict(sorted(summary.items(), key=lambda item: (-item[1], item[0])))

    def _compute_scores(self, findings: list[Finding]) -> tuple[int, int]:
        security_penalty = 0
        production_penalty = 0

        for finding in findings:
            category = self._category_for(finding)
            if category in SECURITY_CATEGORIES or finding.agent_source in {
                "Security Agent",
                "Config Agent",
                "Dependency Agent",
                "CUDA-to-ROCm Agent",
            }:
                security_penalty += SECURITY_WEIGHTS[finding.severity]
            if category in PRODUCTION_CATEGORIES or finding.agent_source in {
                "Performance Agent",
                "Quality Agent",
                "Docs Agent",
                "Error Handling Agent",
                "Observability Agent",
            }:
                production_penalty += PRODUCTION_WEIGHTS[finding.severity]

        return max(0, 100 - security_penalty), max(0, 100 - production_penalty)

    def _build_roadmap(self, findings: list[Finding]) -> dict[str, list[dict[str, str]]]:
        critical = [finding for finding in findings if finding.severity == Severity.critical]
        high = [finding for finding in findings if finding.severity == Severity.high]
        medium = [finding for finding in findings if finding.severity == Severity.medium]
        low = [finding for finding in findings if finding.severity == Severity.low]

        this_week = critical + high[:5]
        next_sprint = high[5:] + medium[:10]
        backlog = medium[10:] + low

        return {
            "this_week": [self._roadmap_item(finding) for finding in this_week],
            "next_sprint": [self._roadmap_item(finding) for finding in next_sprint],
            "backlog": [self._roadmap_item(finding) for finding in backlog],
        }

    def _roadmap_item(self, finding: Finding) -> dict[str, str]:
        return {
            "title": finding.title,
            "severity": finding.severity.value,
            "category": self._category_for(finding),
            "file_path": finding.file_path,
            "line_start": str(finding.line_start),
            "agent_source": finding.agent_source,
        }
