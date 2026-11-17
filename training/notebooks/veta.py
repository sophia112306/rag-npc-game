# -*- coding: utf-8 -*-
"""veta_7b_training
支援 7B 模型與多輪純台詞輸出的微調訓練（角色：維塔）
"""

import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from unsloth.chat_templates import train_on_responses_only
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

max_seq_length = 2048  # 保留足夠的 Context 長度以容納結構化設定與多輪對話[cite: 14]
dtype = None
load_in_4bit = True    # 16GB VRAM 務必開啟；若為 24GB+ 顯卡可改為 False[cite: 14]

print("正在載入基底模型與 Tokenizer...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-7B-Instruct",  # 沿用原本的 7B 基底模型[cite: 14]
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# 加入 LoRA 配適層[cite: 14]
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 32,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",  # 節省 VRAM[cite: 14]
    random_state = 3407,
    max_seq_length = max_seq_length,
)

print("正在載入並處理維塔訓練資料集...")
# 讀取維塔訓練資料集（請確認實際檔案路徑與檔名是否一致）
dataset_filename = "training/data/npc_train_veta.jsonl"
raw_dataset = load_dataset("json", data_files=dataset_filename, split="train")

# 套用 Qwen 的 ChatML 對話模板（完整支援單輪與多輪對話）[cite: 13]
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
print(f"資料處理完成！訓練集總筆數：{len(dataset)}")

# 訓練參數設定[cite: 14]
training_args = TrainingArguments(
    per_device_train_batch_size = 1,          # 7B 較大，batch size 設 1[cite: 14]
    gradient_accumulation_steps = 8,          # 累積梯度相當於 batch size 8[cite: 14]
    warmup_steps = 5,
    num_train_epochs = 2,                     # 純台詞與 RAG 遵循設 2~3 個 epoch 即可，避免死背台詞[cite: 12]
    learning_rate = 2e-4,
    fp16 = not is_bfloat16_supported(),
    bf16 = is_bfloat16_supported(),
    logging_steps = 2,
    output_dir = "training/outputs/veta_checkpoints",  # 獨立存放維塔的 checkpoints，避免覆蓋舊檔[cite: 14]
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

# 關鍵：只計算 assistant（維塔台詞）的 Loss，不計算 system 與 user 的 Loss（支援多輪）[cite: 12, 13, 14]
trainer = train_on_responses_only(
    trainer,
    instruction_part = "<|im_start|>user\n",
    response_part = "<|im_start|>assistant\n",
)

print("\n🚀 開始執行維塔 7B 模型微調訓練...")
trainer_stats = trainer.train()
print("訓練完成！")

# 儲存最終 LoRA 權重[cite: 14]
output_path = "training/outputs/veta_lora_model"
model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)
print(f"新模型權重已成功儲存至 {output_path}")