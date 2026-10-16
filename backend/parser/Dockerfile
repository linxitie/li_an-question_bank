# syntax=docker/dockerfile:1
#
# parser sidecar 镜像 —— 扫描件 PDF → Markdown
#
# 为什么要独立成服务：
#   主后端跑在 Python 3.13，而 MinerU 的 Windows 支持上限是 3.12，
#   PaddleOCR 要求 ≤3.12 —— 两者都无法在主进程内安装。
#   拆成独立服务后，主后端依赖面保持干净，解析栈可单独升级。
#
# 构建：
#   docker build -t liankao/parser:test backend/parser
#
# 运行：
#   docker run --rm -p 8080:8080 liankao/parser:test
#   curl -f http://localhost:8080/health

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

# ffmpeg/libgl/libglib : MinerU 与 PaddleOCR 的图像预处理运行时依赖
# curl                 : HEALTHCHECK 探针（slim 默认无 curl）
# tini                 : PID 1 信号转发，保证 uvicorn 能优雅退出
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./app.py

# 模型缓存挂载点。MinerU 默认把模型拉到 ~/.cache，
# 挂成卷可避免每次重建镜像都重新下载数 GB 权重。
ENV MINERU_MODEL_SOURCE=modelscope
RUN mkdir -p /root/.cache
VOLUME ["/root/.cache"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "app:app", \
     "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]