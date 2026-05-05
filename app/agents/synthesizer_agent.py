from app.schemas import AgentOutput, AuditReport, Finding, RepoScanResult, Severity


SEVERITY_ORDER = {
    Severity.critical: 0,
    Severity.high: 1,
    Severity.medium: 2,
    Severity.low: 3,
}


class SynthesizerAgent:
    name = "Synthesizer Agent"

    async def synthesize(self, repo: RepoScanResult, outputs: list[AgentOutput]) -> AuditReport:
        findings = self._dedupe([finding for output in outputs for finding in output.findings])
        findings.sort(key=lambda finding: (SEVERITY_ORDER[finding.severity], finding.file_path, finding.line_start))

        summary = {severity: 0 for severity in Severity}
        for finding in findings:
            summary[finding.severity] += 1

        return AuditReport(
            repo_url=repo.repo_url,
            scanned_file_count=len(repo.files),
            skipped_file_count=repo.skipped_files,
            findings=findings,
            severity_summary=summary,
            agents_run=[output.agent_name for output in outputs] + [self.name],
            warnings=repo.warnings,
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
