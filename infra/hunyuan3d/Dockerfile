FROM nvidia/cuda:12.8.1-devel-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG HUNYUAN3D_REPOSITORY=https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git
ARG HUNYUAN3D_COMMIT=f8db63096c8282cb27354314d896feba5ba6ff8a

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    HF_HOME=/models/huggingface \
    HUNYUAN3D_UPSTREAM_COMMIT=${HUNYUAN3D_COMMIT}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
        libegl1 \
        libgl1 \
        libglib2.0-0 \
        python3 \
        python3-dev \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade "pip<26" setuptools wheel \
    && python3 -m pip install \
        torch==2.7.1 \
        torchvision==0.22.1 \
        --index-url https://download.pytorch.org/whl/cu128

WORKDIR /opt
RUN git clone --filter=blob:none "${HUNYUAN3D_REPOSITORY}" Hunyuan3D-2 \
    && cd Hunyuan3D-2 \
    && git checkout --detach "${HUNYUAN3D_COMMIT}"

COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN python3 -m pip install -r /tmp/requirements-runtime.txt \
    && python3 -m pip install --no-deps -e /opt/Hunyuan3D-2

WORKDIR /srv/hunyuan3d
COPY server.py ./server.py

RUN mkdir -p /models/huggingface /outputs \
    && python3 -c "import torch; assert torch.version.cuda == '12.8'; print(torch.__version__, torch.version.cuda)"

EXPOSE 8081
CMD ["python3", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8081", "--no-access-log"]
