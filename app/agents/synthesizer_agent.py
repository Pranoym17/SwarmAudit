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
