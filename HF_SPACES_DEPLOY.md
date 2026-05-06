# Hugging Face Spaces Deployment Checklist

## Local Preflight

Run these from the repo root:

```bash
pip install -r requirements.txt
pytest
python app.py
```

Open:

```text
http://127.0.0.1:7860
```

Test a small repo first:

```text
https://github.com/pallets/itsdangerous
```

## Create The Space

1. Go to Hugging Face Spaces.
2. Create a new Space.
3. Choose SDK: `Gradio`.
4. Choose hardware: CPU basic for the mock MVP.
5. Use the AMD hackathon organization if the event requires it.

## Required Files

These must be at the repo root:

```text
app.py
requirements.txt
README.md
```

The README includes the Space metadata:

```yaml
sdk: gradio
sdk_version: 6.14.0
app_file: app.py
```

## Environment Variables

For the public mock demo:

```text
LLM_PROVIDER=mock
```

For a later AMD/vLLM deployment:

```text
LLM_PROVIDER=vllm
LLM_BASE_URL=http://YOUR_VLLM_ENDPOINT/v1
LLM_API_KEY=not-needed-if-your-endpoint-does-not-require-one
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
```

## First Hosted Smoke Test

In the deployed Space, test:

```text
https://github.com/pallets/itsdangerous
```

Then test:

```text
https://github.com/psf/requests
```

Expected behavior:

- Crawler maps files.
- Chunker creates chunks.
- Security, Performance, Quality, and Docs agents run.
- Synthesizer returns a report.
- Report shows a prioritized subset while preserving total finding counts.

## If The Space Fails

Check the Space logs first. Common issues:

- Dependency install failure: verify `requirements.txt`.
- App import failure: verify root `app.py`.
- GitHub clone failure: verify Space has outbound internet access.
- Large repo timeout: test `pallets/itsdangerous` before larger repos.
