# NPC RAG starter corpus

`corpus/npc_knowledge.jsonl` 是經來源審核的最小可公開知識集。每行是一個可獨立索引的片段，後端目前會先依 `npc_ids`、`visibility`、`available_from_turn` 與角色設定版本過濾，再放入該 NPC 的 `target_context.knowledge`。

這份 corpus 是後續 embedding／Qdrant 匯入的單一資料來源，不代表向量服務已完成。新增資料時必須：

- 一筆只包含一個可追溯主題，保留 `source_id` 與 `source_locator`。
- 不把訓練樣本中的敘事自動升格為 canon。
- 未確認內容要明寫成未知邊界，不能補成肯定事實。
- `npc_ids` 只能列出確實獲授權的角色；秘密不得標成 `public`。
- 提升 `canon_version` 時同步更新角色 `setting_version` 與測試。

目前只發布維達利亞與門梅司文托的公開核心片段。兩人的作者層秘密與揭露條件仍保留在角色卡的未知邊界，不進入開場 RAG。
