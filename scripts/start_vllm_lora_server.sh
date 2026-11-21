#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_MODEL_NAME="${BASE_MODEL_NAME:-Qwen/Qwen2.5-7B-Instruct-AWQ}"
MENMESVENTO_LORA_PATH="${MENMESVENTO_LORA_PATH:-${PROJECT_ROOT}/training/outputs/menmesvento_lora_model}"
VIDALIA_LORA_PATH="${VIDALIA_LORA_PATH:-${PROJECT_ROOT}/training/outputs/vidalia_lora_model}"
ANDRE_LORA_PATH="${ANDRE_LORA_PATH:-${PROJECT_ROOT}/training/outputs/andre_lora_model}"
# Keep the runtime NPC ID/model ID as "dasso" even though the training
# directory landed in GitHub with the historical "dhaso" spelling.
DASSO_LORA_PATH="${DASSO_LORA_PATH:-${DHASO_LORA_PATH:-${PROJECT_ROOT}/training/outputs/dhaso_lora_model}}"
SETH_LORA_PATH="${SETH_LORA_PATH:-${PROJECT_ROOT}/training/outputs/seth_lora_model}"
SYRA_LORA_PATH="${SYRA_LORA_PATH:-${PROJECT_ROOT}/training/outputs/syra_lora_model}"
VETA_LORA_PATH="${VETA_LORA_PATH:-${PROJECT_ROOT}/training/outputs/veta_lora_model}"
ALAN_WALKER_LORA_PATH="${ALAN_WALKER_LORA_PATH:-${PROJECT_ROOT}/training/outputs/alan_walker_lora_model}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8001}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.65}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-4096}"
NPC_VLLM_MAX_LORAS="${NPC_VLLM_MAX_LORAS:-2}"
NPC_VLLM_MAX_CPU_LORAS="${NPC_VLLM_MAX_CPU_LORAS:-8}"

LORA_MODULES=(
  "andre-lora=${ANDRE_LORA_PATH}"
  "dasso-lora=${DASSO_LORA_PATH}"
  "menmesvento-lora=${MENMESVENTO_LORA_PATH}"
  "seth-lora=${SETH_LORA_PATH}"
  "syra-lora=${SYRA_LORA_PATH}"
  "vidalia-lora=${VIDALIA_LORA_PATH}"
  "veta-lora=${VETA_LORA_PATH}"
  "alan-walker-lora=${ALAN_WALKER_LORA_PATH}"
)

if ! command -v vllm >/dev/null 2>&1; then
  echo "vllm is not installed or not available on PATH" >&2
  exit 2
fi

for module in "${LORA_MODULES[@]}"; do
  adapter_path="${module#*=}"
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
  --max-loras "${NPC_VLLM_MAX_LORAS}" \
  --max-cpu-loras "${NPC_VLLM_MAX_CPU_LORAS}" \
  --max-lora-rank 16 \
  --lora-modules \
    "${LORA_MODULES[@]}"
