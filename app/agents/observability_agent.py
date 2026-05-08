import re
from collections import Counter

from app.schemas import AgentOutput, CodeChunk, Finding, Severity


PRINT_CALL = re.compile(r"\bprint\s*\(")
LOGGER_CALL = re.compile(r"\b(logging|logger|log)\.(debug|info|warning|error|exception|critical)\s*\(")
ROUTE_DECLARATION = re.compile(r"@\w*(app|router)\.(get|post|put|patch|delete|route)\s*\(\s*['\"]([^'\"]+)['\"]")
JS_ROUTE_DECLARATION = re.compile(r"\b(app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]")
SENSITIVE_LOG_LINE = re.compile(r"(?i)(print|logging|logger|console)\S*\s*\(.*(password|passwd|secret|token|api[_-]?key)")
HEALTH_PATHS = {"/health", "/healthz", "/ready", "/readiness", "/live", "/liveness", "/ping"}


class ObservabilityAgent:
    name = "Observability Agent"

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        findings: list[Finding] = []
        route_paths: set[str] = set()
        print_counts: Counter[str] = Counter()
        logger_seen = False

        for chunk in chunks:
            chunk_findings, chunk_routes, chunk_prints, chunk_has_logger = self._scan_chunk(chunk)
            findings.extend(chunk_findings)
            route_paths.update(chunk_routes)
            print_counts[chunk.file_path] += chunk_prints
            logger_seen = logger_seen or chunk_has_logger

        findings.extend(self._print_overuse_findings(chunks, print_counts, logger_seen))
        if route_paths and not any(path in HEALTH_PATHS for path in route_paths):
            findings.append(self._missing_health_finding(chunks[0]))

        return AgentOutput(
            agent_name=self.name,
            findings=findings,
            metadata={
                "chunks_scanned": len(chunks),
                "mode": "static-rules",
                "routes_seen": len(route_paths),
                "logging_seen": logger_seen,
            },
        )

    def _scan_chunk(self, chunk: CodeChunk) -> tuple[list[Finding], set[str], int, bool]:
        findings: list[Finding] = []
        routes: set[str] = set()
        print_count = 0
        has_logger = False

        for offset, line in enumerate(chunk.content.splitlines()):
            actual_line = chunk.line_start + offset
            if PRINT_CALL.search(line):
                print_count += 1
            if LOGGER_CALL.search(line):
                has_logger = True
            if SENSITIVE_LOG_LINE.search(line):
                findings.append(
                    self._finding(
                        "Sensitive value may be written to logs",
                        Severity.high,
                        chunk,
                        actual_line,
                        "The log/print statement appears to include credential-like data.",
                        "Remove secrets from logs and log stable identifiers or masked values instead.",
                        0.86,
                    )
                )

            routes.update(match.group(3) for match in ROUTE_DECLARATION.finditer(line))
            routes.update(match.group(3) for match in JS_ROUTE_DECLARATION.finditer(line))

        return findings, routes, print_count, has_logger

    def _print_overuse_findings(
        self,
        chunks: list[CodeChunk],
        print_counts: Counter[str],
        logger_seen: bool,
    ) -> list[Finding]:
        if logger_seen:
            return []

        findings: list[Finding] = []
        first_chunk_by_path = {chunk.file_path: chunk for chunk in chunks}
        for file_path, count in print_counts.items():
            if count < 3:
                continue
            chunk = first_chunk_by_path[file_path]
            findings.append(
                self._finding(
                    "Print statements used instead of structured logging",
                    Severity.low,
                    chunk,
                    chunk.line_start,
                    f"This file has {count} print statements and no structured logging was detected in the scanned repo.",
                    "Use a logger with levels and structured context such as request_id, route, and operation.",
                    0.72,
                )
            )

        return findings

    def _missing_health_finding(self, chunk: CodeChunk) -> Finding:
        return self._finding(
            "Web service has routes but no health endpoint detected",
            Severity.medium,
            chunk,
            chunk.line_start,
            "The scanned code defines web routes but no /health, /ready, /live, or /ping endpoint was detected.",
            "Add a lightweight health endpoint that returns process readiness and dependency status appropriate for your deployment.",
            0.74,
        )

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
            why_it_matters="Without basic observability, production failures are harder to detect, triage, and explain during incidents.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
            category="observability",
            confidence=confidence,
        )
