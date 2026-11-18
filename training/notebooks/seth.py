# -*- coding: utf-8 -*-
"""seth_7b_model_story_output_training
訓練塞特（Seth）NPC LoRA；直接輸出動態 ModelStoryOutput JSON（不含 relation）。
"""

import os
from pathlib import Path

import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from unsloth.chat_templates import train_on_responses_only
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq

# 1. 提高預設長度至 2048，避免 System Prompt + 參考資料 + JSON 輸出被截斷
max_seq_length = int(os.getenv("MAX_SEQ_LENGTH", "2048"))
dtype = None
load_in_4bit = True

# 2. 自動偵測專案根目錄（無論放在 scripts/ 或 training/scripts/ 都能正確找到 training/）
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = next((p for p in CURRENT_FILE.parents if (p / "training").is_dir()), CURRENT_FILE.parents[1])

dataset_filename = os.getenv(
    "TRAINING_DATA_FILE",
    str(ROOT_DIR / "training" / "data" / "npc_train_seth.jsonl"),
)
checkpoint_dir = os.getenv(
    "TRAINING_CHECKPOINT_DIR",
    str(ROOT_DIR / "training" / "outputs" / "seth_checkpoints"),
)
output_path = os.getenv(
    "LORA_OUTPUT_PATH",
    str(ROOT_DIR / "training" / "outputs" / "seth_lora_model"),
)

print(f"專案根目錄：{ROOT_DIR}")
print(f"訓練資料集：{dataset_filename}")
print("正在載入基底模型與 Tokenizer...")

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct-unsloth-bnb-4bit",
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    max_seq_length=max_seq_length,
)

print("正在載入並處理塞特結構化訓練資料集...")
raw_dataset = load_dataset("json", data_files=dataset_filename, split="train")


def formatting_prompts_func(examples):
    texts = [
        tokenizer.apply_chat_template(
            convo,
            tokenize=False,
            add_generation_prompt=False
        )
        for convo in examples["messages"]
    ]
    return {"text": texts}


tokenized_dataset = raw_dataset.map(formatting_prompts_func, batched=True)
print(f"資料處理完成！訓練集總筆數：{len(tokenized_dataset)}")

training_args = TrainingArguments(
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    warmup_steps=5,
    num_train_epochs=4,
    learning_rate=2e-4,
    fp16=not is_bfloat16_supported(),
    bf16=is_bfloat16_supported(),
    logging_steps=2,
    output_dir=checkpoint_dir,
    report_to="none"
)

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    args=training_args,
    train_dataset=tokenized_dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    packing=False,
    data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True),
)

# 3. 支援單輪與多輪對話的精準 Loss Masking（只對 assistant 的 JSON 輸出計算 Loss）
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)

print("\n🚀 開始執行塞特 7B ModelStoryOutput 微調訓練...")
trainer_stats = trainer.train()
print("訓練完成！")

model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)
print(f"新模型權重已成功儲存至 {output_path}")