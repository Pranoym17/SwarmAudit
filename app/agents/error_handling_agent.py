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
                call_snippet = self._snippet(line)
                findings.append(
                    self._finding(
                        "External HTTP call without timeout",
                        Severity.medium,
                        chunk,
                        actual_line,
                        f"`{call_snippet}` makes an external request without an explicit timeout.",
                        f"Add `timeout=` to `{call_snippet}` and handle timeout exceptions with logging or retry policy.",
                        0.84,
                        why_it_matters=(
                            "This exact call can hold the worker until the operating system or remote service gives up, "
                            "which makes downstream outages spread into the app."
                        ),
                    )
                )

            if JS_FETCH_WITHOUT_ABORT.search(line) and "AbortController" not in chunk.content:
                call_snippet = self._snippet(line)
                findings.append(
                    self._finding(
                        "Fetch call has no cancellation timeout",
                        Severity.low,
                        chunk,
                        actual_line,
                        f"`{call_snippet}` uses fetch without an AbortController or deadline in this scanned chunk.",
                        "Wrap this fetch in an AbortController timeout or a shared HTTP client that enforces request deadlines.",
                        0.76,
                        why_it_matters="A stuck fetch can leave the user action or server-side request waiting with no bounded failure path.",
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
            exception_label = exception_name or "bare except"
            findings.append(
                self._finding(
                    "Broad exception handler",
                    Severity.medium,
                    chunk,
                    actual_line,
                    f"The handler catches `{exception_label}`, which can group unrelated failures into the same recovery path.",
                    f"Replace `{exception_label}` with the narrow exception type expected here, and let unexpected failures surface with context.",
                    0.82,
                    why_it_matters="Broad handlers make different failure modes look identical during incident triage.",
                )
            )

        if not block_lines:
            return findings

        has_logging = any(signal in normalized for signal in LOGGING_SIGNALS)
        reraises = re.search(r"(^|\n)raise(\s|$)", normalized) is not None
        silent_body = normalized in {"pass", "..."} or normalized.startswith("return None")

        if silent_body:
            body_preview = self._snippet(normalized.splitlines()[0] if normalized else "empty handler")
            findings.append(
                self._finding(
                    "Exception swallowed without recovery",
                    Severity.high,
                    chunk,
                    actual_line,
                    f"The except block uses `{body_preview}` and suppresses the failure without logging, retrying, or returning a meaningful fallback.",
                    "Log the exception with local context, re-raise when the caller must handle it, or return a deliberate typed fallback.",
                    0.9,
                    why_it_matters="This handler erases the original failure at the exact point where debugging context is still available.",
                )
            )
        elif not has_logging and not reraises:
            first_action = self._snippet(normalized.splitlines()[0] if normalized else "handler body")
            findings.append(
                self._finding(
                    "Exception handled without logging or re-raise",
                    Severity.medium,
                    chunk,
                    actual_line,
                    f"The except block continues with `{first_action}` but does not log or re-raise the exception.",
                    "Add structured logging before this recovery path, or re-raise after adding recovery-specific context.",
                    0.82,
                    why_it_matters="The recovery branch may keep execution going while hiding why the branch was needed.",
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
            or "Weak error handling turns small downstream failures into outages that are hard to diagnose and recover from.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
            category="error_handling",
            confidence=confidence,
        )

    def _snippet(self, line: str, max_length: int = 96) -> str:
        normalized = " ".join(line.strip().split())
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[: max_length - 3]}..."
