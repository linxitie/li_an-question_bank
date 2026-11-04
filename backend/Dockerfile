# syntax=docker/dockerfile:1
#
# 后端镜像 —— FastAPI + SQLite(WAL) + PDF解析 + 爬虫
#
# 硬性约束（红线见 AGENTS.md，改动本文件前必读）：
#   R7   app/static/ 是约 7.1 GB 的题图库，
#        绝不 COPY 进镜像，必须由宿主 STATIC_ROOT 在运行时挂载。
#   R10  SQLite 处于 WAL 模式。容器启动时若发现遗留的 -wal/-shm
#        而无对应主库，必须连同 -wal/-shm 一起清理，否则库打不开。
#   R11  /api/v1/... 路径冻结。本文件不改动任何路由。
#
# 构建：
#   docker build -t liankao/backend:test backend
#
# 运行（数据全部走卷，镜像内不留任何持久化数据）：
#   docker run --rm -p 8000:8000 \
#     -v liankao_db:/app/data -v liankao_uploads:/app/uploads \
#     -v liankao_qimg:/app/app/static \
#     liankao/backend:test

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TZ=Asia/Shanghai

# ffmpeg            : MinerU / OCR 侧的图像与媒体预处理
# libgl1 libglib2.0 : opencv-python 运行时依赖
# curl              : HEALTHCHECK 探针（slim 镜像默认无 curl）
# tini              : PID 1 信号转发，保证 uvicorn 能优雅退出与滚动重启
# 构建机在国内访问 deb.debian.org 常见丢包（实测同一 .deb 80KB/s vs 清华 2.3MB/s），
# 故镜像源可替换；海外构建可 --build-arg APT_MIRROR=deb.debian.org 还原。
ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=10 -o Acquire::http::Timeout=45 -o Acquire::ForceIPv4=true update \
    && apt-get install -y --no-install-recommends \
        -o Acquire::Retries=10 -o Acquire::http::Timeout=45 -o Acquire::ForceIPv4=true \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libxslt1.1 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖单独成层：业务代码频繁改动时，这层走缓存，不必重装 1GB+ 的依赖。
# PyPI 官方源在部分网络下会返回空版本列表（实测），默认走清华镜像；
# 海外构建可 --build-arg PIP_INDEX_URL=https://pypi.org/simple 还原。
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# playwright 被生产代码使用（exam_scraper / news_scraper / recruitment_scraper），
# 不是仅门禁需要，故 chromium 必须进镜像。--with-deps 补齐其系统库。
# 浏览器包默认走 npmmirror，海外构建可 --build-arg PLAYWRIGHT_DOWNLOAD_HOST= 清空回官方 CDN。
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
ENV PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST} \
    PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000
# Chromium 约 191MB，弱网下单次构建可能超过 1 小时；默认安装（生产镜像），
# staging/CI 可用 --build-arg INSTALL_PLAYWRIGHT_BROWSERS=0 跳过，仅影响爬虫功能。
ARG INSTALL_PLAYWRIGHT_BROWSERS=1
RUN if [ "${INSTALL_PLAYWRIGHT_BROWSERS}" = "1" ]; then \
        playwright install --with-deps chromium; \
    fi \
    && rm -rf /var/lib/apt/lists/*

# 业务代码。app/static 被 .dockerignore 排除，此处不会出现 7.1 GB 题图。
COPY app ./app

# scripts/ 是运行时依赖：main.py 启动时 from scripts.admin.seed import run_seed。
# 只排除门禁/校验脚本（.dockerignore），其余 2MB 运维脚本随镜像发布，
# 供备份/恢复/回填使用；seed 在非 DEBUG 下只 import 不执行。
COPY scripts ./scripts

# 仅门禁基线入镜像。data/ 其余内容（SQLite 主库、41 份 .bak*、audit、
# snapshots、text_cache、xingce_cache）一律排除，走 db_data 卷。
COPY data/gates ./data/gates
COPY data/refactor_baseline ./data/refactor_baseline

# 必须在 chmod 之前 COPY —— 目标文件不存在时 chmod 会失败，构建直接中断。
COPY docker-entrypoint.sh ./docker-entrypoint.sh

# 非 root 运行。logs 由入口脚本按需创建。
#
# 刻意不写 VOLUME 指令：三个数据目录（data / uploads / app/static）一律
# 由 docker-compose.yml 显式挂载。Dockerfile 里声明 VOLUME 会让
# `docker run` 未带 -v 时生成匿名卷 —— 对 app/static 而言就是空目录，
# 题目图片全部 404（R7 后果），且匿名卷会静默堆积难以回收。
RUN groupadd -r app && useradd -r -g app -d /app app \
    && mkdir -p /app/data /app/uploads /app/logs \
    && chown -R app:app /app \
    && chmod +x /app/docker-entrypoint.sh

USER app

EXPOSE 8000

# 复用 main.py:608 既有 /health，不另造端点（AGENTS.md：健康检查已存在，勿重复实现）
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]