import re

from app.schemas import AgentOutput, CodeChunk, Finding, Severity
from app.services.json_parser import parse_agent_output
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

        llm_output = await self._run_llm_enrichment(chunks)
        findings.extend(llm_output.findings)

        return AgentOutput(
            agent_name=self.name,
            findings=findings,
            metadata={
                "chunks_scanned": len(chunks),
                "mode": "static-rules-plus-optional-llm",
                "llm_enrichment_enabled": self.llm_client.settings.enable_llm_enrichment,
                "llm_findings": len(llm_output.findings),
                **llm_output.metadata,
            },
        )

    async def _run_llm_enrichment(self, chunks: list[CodeChunk]) -> AgentOutput:
        if not self.llm_client.settings.enable_llm_enrichment:
            return AgentOutput(agent_name=self.name)

        selected_chunks = chunks[: self.llm_client.settings.max_llm_chunks]
        if not selected_chunks:
            return AgentOutput(agent_name=self.name)

        prompt = self._build_llm_prompt(selected_chunks)
        try:
            raw_output = await self.llm_client.complete_json(
                "You are a senior application security reviewer. Return only JSON.",
                prompt,
            )
            return parse_agent_output(raw_output, self.name)
        except Exception as exc:
            return AgentOutput(
                agent_name=self.name,
                metadata={"llm_error": str(exc)},
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

    def _build_llm_prompt(self, chunks: list[CodeChunk]) -> str:
        chunk_text = "\n\n".join(
            [
                f"File: {chunk.file_path}\n"
                f"Lines: {chunk.line_start}-{chunk.line_end}\n"
                "```code\n"
                f"{chunk.content[:4000]}\n"
                "```"
                for chunk in chunks
            ]
        )
        return (
            "Review these code chunks for high-confidence security issues. "
            "Return JSON matching this schema exactly:\n"
            "{\n"
            '  "agent_name": "Security Agent",\n'
            '  "findings": [\n'
            "    {\n"
            '      "title": "short title",\n'
            '      "severity": "CRITICAL|HIGH|MEDIUM|LOW",\n'
            '      "file_path": "path from input",\n'
            '      "line_start": 1,\n'
            '      "line_end": 1,\n'
            '      "description": "what is wrong",\n'
            '      "why_it_matters": "impact",\n'
            '      "suggested_fix": "specific fix",\n'
            '      "agent_source": "Security Agent"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Only include findings that are specific, actionable, and tied to the provided files.\n\n"
            f"{chunk_text}"
        )
