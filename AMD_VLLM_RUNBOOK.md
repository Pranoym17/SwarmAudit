# AMD vLLM Runbook

SwarmAudit is AMD-ready through an HTTP-only vLLM integration. The app does not install vLLM. It calls an OpenAI-compatible endpoint that can be hosted on AMD Developer Cloud with ROCm.

## What Was Validated

During development, SwarmAudit was tested against:

- AMD Developer Cloud GPU instance
- ROCm visible through `rocm-smi`
- Docker-based vLLM environment
- `Qwen/Qwen2.5-Coder-32B-Instruct`
- OpenAI-compatible routes:
  - `/v1/models`
  - `/v1/chat/completions`
- SwarmAudit Diagnostics tab
- SwarmAudit Benchmark tab
- real audit run with `ENABLE_LLM_ENRICHMENT=true` and `MAX_LLM_CHUNKS=2`

The AMD instance was destroyed afterward to avoid credit burn.

## Safe Default

Use this locally and on Hugging Face Spaces when AMD is not running:

```text
LLM_PROVIDER=mock
ENABLE_LLM_ENRICHMENT=false
ENABLE_DEPENDENCY_CVE_LOOKUP=false
```

## Credit-Safe AMD Settings

Use these for the first AMD session:

```text
LLM_PROVIDER=vllm
LLM_BASE_URL=http://YOUR_VLLM_ENDPOINT/v1
LLM_API_KEY=not-needed-if-open
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
ENABLE_LLM_ENRICHMENT=false
ENABLE_DEPENDENCY_CVE_LOOKUP=false
MAX_FILES=100
MAX_FILE_SIZE_KB=150
MAX_CHARS_PER_CHUNK=8000
MAX_LLM_CHUNKS=2
```

Only switch this after Diagnostics passes:

```text
ENABLE_LLM_ENRICHMENT=true
```

## AMD Session Flow

1. Create/start the AMD GPU instance.
2. SSH into the instance.
3. Confirm GPU visibility:

```bash
rocm-smi
```

4. If the image provides a vLLM container, enter it:

```bash
docker exec -it rocm /bin/bash
```

5. Start vLLM:

```bash
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype float16 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90
```

If the provided AMD image recommends different flags, use the provided image guidance first. The important part is that `/v1/models` and `/v1/chat/completions` are reachable.

## Endpoint Checks

From a machine that can reach the endpoint:

```bash
curl http://YOUR_VLLM_ENDPOINT/v1/models
```

Then:

```bash
curl http://YOUR_VLLM_ENDPOINT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "messages": [
      {"role": "user", "content": "Reply with exactly: SwarmAudit LLM OK"}
    ],
    "max_tokens": 16,
    "temperature": 0
  }'
```

Expected completion:

```text
SwarmAudit LLM OK
```

## Connect SwarmAudit

Set local `.env` or Space secrets:

```text
LLM_PROVIDER=vllm
LLM_BASE_URL=http://YOUR_VLLM_ENDPOINT/v1
LLM_API_KEY=not-needed-if-open
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
ENABLE_LLM_ENRICHMENT=false
MAX_LLM_CHUNKS=2
```

Run:

```bash
python app.py
```

Open the Diagnostics tab and confirm:

- provider is `vllm`
- model is `Qwen/Qwen2.5-Coder-32B-Instruct`
- `/v1/models` succeeds
- chat completion succeeds

Then enable:

```text
ENABLE_LLM_ENRICHMENT=true
```

Restart the app after changing env vars.

## Credit-Safe Demo Order

1. Local mock test.
2. HF Space mock test.
3. Start AMD GPU.
4. Start vLLM.
5. Run Diagnostics once.
6. Run Benchmark once.
7. Enable enrichment with `MAX_LLM_CHUNKS=2`.
8. Audit:

```text
https://github.com/pallets/itsdangerous
```

9. If good, audit:

```text
https://github.com/psf/requests
```

10. Capture screenshots:
    - `rocm-smi`
    - vLLM startup/model logs
    - Diagnostics OK
    - Benchmark result
    - SwarmAudit report
11. Destroy the GPU instance when done.

## Important Billing Note

For AMD GPU droplets, powering off may still reserve billable resources. Destroy the instance when finished unless the provider explicitly says billing stops.

## Fallback

If anything fails, use:

```text
LLM_PROVIDER=mock
ENABLE_LLM_ENRICHMENT=false
```

SwarmAudit still runs the static multi-agent audit and remains demo-ready.

