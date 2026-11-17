#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NPC_GATEWAY_PYTHON="${NPC_GATEWAY_PYTHON:-python3}"
NPC_GATEWAY_HOST="${NPC_GATEWAY_HOST:-127.0.0.1}"
NPC_GATEWAY_PORT="${NPC_GATEWAY_PORT:-8000}"

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

exec "${NPC_GATEWAY_PYTHON}" -m uvicorn gpu_gateway.app:app \
  --host "${NPC_GATEWAY_HOST}" \
  --port "${NPC_GATEWAY_PORT}"
