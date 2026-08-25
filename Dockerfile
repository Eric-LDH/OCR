# 基于 python slim 镜像（减小体积）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装系统依赖（onnxruntime + opencv/rapidocr 需要部分系统库）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        libglib2.0-0 \
        libxcb1 \
        libxcb-render0 \
        libxcb-shm0 \
        libxcb-shape0 \
        libxcb-randr0 \
        libxcb-xfixes0 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-render-util0 \
        libxcb-xkb1 \
        libxcb-util1 \
        libgl1 \
        libgl1-mesa-dri \
        libglx0 \
        libxrender1 \
        libxext6 \
        libxfixes3 \
        libsm6 \
        libice6 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libfontconfig1 \
        libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
