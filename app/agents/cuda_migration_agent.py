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
        suggested_fix: str,
        confidence: float,
    ) -> Finding:
        return Finding(
            title=title,
            severity=Severity.medium,
            file_path=chunk.file_path,
            line_start=line_number,
            line_end=line_number,
            description="The code references CUDA/NVIDIA-specific APIs that may need review before running on AMD ROCm infrastructure.",
            why_it_matters="AMD MI300X deployment works best when GPU code avoids hard NVIDIA assumptions or has a clear ROCm migration path.",
            suggested_fix=suggested_fix,
            agent_source=self.name,
            category="cuda_migration",
            confidence=confidence,
        )
