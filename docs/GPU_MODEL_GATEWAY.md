# 多 NPC LoRA GPU Gateway

這條串接把 CUDA 完全留在學校 GPU server。遊戲後端只傳 `ModelTurnRequest`，並只需設定一個 `MODEL_GATEWAY_URL`；GPU gateway 依後端授權的 `target_context.npc_id` 選擇 LoRA，再把模型輸出驗成 `ModelStoryOutput`。

**2026-11-20 真機結果：** 校內 RTX 5060 Ti（16 GB）已用 vLLM 0.31.0 同時註冊 AWQ base 與目前 2D 地圖上的六個 LoRA；`/health` ready，六個角色都能生成合法 `ModelStoryOutput`，並已由完整遊戲後端依正式路線走到鳴霖、流塵谷、烈燚原與邊境廢墟完成回合。服務以 loopback + `nohup` 運行，主機重開後仍要重新啟動，尚未做成 systemd 常駐服務。

**2026-11-22 程式狀態：** 主故事已新增記憶圖書館的艾倫通訊與命脈之泉源頭的維塔三問，角色 Registry、gateway map、權重下載與 vLLM 啟動腳本因此擴為八個 adapter。這只是程式接線；本輪沒有部署、重啟校機或量測八模型容量，最近一次可宣稱的真機結果仍是上面的六模型結果。

**2026-11-22 現有服務複查：** 當天唯讀查詢正在執行的校機 `/health`，實際只列出 `vidalia-lora`、`menmesvento-lora` 與 base model；安德烈、達索、塞特、希拉會退回 base，艾倫／維塔則被舊 gateway 以 422 拒絕。八個最終目錄各有約 161.5 MB 權重，模型確實已訓練；但 `rag-npc-llm` Docker 只有閒置 shell，實際 8000／8001 服務是 host `.venv-gpu` 程序，啟動時只載入兩個 adapter。完整 93 次請求與容器檢查見 [多角色真機回覆評測](qa/model-evaluation/2026-11-22.md)。

**2026-11-22 Docker 切換完成：** 已停止 host `.venv-gpu` 的 vLLM／Uvicorn，正式 runtime 改為 `infra/npc_gateway/compose.yaml` 管理。`rag-npc-llm` 內同時執行 vLLM 0.31.0 與 Gateway，`/health` 列出八條專屬 LoRA 路由；host 只綁 `127.0.0.1:8000`、`127.0.0.1:8001`，沒有公開部署。守門後系統測試為 93／93，其中 90 次是前置守門、3 次採用模型；開放式原始 LoRA 的早期逐字基準為 47／72，人工確認維塔同義回答後最新為 53／72，權重未變。五種結局與六位地圖 NPC 真機回合已經正式 API 實走完成；Docker 內 207 個後端測試通過。

八份權重與路由已在同一個 Docker runtime 真機接通，但不能把 93／93 的系統成績寫成原始 LoRA 單獨達成。第一次八模型測試只有 61／93；目前 93／93 包含 Gateway 的公開角色卡、知識邊界與故事權限守門。11 月 18 日的新資料仍多以純台詞或舊 `relation_delta/line` 為訓練目標，後續若要宣稱模型本身的內容品質提升，仍需資料遷移、重訓及盲測。

```text
終端／前端 → 遊戲 FastAPI → MODEL_GATEWAY_URL (/generate)
                         → NPC adapter gateway → vLLM /v1/chat/completions → GPU
                                                   ├─ vidalia-lora / andre-lora
                                                   ├─ menmesvento-lora / dasso-lora
                                                   ├─ seth-lora / syra-lora
                                                   └─ alan-lora / veta-lora
```

玩家／主角不是 NPC Registry 成員，gateway 會回 `UNSUPPORTED_NPC`，不會替主角選 adapter。艾倫與維塔現在是主故事中的遠端／地標角色，不加入 `NPC_SCENES` 的實體人物碰撞表；正式事件、道具與結局仍由伺服器規則決定，LoRA 不能自行改變故事狀態。

## 1. LoRA 權重

GitHub 只有訓練程式與資料，不含權重。每個 adapter 目錄至少要有：

```text
adapter_config.json
adapter_model.safetensors   # 或 adapter_model.bin
```

若要把學校主機上的權重複製到目前 checkout，先填入實際遠端絕對路徑：

