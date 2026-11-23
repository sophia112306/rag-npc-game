FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-gpu.txt /tmp/rag-npc-requirements/

RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install \
        -r /tmp/rag-npc-requirements/requirements-gpu.txt \
    && python3 -c "import fastapi, httpx, pydantic, uvicorn, vllm"

COPY requirements-dev.txt /tmp/rag-npc-requirements/

RUN python3 -m pip install -r /tmp/rag-npc-requirements/requirements-dev.txt

WORKDIR /workspace/rag-npc-game

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "scripts/start_npc_docker_runtime.sh"]
