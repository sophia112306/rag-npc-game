# 多 NPC LoRA GPU Gateway

這條串接把 CUDA 完全留在學校 GPU server。遊戲後端只傳 `ModelTurnRequest`，並只需設定一個 `MODEL_GATEWAY_URL`；GPU gateway 依後端授權的 `target_context.npc_id` 選擇 LoRA，再把模型輸出驗成 `ModelStoryOutput`。

**2026-11-20 真機結果：** 校內 RTX 5060 Ti（16 GB）已用 vLLM 0.31.0 同時註冊 AWQ base 與目前 2D 地圖上的六個 LoRA；`/health` ready，六個角色都能生成合法 `ModelStoryOutput`，並已由完整遊戲後端依正式路線走到鳴霖、流塵谷、烈燚原與邊境廢墟完成回合。服務以 loopback + `nohup` 運行，主機重開後仍要重新啟動，尚未做成 systemd 常駐服務。

這是「程式與路由已接通」，不是六個模型的內容已全部核准。11 月 18 日的新資料多數仍以純台詞或舊 `relation_delta/line` 為訓練目標，runtime 靠 strict JSON Schema 約束結構；真機抽測仍看到安德烈提出未授權的責任猜測、門梅司文托補寫千年往事、達索夾入英文或迴避問題。gateway 已擋掉直接羞辱與無效自介，但其餘人格、事實邊界與中英混雜仍要完成資料遷移、重訓及人工驗收，不能只因 JSON 合法就標為正式上線。

```text
終端／前端 → 遊戲 FastAPI → MODEL_GATEWAY_URL (/generate)
                         → NPC adapter gateway → vLLM /v1/chat/completions → GPU
                                                   ├─ vidalia-lora / andre-lora
                                                   ├─ menmesvento-lora / dasso-lora
                                                   └─ seth-lora / syra-lora
```

玩家／主角不是 NPC Registry 成員，gateway 會回 `UNSUPPORTED_NPC`，不會替主角選 adapter。維塔與 2026-11-20 最新的艾倫權重都存在校機，但兩者不在目前主遊戲地圖的 NPC Registry／場景流程，因此本輪沒有硬接進 2D 主線。

## 1. LoRA 權重

GitHub 只有訓練程式與資料，不含權重。每個 adapter 目錄至少要有：

```text
adapter_config.json
adapter_model.safetensors   # 或 adapter_model.bin
```

若要把學校主機上的權重複製到目前 checkout，先填入實際遠端絕對路徑：

```bash
export SCHOOL_GPU_SSH=nccu-gpu
export REMOTE_ANDRE_LORA_PATH='/absolute/path/andre_lora_model'
export REMOTE_DASSO_LORA_PATH='/absolute/path/dhaso_lora_model'
export REMOTE_MENMESVENTO_LORA_PATH='/absolute/path/menmesvento_lora_model'
export REMOTE_SETH_LORA_PATH='/absolute/path/seth_lora_model'
export REMOTE_SYRA_LORA_PATH='/absolute/path/syra_lora_model'
export REMOTE_VIDALIA_LORA_PATH='/absolute/path/vidalia_lora_model'
./scripts/fetch_lora_weights.sh
```

腳本只新增／更新 `training/outputs/`，不會刪除遠端或本機資料。`training/outputs/` 已被 Git 忽略，不可提交權重。

目前校機 `rag-npc-game/training/outputs` 中的地圖權重：

| NPC | 目錄 | `adapter_model.safetensors` SHA-256 |
| --- | --- | --- |
| 安德烈 | `andre_lora_model` | `26a0116c98ce17ea5578bfc7429bc0da985c6898fe85689f665bf7c10f0d83e0` |
| 達索 | `dhaso_lora_model` | `9dc151436650f0228d096cf5b6281b31d5e24f09b5d30ae270a7a7f4f1b3c13a` |
| 門梅司文托 | `menmesvento_lora_model` | `5b568e2c663fa8a28abbc2398b5f83b0c52f909a0b78b4c624b53794e9c5f1ee` |
| 塞特 | `seth_lora_model` | `873d55451f0a07ff92b842c499d2306968ccbf87dfafaa19aaf83aea6fb9a7aa` |
| 希拉 | `syra_lora_model` | `5ad48e351eda243db6f6204f4e2928db5d83f39f7c2efd8ae41b481413746c53` |
| 維達利亞 | `vidalia_lora_model` | `bc51ced1ffe2951cb209e0475ad1ab9b95fb6fba6a813eee60964c32894f1497` |

