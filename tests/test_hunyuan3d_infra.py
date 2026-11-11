from pathlib import Path


ROOT = Path(__file__).parents[1]
INFRA = ROOT / "infra" / "hunyuan3d"


def test_gpu_image_is_pinned_for_blackwell_cuda() -> None:
    dockerfile = (INFRA / "Dockerfile").read_text()

    assert "nvidia/cuda:12.8.1-devel-ubuntu22.04" in dockerfile
    assert "torch==2.7.1" in dockerfile
    assert "torchvision==0.22.1" in dockerfile
    assert "HUNYUAN3D_COMMIT=f8db63096c8282cb27354314d896feba5ba6ff8a" in dockerfile
    assert "--index-url https://download.pytorch.org/whl/cu128" in dockerfile


def test_compose_only_publishes_gateway_on_remote_loopback() -> None:
    compose = (INFRA / "compose.yaml").read_text()

    assert '"127.0.0.1:${HUNYUAN3D_PORT:-8081}:8081"' in compose
    assert '"nvidia.com/gpu=all"' in compose
    assert "privileged:" not in compose
    assert "network_mode: host" not in compose


def test_gateway_is_shape_only_and_has_bounded_generation() -> None:
    server = (INFRA / "server.py").read_text()

    assert "Hunyuan3DPaintPipeline" not in server
    assert "enable_flashvdm(" not in server
    assert "GENERATION_LOCK = asyncio.Lock()" in server
    assert '@app.get("/health")' in server
    assert '@app.post("/generate"' in server
    assert "CORSMiddleware" not in server
