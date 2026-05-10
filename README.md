 ---
title: SwarmAudit
emoji: 🚀
colorFrom: blue
colorTo: cyan
sdk: gradio
sdk_version: 6.14.0
app_file: app.py
pinned: false
license: mit
short_description: Multi-agent production-readiness scanner for AI-generated code
---

# SwarmAudit

SwarmAudit is a multi-agent production-readiness scanner for AI-generated code.

Paste a public GitHub repository URL and SwarmAudit clones the repo, maps source files, runs specialized static and optional LLM-enriched agents, then returns a prioritized audit report with severity filters, file references, remediation guidance, scores, and Markdown/JSON exports.

The project was built for the AMD Developer Hackathon Track 1: AI Agents & Agentic Workflows. It is designed to run reliably in mock/static mode for public demos and switch to AMD Developer Cloud + ROCm + vLLM + Qwen2.5-Coder when GPU credits are available.

## Why It Exists

AI coding tools are fast, but they often miss production concerns: broken security assumptions, unsafe configuration, missing timeouts, swallowed exceptions, weak observability, dependency risk, and GPU portability issues. SwarmAudit turns those review concerns into a coordinated agent workflow.

The goal is not to replace linters. The goal is to give teams a fast second-pass review for code that might be functionally correct but not production-ready.

## Current Status

Working now:

- Gradio dashboard with agent progress, activity log, summary cards, clickable severity filters, finding inspector, and report downloads.
- FastAPI backend with `/health`, `/llm/health`, and `/audit`.
- GitHub repo cloning with file limits and Windows-safe temp paths.
- Static multi-agent audit path that works without GPU access.
- Optional vLLM/Qwen enrichment behind config.
- LLM Diagnostics tab for `/v1/models` and chat-completion checks.
- Benchmark tab for latency checks against mock or vLLM backends.
- Markdown and JSON report export.
- Hugging Face Spaces entrypoint through root `app.py`.
- AMD/vLLM runbook for credit-safe MI300X testing.

Validated during development:

- Hugging Face Space running in mock/static mode.
- AMD Developer Cloud GPU instance with ROCm visible through `rocm-smi`.
- vLLM serving `Qwen/Qwen2.5-Coder-32B-Instruct` through an OpenAI-compatible `/v1` API.
- SwarmAudit Diagnostics and Benchmark tabs connected successfully to the AMD-hosted vLLM endpoint.

## Agent Workflow

```text
GitHub URL
  -> Crawler Agent
  -> Chunker
  -> Parallel Analysis Agents
       Security
       Performance
       Quality
       Docs
       Config
       Dependency
       Error Handling
       Observability
       CUDA-to-ROCm
  -> Synthesizer
  -> Scores + Roadmap + Report
```

## Agents

- **Security Agent**: hardcoded secrets, disabled TLS verification, dynamic execution, insecure dependency version ranges.
- **Performance Agent**: missing HTTP timeouts, blocking work in async paths, nested loops, repeated file reads, synchronous hot-path operations.
- **Quality Agent**: long functions, high branch density, very short identifiers, TODO/FIXME/HACK comments, maintainability signals.
- **Docs Agent**: README gaps, missing install/run/test guidance, public Python symbols without docstrings.
- **Config Agent**: production-dangerous defaults such as debug mode, open CORS, disabled TLS checks, weak secrets, unsafe config patterns.
- **Dependency Agent**: parses manifests and optionally queries OSV.dev for CVE data when enabled.
- **Error Handling Agent**: swallowed exceptions, missing timeouts, missing retry/fallback behavior, resilience gaps.
- **Observability Agent**: `print` logging, sensitive data in logs, missing health checks, missing metrics/tracing signals.
- **CUDA-to-ROCm Agent**: flags CUDA/NVIDIA-specific assumptions such as `torch.cuda`, `.cuda()`, `pynvml`, `nvidia-smi`, `cudaMalloc`, and `cudaMemcpy`, then suggests ROCm/generic alternatives.
- **Synthesizer Agent**: deduplicates findings, ranks by severity, computes scores, groups categories, and builds the remediation roadmap.

## Report Output

Each audit report includes:

- Repository URL
- scanned/skipped file counts
- severity summary
- total/displayed/hidden finding counts
- agent finding counts
- category summary
- security score
- production readiness score
- remediation roadmap:
  - This Week
  - Next Sprint
  - Backlog
- structured findings with:
  - title
  - severity
  - file path and line range
  - explanation
  - why it matters
  - suggested fix
  - agent source
  - category
  - confidence when available
- Markdown export
- JSON export

The UI displays a prioritized subset for readability while preserving full totals in the structured report.

## AMD + Qwen Integration

SwarmAudit uses Qwen through an OpenAI-compatible vLLM endpoint. The app does not install or run vLLM directly; it calls vLLM over HTTP.

