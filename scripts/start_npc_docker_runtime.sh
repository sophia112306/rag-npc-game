#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${NPC_RUNTIME_LOG_DIR:-/var/log/rag-npc}"
VLLM_READY_TIMEOUT_SECONDS="${VLLM_READY_TIMEOUT_SECONDS:-900}"
mkdir -p "${LOG_DIR}"

vllm_pid=""
gateway_pid=""

stop_children() {
  if [[ -n "${gateway_pid}" ]]; then
    kill "${gateway_pid}" 2>/dev/null || true
  fi
  if [[ -n "${vllm_pid}" ]]; then
    kill "${vllm_pid}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}
trap stop_children EXIT INT TERM

cd "${PROJECT_ROOT}"
VLLM_HOST="${VLLM_HOST:-0.0.0.0}" \
  scripts/start_vllm_lora_server.sh \
  >"${LOG_DIR}/vllm.log" 2>&1 &
vllm_pid=$!

deadline=$((SECONDS + VLLM_READY_TIMEOUT_SECONDS))
until curl --fail --silent --show-error \
  "http://127.0.0.1:${VLLM_PORT:-8001}/v1/models" >/dev/null; do
  if ! kill -0 "${vllm_pid}" 2>/dev/null; then
    echo "vLLM stopped before becoming ready" >&2
    tail -n 100 "${LOG_DIR}/vllm.log" >&2 || true
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for vLLM readiness" >&2
    tail -n 100 "${LOG_DIR}/vllm.log" >&2 || true
    exit 1
  fi
  sleep 5
done

NPC_GATEWAY_HOST="${NPC_GATEWAY_HOST:-0.0.0.0}" \
  scripts/start_npc_gateway.sh \
  >"${LOG_DIR}/npc_gateway.log" 2>&1 &
gateway_pid=$!

deadline=$((SECONDS + 60))
until curl --fail --silent --show-error \
  "http://127.0.0.1:${NPC_GATEWAY_PORT:-8000}/health" >/dev/null; do
  if ! kill -0 "${gateway_pid}" 2>/dev/null; then
    echo "NPC Gateway stopped before becoming ready" >&2
    tail -n 100 "${LOG_DIR}/npc_gateway.log" >&2 || true
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for NPC Gateway readiness" >&2
    tail -n 100 "${LOG_DIR}/npc_gateway.log" >&2 || true
    exit 1
  fi
  sleep 2
done

set +e
wait -n "${vllm_pid}" "${gateway_pid}"
exit $?
