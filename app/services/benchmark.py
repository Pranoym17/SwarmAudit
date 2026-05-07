import time

from app.config import Settings
from app.schemas import BenchmarkResult
from app.services.llm_client import LLMClient


BENCHMARK_PROMPT = (
    "Review this Python snippet for one security issue and answer in one concise sentence:\n"
    "user_code = input('code: ')\n"
    "eval(user_code)\n"
)


class BenchmarkService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_client = LLMClient(settings)

    async def run_llm_benchmark(self) -> BenchmarkResult:
        start = time.perf_counter()
        try:
            completion = await self.llm_client.test_completion()
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            completion_chars = len(completion)
            chars_per_second = self._chars_per_second(completion_chars, latency_ms)
            return BenchmarkResult(
                provider=self.settings.llm_provider,
                model=self.settings.llm_model,
                backend=self._backend_name(),
                hardware=self._hardware_label(),
                ok=True,
                latency_ms=latency_ms,
                prompt_chars=len(BENCHMARK_PROMPT),
                completion_chars=completion_chars,
                chars_per_second=chars_per_second,
                completion_preview=completion,
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return BenchmarkResult(
                provider=self.settings.llm_provider,
                model=self.settings.llm_model,
                backend=self._backend_name(),
                hardware=self._hardware_label(),
                ok=False,
                latency_ms=latency_ms,
                prompt_chars=len(BENCHMARK_PROMPT),
                error=str(exc),
            )

    def _backend_name(self) -> str:
        if self.settings.llm_provider == "mock":
            return "Mock local backend"
        if self.settings.llm_provider == "vllm":
            return "vLLM OpenAI-compatible endpoint"
        return self.settings.llm_provider

    def _hardware_label(self) -> str:
        if self.settings.llm_provider == "vllm":
            return "AMD MI300X target"
        return "Local/mock"

    def _chars_per_second(self, completion_chars: int, latency_ms: float) -> float | None:
        if latency_ms <= 0:
            return None
        return round(completion_chars / (latency_ms / 1000), 2)
