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

# 国内构建机（本项目部署环境）访问 deb.debian.org / pypi.org 极慢，
# 默认切到清华镜像；海外构建可显式覆盖：
#   --build-arg APT_MIRROR=deb.debian.org --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    TZ=Asia/Shanghai

# ffmpeg/libgl/libglib : MinerU 与 PaddleOCR 的图像预处理运行时依赖
# curl                 : HEALTHCHECK 探针（slim 默认无 curl）
# tini                 : PID 1 信号转发，保证 uvicorn 能优雅退出
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=10 -o Acquire::http::Timeout=45 -o Acquire::ForceIPv4=true update \
    && apt-get install -y --no-install-recommends \
        -o Acquire::Retries=10 -o Acquire::http::Timeout=45 -o Acquire::ForceIPv4=true \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

# MinerU 依赖 torch，但 Linux 上默认轮子会拖入 cuda-toolkit/cudnn 等约 2GB GPU 库；
# 本项目 parser 只跑 CPU pipeline，先装 CPU 版 torch/torchvision，后续 pip 会判定已满足。
# 阿里云镜像实测约 1MB/s；海外可覆盖 TORCH_CPU_WHEEL_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_CPU_WHEEL_URL=https://mirrors.aliyun.com/pytorch-wheels/cpu
RUN pip install --no-cache-dir \
        "${TORCH_CPU_WHEEL_URL}/torch-2.8.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl" \
        "${TORCH_CPU_WHEEL_URL}/torchvision-0.23.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl"

RUN pip install --no-cache-dir --retries 10 --timeout 60 -r requirements.txt

COPY app.py ./app.py

# 非 root 运行（R-01 最小权限）。uid/gid 固定为 10001，compose 用同一数值，
# 避免 named volume 初始化后属主漂移导致模型缓存不可写。
RUN groupadd -g 10001 parser \
    && useradd -u 10001 -g parser -d /home/parser -m parser \
    && mkdir -p /home/parser/.cache \
    && chown -R parser:parser /home/parser

# 模型路径固定到 parser_cache 卷。没有该配置时 MinerU 每次都会先访问 modelscope.cn
# 列仓库文件；parser 仅连 internal 网络，离线部署会直接 502。
COPY --chown=parser:parser mineru.json /home/parser/mineru.json

# 模型缓存挂载点。MinerU 默认把模型拉到 HOME 下的 .cache，
# 挂成卷可避免每次重建镜像都重新下载数 GB 权重。
ENV MINERU_MODEL_SOURCE=modelscope \
    HOME=/home/parser \
    HF_HOME=/home/parser/.cache \
    MODELSCOPE_CACHE=/home/parser/.cache
VOLUME ["/home/parser/.cache"]

USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "app:app", \
     "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]