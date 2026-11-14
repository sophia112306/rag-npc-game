import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    BASE_MODEL_NAME: str = os.getenv("BASE_MODEL_NAME", "unsloth/Qwen2.5-7B-Instruct")
    LORA_MODEL_PATH: str = os.getenv(
        "LORA_MODEL_PATH",
        str(BASE_DIR / "training" / "outputs" / "menmesvento_lora_model")
    )
    MAX_SEQ_LENGTH: int = 2048
    LOAD_IN_4BIT: bool = True
    INPUT_PARSER_PROMPT_PATH: str = str(BASE_DIR / "backend" / "prompts" / "input_parser.txt")

settings = Settings()
