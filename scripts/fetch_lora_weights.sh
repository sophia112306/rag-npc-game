#!/usr/bin/env bash
set -euo pipefail

# Copy the two adapter directories from the school GPU host without deleting
# anything already present locally. Remote locations are explicit because
# weights are not stored in GitHub.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESTINATION_ROOT="${LORA_DESTINATION_ROOT:-${PROJECT_ROOT}/training/outputs}"

: "${SCHOOL_GPU_SSH:?Set SCHOOL_GPU_SSH, for example nccu-gpu}"
: "${REMOTE_MENMESVENTO_LORA_PATH:?Set the absolute remote Menmesvento adapter path}"
: "${REMOTE_VIDALIA_LORA_PATH:?Set the absolute remote Vidalia adapter path}"

if [[ "${SCHOOL_GPU_SSH}" == -* ]]; then
  echo "SCHOOL_GPU_SSH cannot start with '-'" >&2
  exit 2
fi

for remote_path in "${REMOTE_MENMESVENTO_LORA_PATH}" "${REMOTE_VIDALIA_LORA_PATH}"; do
  if [[ ! "${remote_path}" =~ ^/[A-Za-z0-9._/-]+$ || "${remote_path}" == *".."* ]]; then
    echo "Remote adapter paths must be simple absolute paths without '..': ${remote_path}" >&2
    exit 2
  fi
done

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required to copy the adapters" >&2
  exit 2
fi

mkdir -p \
  "${DESTINATION_ROOT}/menmesvento_lora_model" \
  "${DESTINATION_ROOT}/vidalia_lora_model"

rsync -av --partial \
  "${SCHOOL_GPU_SSH}:${REMOTE_MENMESVENTO_LORA_PATH%/}/" \
  "${DESTINATION_ROOT}/menmesvento_lora_model/"
rsync -av --partial \
  "${SCHOOL_GPU_SSH}:${REMOTE_VIDALIA_LORA_PATH%/}/" \
  "${DESTINATION_ROOT}/vidalia_lora_model/"

for adapter_path in \
  "${DESTINATION_ROOT}/menmesvento_lora_model" \
  "${DESTINATION_ROOT}/vidalia_lora_model"; do
  if [[ ! -f "${adapter_path}/adapter_config.json" ]]; then
    echo "Missing ${adapter_path}/adapter_config.json" >&2
    exit 1
  fi
  if [[ ! -f "${adapter_path}/adapter_model.safetensors" && ! -f "${adapter_path}/adapter_model.bin" ]]; then
    echo "Missing adapter weights in ${adapter_path}" >&2
    exit 1
  fi
done

echo "Both LoRA adapters are ready under ${DESTINATION_ROOT}"
