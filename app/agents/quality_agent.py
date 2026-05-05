from app.schemas import AgentOutput, CodeChunk


class QualityAgent:
    name = "Quality Agent"

    async def analyze(self, chunks: list[CodeChunk]) -> AgentOutput:
        return AgentOutput(agent_name=self.name, findings=[], metadata={"chunks_scanned": len(chunks)})
