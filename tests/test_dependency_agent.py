import pytest

from app.agents.dependency_agent import DependencyAgent
from app.config import Settings
from app.schemas import CodeChunk, Severity


def make_chunk(file_path: str, content: str) -> CodeChunk:
    return CodeChunk(
        file_path=file_path,
        language="Manifest",
        line_start=1,
        line_end=max(1, len(content.splitlines())),
        content=content,
    )


@pytest.mark.anyio
async def test_dependency_agent_parses_common_manifests_without_network():
    chunks = [
        make_chunk("requirements.txt", "requests==2.28.0\nfastapi>=0.100.0\n"),
        make_chunk("package.json", '{"dependencies": {"express": "^4.18.2"}}'),
        make_chunk("pyproject.toml", '[project]\ndependencies = ["pydantic==2.0.0"]\n'),
        make_chunk("go.mod", "module demo\n\nrequire github.com/gin-gonic/gin v1.9.1\n"),
        make_chunk("Cargo.toml", '[dependencies]\nserde = "1.0.0"\n'),
    ]

    output = await DependencyAgent(Settings(enable_dependency_cve_lookup=False)).analyze(chunks)

    assert output.agent_name == "Dependency Agent"
    assert output.findings == []
    assert output.metadata["dependency_count"] == 6
    assert "requirements.txt" in output.metadata["manifests"]
    assert output.metadata["dependency_cves"] == []


@pytest.mark.anyio
async def test_dependency_agent_turns_cves_into_findings(monkeypatch):
    async def fake_lookup_cves(dependencies):
        return (
            [
                {
                    "id": "GHSA-test",
                    "package": "requests",
                    "version": "2.28.0",
                    "ecosystem": "PyPI",
                    "severity": "HIGH",
                    "summary": "Demo vulnerability",
                    "manifest_path": "requirements.txt",
                    "line_number": 1,
                    "fixed_version": "2.32.0",
                }
            ],
            [],
        )

    agent = DependencyAgent(Settings(enable_dependency_cve_lookup=True))
    monkeypatch.setattr(agent, "_lookup_cves", fake_lookup_cves)

    output = await agent.analyze([make_chunk("requirements.txt", "requests==2.28.0\n")])

    assert output.findings[0].severity == Severity.high
    assert output.findings[0].category == "dependency"
    assert output.findings[0].agent_source == "Dependency Agent"
    assert output.metadata["dependency_cves"][0]["id"] == "GHSA-test"


@pytest.mark.anyio
async def test_dependency_agent_fails_gracefully_when_osv_is_unavailable(monkeypatch):
    async def fake_lookup_cves(dependencies):
        return [], ["Dependency CVE lookup failed gracefully: network unavailable"]

    agent = DependencyAgent(Settings(enable_dependency_cve_lookup=True))
    monkeypatch.setattr(agent, "_lookup_cves", fake_lookup_cves)

    output = await agent.analyze([make_chunk("requirements.txt", "requests==2.28.0\n")])

    assert output.findings == []
    assert output.metadata["dependency_cves"] == []
    assert "network unavailable" in output.metadata["warnings"][0]
