# 多 NPC LoRA GPU Gateway

這條串接把 CUDA 完全留在學校 GPU server。遊戲後端只傳 `ModelTurnRequest`，並只需設定一個 `MODEL_GATEWAY_URL`；GPU gateway 依後端授權的 `target_context.npc_id` 選擇 LoRA，再把模型輸出驗成 `ModelStoryOutput`。

**2026-11-17 真機結果：** 校內 RTX 5060 Ti（16 GB）已用 vLLM 0.31.0 同時載入 AWQ base 與兩個重新訓練的 LoRA，`/health` ready；兩個角色均能生成合法 `ModelStoryOutput`，完整遊戲後端的終端回合也成功。服務目前以 loopback + `nohup` 運行，主機重開後要重新啟動，尚未做成 systemd 常駐服務。

```text
終端／前端 → 遊戲 FastAPI → MODEL_GATEWAY_URL (/generate)
                         → NPC adapter gateway → vLLM /v1/chat/completions → GPU
                                                   ├─ vidalia-lora
                                                   ├─ menmesvento-lora
                                                   └─ 其他已登記 NPC：base model
```

玩家／主角不是 NPC Registry 成員，gateway 會回 `UNSUPPORTED_NPC`，不會替主角選 adapter。現階段只有維達利亞與門梅司文托受過 NPC LoRA 訓練。

## 1. LoRA 權重

GitHub 只有訓練程式與資料，不含權重。兩個 adapter 目錄至少要有：

```text
adapter_config.json
adapter_model.safetensors   # 或 adapter_model.bin
```

若要把學校主機上的權重複製到目前 checkout，先填入實際遠端絕對路徑：

```bash
export SCHOOL_GPU_SSH=nccu-gpu
export REMOTE_MENMESVENTO_LORA_PATH='/absolute/path/menmesvento_lora_model'
export REMOTE_VIDALIA_LORA_PATH='/absolute/path/vidalia_lora_model'
./scripts/fetch_lora_weights.sh
```

腳本只新增／更新 `training/outputs/`，不會刪除遠端或本機資料。`training/outputs/` 已被 Git 忽略，不可提交權重。

目前校機已驗收的新版權重（舊版仍保留，未覆寫）：

| NPC | 校機路徑 | `adapter_model.safetensors` SHA-256 |
| --- | --- | --- |
| 門梅司文托 | `/home/team115_1/rag-npc-retrain-20261117/outputs/menmesvento_model_story_output_lora` | `25f10504ac12d81d7019452d58b35ab593a625670cdc35fafade11bb9f5c026a` |
| 維達利亞 v2 | `/home/team115_1/rag-npc-retrain-20261117/outputs/vidalia_model_story_output_lora_v2` | `61722f91946d76dbd11ecb3e6703a1c4ea57c906e5a9a43c0dd4dbbbe8d1ccce` |

## 2. 在 GPU server 啟動兩個程序

第一次建立 GPU 推論環境：

```bash
python3 -m venv .venv-gpu
source .venv-gpu/bin/activate
python -m pip install -r requirements-gpu.txt
```

終端 A 啟動 vLLM。若權重不在 repo 預設位置，就設定兩個絕對路徑：

```bash
source .venv-gpu/bin/activate
export MENMESVENTO_LORA_PATH='/absolute/path/menmesvento_lora_model'
export VIDALIA_LORA_PATH='/absolute/path/vidalia_lora_model'
./scripts/start_vllm_lora_server.sh
```

此命令在 `127.0.0.1:8001` 載入一次 `Qwen/Qwen2.5-7B-Instruct-AWQ`，並註冊 `menmesvento-lora`、`vidalia-lora`。LoRA 雖是在同架構的 Unsloth BNB 4-bit base 上訓練，但校機目前的 vLLM 0.31.0 不接受 bitsandbytes 推論格式，因此用 vLLM 原生支援的同架構 AWQ base 承載相同 adapter。兩個訓練程式的 rank 都是 16，因此啟動參數固定 `--max-lora-rank 16`。校機為 16 GB GPU，預設 `VLLM_GPU_MEMORY_UTILIZATION=0.65`、`VLLM_MAX_MODEL_LEN=4096`，避免與既有 Hunyuan container 的約 4 GB 顯存互撞；若該 container 已停用，再依量測提高。

終端 B 啟動契約 gateway：

```bash
source .venv-gpu/bin/activate
./scripts/start_npc_gateway.sh
curl --fail http://127.0.0.1:8000/health
```