```bash
export SCHOOL_GPU_SSH=nccu-gpu
export REMOTE_ALAN_LORA_PATH='/absolute/path/alan_walker_lora_model'
export REMOTE_ANDRE_LORA_PATH='/absolute/path/andre_lora_model'
export REMOTE_DASSO_LORA_PATH='/absolute/path/dhaso_lora_model'
export REMOTE_MENMESVENTO_LORA_PATH='/absolute/path/menmesvento_lora_model'
export REMOTE_SETH_LORA_PATH='/absolute/path/seth_lora_model'
export REMOTE_SYRA_LORA_PATH='/absolute/path/syra_lora_model'
export REMOTE_VIDALIA_LORA_PATH='/absolute/path/vidalia_lora_model'
export REMOTE_VETA_LORA_PATH='/absolute/path/veta_lora_model'
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
| 艾倫 | `alan_walker_lora_model` | `c68472e08f6fa27b125a13dbebea2df4fda97f9380f79fefb09a32a80ca37245` |
| 維塔 | `veta_lora_model` | `d6bed863744e2f557c7a3cfcf7ef378a365712d5366ddb9234ee0067423e2a1a` |

`dhaso_lora_model` 是訓練端已落地的歷史拼字；遊戲與 gateway 的正式 ID 一律使用 `dasso`／`dasso-lora`。2026-11-17 通過較完整知識邊界驗收的門梅司文托與維達利亞 v2 權重仍保留在 `/home/team115_1/rag-npc-retrain-20261117/outputs/`；內容正式發布前，應比較這兩份已核准版本與 11 月 18 日新版，而不是只看時間或 training loss。

## 2. 在 GPU server 以 Docker 啟動

所有模型、Gateway 與評測操作都必須先 SSH 到校機，再進 Docker。禁止在 host 建立 `.venv-gpu`、直接啟動 vLLM／Uvicorn，或在本機 checkout 執行 GPU 評測。

```bash
ssh nccu-gpu
cd /home/team115_1/rag-npc-game
docker compose -f infra/npc_gateway/compose.yaml build runtime
docker compose -f infra/npc_gateway/compose.yaml up -d runtime
docker compose -f infra/npc_gateway/compose.yaml ps
docker compose -f infra/npc_gateway/compose.yaml logs --tail=100 runtime
```

Compose 會在同一個容器載入 Qwen2.5-7B AWQ 與八個 adapter，以 `NPC_VLLM_MAX_LORAS=2`、`NPC_VLLM_MAX_CPU_LORAS=8` 管理 GPU／CPU LoRA cache。Hugging Face cache 與 vLLM compile cache 都掛載為持久化 volume；重建容器不會刪除權重或 cache。

驗收時 `/health` 必須列出 base model 與八個 LoRA ID；少任何一條都不算 ready。兩個 host port 只能綁 loopback，不可改成公開位址。

## 3. 從本機存取時只建立 SSH tunnel

本機若要查看遊戲，只建立 loopback tunnel；模型與 Gateway 的開發、啟動及測試仍在遠端 Docker 內完成。

```bash
ssh -N -L 8800:127.0.0.1:8000 nccu-gpu
```

遊戲後端只需把 `MODEL_GATEWAY_URL` 指向完整 `/generate` URL。若 Gateway 設定 `NPC_GATEWAY_API_KEY`，呼叫端才需設定相同的 `MODEL_GATEWAY_API_KEY`。

## 4. 在 Docker 內測試

```bash
ssh nccu-gpu
cd /home/team115_1/rag-npc-game

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

模型評測與後端故事測試都使用容器內同一份 checkout。不要從 host 的 Python 或本機虛擬環境替代執行。

## 5. 資料與驗收

Runtime 的唯一合法輸出仍是：

```json
{
  "intent_summary": "簡短意圖摘要",
  "npc_dialogue": [{"text": "NPC 台詞", "emotion": null}],
  "event_proposals": []
}
```

人格樣本不直接教模型修改世界狀態，所以 `event_proposals` 應固定為空。目前固定故事的客觀事件由後端選項與規則決定；GPU Gateway 若收到模型夾帶的事件提案，會先移除提案並保留安全台詞，不能讓自由對話改動場景、道具或結局。

