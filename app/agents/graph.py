from collections.abc import AsyncIterator
from dataclasses import dataclass
from operator import add
from typing import Annotated, Protocol, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.docs_agent import DocsAgent
from app.agents.performance_agent import PerformanceAgent
from app.agents.quality_agent import QualityAgent
from app.agents.security_agent import SecurityAgent
from app.agents.synthesizer_agent import SynthesizerAgent
from app.config import Settings, get_settings
from app.schemas import AgentOutput, AuditReport, CodeChunk, RepoScanResult
from app.services.chunker import Chunker
from app.services.llm_client import LLMClient
from app.services.repo_crawler import RepoCrawler


class AnalysisAgent(Protocol):
    name: str

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        ...


@dataclass(frozen=True)
class AnalysisAgentSpec:
    node_name: str
    state_key: str
    progress_label: str
    start_message: str
    agent: AnalysisAgent


class AuditState(TypedDict, total=False):
    repo_url: str
    repo: RepoScanResult
    chunks: list[CodeChunk]
    security_output: AgentOutput
    performance_output: AgentOutput
    quality_output: AgentOutput
    docs_output: AgentOutput
    report: AuditReport
    progress: Annotated[list[str], add]


class AuditGraph:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.crawler = RepoCrawler(self.settings)
        self.chunker = Chunker(self.settings)
        self.llm_client = LLMClient(self.settings)
        self.analysis_agents = self._build_agent_registry()
        self.synthesizer = SynthesizerAgent()
        self.graph = self._build_graph()

    def _build_agent_registry(self) -> list[AnalysisAgentSpec]:
        return [
            AnalysisAgentSpec(
                node_name="security",
                state_key="security_output",
                progress_label="Security Agent",
                start_message="Security Agent: scanning for risky patterns...",
                agent=SecurityAgent(self.llm_client),
            ),
            AnalysisAgentSpec(
                node_name="performance",
                state_key="performance_output",
                progress_label="Performance Agent",
                start_message="Performance Agent: scanning for slow-path patterns...",
                agent=PerformanceAgent(self.llm_client),
            ),
            AnalysisAgentSpec(
                node_name="quality",
                state_key="quality_output",
                progress_label="Quality Agent",
                start_message="Quality Agent: scanning maintainability signals...",
                agent=QualityAgent(self.llm_client),
            ),
            AnalysisAgentSpec(
                node_name="docs",
                state_key="docs_output",
                progress_label="Docs Agent",
                start_message="Docs Agent: scanning README and public documentation...",
                agent=DocsAgent(self.llm_client),
            ),
        ]

    def _build_graph(self):
        graph = StateGraph(AuditState)
        graph.add_node("crawl", self._crawl)
        graph.add_node("chunk", self._chunk)
        for spec in self.analysis_agents:
            graph.add_node(spec.node_name, self._make_agent_node(spec))
        graph.add_node("synthesize", self._synthesize)
        graph.set_entry_point("crawl")
        graph.add_edge("crawl", "chunk")
        agent_node_names = [spec.node_name for spec in self.analysis_agents]
        for node_name in agent_node_names:
            graph.add_edge("chunk", node_name)
        graph.add_edge(agent_node_names, "synthesize")
        graph.add_edge("synthesize", END)
        return graph.compile()

    def _make_agent_node(self, spec: AnalysisAgentSpec):
        async def run_agent(state: AuditState) -> AuditState:
            output = await spec.agent.analyze(state["chunks"])
            return {
                spec.state_key: output,
                "progress": [f"{spec.progress_label}: found {len(output.findings)} findings."],
            }

        return run_agent

    async def run(self, repo_url: str) -> AuditReport:
        result = await self.graph.ainvoke({"repo_url": repo_url, "progress": []})
        return result["report"]

    async def run_with_progress(self, repo_url: str) -> AsyncIterator[str | AuditReport]:
        repo: RepoScanResult | None = None
        yield "Crawler Agent: cloning and mapping repository..."
        repo = self.crawler.clone_and_scan(repo_url)
        yield f"Crawler Agent: mapped {len(repo.files)} files and skipped {repo.skipped_files}."

        try:
            yield "Chunker: filtering source files and creating chunks..."
            chunks = self.chunker.chunk_files(repo.files)
            yield f"Chunker: created {len(chunks)} code chunks."

            outputs: list[AgentOutput] = []
            for spec in self.analysis_agents:
                yield spec.start_message
                output = await spec.agent.analyze(chunks)
                outputs.append(output)
                yield f"{spec.progress_label}: found {len(output.findings)} findings."

            yield "Synthesizer Agent: ranking findings and formatting report..."
            report = await self.synthesizer.synthesize(
                repo,
                outputs,
            )
            yield "Synthesizer Agent: final report generated."
            yield report
        finally:
            self.crawler.cleanup(repo)

    async def _crawl(self, state: AuditState) -> AuditState:
        repo = self.crawler.clone_and_scan(state["repo_url"])
        return {"repo": repo, "progress": [f"Crawler Agent: mapped {len(repo.files)} files."]}

    async def _chunk(self, state: AuditState) -> AuditState:
        chunks = self.chunker.chunk_files(state["repo"].files)
        return {"chunks": chunks, "progress": [f"Chunker: created {len(chunks)} code chunks."]}

    async def _synthesize(self, state: AuditState) -> AuditState:
        outputs = [state[spec.state_key] for spec in self.analysis_agents]
        report = await self.synthesizer.synthesize(
            state["repo"],
            outputs,
        )
        self.crawler.cleanup(state["repo"])
        return {"report": report, "progress": ["Synthesizer Agent: final report generated."]}
