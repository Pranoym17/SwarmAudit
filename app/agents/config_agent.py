import re

from app.schemas import AgentOutput, CodeChunk, Finding, Severity


CONFIG_PATTERNS = [
    (
        re.compile(r"(?i)\bdebug\s*=\s*true\b"),
        "Debug mode enabled",
        Severity.high,
        "Debug mode can expose stack traces, environment details, and interactive debugger behavior.",
        "Disable debug mode in production and load it from an environment-specific setting.",
        0.9,
    ),
    (
        re.compile(r"(?i)(allow_origins|cors_allowed_origins)\s*=\s*\[[^\]]*['\"]\*['\"]"),
        "Wildcard CORS origin",
        Severity.medium,
        "A wildcard CORS policy can allow untrusted origins to interact with browser-protected resources.",
        "Replace '*' with an explicit allowlist of trusted production origins.",
        0.86,
    ),
    (
        re.compile(r"(?i)access-control-allow-origin['\"]?\s*[:=]\s*['\"]\*['\"]"),
        "Wildcard Access-Control-Allow-Origin",
        Severity.medium,
        "A wildcard Access-Control-Allow-Origin header weakens browser origin protections.",
        "Set Access-Control-Allow-Origin to specific trusted domains.",
        0.86,
    ),
    (
        re.compile(r"(?i)verify\s*=\s*false\b"),
        "TLS verification disabled in configuration",
        Severity.high,
        "Disabling TLS verification lets attackers intercept traffic that should be protected.",
        "Remove verify=False and configure a trusted CA bundle if custom certificates are required.",
        0.91,
    ),
    (
        re.compile(r"(?i)node_tls_reject_unauthorized\s*=\s*['\"]?0['\"]?"),
        "Node TLS certificate checks disabled",
        Severity.high,
        "Disabling Node.js TLS verification makes HTTPS connections vulnerable to interception.",
        "Remove NODE_TLS_REJECT_UNAUTHORIZED=0 and fix certificate trust at the environment level.",
        0.92,
    ),
    (
        re.compile(r"(?i)(secret_key|jwt_secret|session_secret)\s*=\s*['\"](secret|changeme|change-me|password|django-insecure[^'\"]*)['\"]"),
        "Weak default secret configured",
        Severity.high,
        "Default secrets are easy to guess and can compromise sessions, JWTs, or signed cookies.",
        "Generate a strong secret and load it from a secret manager or environment variable.",
        0.9,
    ),
]


class ConfigAgent:
    name = "Config Agent"

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
        for offset, line in enumerate(chunk.content.splitlines()):
            actual_line = chunk.line_start + offset
            for pattern, title, severity, description, fix, confidence in CONFIG_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        self._finding(
                            title=title,
                            severity=severity,
                            chunk=chunk,
                            line_number=actual_line,
                            description=description,
                            suggested_fix=fix,
                            confidence=confidence,
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
        confidence: float,
    ) -> Finding:
        return Finding(
            title=title,
            severity=severity,
            file_path=chunk.file_path,
            line_start=line_number,
            line_end=line_number,
            description=description,
            why_it_matters="Development-safe configuration often becomes production risk when copied into deployed environments.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
            category="config",
            confidence=confidence,
        )
