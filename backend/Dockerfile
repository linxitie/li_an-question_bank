# syntax=docker/dockerfile:1
#
# 后端镜像 —— FastAPI + SQLite(WAL) + PDF解析 + 爬虫
#
# 硬性约束（红线见 AGENTS.md，改动本文件前必读）：
#   R7   app/static/ 是 4.27 GB / 94814 个文件的题图库，
#        绝不 COPY 进镜像，必须由 qimg 卷在运行时挂载。
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
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libxslt1.1 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖单独成层：业务代码频繁改动时，这层走缓存，不必重装 1GB+ 的依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# playwright 被生产代码使用（exam_scraper / news_scraper / recruitment_scraper），
# 不是仅门禁需要，故 chromium 必须进镜像。--with-deps 补齐其系统库。
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# 业务代码。app/static 被 .dockerignore 排除，此处不会出现 4.27 GB 题图。
COPY app ./app

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