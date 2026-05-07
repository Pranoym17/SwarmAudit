import re

from app.agents.llm_enrichment import LLMEnrichmentMixin
from app.config import Settings
from app.schemas import AgentOutput, CodeChunk, Finding, Severity
from app.services.llm_client import LLMClient


PYTHON_DEF = re.compile(r"^\s*(async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")
PYTHON_BRANCH = re.compile(r"^\s*(if|elif|for|while|except|with)\b")
JS_FUNCTION = re.compile(r"^\s*(function\s+[A-Za-z_$][\w$]*|(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?\()")
JS_BRANCH = re.compile(r"^\s*(if|else\s+if|for|while|switch|catch)\b")
TODO_COMMENT = re.compile(r"(?i)\b(TODO|FIXME|HACK)\b")


MAX_CHUNK_LINES = 300
MAX_FUNCTION_LINES = 80
MAX_BRANCHES_PER_CHUNK = 25
MIN_MEANINGFUL_NAME_LENGTH = 3


class QualityAgent(LLMEnrichmentMixin):
    name = "Quality Agent"

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient(Settings())

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        findings: list[Finding] = []
        for chunk in chunks:
            findings.extend(self._scan_chunk(chunk))

        llm_output = await self._run_llm_enrichment(
            chunks,
            "Review these code chunks for high-confidence code quality issues such as overly complex structure, risky abstractions, poor naming, or maintainability problems.",
        )
        findings.extend(llm_output.findings)

        return AgentOutput(
            agent_name=self.name,
            findings=findings,
            metadata=self._llm_metadata(chunks, llm_output),
        )

    def _scan_chunk(self, chunk: CodeChunk) -> list[Finding]:
        findings: list[Finding] = []
        lines = chunk.content.splitlines()

        findings.extend(self._check_large_chunk(chunk, lines))
        findings.extend(self._check_long_functions(chunk, lines))
        findings.extend(self._check_branch_density(chunk, lines))
        findings.extend(self._check_todo_comments(chunk, lines))
        findings.extend(self._check_short_names(chunk, lines))

        return findings

    def _check_large_chunk(self, chunk: CodeChunk, lines: list[str]) -> list[Finding]:
        if len(lines) <= MAX_CHUNK_LINES:
            return []

        return [
            self._finding(
                "Large source file section",
                Severity.low,
                chunk,
                chunk.line_start,
                chunk.line_end,
                "This source section is large enough to make review, testing, and future changes harder.",
                "Split unrelated responsibilities into smaller modules or focused helper functions.",
            )
        ]

    def _check_long_functions(self, chunk: CodeChunk, lines: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        active_start: int | None = None
        active_name: str | None = None
        active_indent = 0

        for index, line in enumerate(lines):
            if not line.strip():
                continue

            match = self._definition_match(line)
            indent = self._indent_width(line)

            if active_start is not None and indent <= active_indent and match:
                findings.extend(self._long_function_finding(chunk, active_name, active_start, chunk.line_start + index - 1))
                active_start = None
                active_name = None

            if match:
                active_start = chunk.line_start + index
                active_name = match.group(2) if match.lastindex and match.lastindex >= 2 else "function"
                active_indent = indent

        if active_start is not None:
            findings.extend(self._long_function_finding(chunk, active_name, active_start, chunk.line_end))

        return findings

    def _check_branch_density(self, chunk: CodeChunk, lines: list[str]) -> list[Finding]:
        branch_count = sum(1 for line in lines if PYTHON_BRANCH.match(line) or JS_BRANCH.match(line))
        if branch_count <= MAX_BRANCHES_PER_CHUNK:
            return []

        return [
            self._finding(
                "High branching complexity",
                Severity.medium,
                chunk,
                chunk.line_start,
                chunk.line_end,
                f"This code section contains {branch_count} control-flow branches.",
                "Extract decision-heavy logic into named helpers and add focused tests around each path.",
            )
        ]

    def _check_todo_comments(self, chunk: CodeChunk, lines: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        for offset, line in enumerate(lines):
            if TODO_COMMENT.search(line):
                line_number = chunk.line_start + offset
                findings.append(
                    self._finding(
                        "Unresolved maintenance comment",
                        Severity.low,
                        chunk,
                        line_number,
                        line_number,
                        "A TODO/FIXME/HACK marker indicates known unfinished or fragile code.",
                        "Convert the comment into a tracked issue or resolve it before shipping.",
                    )
                )
        return findings

    def _check_short_names(self, chunk: CodeChunk, lines: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        for offset, line in enumerate(lines):
            match = self._definition_match(line)
            if not match:
                continue

            name = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
            if len(name) < MIN_MEANINGFUL_NAME_LENGTH and name not in {"id"}:
                line_number = chunk.line_start + offset
                findings.append(
                    self._finding(
                        "Very short symbol name",
                        Severity.low,
                        chunk,
                        line_number,
                        line_number,
                        f"The symbol `{name}` is short enough to make intent unclear.",
                        "Use a descriptive function, class, or variable name that explains the role of this code.",
                    )
                )
        return findings

    def _long_function_finding(
        self,
        chunk: CodeChunk,
        name: str | None,
        line_start: int,
        line_end: int,
    ) -> list[Finding]:
        if line_end - line_start + 1 <= MAX_FUNCTION_LINES:
            return []

        return [
            self._finding(
                "Long function or class body",
                Severity.medium,
                chunk,
                line_start,
                line_end,
                f"`{name or 'This symbol'}` spans more than {MAX_FUNCTION_LINES} lines.",
                "Extract cohesive helper functions and keep each function centered on one responsibility.",
            )
        ]

    def _definition_match(self, line: str) -> re.Match[str] | None:
        return PYTHON_DEF.match(line) or JS_FUNCTION.match(line)

    def _indent_width(self, line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def _finding(
        self,
        title: str,
        severity: Severity,
        chunk: CodeChunk,
        line_start: int,
        line_end: int,
        description: str,
        suggested_fix: str,
    ) -> Finding:
        return Finding(
            title=title,
            severity=severity,
            file_path=chunk.file_path,
            line_start=line_start,
            line_end=line_end,
            description=description,
            why_it_matters="Maintainable code is easier to review, test, debug, and safely extend during a hackathon demo.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
        )
