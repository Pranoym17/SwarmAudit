---
title: SwarmAudit
sdk: gradio
sdk_version: 6.14.0
app_file: app.py
pinned: false
license: mit
---

# SwarmAudit

Paste any public GitHub URL. Get a structured multi-agent code audit in minutes.

SwarmAudit is an AI-agent code review system for the AMD Developer Hackathon. It clones a public repository, filters and chunks source files, runs specialized review agents, and returns a severity-ranked report with file references and suggested fixes.

The local MVP runs in mock-first mode, so the demo works without waiting for ROCm, vLLM, or MI300X infrastructure. The inference layer is designed to switch to a vLLM-compatible Qwen2.5-Coder endpoint later.

## MVP

SwarmAudit currently runs with a mock-first LLM interface so the demo is not blocked by ROCm, vLLM, or AMD MI300X setup. The current graph is:

```text
GitHub URL -> Crawler -> Chunker -> [Security Agent + Performance Agent + Quality Agent + Docs Agent] -> Synthesizer -> Report
```

## Demo Status

Working locally:

- Gradio UI with live agent progress
- FastAPI `/health` and `/audit` endpoints
- GitHub clone and repo scan on public repos
- Four analysis agents plus synthesizer
- Prioritized report display with full raw finding totals preserved
- Hugging Face Spaces-style `app.py` entrypoint

Smoke-tested repos:

- `https://github.com/psf/requests`
- `https://github.com/pallets/itsdangerous`

Example output is available in [`examples/requests_report_excerpt.md`](examples/requests_report_excerpt.md).

## Architecture

```mermaid
flowchart LR
    U[User enters GitHub URL] --> API[FastAPI / Gradio]
    API --> C[Crawler Agent]
    C --> F[File Filter]
    F --> K[Chunker]
    K --> S[Security Agent]
    K --> P[Performance Agent]
    K --> Q[Quality Agent]
    K --> D[Docs Agent]
    S --> Y[Synthesizer Agent]
    P --> Y
    Q --> Y
    D --> Y
    Y --> R[Structured Audit Report]
```

The graph is intentionally modular: each agent returns strict Pydantic findings, and the synthesizer merges, deduplicates, prioritizes, and formats the final report.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the FastAPI backend:

```bash
uvicorn app.main:app --reload
```

If port 8000 is busy on Windows, use:

```bash
uvicorn app.main:app --reload --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Audit endpoint:

```bash
curl -X POST http://127.0.0.1:8000/audit \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/psf/requests"}'
```

Run the Gradio demo:

```bash
python -m app.ui.gradio_app
```

For Hugging Face Spaces-style startup:

```bash
python app.py
```

The Gradio app includes example repos, a live agent progress panel, and a structured markdown report panel.
The launcher binds to `0.0.0.0` and uses `PORT` when provided, which matches hosted Gradio deployment expectations.

## Configuration

Copy `.env.example` to `.env` for local overrides. Default inference mode is:

```text
LLM_PROVIDER=mock
```

Later, set `LLM_PROVIDER=vllm` and point `LLM_BASE_URL` at an OpenAI-compatible vLLM endpoint running Qwen2.5-Coder.

Key safety limits:

```text
MAX_FILES=200
MAX_FILE_SIZE_KB=250
MAX_CHARS_PER_CHUNK=12000
CLONE_BASE_DIR=.swarm_audit_tmp
```

## Report Schema

Each finding includes:

- title
- severity: CRITICAL, HIGH, MEDIUM, LOW
- file path and line range
- description
- why it matters
- suggested fix
- agent source

Reports preserve full finding totals while displaying a prioritized subset for readability. High-severity findings are shown first, repeated low-severity findings are summarized, and warnings explain when lower-priority findings are hidden from the demo report.

## Current Agents

- Security Agent: flags hardcoded secrets, disabled TLS verification, and dynamic code execution.
- Performance Agent: flags HTTP calls without timeouts, blocking sleep inside async functions, nested loops, file reads in loops, and synchronous Node.js filesystem calls.
- Quality Agent: flags long functions, high branch density, large source sections, unresolved TODO/FIXME/HACK comments, and very short symbol names.
- Docs Agent: flags incomplete README guidance and public Python symbols missing docstrings.
- Synthesizer Agent: deduplicates findings, sorts by severity, and builds the final report.

## Hugging Face Spaces

SwarmAudit is ready to launch as a Gradio Space with the root `app.py` entrypoint. Keep `LLM_PROVIDER=mock` for a reliable public demo, then switch to `LLM_PROVIDER=vllm` when an AMD MI300X-hosted Qwen2.5-Coder endpoint is available.

See [`HF_SPACES_DEPLOY.md`](HF_SPACES_DEPLOY.md) for the deployment checklist.

Recommended Space settings:

- SDK: Gradio
- App file: `app.py`
- Python: 3.11 or newer
- Default env: `LLM_PROVIDER=mock`

## AMD MI300X Roadmap

The current code path is intentionally mock-first. The next inference phase is:

1. Start a Qwen2.5-Coder vLLM server on AMD Developer Cloud.
2. Expose an OpenAI-compatible `/v1/chat/completions` endpoint.
3. Set `LLM_PROVIDER=vllm`, `LLM_BASE_URL`, and `LLM_MODEL`.
4. Add LLM enrichment to agent findings while keeping static rules as deterministic guardrails.
5. Add a benchmark tab with MI300X latency and throughput numbers.

## Tests

```bash
python -m pytest
```


