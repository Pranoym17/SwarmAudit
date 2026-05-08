import re

from app.schemas import AgentOutput, CodeChunk, Finding, Severity


EXCEPT_LINE = re.compile(r"^\s*except(?:\s+([\w.]+))?.*:")
REQUEST_WITHOUT_TIMEOUT = re.compile(r"\brequests\.(get|post|put|patch|delete)\s*\((?!.*\btimeout\s*=)")
JS_FETCH_WITHOUT_ABORT = re.compile(r"\bfetch\s*\([^,\n)]+\)")
LOGGING_SIGNALS = ("logging.", "logger.", ".exception(", ".error(", ".warning(", "console.error", "console.warn")


class ErrorHandlingAgent:
    name = "Error Handling Agent"

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

        for index, line in enumerate(lines):
            actual_line = chunk.line_start + index
            stripped = line.strip()

            except_match = EXCEPT_LINE.match(line)
            if except_match:
                findings.extend(self._scan_except_block(chunk, lines, index, actual_line, except_match.group(1)))

            if REQUEST_WITHOUT_TIMEOUT.search(line):
                findings.append(
                    self._finding(
                        "External HTTP call without timeout",
                        Severity.medium,
                        chunk,
                        actual_line,
                        "An external request without a timeout can hang a worker during a downstream outage.",
                        "Pass an explicit timeout and handle timeout exceptions with logging or retry policy.",
                        0.84,
                    )
                )

            if JS_FETCH_WITHOUT_ABORT.search(line) and "AbortController" not in chunk.content:
                findings.append(
                    self._finding(
                        "Fetch call has no cancellation timeout",
                        Severity.low,
                        chunk,
                        actual_line,
                        "Browser or Node fetch calls can wait indefinitely unless a timeout/cancellation path is provided.",
                        "Use AbortController or a client wrapper that enforces request deadlines.",
                        0.76,
                    )
                )

        return findings

    def _scan_except_block(
        self,
        chunk: CodeChunk,
        lines: list[str],
        except_index: int,
        actual_line: int,
        exception_name: str | None,
    ) -> list[Finding]:
        block_lines = self._collect_block(lines, except_index)
        normalized = "\n".join(line.strip() for line in block_lines)
        findings: list[Finding] = []

        if exception_name in (None, "Exception", "BaseException"):
            findings.append(
                self._finding(
                    "Broad exception handler",
                    Severity.medium,
                    chunk,
                    actual_line,
                    "Broad exception handlers can hide unrelated production failures and make incidents harder to diagnose.",
                    "Catch the narrow exception type you expect and let unexpected failures surface with context.",
                    0.82,
                )
            )

        if not block_lines:
            return findings

        has_logging = any(signal in normalized for signal in LOGGING_SIGNALS)
        reraises = re.search(r"(^|\n)raise(\s|$)", normalized) is not None
        silent_body = normalized in {"pass", "..."} or normalized.startswith("return None")

        if silent_body:
            findings.append(
                self._finding(
                    "Exception swallowed without recovery",
                    Severity.high,
                    chunk,
                    actual_line,
                    "The handler suppresses the exception without logging, retrying, or returning a meaningful fallback.",
                    "Log the exception with context, re-raise when appropriate, or return a deliberate typed fallback.",
                    0.9,
                )
            )
        elif not has_logging and not reraises:
            findings.append(
                self._finding(
                    "Exception handled without logging or re-raise",
                    Severity.medium,
                    chunk,
                    actual_line,
                    "Handling an exception without logging or re-raising can erase the root cause during production incidents.",
                    "Add structured logging with request context, or re-raise after adding recovery-specific context.",
                    0.82,
                )
            )

        return findings

    def _collect_block(self, lines: list[str], except_index: int) -> list[str]:
        except_line = lines[except_index]
        except_indent = len(except_line) - len(except_line.lstrip(" "))
        block: list[str] = []

        for line in lines[except_index + 1 :]:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= except_indent:
                break
            block.append(line)

        return block

    def _finding(
        self,
        title: str,
        severity: Severity,
        chunk: CodeChunk,
        line_number: int,
        description: str,
        suggested_fix: str,
        confidence: float,
    ) -> Finding:
        return Finding(
            title=title,
            severity=severity,
            file_path=chunk.file_path,
            line_start=line_number,
            line_end=line_number,
            description=description,
            why_it_matters="Weak error handling turns small downstream failures into outages that are hard to diagnose and recover from.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
            category="error_handling",
            confidence=confidence,
        )
