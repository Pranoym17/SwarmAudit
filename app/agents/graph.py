from collections.abc import AsyncIterator
from operator import add
from typing import Annotated, TypedDict

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
        self.security_agent = SecurityAgent(self.llm_client)
        self.performance_agent = PerformanceAgent()
        self.quality_agent = QualityAgent()
        self.docs_agent = DocsAgent()
        self.synthesizer = SynthesizerAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AuditState)
        graph.add_node("crawl", self._crawl)
        graph.add_node("chunk", self._chunk)
        graph.add_node("security", self._security)
        graph.add_node("performance", self._performance)
        graph.add_node("quality", self._quality)
        graph.add_node("docs", self._docs)
        graph.add_node("synthesize", self._synthesize)
        graph.set_entry_point("crawl")
        graph.add_edge("crawl", "chunk")
        graph.add_edge("chunk", "security")
        graph.add_edge("chunk", "performance")
        graph.add_edge("chunk", "quality")
        graph.add_edge("chunk", "docs")
        graph.add_edge(["security", "performance", "quality", "docs"], "synthesize")
        graph.add_edge("synthesize", END)
        return graph.compile()

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

            yield "Security Agent: scanning for risky patterns..."
            security_output = await self.security_agent.analyze(chunks)
            yield f"Security Agent: found {len(security_output.findings)} findings."

            yield "Performance Agent: scanning for slow-path patterns..."
            performance_output = await self.performance_agent.analyze(chunks)
            yield f"Performance Agent: found {len(performance_output.findings)} findings."

            yield "Quality Agent: scanning maintainability signals..."
            quality_output = await self.quality_agent.analyze(chunks)
            yield f"Quality Agent: found {len(quality_output.findings)} findings."

            yield "Docs Agent: scanning README and public documentation..."
            docs_output = await self.docs_agent.analyze(chunks)
            yield f"Docs Agent: found {len(docs_output.findings)} findings."

            yield "Synthesizer Agent: ranking findings and formatting report..."
            report = await self.synthesizer.synthesize(
                repo,
                [security_output, performance_output, quality_output, docs_output],
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

    async def _security(self, state: AuditState) -> AuditState:
        output = await self.security_agent.analyze(state["chunks"])
        return {"security_output": output, "progress": [f"Security Agent: found {len(output.findings)} findings."]}

    async def _performance(self, state: AuditState) -> AuditState:
        output = await self.performance_agent.analyze(state["chunks"])
        return {"performance_output": output, "progress": [f"Performance Agent: found {len(output.findings)} findings."]}

    async def _quality(self, state: AuditState) -> AuditState:
        output = await self.quality_agent.analyze(state["chunks"])
        return {"quality_output": output, "progress": [f"Quality Agent: found {len(output.findings)} findings."]}

    async def _docs(self, state: AuditState) -> AuditState:
        output = await self.docs_agent.analyze(state["chunks"])
        return {"docs_output": output, "progress": [f"Docs Agent: found {len(output.findings)} findings."]}

    async def _synthesize(self, state: AuditState) -> AuditState:
        report = await self.synthesizer.synthesize(
            state["repo"],
            [state["security_output"], state["performance_output"], state["quality_output"], state["docs_output"]],
        )
        self.crawler.cleanup(state["repo"])
        return {"report": report, "progress": ["Synthesizer Agent: final report generated."]}
