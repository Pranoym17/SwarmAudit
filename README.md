# SwarmAudit

AI-powered multi-agent code auditing for GitHub repositories. Paste a public GitHub URL and get a structured audit report with severity, file references, and suggested fixes.

## MVP

SwarmAudit currently runs with a mock-first LLM interface so the demo is not blocked by ROCm, vLLM, or AMD MI300X setup. The current graph is:

```text
GitHub URL -> Crawler -> Chunker -> [Security Agent + Performance Agent + Quality Agent + Docs Agent] -> Synthesizer -> Report
```

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

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Run the Gradio demo:

```bash
python -m app.ui.gradio_app
```

## Configuration

Copy `.env.example` to `.env` for local overrides. Default inference mode is:

```text
LLM_PROVIDER=mock
```

Later, set `LLM_PROVIDER=vllm` and point `LLM_BASE_URL` at an OpenAI-compatible vLLM endpoint running Qwen2.5-Coder.

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

## Tests

```bash
pytest
```