`dhaso_lora_model` 是訓練端已落地的歷史拼字；遊戲與 gateway 的正式 ID 一律使用 `dasso`／`dasso-lora`。2026-11-17 通過較完整知識邊界驗收的門梅司文托與維達利亞 v2 權重仍保留在 `/home/team115_1/rag-npc-retrain-20261117/outputs/`；內容正式發布前，應比較這兩份已核准版本與 11 月 18 日新版，而不是只看時間或 training loss。

## 2. 在 GPU server 啟動兩個程序

第一次建立 GPU 推論環境：

```bash
python3 -m venv .venv-gpu
source .venv-gpu/bin/activate
python -m pip install -r requirements-gpu.txt
```

終端 A 啟動 vLLM。若權重不在 repo 預設位置，就設定六個絕對路徑：

```bash
source .venv-gpu/bin/activate
export ANDRE_LORA_PATH='/absolute/path/andre_lora_model'
export DASSO_LORA_PATH='/absolute/path/dhaso_lora_model'
export MENMESVENTO_LORA_PATH='/absolute/path/menmesvento_lora_model'
export SETH_LORA_PATH='/absolute/path/seth_lora_model'
export SYRA_LORA_PATH='/absolute/path/syra_lora_model'
export VIDALIA_LORA_PATH='/absolute/path/vidalia_lora_model'
./scripts/start_vllm_lora_server.sh
```

此命令在 `127.0.0.1:8001` 載入一次 `Qwen/Qwen2.5-7B-Instruct-AWQ`，註冊六個地圖 adapter，並以 `NPC_VLLM_MAX_LORAS=2`、`NPC_VLLM_MAX_CPU_LORAS=6` 控制同批 GPU adapter 與 CPU adapter cache。六份權重的 rank 都是 16。校機目前同時保留約 4 GB 的 Hunyuan 程序，vLLM 使用 `VLLM_GPU_MEMORY_UTILIZATION=0.65`、`VLLM_MAX_MODEL_LEN=4096` 且跑過六位角色後，實測總顯存約 14.6 GiB、剩餘約 1.2 GiB；不要未量測就提高比例。

終端 B 啟動契約 gateway：

```bash
source .venv-gpu/bin/activate
./scripts/start_npc_gateway.sh
curl --fail http://127.0.0.1:8000/health
```

`/health` 必須列出 base model 與六個 LoRA ID；少任何一個都不算 ready。兩個服務預設只綁 loopback，不公開到校外網路。

## 3. 本機只設定 MODEL_GATEWAY_URL

先建立 SSH tunnel：

```bash
ssh -N -L 8800:127.0.0.1:8000 nccu-gpu
```

另一個本機終端啟動遊戲後端：

```bash
MODEL_GATEWAY_URL=http://127.0.0.1:8800/generate \
  ./.venv/bin/uvicorn backend.main:app --reload --port 8300
```

`MODEL_GATEWAY_PROVIDER` 預設已是 `contract_http`，不需要填 `MODEL_GATEWAY_MODEL`。若 gateway 有設定 `NPC_GATEWAY_API_KEY`，本機才需額外設定相同的 `MODEL_GATEWAY_API_KEY`。

## 4. 先用終端測試

直接測 GPU gateway 與 LoRA JSON：

```bash
for npc in vidalia andre menmesvento dasso seth syra; do
  PYTHONPATH=. ./.venv/bin/python scripts/smoke_npc_gateway.py \
    --url http://127.0.0.1:8800/generate --npc "$npc"
done
```

測完整遊戲後端、Session 與狀態版本：

```bash
for npc in vidalia andre menmesvento dasso seth syra; do
  ./.venv/bin/python scripts/chat_backend.py --npc "$npc" \
    --once "請用一句話告訴我，目前最值得注意的是什麼？"
done
```

