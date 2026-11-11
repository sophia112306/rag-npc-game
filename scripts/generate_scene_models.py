"""Generate versioned, reviewable offline defaults using the private GPU API.

Run: PYTHONPATH=. ./.venv/bin/python scripts/generate_scene_models.py
The game's live asset worker uses the same adapter and GLB validation.
"""

import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import httpx

from backend.generation.scene_assets import (
    ASSET_KINDS,
    HunyuanAssetGateway,
    validate_glb,
)


async def main():
    url = os.getenv("HUNYUAN3D_URL", "http://127.0.0.1:8081")
    gateway = HunyuanAssetGateway(url)
    async with httpx.AsyncClient(trust_env=False) as client:
        for _ in range(90):
            health = (await client.get(f"{url}/health")).json()
            if health["status"] == "ready":
                break
            if health["status"] == "error":
                raise RuntimeError(health["error"])
            await asyncio.sleep(2)
        else:
            raise TimeoutError("GPU did not become ready")
    root = Path("frontend/public/game/models")
    results = []
    for kind in ASSET_KINDS:
        started = time.monotonic()
        raw = await gateway.generate(kind, 1234)
        validate_glb(raw)
        path = root / f"{kind}-v1.glb"
        path.write_bytes(raw)
        record = {
            "kind": kind,
            "file": path.name,
            "seed": 1234,
            "bytes": len(raw),
            "sha256": sha256(raw).hexdigest(),
            "seconds": round(time.monotonic() - started, 2),
            "reference": f"references/{kind}-v1.png",
            "provider": "Hunyuan3D-2mini-turbo",
            "material": "reference-projected texture and smooth normals",
            "status": "provisional",
        }
        results.append(record)
        print(json.dumps(record), flush=True)
    (root / "manifest.json").write_text(
        json.dumps({"version": 1, "assets": results}, indent=2) + "\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
