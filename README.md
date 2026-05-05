# SwarmAudit

AI-powered multi-agent code auditing for GitHub repositories. Paste a public GitHub URL and get a structured audit report with severity, file references, and suggested fixes.

## MVP

SwarmAudit currently runs with a mock-first LLM interface so the demo is not blocked by ROCm, vLLM, or AMD MI300X setup. The first graph is:

```text
GitHub URL -> Crawler -> Chunker -> Security Agent -> Synthesizer -> Report
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

## Tests

```bash
pytest
```
