import json
import re
import torch
from typing import Dict, Any, List
from unsloth import FastLanguageModel
from backend.config import settings


class LocalLoRALLMClient:
    """本地 7B + LoRA 模型推論客戶端 (單例模式)"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        print(f"正在載入本地敘事模型：{settings.LORA_MODEL_PATH} ...")
        self.model, self.tokenizer = FastLanguageModel.from_pretrained(
            model_name=settings.LORA_MODEL_PATH,
            max_seq_length=settings.MAX_SEQ_LENGTH,
            dtype=None,
            load_in_4bit=settings.LOAD_IN_4BIT,
        )
        FastLanguageModel.for_inference(self.model)
        self._initialized = True
        print("本地 7B 敘事模型載入完成，已進入推理模式！")

    def generate_json(self, messages: List[Dict[str, str]], max_new_tokens: int = 512) -> Dict[str, Any]:
        prompt_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = self.tokenizer(prompt_text, return_tensors="pt").to("cuda")
        input_len = inputs.input_ids.shape[1]

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.4,
                top_p=0.9,
                repetition_penalty=1.05,
                use_cache=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        raw_output = self.tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True).strip()
        return self._parse_safe_json(raw_output)

    def _parse_safe_json(self, raw_text: str) -> Dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.IGNORECASE)
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            cleaned = match.group(0)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"[警告] 模型輸出 JSON 解析失敗：{e}\n原始輸出：{raw_text}")
            data = {}

        # 自動補全與標準化結構，確保 100% 符合 input_parser.txt Schema
        delta = data.get("delta") if isinstance(data.get("delta"), dict) else {}
        rel = delta.get("relation") if isinstance(delta.get("relation"), dict) else {}

        normalized = {
            "scene": data.get("scene") or (raw_text if raw_text else "風暴之眼深殿內一片死寂，黃沙緩緩滑落。"),
            "speaker": data.get("speaker") or "menmesvento",
            "delta": {
                "axis": int(delta.get("axis", 0)),
                "usurp": int(delta.get("usurp", 0)),
                "relation": {
                    "andre": int(rel.get("andre", 0)),
                    "vidalia": int(rel.get("vidalia", 0)),
                    "menmesvento": int(rel.get("menmesvento", 0)),
                },
            },
            "event_done": data.get("event_done", None),
            "flags_set": data.get("flags_set") if isinstance(data.get("flags_set"), list) else [],
            "reason": data.get("reason") or "模型結構自動標準化完成。",
        }
        return normalized
