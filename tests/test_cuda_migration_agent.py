import pytest

from app.agents.cuda_migration_agent import CudaMigrationAgent
from app.schemas import CodeChunk, Severity


def make_chunk(content: str, file_path: str = "model.py") -> CodeChunk:
    return CodeChunk(
        file_path=file_path,
        language="Python",
        line_start=1,
        line_end=max(1, len(content.splitlines())),
        content=content,
    )


@pytest.mark.anyio
async def test_cuda_migration_agent_detects_torch_cuda():
    output = await CudaMigrationAgent().analyze([make_chunk("device = torch.cuda.current_device()")])

    assert output.findings[0].title == "PyTorch CUDA-specific API usage"
    assert output.findings[0].severity == Severity.medium
    assert output.findings[0].category == "cuda_migration"


@pytest.mark.anyio
async def test_cuda_migration_agent_detects_nvidia_monitoring():
    output = await CudaMigrationAgent().analyze([make_chunk("import pynvml\nsubprocess.run(['nvidia-smi'])")])

    assert output.findings[0].title == "NVIDIA-specific GPU monitoring"
    assert "rocm-smi" in output.findings[0].suggested_fix


@pytest.mark.anyio
async def test_cuda_migration_agent_detects_cuda_runtime_calls():
    output = await CudaMigrationAgent().analyze([make_chunk("cudaMemcpy(dst, src, size, cudaMemcpyDeviceToHost);", "kernel.cu")])

    assert output.findings[0].title == "CUDA runtime API call"
    assert output.findings[0].confidence is not None


@pytest.mark.anyio
async def test_cuda_migration_agent_detects_cuda_libraries():
    output = await CudaMigrationAgent().analyze([make_chunk("handle = cublasCreate()", "linear_algebra.cpp")])

    assert output.findings[0].title == "CUDA library dependency"
    assert "rocBLAS" in output.findings[0].suggested_fix


@pytest.mark.anyio
async def test_cuda_migration_agent_returns_empty_for_cpu_code():
    output = await CudaMigrationAgent().analyze([make_chunk("device = torch.device('cpu')")])

    assert output.findings == []
