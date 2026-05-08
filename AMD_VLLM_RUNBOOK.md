# AMD vLLM Runbook

This runbook keeps SwarmAudit ready for AMD Developer Cloud without requiring code changes after credits arrive. SwarmAudit talks to vLLM over an OpenAI-compatible HTTP API, so the app only needs environment variables once the endpoint is live.

## Current Safe Default

Use this locally and on Hugging Face Spaces until the AMD endpoint is verified:

```text
LLM_PROVIDER=mock
ENABLE_LLM_ENRICHMENT=false
```

In this mode, SwarmAudit still produces reports from static analysis agents. The mock LLM is only a local development placeholder.

## Credit-Safe AMD Test Settings

Start with small limits while proving the endpoint:

```text
LLM_PROVIDER=vllm
LLM_BASE_URL=http://YOUR_VLLM_ENDPOINT/v1
LLM_API_KEY=not-needed-if-open
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
ENABLE_LLM_ENRICHMENT=false
MAX_FILES=100
MAX_FILE_SIZE_KB=150
MAX_CHARS_PER_CHUNK=8000
MAX_LLM_CHUNKS=2
```

Only switch `ENABLE_LLM_ENRICHMENT=true` after the Diagnostics tab passes.

## AMD Developer Cloud Flow

1. Create or start an AMD Developer Cloud GPU instance.
2. Confirm the instance has ROCm/GPU access using the image or environment provided by AMD.
3. Install/use vLLM in the GPU environment. Do not add vLLM to SwarmAudit's local `requirements.txt`.
4. Start an OpenAI-compatible vLLM server.

Example shape:

```bash
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --api-key swarm-audit-demo-key
```

If the AMD environment provides a managed vLLM image or launch template, use that instead, but keep the same OpenAI-compatible `/v1` API.

## Endpoint Checks

From a machine that can reach the vLLM server:

```bash
curl http://YOUR_VLLM_ENDPOINT/v1/models \
  -H "Authorization: Bearer swarm-audit-demo-key"
```

Then test chat completions:

```bash
curl http://YOUR_VLLM_ENDPOINT/v1/chat/completions \
  -H "Authorization: Bearer swarm-audit-demo-key" \
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

## Connect SwarmAudit

Set these in `.env`, Hugging Face Space secrets, or your shell:

```text
LLM_PROVIDER=vllm
LLM_BASE_URL=http://YOUR_VLLM_ENDPOINT/v1
LLM_API_KEY=swarm-audit-demo-key
LLM_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
ENABLE_LLM_ENRICHMENT=false
MAX_LLM_CHUNKS=2
```

Open the Gradio Diagnostics tab and confirm:

- Provider is `vllm`
- `/v1/models` responds
- The simple chat completion succeeds
- The configured model appears in the model list

Then enable enrichment:

```text
ENABLE_LLM_ENRICHMENT=true
```

Restart the app after changing env vars.

## Credit-Safe Test Order

1. Test SwarmAudit locally in mock mode.
2. Confirm Hugging Face Spaces still works in mock mode.
3. Start AMD GPU instance.
4. Start vLLM.
5. Run Diagnostics once.
6. Run Benchmark once.
7. Enable enrichment with `MAX_LLM_CHUNKS=2`.
8. Audit:

```text
https://github.com/pallets/itsdangerous
```

9. If that works, audit:

```text
https://github.com/psf/requests
```

10. Capture screenshots and benchmark output.
11. Stop the GPU instance immediately after collecting demo proof.

## If Anything Fails

Return to the reliable demo path:

```text
LLM_PROVIDER=mock
ENABLE_LLM_ENRICHMENT=false
```

The app will still run the static multi-agent audit and produce exportable Markdown/JSON reports.

## References

- vLLM OpenAI-compatible server docs: https://docs.vllm.ai/en/stable/serving/openai_compatible_server/
- vLLM serve CLI docs: https://docs.vllm.ai/en/stable/cli/serve/
