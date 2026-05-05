from collections.abc import AsyncIterator
from typing import TypedDict

from langgraph.graph import END, StateGraph

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
    report: AuditReport
    progress: list[str]


class AuditGraph:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.crawler = RepoCrawler(self.settings)
        self.chunker = Chunker(self.settings)
        self.llm_client = LLMClient(self.settings)
        self.security_agent = SecurityAgent(self.llm_client)
        self.synthesizer = SynthesizerAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AuditState)
        graph.add_node("crawl", self._crawl)
        graph.add_node("chunk", self._chunk)
        graph.add_node("security", self._security)
        graph.add_node("synthesize", self._synthesize)
        graph.set_entry_point("crawl")
        graph.add_edge("crawl", "chunk")
        graph.add_edge("chunk", "security")
        graph.add_edge("security", "synthesize")
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

            yield "Synthesizer Agent: ranking findings and formatting report..."
            report = await self.synthesizer.synthesize(repo, [security_output])
            yield "Synthesizer Agent: final report generated."
            yield report
        finally:
            self.crawler.cleanup(repo)

    async def _crawl(self, state: AuditState) -> AuditState:
        repo = self.crawler.clone_and_scan(state["repo_url"])
        progress = state.get("progress", []) + [f"Crawler Agent: mapped {len(repo.files)} files."]
        return {"repo": repo, "progress": progress}

    async def _chunk(self, state: AuditState) -> AuditState:
        chunks = self.chunker.chunk_files(state["repo"].files)
        progress = state.get("progress", []) + [f"Chunker: created {len(chunks)} code chunks."]
        return {"chunks": chunks, "progress": progress}

    async def _security(self, state: AuditState) -> AuditState:
        output = await self.security_agent.analyze(state["chunks"])
        progress = state.get("progress", []) + [f"Security Agent: found {len(output.findings)} findings."]
        return {"security_output": output, "progress": progress}

    async def _synthesize(self, state: AuditState) -> AuditState:
        report = await self.synthesizer.synthesize(state["repo"], [state["security_output"]])
        progress = state.get("progress", []) + ["Synthesizer Agent: final report generated."]
        self.crawler.cleanup(state["repo"])
        return {"report": report, "progress": progress}
