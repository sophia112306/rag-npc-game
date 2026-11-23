# NPC LoRA 訓練資料契約

## 來源與目前狀態

八份角色資料主要由 `wyz279 / WU, YUN CHEN` 在 `b4118c8`、`fb0ed8a`、`f6827fe`、`3fadb75`、`4a48221`、`aaf13a8`、`9eabf31`、`0cb355e`、`7352f87` 提交。作者已統一使用 OpenAI ChatML 外層：

```json
{
  "messages": [
    {"role": "system", "content": "角色與本筆情境"},
    {"role": "user", "content": "玩家台詞"},
    {"role": "assistant", "content": "模型目標"}
  ]
}
```

目前 assistant 目標仍有三種歷史格式：純台詞、`relation_delta/line` JSON，以及正式 `ModelStoryOutput`。部分資料是一筆多輪對話，因此不能只轉換最後一個 assistant。

主線 runtime 的唯一輸出契約是：

```json
{
  "intent_summary": "簡短意圖摘要",
  "npc_dialogue": [{"text": "NPC 台詞", "emotion": null}],
  "event_proposals": []
}
```

人格資料的 `event_proposals` 固定為空；場景、道具、選項與結局仍由後端規則決定。

## 非破壞性標準化

所有操作必須先 SSH 到校機，再於 `infra/npc_gateway/compose.yaml` 的 Docker runtime 內執行。先輸出獨立副本，不要直接覆寫作者原始 JSONL：

```bash
docker compose -f infra/npc_gateway/compose.yaml exec runtime sh -lc '
  normalized_dir="$(mktemp -d /tmp/rag-npc-normalized.XXXXXX)"
  python3 scripts/migrate_training_data_to_model_story_output.py \
    --output-dir "$normalized_dir"
  python3 scripts/validate_training_data.py \
    --data-dir "$normalized_dir"
  echo "$normalized_dir"
'
```

遷移器會：

- 保留作者每筆資料的場景、信任度、階段、已發生事件與參考資料。
- 轉換每一個 assistant 回合，而不只最後一個。
- 將純台詞與 `line` 包成 `ModelStoryOutput`。
- 清除人格樣本中的事件提案，避免模型學會直接改寫遊戲狀態。
- 保留原始 `training/data/*.jsonl` 不變。

2026-11-22 實際匯出結果為 3,437 筆資料、3,474 個 assistant 目標，八個檔案全部通過 runtime Pydantic 契約。

## 重訓邊界

標準化資料不會自動改變現有 LoRA 權重。只有在人工抽查情境沒有被錯誤改寫後，才把 `TRAINING_DATA_FILE` 指向標準化副本並於 Docker 訓練環境重訓。重訓完成後仍須保留舊權重、記錄新權重雜湊，並分開比較原始模型探針與 Gateway 守門後成績。

GitHub 的 `train` 分支是另一套無共同祖先的 RAG 實驗，不是這八份 NPC LoRA 資料的統一格式來源，不應直接合併到 `main`。