目前新 Session 位於鳴霖，可直接與維達利亞或安德烈對話。腳本會依正式劇情選項走到門梅司文托所在的流塵谷、達索所在的烈燚原，以及塞特／希拉所在的邊境廢墟，不會繞過解鎖或場景規則。

## 5. 資料與驗收

Runtime 的唯一合法輸出仍是：

```json
{
  "intent_summary": "簡短意圖摘要",
  "npc_dialogue": [{"text": "NPC 台詞", "emotion": null}],
  "event_proposals": []
}
```

人格樣本不直接教模型修改世界狀態，所以 `event_proposals` 應固定為空；事件只有在 runtime 中由模型提出、再由後端驗證。

但 2026-11-18 合併進 GitHub 的六份地圖資料尚未全部遷移：多數 assistant target 是純台詞，安德烈仍是 `relation_delta/line`。`menmesvento_data.jsonl` 另帶入一段舊版結構資料；本輪已移除其中一個殘留的 merge marker，所有 JSONL 現在可解析。以下 `--check` 在真正遷移前應回報六個檔案待處理；不要把它的失敗誤判成權重檔壞掉，也不要在沒有安排重訓時直接提交數千行機械改寫。

```bash
./.venv/bin/python scripts/migrate_training_data_to_model_story_output.py --check
# 遷移完成後才執行：
./.venv/bin/python scripts/validate_training_data.py
```

真實權重啟動後，依 [B AI／RAG 交接清單](B_AI_RAG_HANDOFF.md#p3b-需要完成的驗收案例) 測人格、prompt injection、未解鎖秘密、跨 NPC 記憶、合法 JSON、timeout 與錯誤回復。程式測試能保證路由和結構，但角色品質與知識邊界仍必須用真實權重實測。

可重複執行的 13 題 smoke evaluation（四位新增地圖 NPC 自介＋原有安全與邊界案例）：

```bash
PYTHONPATH=. ./.venv/bin/python scripts/evaluate_npc_gateway.py \
  --url http://127.0.0.1:8800/generate
```

腳本會強制驗證 `ModelStoryOutput`、沒有 Markdown fence、沒有角色外占位文字、沒有未授權事件，並檢查四位新增角色能用公開身分自介。人格、未知設定與其他事實邊界仍需閱讀輸出人工判定。

2026-11-20 六模型整合結果：

- 六個 adapter 都能在同一 vLLM 列出並回傳合法結構；完整遊戲後端六位角色的回合與正式地圖路線都成功。
- 達索的訓練輸出曾出現直接羞辱或不回答自介；gateway 現在以公開角色卡替換這類輸出。
- prompt injection、假道具、具體 `missing_data` 與跨 NPC 私人記憶仍有 gateway fail-closed 防線，不把安全性只押在 LoRA 上。
- 新四位 NPC 的完整角色卡、授權知識與逐題內容評分仍未完成；安德烈與門梅司文托的抽測已證明 strict JSON 不等於事實邊界通過。
- vLLM 偶發回傳 200 但內容不可解析時，gateway 最多重試一次；持續失敗才回暫時錯誤，不提交半個遊戲回合。

2026-11-17 通過較完整邊界驗收的兩份舊權重仍可作發布候選；11 月 18 日六份新版目前定位為整合／比較候選。正式發布前須先完成六份資料的契約遷移與角色設定審核，再重訓或選回已核准權重。

## 已移除的舊單模型路徑

本次不再保留 `backend/config.py`、`backend/services/llm_client.py`、`backend/services/model_gateway.py` 與 `training/notebooks/alan_vance.py`。前三者會在遊戲後端直接載入單一 LoRA、依賴 CUDA／Unsloth，與現在「遊戲後端只呼叫一個 GPU Gateway URL」的架構衝突。新加入的 `alan_walker.py` 仍是離線訓練／測試項目；在艾倫尚未成為地圖 NPC 前，不加入 runtime 路由。所有 runtime 選模、strict JSON 與安全邊界由 `gpu_gateway/` 負責。
