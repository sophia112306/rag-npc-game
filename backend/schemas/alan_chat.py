"""Public, read-only retinal communication contracts."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .alan_hud import AlanTone


class AlanChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=500)
    expected_state_version: int = Field(..., ge=1)

    @field_validator("question")
    @classmethod
    def non_blank_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("請輸入問題。")
        return value


class AlanModelRequest(BaseModel):
    """Only player-visible context is sent to the GPU; no GameState snapshot."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=500)
    scene_name: str = Field(..., min_length=1, max_length=100)
    objective: str = Field(..., min_length=1, max_length=500)
    available_actions: list[str] = Field(default_factory=list, max_length=8)
    tone: AlanTone
    identity_revealed: bool = False


class AlanModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(..., min_length=1, max_length=500)
