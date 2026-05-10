import re

from app.schemas import AgentOutput, CodeChunk, Finding, Severity


CUDA_PATTERNS = [
    (
        re.compile(r"\btorch\.cuda\b|\.cuda\s*\("),
        "PyTorch CUDA-specific API usage",
        "Use device-agnostic PyTorch code such as torch.device('cuda' if torch.cuda.is_available() else 'cpu') only when portability is intended, and validate the same path under ROCm where PyTorch maps CUDA APIs to HIP.",
        0.82,
    ),
    (
        re.compile(r"\bpynvml\b|\bnvidia-smi\b"),
        "NVIDIA-specific GPU monitoring",
        "Replace NVIDIA-specific monitoring with ROCm tools such as rocm-smi or a metrics adapter that supports AMD GPUs.",
        0.9,
    ),
    (
        re.compile(r"\bcuda(Malloc|Free|Memcpy|Memset|DeviceSynchronize|GetDevice|SetDevice)\b"),
        "CUDA runtime API call",
        "Map CUDA runtime calls to HIP/ROCm equivalents and validate memory transfer semantics on AMD hardware.",
        0.88,
    ),
    (
        re.compile(r"\b(cublas|cudnn|cufft|curand)\w*\b", re.IGNORECASE),
        "CUDA library dependency",
        "Review ROCm equivalents such as rocBLAS, MIOpen, rocFFT, or rocRAND before running on AMD GPUs.",
        0.86,
    ),
    (
        re.compile(r"\bnccl\w*\b", re.IGNORECASE),
        "NCCL-specific distributed GPU dependency",
        "Use RCCL or a framework abstraction that supports AMD GPU collectives.",
        0.84,
    ),
]


class CudaMigrationAgent:
    name = "CUDA-to-ROCm Agent"

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
        seen_titles: set[str] = set()

        for offset, line in enumerate(chunk.content.splitlines()):
            actual_line = chunk.line_start + offset
            for pattern, title, fix, confidence in CUDA_PATTERNS:
                if title in seen_titles:
                    continue
                if pattern.search(line):
                    seen_titles.add(title)
                    findings.append(
                        self._finding(
                            title=title,
                            chunk=chunk,
                            line_number=actual_line,
                            matched_line=line,
                            suggested_fix=fix,
                            confidence=confidence,
                        )
                    )

        return findings

    def _finding(
        self,
        title: str,
        chunk: CodeChunk,
        line_number: int,
        matched_line: str,
        suggested_fix: str,
        confidence: float,
    ) -> Finding:
        snippet = self._snippet(matched_line)
        return Finding(
            title=title,
            severity=Severity.medium,
            file_path=chunk.file_path,
            line_start=line_number,
            line_end=line_number,
            description=f"`{snippet}` references a CUDA/NVIDIA-specific API that needs review before AMD ROCm deployment.",
            why_it_matters="This exact GPU assumption can fail or reduce portability when the app moves from NVIDIA CUDA environments to AMD MI300X/ROCm.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
            category="cuda_migration",
            confidence=confidence,
        )

    def _snippet(self, line: str, max_length: int = 96) -> str:
        normalized = " ".join(line.strip().split())
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[: max_length - 3]}..."
