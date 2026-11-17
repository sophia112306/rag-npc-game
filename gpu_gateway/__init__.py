"""GPU-side NPC adapter gateway.

This package intentionally has no CUDA imports.  vLLM owns the GPU process;
the gateway only validates the game contract and selects one model/LoRA ID.
"""

from .app import create_app

__all__ = ["create_app"]
