import re

from app.schemas import AgentOutput, CodeChunk, Finding, Severity


PYTHON_PUBLIC_DEF = re.compile(r"^(\s*)(async\s+def|def|class)\s+([A-Za-z][A-Za-z0-9_]*)")
README_SETUP_TERMS = ("install", "setup", "quick start", "usage", "run")
README_TEST_TERMS = ("test", "pytest", "unittest")
README_CONFIG_TERMS = ("config", "environment", ".env", "settings")


class DocsAgent:
    name = "Docs Agent"

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        findings: list[Finding] = []
        readme_seen = False

        for chunk in chunks:
            if self._is_readme(chunk.file_path):
                readme_seen = True
                findings.extend(self._scan_readme(chunk))
            elif chunk.language == "Python":
                findings.extend(self._scan_python_docstrings(chunk))

        if not readme_seen and chunks:
            first_chunk = chunks[0]
            findings.append(
                self._finding(
                    "README not found in scanned files",
                    Severity.medium,
                    first_chunk,
                    first_chunk.line_start,
                    first_chunk.line_start,
                    "The crawler did not find a top-level README file in the scanned repository inputs.",
                    "Add a README with setup, usage, configuration, and test instructions.",
                )
            )

        return AgentOutput(
            agent_name=self.name,
            findings=findings,
            metadata={"chunks_scanned": len(chunks), "mode": "static-rules"},
        )

    def _scan_readme(self, chunk: CodeChunk) -> list[Finding]:
        content = chunk.content.lower()
        findings: list[Finding] = []

        checks = [
            (
                any(term in content for term in README_SETUP_TERMS),
                "README missing usage/setup guidance",
                "A README should quickly tell visitors how to install and run the project.",
                "Add a Quick Start or Usage section with the commands needed to run the app.",
            ),
            (
                any(term in content for term in README_TEST_TERMS),
                "README missing test instructions",
                "Developers need a reliable way to verify the project after cloning it.",
                "Add a Tests section with the command used to run the test suite.",
            ),
            (
                any(term in content for term in README_CONFIG_TERMS),
                "README missing configuration notes",
                "Environment variables and model/provider settings are easy to misconfigure without documentation.",
                "Document required environment variables and include an `.env.example` reference.",
            ),
        ]

        for passed, title, description, suggested_fix in checks:
            if passed:
                continue
            findings.append(
                self._finding(
                    title,
                    Severity.low,
                    chunk,
                    chunk.line_start,
                    chunk.line_end,
                    description,
                    suggested_fix,
                )
            )

        return findings

    def _scan_python_docstrings(self, chunk: CodeChunk) -> list[Finding]:
        findings: list[Finding] = []
        lines = chunk.content.splitlines()

        for index, line in enumerate(lines):
            match = PYTHON_PUBLIC_DEF.match(line)
            if not match:
                continue

            symbol_name = match.group(3)
            if symbol_name.startswith("_"):
                continue
            if self._has_docstring(lines, index):
                continue

            line_number = chunk.line_start + index
            findings.append(
                self._finding(
                    "Public Python symbol missing docstring",
                    Severity.low,
                    chunk,
                    line_number,
                    line_number,
                    f"`{symbol_name}` is public but does not start with a docstring.",
                    "Add a short docstring describing purpose, parameters, return value, or side effects.",
                )
            )

        return findings

    def _has_docstring(self, lines: list[str], definition_index: int) -> bool:
        for line in lines[definition_index + 1 : definition_index + 5]:
            stripped = line.strip()
            if not stripped:
                continue
            return stripped.startswith(('"""', "'''"))
        return False

    def _is_readme(self, file_path: str) -> bool:
        return file_path.rsplit("/", 1)[-1].lower() in {"readme", "readme.md", "readme.rst", "readme.txt"}

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
            why_it_matters="Good documentation helps reviewers, users, and judges understand the project quickly.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
        )
