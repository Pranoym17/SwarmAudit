import re

from app.schemas import AgentOutput, CodeChunk, Finding, Severity


REQUEST_WITHOUT_TIMEOUT = re.compile(r"\brequests\.(get|post|put|patch|delete)\s*\((?!.*\btimeout\s*=)")
SYNC_FS_JS = re.compile(r"\b(readFileSync|writeFileSync|readdirSync|statSync)\s*\(")
PYTHON_LOOP = re.compile(r"^(\s*)(for|while)\b")
PYTHON_FILE_READ = re.compile(r"\b(open\s*\(|Path\s*\([^)]*\)\.read_(text|bytes)\s*\()")


class PerformanceAgent:
    name = "Performance Agent"

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        findings: list[Finding] = []
        for chunk in chunks:
            findings.extend(self._scan_chunk(chunk))

        return AgentOutput(
            agent_name=self.name,
            findings=findings,
            metadata={"chunks_scanned": len(chunks), "mode": "static-rules"},
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
                findings.append(
                    self._finding(
                        "HTTP request without timeout",
                        Severity.medium,
                        chunk,
                        actual_line,
                        "Network calls without timeouts can hang workers and make the app appear frozen under bad network conditions.",
                        "Pass an explicit timeout, for example requests.get(url, timeout=10).",
                    )
                )

            if async_indent_stack and "time.sleep(" in line:
                findings.append(
                    self._finding(
                        "Blocking sleep inside async function",
                        Severity.medium,
                        chunk,
                        actual_line,
                        "time.sleep blocks the event loop, delaying unrelated async work.",
                        "Use await asyncio.sleep(...) inside async functions.",
                    )
                )

            if loop_stack and PYTHON_FILE_READ.search(line):
                findings.append(
                    self._finding(
                        "File read inside loop",
                        Severity.low,
                        chunk,
                        actual_line,
                        "Repeated disk reads inside loops can dominate runtime and slow audits on larger inputs.",
                        "Read once before the loop, cache results, or stream data deliberately.",
                    )
                )

            if SYNC_FS_JS.search(line):
                findings.append(
                    self._finding(
                        "Synchronous filesystem call",
                        Severity.low,
                        chunk,
                        actual_line,
                        "Synchronous filesystem APIs block the Node.js event loop and can hurt request latency.",
                        "Use async fs.promises APIs or move blocking work outside latency-sensitive paths.",
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
    ) -> Finding:
        return Finding(
            title=title,
            severity=severity,
            file_path=chunk.file_path,
            line_start=line_number,
            line_end=line_number,
            description=description,
            why_it_matters="Performance issues in hot paths can increase latency, resource usage, and demo analysis time.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
        )
