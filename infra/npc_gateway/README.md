# NPC model runtime

The school GPU runtime is Docker-only. vLLM and the FastAPI NPC Gateway run in the same container, publish only to host loopback, and load all eight trained adapters from `training/outputs/`.

## Build and start

Run these commands only after connecting to the school machine:

```bash
ssh nccu-gpu
cd /home/team115_1/rag-npc-game
docker compose -f infra/npc_gateway/compose.yaml build runtime
docker compose -f infra/npc_gateway/compose.yaml up -d runtime
docker compose -f infra/npc_gateway/compose.yaml ps
docker compose -f infra/npc_gateway/compose.yaml logs --tail=100 runtime
```

The only host listeners are `127.0.0.1:8000` for the Gateway and `127.0.0.1:8001` for vLLM. Do not change them to a public bind address.

## Verify before accepting a cutover

```bash
docker compose -f infra/npc_gateway/compose.yaml exec runtime \
  python3 -m pytest -q

docker compose -f infra/npc_gateway/compose.yaml exec runtime \
  python3 -c "import json, urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')), ensure_ascii=False, indent=2))"

docker compose -f infra/npc_gateway/compose.yaml exec runtime \
  python3 scripts/evaluate_npc_gateway.py \
    --url http://127.0.0.1:8000/generate \
    --samples-per-case 3 \
    --require-dedicated-adapters \
    --require-observability

docker compose -f infra/npc_gateway/compose.yaml exec runtime \
  python3 scripts/evaluate_npc_gateway.py \
    --url http://127.0.0.1:8000/generate \
    --suite model-probe \
    --samples-per-case 3 \
    --require-dedicated-adapters \
    --require-observability \
    --require-model-source

docker compose -f infra/npc_gateway/compose.yaml exec runtime \
  python3 scripts/evaluate_live_story.py \
    --gateway-url http://127.0.0.1:8000/generate
```

Acceptance requires eight dedicated routes in `/health`, no base fallback for the eight story NPCs, complete observability headers, passing contract tests, and reviewed generated replies. The 2026-11-22 baseline is 201 backend tests, 93/93 guarded cases (90 pre-generation guards, 3 model replies), 47/72 open-ended raw LoRA probes, and five completed live ending routes. Weight files alone are not sufficient.

## Stop and inspect

```bash
docker compose -f infra/npc_gateway/compose.yaml stop runtime
docker compose -f infra/npc_gateway/compose.yaml logs --tail=200 runtime
```

Successful `/generate` responses expose `X-NPC-Generation-Source`, `X-NPC-Model-ID`, `X-NPC-Route-Kind`, `X-NPC-Upstream-Attempts`, and `Server-Timing`; `/metrics` aggregates the same routing, retry, failure, and latency data without storing prompts or dialogue.

The source checkout, model weights, Hugging Face cache, and vLLM compile cache survive container recreation. Runtime logs use the `npc-runtime-logs` Docker volume; vLLM uses `vllm-runtime-cache`. The Gateway attempts an invalid upstream model response up to three times before returning a temporary error.

## Development rule

Use `docker compose ... exec runtime` for model/Gateway work and tests. Do not run `.venv-gpu/bin/vllm`, host Uvicorn, or GPU evaluation directly on the school host.