The AMD path improves the project by allowing the same agent workflow to use a stronger code model on AMD GPU infrastructure:

- AMD Developer Cloud provides the GPU runtime.
- ROCm exposes AMD GPU acceleration.
- vLLM serves Qwen2.5-Coder as an OpenAI-compatible API.
- SwarmAudit uses that endpoint for Diagnostics, Benchmark, and optional LLM enrichment.
- Static agents remain the reliable fallback if the endpoint is unavailable.

Default public/demo mode stays cheap and reliable:

```text
LLM_PROVIDER=mock
ENABLE_LLM_ENRICHMENT=false
```

Credit-safe AMD test mode:

```text
LLM_PROVIDER=vllm
LLM_BASE_URL=http://YOUR_VLLM_ENDPOINT/v1
LLM_API_KEY=swarm-audit-demo-key
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
ENABLE_LLM_ENRICHMENT=true
MAX_FILES=100
MAX_FILE_SIZE_KB=150
MAX_CHARS_PER_CHUNK=8000
MAX_LLM_CHUNKS=2
```

See [`AMD_VLLM_RUNBOOK.md`](AMD_VLLM_RUNBOOK.md) for the exact AMD setup and shutdown checklist.

## Hugging Face Spaces

SwarmAudit is deployable as a Gradio Space using the root `app.py`.

Recommended public Space settings:

- SDK: Gradio
- Hardware: CPU basic
- App file: `app.py`
- Environment:

```text
LLM_PROVIDER=mock
ENABLE_LLM_ENRICHMENT=false
ENABLE_DEPENDENCY_CVE_LOOKUP=false
```

Keep the public Space in mock/static mode unless a stable vLLM endpoint is available for the full judging window. Do not expose private endpoint keys in the README or UI.

See [`HF_SPACES_DEPLOY.md`](HF_SPACES_DEPLOY.md) for the deployment checklist.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the Gradio app:

```bash
python app.py
```

Open the URL printed by Gradio. The app tries port `7860` first and falls back to another local Gradio port if `7860` is busy.

Run the FastAPI backend:

```bash
uvicorn app.main:app --reload
```

If port `8000` is busy:

```bash
uvicorn app.main:app --reload --port 8001
```

Health checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/llm/health
```

Audit API:

```bash
curl -X POST http://127.0.0.1:8000/audit \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/pallets/itsdangerous"}'
```

Recommended first test repos:

```text
https://github.com/pallets/itsdangerous
https://github.com/psf/requests
```

## Configuration

Copy `.env.example` to `.env` for local overrides.

Important settings:

```text
LLM_PROVIDER=mock
LLM_BASE_URL=http://localhost:9000/v1
LLM_API_KEY=not-needed-for-mock
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
ENABLE_LLM_ENRICHMENT=false
ENABLE_DEPENDENCY_CVE_LOOKUP=false
MAX_LLM_CHUNKS=5
LLM_TIMEOUT_SECONDS=120
MAX_FILES=200
MAX_FILE_SIZE_KB=250
MAX_CHARS_PER_CHUNK=12000
CLONE_TIMEOUT_SECONDS=60
CLONE_BASE_DIR=.swarm_audit_tmp
```

Dependency CVE lookup is off by default so demos do not depend on network calls beyond cloning the target repo:

```text
ENABLE_DEPENDENCY_CVE_LOOKUP=false
```

Enable it only when you want OSV.dev CVE checks:

```text
ENABLE_DEPENDENCY_CVE_LOOKUP=true
```

## Tests

```bash
python -m compileall -q app tests app.py
python -m pytest --basetemp=.tmp_pytest -p no:cacheprovider
```

Current local suite:

```text
104 tests
```

## Project Structure

```text
app.py                         # Hugging Face/Gradio entrypoint
app/
  main.py                      # FastAPI API
  config.py                    # environment settings
  schemas.py                   # Pydantic models
  agents/
    graph.py                   # orchestration
    security_agent.py
    performance_agent.py
    quality_agent.py
    docs_agent.py
    config_agent.py
    dependency_agent.py
    error_handling_agent.py
    observability_agent.py
    cuda_migration_agent.py
    synthesizer_agent.py
    llm_enrichment.py
  services/
    llm_client.py
    benchmark.py
    report_formatter.py
  ui/
    gradio_app.py
tests/
examples/
```

## Submission Notes

For the hackathon submission, highlight:

- agentic workflow with multiple specialized agents
- Qwen2.5-Coder integration through vLLM
- AMD Developer Cloud + ROCm validation
- Hugging Face Space deployment
- practical business value: production readiness for AI-generated code
- originality: combining security, operations, dependency, and CUDA-to-ROCm portability checks in one audit workflow
