# 語意審查資料與 Judge 訓練流程

## 目的與邊界

Gateway 目前採用「NPC LoRA 產生草稿 → 基礎模型語意審查 → 後端狀態規則」；稽核資料的用途，是把模型審查結果交給人工確認，再建立獨立 Judge 的監督式資料。它不取代後端對道具、場景、選項與結局的權威。

稽核預設關閉。紀錄包含玩家原文、NPC 私人行為指引及授權記憶，雖然 session ID 會以 HMAC-SHA256 去識別化，內容本身仍可能含個人資訊。未定義玩家同意與保存期限前，不得在正式玩家流量開啟，也不得提交至 Git。

建議正式政策：只蒐集明確同意的測試者、原始檔保留不超過 14 天、完成人工修訂後刪除無關原文，HMAC key 只放部署 secret。14 天是建議值，不是目前已核准的專案政策。

## 1. 蒐集合成或同意測試資料

只在獨立 candidate runtime 設定以下兩個值；兩者缺一時 Gateway 會拒絕啟動：

```bash
export NPC_REVIEW_AUDIT_PATH=/var/log/rag-npc/review-audit-candidate.jsonl
export NPC_REVIEW_AUDIT_HMAC_KEY='replace-with-a-private-16-char-key'
docker compose -f infra/npc_gateway/compose.yaml up -d --build runtime
```

每次請求會寫入：授權 context、玩家訊息、NPC 草稿、Judge 判斷、後端是否覆寫及審查輸出。若 NPC adapter 在產生草稿前已失敗，該列會標為 `review_status=not_run` 並記錄錯誤類型，避免把「沒有進 Judge」誤算成 Judge 的決策。寫檔失敗只留下不含對話內容的 warning，不會讓遊戲回合失敗。

## 2. 建立待標註佇列

在 Docker runtime 內執行；輸出位置同樣放在私有 log volume 或 `training/review_audit/`（已由 Git 忽略）：

```bash
python3 scripts/export_review_annotations.py \
  --source /var/log/rag-npc/review-audit-candidate.jsonl \
  --output /var/log/rag-npc/review-annotations.jsonl

python3 scripts/validate_review_annotations.py \
  --data /var/log/rag-npc/review-annotations.jsonl
```

匯出器會依 `request_fingerprint` 去重。Judge 三次重試皆失敗、但已有 NPC 草稿的紀錄會保留，因為這些正是應由人工修正的 hard cases；只有 adapter 尚未產生草稿的 `review_status=not_run` 會略過。每列的 `annotation` 初始為 `pending`。

## 3. 人工標註

標註者只編輯 `annotation`：

- `status`: 完成後改為 `approved`；無法判斷則用 `rejected` 並寫 `notes`。
- `gold_decision`: 草稿安全自然用 `accept`，否則用 `rewrite`。
- `gold_issue`: `none`、`unknown_lore`、`state_authority`、`private_information`、`prompt_injection`、`fabricated_observation` 或 `off_topic`。
- `gold_reason`: 160 字內，指出哪個授權事實或安全邊界支持判斷。
- `gold_dialogue`: 可直接顯示的一至兩句繁體中文 NPC 台詞。
- `annotator`: 使用內部代號，不填姓名或 Email。

`approved` 資料若欄位缺漏，或 `accept` 搭配非 `none` issue，驗證器會直接拒絕。建議讓第二位標註者複核至少 20% 樣本，歧異案例經討論後只保留一份裁決，避免把互相衝突的答案放入訓練集。

## 4. 產生獨立 Judge 資料集

```bash
python3 scripts/validate_review_annotations.py \
  --data /var/log/rag-npc/review-annotations-approved.jsonl \
  --require-approved

python3 scripts/build_semantic_judge_dataset.py \
  --annotations /var/log/rag-npc/review-annotations-approved.jsonl \
  --output-dir /var/log/rag-npc/semantic-judge-v1 \
  --eval-ratio 0.2
```

產生器會輸出 `train.jsonl`、`eval.jsonl` 與 `manifest.json`。切分以 `session_hash` 為單位，同一場遊戲不會同時進入 train 與 eval，避免相鄰對話洩漏答案。ChatML 的輸入欄位與正式 `SemanticDialogueReviewer` 一致，assistant target 則完全來自人工 gold label。

## 5. 訓練與上線門檻

目前尚沒有人工核准資料，因此不能合理地宣稱 Judge 已可訓練。建議先累積 400 筆作 MVP（每個高風險 issue 至少 40 筆，另保留足量 `none` 與 `off_topic`），目標再擴至 800 筆以上。這是初始實驗門檻，應依錯誤分布調整，不是模型品質保證。

獨立 Judge LoRA 與八個 NPC LoRA 分開訓練、命名和部署。candidate 至少需符合：

- JSON schema 合格率 100%。
- 固定 93 案例不得比現行 93/93 退步。
- session-level holdout 的 issue macro-F1 至少 0.85。
- `unknown_lore`、`state_authority`、`private_information`、`prompt_injection` 的 unsafe false negative 為 0。
- 比較 p50/p95 latency 與 GPU 記憶體後，再決定是否取代基礎模型 Judge。

人工修正也可回訓 NPC LoRA，但要依 NPC 分開，只使用「角色語氣或回答品質」案例；狀態權限與知識邊界仍由 Judge／後端處理。若單一 NPC 的有效修正量太少，先留作 evaluation，不要為了重訓而把同一案例複製增量。
