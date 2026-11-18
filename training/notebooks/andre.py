import json
import torch
from datasets import Dataset
from sklearn.model_selection import train_test_split
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template, train_on_responses_only
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq

# ==========================================
# 1. 參數設定
# ==========================================
MODEL_NAME = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit" # 4-bit 量化，16GB VRAM 可輕鬆訓練
DATA_PATH = "training/data/npc_train_andre.jsonl"
OUTPUT_DIR = "training/outputs/andre_lora_model"
MAX_SEQ_LENGTH = 2048

# ==========================================
# 2. 載入資料並進行「好感度分層抽樣」
# ==========================================
raw_data = []
delta_categories = []

with open(DATA_PATH, "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        item = json.loads(line)
        raw_data.append(item)
        
        # 取得最後一輪 assistant 的 relation_delta 作為分層依據
        last_assistant_msg = [m for m in item["messages"] if m["role"] == "assistant"][-1]["content"]
        delta = json.loads(last_assistant_msg)["relation_delta"]
        
        # 分成三類：負向(-)、零(0)、正向(+)，確保驗證集與訓練集都有好感變化樣本
        if delta < 0:
            delta_categories.append("neg")
        elif delta > 0:
            delta_categories.append("pos")
        else:
            delta_categories.append("zero")

train_list, eval_list = train_test_split(
    raw_data, 
    test_size=0.1, 
    random_state=42, 
    stratify=delta_categories
)

print(f"總筆數: {len(raw_data)} | 訓練集: {len(train_list)} | 驗證集: {len(eval_list)}")

# ==========================================
# 3. 載入模型與 LoRA 設定
# ==========================================
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    lora_dropout=0.05, # 資料集約百餘筆，加入微量 dropout 防止死背
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

def formatting_prompts_func(examples):
    convos = examples["messages"]
    texts = [
        tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False)
        for convo in convos
    ]
    return {"text": texts}

train_dataset = Dataset.from_list(train_list).map(formatting_prompts_func, batched=True)
eval_dataset = Dataset.from_list(eval_list).map(formatting_prompts_func, batched=True)

# ==========================================
# 4. 訓練器設定 (只計算 Assistant 回覆的 Loss)
# ==========================================
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer),
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4, # 等效 batch_size = 8
        warmup_steps=10,
        num_train_epochs=4,            # 資料量適中，4 個 epoch 足以學會 JSON 結構與語氣
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=15,
        save_strategy="steps",
        save_steps=15,
        load_best_model_at_end=True,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        output_dir="outputs",
    ),
)

# 關鍵：只針對 assistant 輸出的 JSON 計算 Loss，避免被 system prompt 稀釋
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)

trainer.train()

# 儲存 LoRA 權重
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"訓練完成！模型已儲存至 {OUTPUT_DIR}")