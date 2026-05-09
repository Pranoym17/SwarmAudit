# Hugging Face Spaces Deployment

Use this checklist when updating the SwarmAudit Space.

## Recommended Public Demo Mode

Keep the public Space reliable unless a stable AMD/vLLM endpoint will remain online for judging.

```text
LLM_PROVIDER=mock
ENABLE_LLM_ENRICHMENT=false
ENABLE_DEPENDENCY_CVE_LOOKUP=false
```

This still runs the static multi-agent audit and produces exportable reports.

## Required Files

These files must be at the Space repo root:

```text
app.py
requirements.txt
README.md
app/
```

The README front matter tells Spaces how to start the app:

```yaml
sdk: gradio
sdk_version: 6.14.0
app_file: app.py
```

## Local Preflight

From the repo root:

```bash
pip install -r requirements.txt
python -m compileall -q app tests app.py
python -m pytest --basetemp=.tmp_pytest -p no:cacheprovider
python app.py
```

Open the local URL printed by Gradio.

Test:

```text
https://github.com/pallets/itsdangerous
```

Then:

```text
https://github.com/psf/requests
```

Confirm:

- agent progress appears
- findings render
- severity filters work
- finding detail panel updates when clicking rows
- Markdown download works
- JSON download works
- Diagnostics tab shows `Provider: mock` and `Status: OK`
- Benchmark tab works in mock mode

## Space Settings

- SDK: Gradio
- Hardware: CPU basic for public mock mode
- App file: `app.py`
- License: MIT
- Suggested short description:

```text
Multi-agent production-readiness scanner for AI-generated code
```

## Deploy / Update

Push the same project code to the hackathon organization Space repo.

After the build starts:

1. Open the Space logs.
2. Wait for the Gradio startup message.
3. Open the app.
4. Run the small repo smoke test.
5. Keep a screenshot of the working report for submission material.

## Optional AMD/vLLM Mode

Only use this if the endpoint is stable:

```text
LLM_PROVIDER=vllm
LLM_BASE_URL=http://YOUR_VLLM_ENDPOINT/v1
LLM_API_KEY=stored-as-space-secret
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
ENABLE_LLM_ENRICHMENT=false
MAX_LLM_CHUNKS=2
```

Run the Diagnostics tab before enabling enrichment.

After diagnostics passes:

```text
ENABLE_LLM_ENRICHMENT=true
```

If the endpoint is temporary, switch back to mock mode after recording demo proof.

## Common Issues

- **Build error**: check `requirements.txt` and root `app.py`.
- **No logs**: verify the code is pushed to the actual Space remote, not only GitHub.
- **Clone error**: test a smaller public repo first.
- **Port issue locally**: `python app.py` tries `7860` first and falls back locally when no explicit port env var is set.
- **Secrets**: never put real API keys in README, screenshots, or `.env.example`.

