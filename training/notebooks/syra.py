# -*- coding: utf-8 -*-
"""syra_7b_training
支援 7B 模型與多輪動態 JSON 輸出的微調訓練（角色：希拉 Syra）
"""

import os
from pathlib import Path

import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from unsloth.chat_templates import train_on_responses_only
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

max_seq_length = int(os.getenv("MAX_SEQ_LENGTH", "2048"))  # 保留足夠的 Context 長度以容納參考資料與多輪對話
dtype = None
load_in_4bit = True    # 16GB VRAM 務必開啟；若為 24GB+ 顯卡可改為 False

print("正在載入基底模型與 Tokenizer...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-7B-Instruct",
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
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
    max_seq_length = max_seq_length,
)

print("正在載入並處理希拉動態 JSON 訓練資料集...")
ROOT_DIR = Path(__file__).resolve().parents[2]
dataset_filename = os.getenv(
    "TRAINING_DATA_FILE",
    str(ROOT_DIR / "training" / "data" / "npc_train_syra.jsonl"),
)
checkpoint_dir = os.getenv(
    "TRAINING_CHECKPOINT_DIR",
    str(ROOT_DIR / "training" / "outputs" / "syra_checkpoints"),
)
output_path = os.getenv(
    "LORA_OUTPUT_PATH",
    str(ROOT_DIR / "training" / "outputs" / "syra_lora_model"),
)
print(f"訓練資料：{dataset_filename}")
print(f"輸出位置：{output_path}")
raw_dataset = load_dataset("json", data_files=dataset_filename, split="train")

# 套用 Qwen 的 ChatML 對話模板（完整支援單輪與多輪對話）
def formatting_prompts_func(examples):
    convos = examples["messages"]
    texts = [
        tokenizer.apply_chat_template(
            convo,
            tokenize=False,
            add_generation_prompt=False
        )
        for convo in convos
    ]
    return {"text": texts}

dataset = raw_dataset.map(formatting_prompts_func, batched=True)
print(f"資料處理完成！希拉訓練集總筆數：{len(dataset)}")

# 訓練參數設定
training_args = TrainingArguments(
    per_device_train_batch_size = 1,          # 7B 較大，batch size 設 1
    gradient_accumulation_steps = 8,          # 累積梯度相當於 batch size 8
    warmup_steps = 5,
    num_train_epochs = 4,                     # 改為 4 個 epoch，確保模型穩定輸出 JSON 格式與數值
    learning_rate = 2e-4,
    fp16 = not is_bfloat16_supported(),
    bf16 = is_bfloat16_supported(),
    logging_steps = 2,
    output_dir = checkpoint_dir,  # 獨立存放希拉的 checkpoints
    report_to = "none"
)

trainer = SFTTrainer(
    model = model,
    processing_class = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    packing = False,
    args = training_args,
)

# 關鍵：只計算 assistant（希拉 JSON 輸出）的 Loss，不計算 system 與 user 的 Loss（支援多輪）
trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|im_start|>user\n",
    response_part = "<|im_start|>assistant\n",
)

print("\n🚀 開始執行希拉（Syra）7B 動態 JSON 模型微調訓練...")
trainer_stats = trainer.train()
print("訓練完成！")

# 儲存最終 LoRA 權重
model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)
print(f"希拉新模型權重已成功儲存至 {output_path}")