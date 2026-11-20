# -*- coding: utf-8 -*-
"""alan_walker_7b_model_story_output_training
訓練艾倫（alan_walker）NPC LoRA；輸出必須符合後端 ModelStoryOutput。
結構與 menmesvento.py 相同，只替換資料／輸出路徑，並加入訓練前的資料檢查。
"""

import json
import os
from pathlib import Path

import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq
from unsloth import is_bfloat16_supported

max_seq_length = int(os.getenv("MAX_SEQ_LENGTH", "1024"))
dtype = None
load_in_4bit = True # 16GB VRAM（如免費 Colab T4）務必開啓；若為 24GB+ 顯卡可改為 False

ROOT_DIR = Path(__file__).resolve().parents[2]
dataset_filename = os.getenv(
    "TRAINING_DATA_FILE",
    str(ROOT_DIR / "training" / "data" / "alan_train.jsonl"),
)
checkpoint_dir = os.getenv(
    "TRAINING_CHECKPOINT_DIR",
    str(ROOT_DIR / "training" / "outputs" / "alan_walker_checkpoints"),
)
output_path = os.getenv(
    "LORA_OUTPUT_PATH",
    str(ROOT_DIR / "training" / "outputs" / "alan_walker_lora_model"),
)

# 現行 ModelStoryOutput 契約（見 scripts/migrate_training_data_to_model_story_output.py）
EXPECTED_TOP_KEYS = ["intent_summary", "npc_dialogue", "event_proposals"]


REQUIRE_JSON = os.getenv("REQUIRE_JSON", "0") == "1"  # 預設只警告；設為 1 時，格式不符就中止訓練


def check_dataset_format(path):
    """訓練前檢查：每行必須是合法 JSON，assistant 內容必須符合現行 ModelStoryOutput 契約。"""
    bad_lines, not_json, wrong_keys = [], [], []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                bad_lines.append((lineno, line.strip()[:30]))
                continue
            target = next((m for m in reversed(row["messages"]) if m["role"] == "assistant"), None)
            try:
                obj = json.loads(target["content"]) if target else None
            except json.JSONDecodeError:
                obj = None
            if not isinstance(obj, dict):
                not_json.append(lineno)
            elif set(obj) != set(EXPECTED_TOP_KEYS) or obj.get("event_proposals") != []:
                wrong_keys.append(lineno)
    if bad_lines:
        raise ValueError(
            f"{len(bad_lines)} 行不是合法 JSON：{bad_lines[:5]}。"
            "常見原因：複製時帶入 ```jsonl 標記行，或一筆資料被換行切成兩行。"
        )
    problems = []
    if not_json:
        problems.append(f"{len(not_json)} 筆 assistant 內容不是 JSON 物件（第 {not_json[:10]} 行…）")
    if wrong_keys:
        problems.append(f"{len(wrong_keys)} 筆欄位不符契約 {EXPECTED_TOP_KEYS}，或 event_proposals 不是空陣列（第 {wrong_keys[:10]} 行…）")
    if problems:
        msg = "；".join(problems) + "。這不是現行 ModelStoryOutput 契約格式；若串接端要求此格式，資料轉換後需要重訓。"
        if REQUIRE_JSON:
            raise ValueError(msg)
        print("⚠️ " + msg)


print("正在檢查訓練資料格式...")
check_dataset_format(dataset_filename)

print("正在載入基底模型與 Tokenizer...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-7B-Instruct-unsloth-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# 加入 LoRA 配適層
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 32,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth", # 極度省 VRAM
    random_state = 3407,
    max_seq_length = max_seq_length,
)

print("正在載入並處理結構化訓練資料集...")
# 讀取已由 scripts/validate_training_data.py 驗證的 ModelStoryOutput 資料集
raw_dataset = load_dataset('json', data_files=dataset_filename, split='train')

truncated_count = 0

def process_messages_with_mask(sample):
    global truncated_count
    messages = sample["messages"]

    # 拆分 Prompt (System + User) 與 Target (Assistant 的 JSON 輸出)
    prompt_msgs = [m for m in messages if m["role"] != "assistant"]
    assistant_msg = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
    if assistant_msg is None:
        raise ValueError("training row has no assistant target")

    prompt_text = tokenizer.apply_chat_template(
        prompt_msgs,
        tokenize=False,
        add_generation_prompt=True
    )
    full_text = prompt_text + assistant_msg["content"] + "<|im_end|>\n"

    prompt_tokens = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
    full_tokens = tokenizer(full_text, add_special_tokens=False)["input_ids"]

    # Prompt 不計 Loss，只訓練模型輸出 ModelStoryOutput JSON。
    labels = [-100] * len(prompt_tokens) + full_tokens[len(prompt_tokens):]

    # 超過 max_seq_length 會被截掉，JSON 結尾缺失的樣本會教壞模型
    if len(full_tokens) > max_seq_length:
        truncated_count += 1

    return {
        "input_ids": full_tokens[:max_seq_length],
        "attention_mask": [1] * len(full_tokens[:max_seq_length]),
        "labels": labels[:max_seq_length]
    }

tokenized_dataset = raw_dataset.map(process_messages_with_mask, remove_columns=raw_dataset.column_names)

print(f"資料處理完成！訓練集總筆數：{len(tokenized_dataset)}")
if truncated_count:
    print(f"⚠️ 有 {truncated_count} 筆超過 MAX_SEQ_LENGTH={max_seq_length} 被截斷，"
          "請調高 MAX_SEQ_LENGTH（例如 2048）或縮短 system prompt。")

# 開始訓練參數設定
training_args = TrainingArguments(
    per_device_train_batch_size = 1,          # 7B 較大，batch size 設 1
    gradient_accumulation_steps = 8,          # 累積梯度相當於 batch size 8
    warmup_steps = 5,
    num_train_epochs = 4,                     # 跑 4 個 epoch 確保模型學會 JSON 語法
    learning_rate = 2e-4,
    fp16 = not is_bfloat16_supported(),
    bf16 = is_bfloat16_supported(),
    logging_steps = 2,
    output_dir = checkpoint_dir,
    report_to = "none"
)

trainer = SFTTrainer(
    model = model,
    processing_class = tokenizer,
    args = training_args,
    train_dataset = tokenized_dataset,
    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True),
)

print("\n🚀 開始執行 7B ModelStoryOutput 微調訓練...")
trainer_stats = trainer.train()
print("訓練完成！")

# 儲存最終 LoRA 權重
model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)
print(f"新模型權重已成功儲存至 {output_path}")
