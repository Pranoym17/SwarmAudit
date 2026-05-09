import json
import re
import tomllib
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.schemas import AgentOutput, CodeChunk, Finding, Severity


@dataclass(frozen=True)
class Dependency:
    name: str
    version: str | None
    ecosystem: str
    manifest_path: str
    line_number: int
    source: str


class DependencyAgent:
    name = "Dependency Agent"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        dependencies = self._parse_dependencies(chunks)
        findings: list[Finding] = []
        cves: list[dict[str, Any]] = []
        warnings: list[str] = []

        if self.settings.enable_dependency_cve_lookup and dependencies:
            cves, warnings = await self._lookup_cves(dependencies)
            findings.extend(self._cve_findings(cves))

        return AgentOutput(
            agent_name=self.name,
            findings=findings,
            metadata={
                "mode": "manifest-parse+optional-osv",
                "dependency_count": len(dependencies),
                "manifests": sorted({dependency.manifest_path for dependency in dependencies}),
                "dependency_cves": cves,
                "warnings": warnings,
            },
        )

    def _parse_dependencies(self, chunks: list[CodeChunk]) -> list[Dependency]:
        dependencies: list[Dependency] = []
        seen: set[tuple[str, str, str, str | None]] = set()

        for chunk in chunks:
            parsed = self._parse_chunk(chunk)
            for dependency in parsed:
                key = (
                    dependency.ecosystem,
                    dependency.name.lower(),
                    dependency.manifest_path,
                    dependency.version,
                )
                if key in seen:
                    continue
                seen.add(key)
                dependencies.append(dependency)

        return dependencies

    def _parse_chunk(self, chunk: CodeChunk) -> list[Dependency]:
        path = chunk.file_path.lower()
        if path.endswith("requirements.txt"):
            return self._parse_requirements(chunk)
        if path.endswith("package.json"):
            return self._parse_package_json(chunk)
        if path.endswith("pyproject.toml"):
            return self._parse_pyproject(chunk)
        if path.endswith("go.mod"):
            return self._parse_go_mod(chunk)
        if path.endswith("cargo.toml"):
            return self._parse_cargo_toml(chunk)
        return []

    def _parse_requirements(self, chunk: CodeChunk) -> list[Dependency]:
        dependencies: list[Dependency] = []
        for offset, raw_line in enumerate(chunk.content.splitlines()):
            line = raw_line.split("#", 1)[0].strip()
            if not line or line.startswith(("-", "git+", "http://", "https://")):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:\[.*?\])?\s*(==|~=|>=|<=|>|<)?\s*([A-Za-z0-9_.*!+-][A-Za-z0-9_.*!+-]*)?", line)
            if not match:
                continue
            name = match.group(1)
            version = self._clean_version(match.group(3))
            dependencies.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem="PyPI",
                    manifest_path=chunk.file_path,
                    line_number=chunk.line_start + offset,
                    source=line,
                )
            )
        return dependencies

    def _parse_package_json(self, chunk: CodeChunk) -> list[Dependency]:
        try:
            data = json.loads(chunk.content)
        except json.JSONDecodeError:
            return []

        dependencies: list[Dependency] = []
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            section_dependencies = data.get(section, {})
            if not isinstance(section_dependencies, dict):
                continue
            for name, raw_version in section_dependencies.items():
                dependencies.append(
                    Dependency(
                        name=name,
                        version=self._clean_version(str(raw_version)),
                        ecosystem="npm",
                        manifest_path=chunk.file_path,
                        line_number=self._line_for_text(chunk, f'"{name}"'),
                        source=section,
                    )
                )
        return dependencies

    def _parse_pyproject(self, chunk: CodeChunk) -> list[Dependency]:
        try:
            data = tomllib.loads(chunk.content)
        except tomllib.TOMLDecodeError:
            return []

        dependencies: list[Dependency] = []
        project_dependencies = data.get("project", {}).get("dependencies", [])
        if isinstance(project_dependencies, list):
            for value in project_dependencies:
                dependency = self._python_dependency_from_string(str(value), chunk)
                if dependency:
                    dependencies.append(dependency)

        poetry_dependencies = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if isinstance(poetry_dependencies, dict):
            for name, value in poetry_dependencies.items():
                if name.lower() == "python":
                    continue
                dependencies.append(
                    Dependency(
                        name=name,
                        version=self._clean_version(str(value)),
                        ecosystem="PyPI",
                        manifest_path=chunk.file_path,
                        line_number=self._line_for_text(chunk, name),
                        source="tool.poetry.dependencies",
                    )
                )
        return dependencies

    def _parse_go_mod(self, chunk: CodeChunk) -> list[Dependency]:
        dependencies: list[Dependency] = []
        in_require_block = False
        for offset, raw_line in enumerate(chunk.content.splitlines()):
            line = raw_line.strip()
            if line.startswith("require ("):
                in_require_block = True
                continue
            if in_require_block and line == ")":
                in_require_block = False
                continue
            if line.startswith("require "):
                line = line.removeprefix("require ").strip()
            elif not in_require_block:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            dependencies.append(
                Dependency(
                    name=parts[0],
                    version=self._clean_version(parts[1]),
                    ecosystem="Go",
                    manifest_path=chunk.file_path,
                    line_number=chunk.line_start + offset,
                    source=line,
                )
            )
        return dependencies

    def _parse_cargo_toml(self, chunk: CodeChunk) -> list[Dependency]:
        try:
            data = tomllib.loads(chunk.content)
        except tomllib.TOMLDecodeError:
            return []

        dependencies: list[Dependency] = []
        for section in ("dependencies", "dev-dependencies", "build-dependencies"):
            section_dependencies = data.get(section, {})
            if not isinstance(section_dependencies, dict):
                continue
            for name, value in section_dependencies.items():
                version = value.get("version") if isinstance(value, dict) else str(value)
                dependencies.append(
                    Dependency(
                        name=name,
                        version=self._clean_version(str(version)),
                        ecosystem="crates.io",
                        manifest_path=chunk.file_path,
                        line_number=self._line_for_text(chunk, name),
                        source=section,
                    )
                )
        return dependencies

    def _python_dependency_from_string(self, value: str, chunk: CodeChunk) -> Dependency | None:
        match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:\[.*?\])?\s*(?:==|~=|>=|<=|>|<)?\s*([A-Za-z0-9_.*!+-]+)?", value)
        if not match:
            return None
        return Dependency(
            name=match.group(1),
            version=self._clean_version(match.group(2)),
            ecosystem="PyPI",
            manifest_path=chunk.file_path,
            line_number=self._line_for_text(chunk, match.group(1)),
            source="project.dependencies",
        )

    async def _lookup_cves(self, dependencies: list[Dependency]) -> tuple[list[dict[str, Any]], list[str]]:
        query_dependencies = [dependency for dependency in dependencies if dependency.version]
        if not query_dependencies:
            return [], []

        queries = [
            {
                "package": {"name": dependency.name, "ecosystem": dependency.ecosystem},
                "version": dependency.version,
            }
            for dependency in query_dependencies
        ]
        try:
            async with httpx.AsyncClient(timeout=self.settings.dependency_osv_timeout_seconds) as client:
                response = await client.post("https://api.osv.dev/v1/querybatch", json={"queries": queries})
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            return [], [f"Dependency CVE lookup failed gracefully: {exc}"]

        cves: list[dict[str, Any]] = []
        results = payload.get("results", [])
        for dependency, result in zip(query_dependencies, results, strict=False):
            for vuln in result.get("vulns", []):
                cves.append(self._cve_record(dependency, vuln))
        return cves, []

    def _cve_record(self, dependency: Dependency, vuln: dict[str, Any]) -> dict[str, Any]:
        severity = self._severity_from_vuln(vuln)
        return {
            "id": vuln.get("id", "UNKNOWN"),
            "package": dependency.name,
            "version": dependency.version,
            "ecosystem": dependency.ecosystem,
            "severity": severity.value,
            "summary": vuln.get("summary") or vuln.get("details", "Known vulnerability reported by OSV.dev."),
            "manifest_path": dependency.manifest_path,
            "line_number": dependency.line_number,
            "fixed_version": self._fixed_version(vuln),
        }

    def _cve_findings(self, cves: list[dict[str, Any]]) -> list[Finding]:
        findings: list[Finding] = []
        for cve in cves:
            package = cve["package"]
            version = cve.get("version") or "unknown"
            cve_id = cve["id"]
            fixed_version = cve.get("fixed_version") or "a non-vulnerable version"
            findings.append(
                Finding(
                    title=f"Vulnerable dependency: {package}",
                    severity=Severity(cve["severity"]),
                    file_path=cve["manifest_path"],
                    line_start=cve["line_number"],
                    line_end=cve["line_number"],
                    description=f"{package}@{version} is associated with {cve_id}: {cve['summary']}",
                    why_it_matters="Known vulnerable dependencies can expose the application to publicly documented exploits.",
                    suggested_fix=f"Upgrade {package} to {fixed_version} after checking compatibility and lockfile updates.",
                    agent_source=self.name,
                    category="dependency",
                    confidence=0.95,
                )
            )
        return findings

    def _severity_from_vuln(self, vuln: dict[str, Any]) -> Severity:
        database_severity = str(vuln.get("database_specific", {}).get("severity", "")).upper()
        if database_severity in Severity._value2member_map_:
            return Severity(database_severity)

        scores = []
        for severity in vuln.get("severity", []):
            score = self._cvss_score(str(severity.get("score", "")))
            if score is not None:
                scores.append(score)
        max_score = max(scores, default=0.0)
        if max_score >= 9:
            return Severity.critical
        if max_score >= 7:
            return Severity.high
        if max_score >= 4:
            return Severity.medium
        return Severity.low

    def _cvss_score(self, score: str) -> float | None:
        match = re.search(r"/AV:|CVSS:", score)
        if match:
            return None
        try:
            return float(score)
        except ValueError:
            return None

    def _fixed_version(self, vuln: dict[str, Any]) -> str | None:
        for affected in vuln.get("affected", []):
            for range_data in affected.get("ranges", []):
                for event in range_data.get("events", []):
                    fixed = event.get("fixed")
                    if fixed:
                        return fixed
        return None

    def _clean_version(self, value: str | None) -> str | None:
        if not value:
            return None
        version = value.strip().strip('"').strip("'")
        version = re.sub(r"^[\^~<>=!\s]+", "", version)
        version = version.split(",", 1)[0].strip()
        if not version or version == "*" or any(char in version for char in "{}"):
            return None
        return version

    def _line_for_text(self, chunk: CodeChunk, text: str) -> int:
        for offset, line in enumerate(chunk.content.splitlines()):
            if text in line:
                return chunk.line_start + offset
        return chunk.line_start
