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
    --require-dedicated-adapters
```

Acceptance requires eight dedicated routes in `/health`, no base fallback for the eight story NPCs, passing contract tests, and reviewed generated replies. Weight files alone are not sufficient.

## Stop and inspect

```bash
docker compose -f infra/npc_gateway/compose.yaml stop runtime
docker compose -f infra/npc_gateway/compose.yaml logs --tail=200 runtime
```

The source checkout, model weights, and Hugging Face cache are bind-mounted and survive container recreation. Runtime logs use the `npc-runtime-logs` Docker volume.

## Development rule

Use `docker compose ... exec runtime` for model/Gateway work and tests. Do not run `.venv-gpu/bin/vllm`, host Uvicorn, or GPU evaluation directly on the school host.