主要模型作者已統一使用 OpenAI ChatML `messages` 外層，但 assistant 目標仍混用純台詞、`relation_delta/line` 與 `ModelStoryOutput`，且部分資料包含多個 assistant 回合。現在的橋接工具會保留每筆場景、信任度、階段與參考資料，並轉換所有 assistant；預設以 `--output-dir` 產生獨立副本，不改作者原始 JSONL。完整來源與重訓邊界見 [訓練資料契約](../training/README.md)。

```bash
docker compose -f infra/npc_gateway/compose.yaml exec runtime sh -lc '
  normalized_dir="$(mktemp -d /tmp/rag-npc-normalized.XXXXXX)"
  python3 scripts/migrate_training_data_to_model_story_output.py \
    --output-dir "$normalized_dir"
  python3 scripts/validate_training_data.py \
    --data-dir "$normalized_dir"
'
```

本輪實際驗證 3,437 筆資料、3,474 個 assistant 目標全部符合 runtime Pydantic 契約。這只證明資料可安全銜接，未改變目前權重；人工抽查後若採用副本重訓，必須另存新權重與雜湊，再重跑原始模型探針。

真實權重啟動後，依 [B AI／RAG 交接清單](B_AI_RAG_HANDOFF.md#p3b-需要完成的驗收案例) 測人格、prompt injection、未解鎖秘密、跨 NPC 記憶、合法 JSON、timeout 與錯誤回復。程式測試能保證路由和結構，但角色品質與知識邊界仍必須用真實權重實測。

可重複執行的 31 題 smoke evaluation（八位角色，每位至少三種人格／安全／劇情導向案例）：

```bash
docker compose -f infra/npc_gateway/compose.yaml exec runtime \
  python3 scripts/evaluate_npc_gateway.py \
    --url http://127.0.0.1:8000/generate \
    --samples-per-case 3 \
    --require-dedicated-adapters \
    --require-observability
```

腳本會強制驗證 `ModelStoryOutput`、沒有 Markdown fence、沒有角色外占位文字、沒有未授權事件，並檢查繁體中文、身分／地點／核心動機、未知設定與合理調查方向。`guarded` suite 驗證整體安全邊界；`model-probe` suite 配合 `--require-model-source` 才量測原始 LoRA 內容。2026-11-22 守門後結果為 93／93（90 次前置守門、3 次模型）；原始 LoRA 開放式早期逐字基準為 47／72，人工校準維塔同義回答後最新為 53／72（另 2 次 503）。權重未變，兩種評分都仍須搭配人工閱讀，也不能與守門後成績互相替代。

2026-11-20 六模型整合結果：

- 六個 adapter 都能在同一 vLLM 列出並回傳合法結構；完整遊戲後端六位角色的回合與正式地圖路線都成功。
- 達索的訓練輸出曾出現直接羞辱或不回答自介；gateway 現在以公開角色卡替換這類輸出。
- prompt injection、假道具、具體 `missing_data` 與跨 NPC 私人記憶仍有 gateway fail-closed 防線，不把安全性只押在 LoRA 上。
- 新四位 NPC 的完整角色卡、授權知識與逐題內容評分仍未完成；安德烈與門梅司文托的抽測已證明 strict JSON 不等於事實邊界通過。
- vLLM 偶發回傳 200 但內容不可解析時，Gateway 最多嘗試三次；持續失敗才回暫時錯誤，不提交半個遊戲回合。

2026-11-17 通過較完整邊界驗收的兩份舊權重仍可作發布比較候選。現行八份權重已完成同一輪 Docker 真機路由與系統評測；若要把 Gateway 守門改回由模型本身負責，仍須先完成八份資料的契約遷移、角色設定審核、重訓與盲測。

## 已移除的舊單模型路徑

本次不再保留 `backend/config.py`、`backend/services/llm_client.py`、`backend/services/model_gateway.py` 與 `training/notebooks/alan_vance.py`。前三者會在遊戲後端直接載入單一 LoRA、依賴 CUDA／Unsloth，與現在「遊戲後端只呼叫一個 GPU Gateway URL」的架構衝突。`alan_walker.py` 仍只負責離線訓練／測試；艾倫的 runtime 路由由共用 Gateway 設定管理，且已納入八模型 Docker 真機驗收。所有 runtime 選模、strict JSON 與安全邊界由 `gpu_gateway/` 負責。