`/health` 必須列出 base model 與兩個 LoRA ID；少任何一個都不算 ready。兩個服務預設只綁 loopback，不公開到校外網路。

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
PYTHONPATH=. ./.venv/bin/python scripts/smoke_npc_gateway.py --url http://127.0.0.1:8800/generate --npc vidalia
PYTHONPATH=. ./.venv/bin/python scripts/smoke_npc_gateway.py --url http://127.0.0.1:8800/generate --npc menmesvento
```

測完整遊戲後端、Session 與狀態版本：

```bash
./.venv/bin/python scripts/chat_backend.py --npc vidalia
./.venv/bin/python scripts/chat_backend.py --npc menmesvento
```

目前新 Session 位於鳴霖，可直接與維達利亞對話。`chat_backend.py --npc menmesvento` 會自動依正式劇情選項走到流塵谷，不會繞過場景規則。

## 5. 資料與驗收

兩份資料已統一成正式輸出，repo 共 100 筆（門梅司文托 45、維達利亞 55；新增的古卷邊界案例需在下一版權重重訓後才會進入 LoRA）：

```json
{
  "intent_summary": "簡短意圖摘要",
  "npc_dialogue": [{"text": "NPC 台詞", "emotion": null}],
  "event_proposals": []
}
```

人格樣本不直接教模型修改世界狀態，所以 `event_proposals` 固定為空；事件只有在 runtime 中由模型提出、再由後端驗證。資料檢查：

```bash
./.venv/bin/python scripts/migrate_training_data_to_model_story_output.py --check
./.venv/bin/python scripts/validate_training_data.py
```

真實權重啟動後，依 [B AI／RAG 交接清單](B_AI_RAG_HANDOFF.md#p3b-需要完成的驗收案例) 測人格、prompt injection、未解鎖秘密、跨 NPC 記憶、合法 JSON、timeout 與錯誤回復。程式測試能保證路由和結構，但角色品質與知識邊界仍必須用真實權重實測。

可重複執行的七題 smoke evaluation：

```bash
PYTHONPATH=. ./.venv/bin/python scripts/evaluate_npc_gateway.py \
  --url http://127.0.0.1:8800/generate
```

腳本會強制驗證七次都符合 `ModelStoryOutput`、沒有 Markdown fence、沒有角色外占位文字、沒有未授權事件；第七題另驗證蒙梅斯文托不會替古卷編造能力、危險或觸碰後果。人格與其他事實邊界的用詞仍需閱讀輸出人工判定。

2026-11-17 重新訓練後的真實權重結果：

- `7/7` 回覆通過 JSON 與 `ModelStoryOutput` 驗證；第七題為古卷知識邊界。
- 維達利亞會直接說明如何查驗命脈之泉異象；不再輸出「角色回應玩家」占位文字。
- 門梅司文托會針對墓碑、名字與見證直接回答，不再退回固定 greeting。
- prompt injection、假道具及跨 NPC 私人記憶均未改變客觀狀態或洩漏資料。
- `missing_data` 與提示注入另有 gateway fail-closed 防線，不把安全性只押在 LoRA 上；兩者均有單測。
- 對「資料不足但要求判斷命脈之泉原因」的問題，gateway 會在呼叫模型前先回證據優先答案，避免模型憑空補出斷流等症狀；此路徑已有單測。
- 對古卷內容、輪迴真相、能力或危險的追問，gateway 只回覆已確認的記錄用途並保留未知設定；此路徑有單測及 live evaluation case。
- vLLM 偶發回傳 200 但內容不可解析時，gateway 最多重試一次；持續失敗才回暫時錯誤，避免單次生成抖動中斷回合。

目前上線的是表中 Vidalia v2（以 50 筆資料訓練）。後續新增的 5 筆證據邊界資料已納入 repo；一次 55 筆 v3 試訓因 strict JSON 生成時可能在 `npc_dialogue` 前陷入空白字元迴圈，已拒絕上線並回退 v2，不能只看 training loss 判定可部署。
## 已移除的舊單模型路徑

本次不再保留 `backend/config.py`、`backend/services/llm_client.py`、`backend/services/model_gateway.py` 與 `training/notebooks/alan_vance.py`。前三者會在遊戲後端直接載入單一 LoRA、依賴 CUDA／Unsloth，與現在「遊戲後端只呼叫一個 GPU Gateway URL」的架構衝突；最後一個會訓練主角，但目前範圍明確只有兩名 NPC adapter。所有 runtime 選模、strict JSON 與安全邊界改由 `gpu_gateway/` 負責。
