import pytest

from app.config import Settings
from app.services.benchmark import BenchmarkService


@pytest.mark.anyio
async def test_mock_benchmark_returns_ok_result():
    result = await BenchmarkService(Settings(llm_provider="mock")).run_llm_benchmark()

    assert result.ok is True
    assert result.provider == "mock"
    assert result.backend == "Mock local backend"
    assert result.hardware == "Local/mock"
    assert result.completion_chars > 0


@pytest.mark.anyio
async def test_benchmark_reports_llm_errors():
    service = BenchmarkService(Settings(llm_provider="mock"))

    async def fail_completion():
        raise RuntimeError("benchmark failed")

    service.llm_client.test_completion = fail_completion
    result = await service.run_llm_benchmark()

    assert result.ok is False
    assert "benchmark failed" in result.error
