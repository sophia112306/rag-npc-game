#!/usr/bin/env bash
set -euo pipefail

# Copy the eight adapters referenced by the current story from the school GPU host
# without deleting anything already present locally. Remote locations are
# explicit because weights are not stored in GitHub.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESTINATION_ROOT="${LORA_DESTINATION_ROOT:-${PROJECT_ROOT}/training/outputs}"

: "${SCHOOL_GPU_SSH:?Set SCHOOL_GPU_SSH, for example nccu-gpu}"
: "${REMOTE_ALAN_LORA_PATH:?Set the absolute remote Alan adapter path}"
: "${REMOTE_ANDRE_LORA_PATH:?Set the absolute remote Andre adapter path}"
: "${REMOTE_DASSO_LORA_PATH:=${REMOTE_DHASO_LORA_PATH:-}}"
: "${REMOTE_DASSO_LORA_PATH:?Set the absolute remote Dasso adapter path}"
: "${REMOTE_MENMESVENTO_LORA_PATH:?Set the absolute remote Menmesvento adapter path}"
: "${REMOTE_SETH_LORA_PATH:?Set the absolute remote Seth adapter path}"
: "${REMOTE_SYRA_LORA_PATH:?Set the absolute remote Syra adapter path}"
: "${REMOTE_VIDALIA_LORA_PATH:?Set the absolute remote Vidalia adapter path}"
: "${REMOTE_VETA_LORA_PATH:?Set the absolute remote Veta adapter path}"

if [[ "${SCHOOL_GPU_SSH}" == -* ]]; then
  echo "SCHOOL_GPU_SSH cannot start with '-'" >&2
  exit 2
fi

ADAPTER_SPECS=(
  "alan|${REMOTE_ALAN_LORA_PATH}|alan_walker_lora_model"
  "andre|${REMOTE_ANDRE_LORA_PATH}|andre_lora_model"
  "dasso|${REMOTE_DASSO_LORA_PATH}|dhaso_lora_model"
  "menmesvento|${REMOTE_MENMESVENTO_LORA_PATH}|menmesvento_lora_model"
  "seth|${REMOTE_SETH_LORA_PATH}|seth_lora_model"
  "syra|${REMOTE_SYRA_LORA_PATH}|syra_lora_model"
  "vidalia|${REMOTE_VIDALIA_LORA_PATH}|vidalia_lora_model"
  "veta|${REMOTE_VETA_LORA_PATH}|veta_lora_model"
)

for spec in "${ADAPTER_SPECS[@]}"; do
  IFS='|' read -r _ remote_path _ <<< "${spec}"
  if [[ ! "${remote_path}" =~ ^/[A-Za-z0-9._/-]+$ || "${remote_path}" == *".."* ]]; then
    echo "Remote adapter paths must be simple absolute paths without '..': ${remote_path}" >&2
    exit 2
  fi
done

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required to copy the adapters" >&2
  exit 2
fi

for spec in "${ADAPTER_SPECS[@]}"; do
  IFS='|' read -r npc_id remote_path directory_name <<< "${spec}"
  adapter_path="${DESTINATION_ROOT}/${directory_name}"
  mkdir -p "${adapter_path}"
  echo "Fetching ${npc_id} adapter..."
  rsync -av --partial \
    "${SCHOOL_GPU_SSH}:${remote_path%/}/" \
    "${adapter_path}/"

  if [[ ! -f "${adapter_path}/adapter_config.json" ]]; then
    echo "Missing ${adapter_path}/adapter_config.json" >&2
    exit 1
  fi
  if [[ ! -f "${adapter_path}/adapter_model.safetensors" && ! -f "${adapter_path}/adapter_model.bin" ]]; then
    echo "Missing adapter weights in ${adapter_path}" >&2
    exit 1
  fi
done

echo "All eight story NPC LoRA adapters are ready under ${DESTINATION_ROOT}"
