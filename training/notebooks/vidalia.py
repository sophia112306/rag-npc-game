# -*- coding: utf-8 -*-
"""vidalia_7b_model_story_output_training
訓練維達利亞 NPC LoRA；輸出必須符合後端 ModelStoryOutput。
"""

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
    str(ROOT_DIR / "training" / "data" / "vidalia_data.jsonl"),
)
checkpoint_dir = os.getenv(
    "TRAINING_CHECKPOINT_DIR",
    str(ROOT_DIR / "training" / "outputs" / "vidalia_checkpoints"),
)
output_path = os.getenv(
    "LORA_OUTPUT_PATH",
    str(ROOT_DIR / "training" / "outputs" / "vidalia_lora_model"),
)

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

def process_messages_with_mask(sample):
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
    
    return {
        "input_ids": full_tokens[:max_seq_length],
        "attention_mask": [1] * len(full_tokens[:max_seq_length]),
        "labels": labels[:max_seq_length]
    }

tokenized_dataset = raw_dataset.map(process_messages_with_mask, remove_columns=raw_dataset.column_names)

print(f"資料處理完成！訓練集總筆數：{len(tokenized_dataset)}")

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
