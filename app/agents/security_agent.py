import re

from app.schemas import AgentOutput, CodeChunk, Finding, Severity
from app.services.llm_client import LLMClient


SECURITY_PATTERNS = [
    (
        re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
        "Potential hardcoded secret",
        Severity.high,
        "A credential-like value appears to be hardcoded.",
        "Move secrets into environment variables or a managed secret store.",
    ),
    (
        re.compile(r"(?i)verify\s*=\s*False"),
        "TLS certificate verification disabled",
        Severity.high,
        "Disabling TLS verification can allow man-in-the-middle attacks.",
        "Remove verify=False and use a trusted CA bundle if needed.",
    ),
    (
        re.compile(r"(?i)(eval|exec)\s*\("),
        "Dynamic code execution",
        Severity.medium,
        "Dynamic execution can turn untrusted input into arbitrary code execution.",
        "Replace eval/exec with explicit parsing or a constrained command map.",
    ),
]


class SecurityAgent:
    name = "Security Agent"

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        findings: list[Finding] = []

        for chunk in chunks:
            findings.extend(self._scan_chunk(chunk))

        await self.llm_client.complete_json(
            "You are a security code review agent. Return JSON findings only.",
            f"Review {len(chunks)} chunks for security issues.",
        )

        return AgentOutput(
            agent_name=self.name,
            findings=findings,
            metadata={"chunks_scanned": len(chunks), "mode": "static-rules-plus-llm-interface"},
        )

    def _scan_chunk(self, chunk: CodeChunk) -> list[Finding]:
        findings: list[Finding] = []
        lines = chunk.content.splitlines()

        for offset, line in enumerate(lines):
            actual_line = chunk.line_start + offset
            for pattern, title, severity, description, fix in SECURITY_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            title=title,
                            severity=severity,
                            file_path=chunk.file_path,
                            line_start=actual_line,
                            line_end=actual_line,
                            description=description,
                            why_it_matters="Attackers often search repos for exposed credentials and unsafe execution paths.",
                            suggested_fix=fix,
                            agent_source=self.name,
                        )
                    )

        return findings
