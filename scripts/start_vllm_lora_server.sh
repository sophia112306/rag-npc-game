#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_MODEL_NAME="${BASE_MODEL_NAME:-Qwen/Qwen2.5-7B-Instruct-AWQ}"
MENMESVENTO_LORA_PATH="${MENMESVENTO_LORA_PATH:-${PROJECT_ROOT}/training/outputs/menmesvento_lora_model}"
VIDALIA_LORA_PATH="${VIDALIA_LORA_PATH:-${PROJECT_ROOT}/training/outputs/vidalia_lora_model}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8001}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.65}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-4096}"

if ! command -v vllm >/dev/null 2>&1; then
  echo "vllm is not installed or not available on PATH" >&2
  exit 2
fi

for adapter_path in "${MENMESVENTO_LORA_PATH}" "${VIDALIA_LORA_PATH}"; do
  if [[ ! -f "${adapter_path}/adapter_config.json" ]]; then
    echo "Invalid LoRA directory; adapter_config.json is missing: ${adapter_path}" >&2
    exit 2
  fi
  if [[ ! -f "${adapter_path}/adapter_model.safetensors" && ! -f "${adapter_path}/adapter_model.bin" ]]; then
    echo "Invalid LoRA directory; adapter weights are missing: ${adapter_path}" >&2
    exit 2
  fi
done

exec vllm serve "${BASE_MODEL_NAME}" \
  --host "${VLLM_HOST}" \
  --port "${VLLM_PORT}" \
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION}" \
  --max-model-len "${VLLM_MAX_MODEL_LEN}" \
  --enable-lora \
  --max-loras 2 \
  --max-cpu-loras 2 \
  --max-lora-rank 16 \
  --lora-modules \
    "menmesvento-lora=${MENMESVENTO_LORA_PATH}" \
    "vidalia-lora=${VIDALIA_LORA_PATH}"
