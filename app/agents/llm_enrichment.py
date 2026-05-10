from app.schemas import AgentOutput, CodeChunk
from app.services.json_parser import parse_agent_output
from app.services.llm_client import LLMClient


FINDING_SCHEMA_INSTRUCTIONS = (
    "Return JSON matching this schema exactly:\n"
    "{\n"
    '  "findings": [\n'
    "    {\n"
    '      "title": "short title",\n'
    '      "severity": "CRITICAL|HIGH|MEDIUM|LOW",\n'
    '      "file_path": "path from input",\n'
    '      "line_start": 1,\n'
    '      "line_end": 1,\n'
    '      "description": "what is wrong",\n'
    '      "why_it_matters": "impact",\n'
    '      "suggested_fix": "specific fix",\n'
    '      "agent_source": "agent name"\n'
    "    }\n"
    "  ]\n"
    "}\n"
)

CONTEXTUAL_REVIEW_INSTRUCTIONS = (
    "Make each finding specific to the exact code shown. "
    "Reference the concrete function, call, config value, exception handler, or line pattern when visible. "
    "Do not reuse generic boilerplate language across findings. "
    "Do not report duplicates of the same issue in the same file unless the risk or fix is meaningfully different. "
    "Descriptions should explain what this exact code does wrong; suggested_fix should name the specific API, guard, timeout, logger, or config change to use."
)


class LLMEnrichmentMixin:
    name: str
    llm_client: LLMClient

    async def _run_llm_enrichment(self, chunks: list[CodeChunk], review_instruction: str) -> AgentOutput:
        if not self.llm_client.settings.enable_llm_enrichment:
            return AgentOutput(agent_name=self.name)

        selected_chunks = chunks[: self.llm_client.settings.max_llm_chunks]
        if not selected_chunks:
            return AgentOutput(agent_name=self.name)

        try:
            raw_output = await self.llm_client.complete_json(
                f"You are a senior {self.name.lower()}. Return only JSON.",
                self._build_llm_prompt(selected_chunks, review_instruction),
            )
            return parse_agent_output(raw_output, self.name)
        except Exception as exc:
            return AgentOutput(
                agent_name=self.name,
                metadata={"llm_error": str(exc)},
            )

    def _llm_metadata(self, chunks: list[CodeChunk], llm_output: AgentOutput) -> dict[str, object]:
        return {
            "chunks_scanned": len(chunks),
            "mode": "static-rules-plus-optional-llm",
            "llm_enrichment_enabled": self.llm_client.settings.enable_llm_enrichment,
            "llm_findings": len(llm_output.findings),
            **llm_output.metadata,
        }

    def _build_llm_prompt(self, chunks: list[CodeChunk], review_instruction: str) -> str:
        chunk_text = "\n\n".join(
            [
                f"File: {chunk.file_path}\n"
                f"Lines: {chunk.line_start}-{chunk.line_end}\n"
                "```code\n"
                f"{chunk.content[:4000]}\n"
                "```"
                for chunk in chunks
            ]
        )
        return (
            f"{review_instruction}\n"
            f"{CONTEXTUAL_REVIEW_INSTRUCTIONS}\n"
            f"{FINDING_SCHEMA_INSTRUCTIONS}\n"
            f'Every finding must set "agent_source" to "{self.name}". '
            "Only include findings that are specific, actionable, and tied to the provided files.\n\n"
            f"{chunk_text}"
        )
