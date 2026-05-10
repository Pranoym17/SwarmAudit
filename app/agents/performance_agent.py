import re

from app.agents.llm_enrichment import LLMEnrichmentMixin
from app.config import Settings
from app.schemas import AgentOutput, CodeChunk, Finding, Severity
from app.services.llm_client import LLMClient


REQUEST_WITHOUT_TIMEOUT = re.compile(r"\brequests\.(get|post|put|patch|delete)\s*\((?!.*\btimeout\s*=)")
SYNC_FS_JS = re.compile(r"\b(readFileSync|writeFileSync|readdirSync|statSync)\s*\(")
PYTHON_LOOP = re.compile(r"^(\s*)(for|while)\b")
PYTHON_FILE_READ = re.compile(r"\b(open\s*\(|Path\s*\([^)]*\)\.read_(text|bytes)\s*\()")


class PerformanceAgent(LLMEnrichmentMixin):
    name = "Performance Agent"

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient(Settings())

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        findings: list[Finding] = []
        for chunk in chunks:
            findings.extend(self._scan_chunk(chunk))

        llm_output = await self._run_llm_enrichment(
            chunks,
            "Review these code chunks for high-confidence performance issues such as algorithmic bottlenecks, blocking I/O, inefficient repeated work, or expensive hot paths.",
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
        loop_stack: list[int] = []
        async_indent_stack: list[int] = []

        for offset, line in enumerate(lines):
            actual_line = chunk.line_start + offset
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))

            loop_stack = [loop_indent for loop_indent in loop_stack if indent > loop_indent]
            async_indent_stack = [async_indent for async_indent in async_indent_stack if indent > async_indent]

            if stripped.startswith("async def "):
                async_indent_stack.append(indent)

            loop_match = PYTHON_LOOP.match(line)
            if loop_match:
                if loop_stack:
                    findings.append(
                        self._finding(
                            "Nested loop may become expensive",
                            Severity.low,
                            chunk,
                            actual_line,
                            "A loop nested inside another loop can turn small inputs into slow O(n^2) work.",
                            "Consider indexing data with a dictionary/set, batching work, or documenting why nested iteration is bounded.",
                        )
                    )
                loop_stack.append(len(loop_match.group(1)))

            if REQUEST_WITHOUT_TIMEOUT.search(line):
                call_snippet = self._snippet(line)
                findings.append(
                    self._finding(
                        "HTTP request without timeout",
                        Severity.medium,
                        chunk,
                        actual_line,
                        f"`{call_snippet}` does not pass `timeout=`, so this request can wait indefinitely.",
                        f"Add a bounded timeout to this call, for example `{call_snippet.rstrip(')')}, timeout=10)` if the arguments fit that shape.",
                        why_it_matters="This specific network call can tie up a worker or thread when the remote service stalls.",
                    )
                )

            if async_indent_stack and "time.sleep(" in line:
                sleep_snippet = self._snippet(line)
                findings.append(
                    self._finding(
                        "Blocking sleep inside async function",
                        Severity.medium,
                        chunk,
                        actual_line,
                        f"`{sleep_snippet}` runs inside an async scope and blocks the event loop.",
                        "Replace this call with `await asyncio.sleep(...)` or move blocking work out of the async path.",
                        why_it_matters="Blocking the event loop here delays unrelated coroutines that should be able to keep running.",
                    )
                )

            if loop_stack and PYTHON_FILE_READ.search(line):
                read_snippet = self._snippet(line)
                findings.append(
                    self._finding(
                        "File read inside loop",
                        Severity.low,
                        chunk,
                        actual_line,
                        f"`{read_snippet}` appears inside a loop, so the same path may hit disk repeatedly.",
                        "Read once before the loop, cache by file path, or stream deliberately if every iteration needs fresh data.",
                        why_it_matters="Repeated disk I/O in this loop can dominate runtime as the input size grows.",
                    )
                )

            if SYNC_FS_JS.search(line):
                fs_snippet = self._snippet(line)
                findings.append(
                    self._finding(
                        "Synchronous filesystem call",
                        Severity.low,
                        chunk,
                        actual_line,
                        f"`{fs_snippet}` uses a synchronous filesystem API.",
                        "Use `fs.promises` or move this filesystem work outside latency-sensitive request paths.",
                        why_it_matters="This call blocks the Node.js event loop while disk I/O completes.",
                    )
                )

        return findings

    def _finding(
        self,
        title: str,
        severity: Severity,
        chunk: CodeChunk,
        line_number: int,
        description: str,
        suggested_fix: str,
        why_it_matters: str | None = None,
    ) -> Finding:
        return Finding(
            title=title,
            severity=severity,
            file_path=chunk.file_path,
            line_start=line_number,
            line_end=line_number,
            description=description,
            why_it_matters=why_it_matters
            or "Performance issues in hot paths can increase latency, resource usage, and demo analysis time.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
        )

    def _snippet(self, line: str, max_length: int = 96) -> str:
        normalized = " ".join(line.strip().split())
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[: max_length - 3]}..."
