#!/bin/sh
# 容器入口 —— 处理卷挂载的初始化，再交棒给 uvicorn
#
# 与 start.py 的区别：start.py 是开发机的看门狗（崩溃自动重启 20 次），
# 容器里重启由 orchestrator 负责（restart: unless-stopped），
# 入口脚本只做一次性初始化，不做重启循环。
#
# 红线：
#   R10  SQLite 处于 WAL 模式。若卷里存在 -wal/-shm 却缺少对应主库，
#        SQLite 会拒绝打开。必须一并清理，不得只删主库。
#   R7   app/static 由 qimg 卷挂载，镜像内是空目录。

set -e

APP_DIR=/app
DATA_DIR="$APP_DIR/data"
DB_PATH="$DATA_DIR/question_bank.db"

echo "[entrypoint] 工作目录: $(pwd)"
echo "[entrypoint] 数据目录: $DATA_DIR"

# ── 卷挂载后的目录归属 ─────────────────────────────────
# 以非 root 运行，卷首次挂载时属主是 root:root，app 用户将无法写入。
for d in "$DATA_DIR" "$APP_DIR/uploads" "$APP_DIR/logs" "$APP_DIR/app/static"; do
    mkdir -p "$d" 2>/dev/null || true
done

# ── R10：清理孤儿 WAL 残留 ─────────────────────────────
# 只有在「主库不存在，但 -wal 存在」时才清理，此时 -wal 无主、内容无意义。
# 主库存在时一律保留 -wal/-shm —— 那是有未落盘数据的正常状态，动它会丢数据。
if [ ! -f "$DB_PATH" ]; then
    if [ -f "$DB_PATH-wal" ] || [ -f "$DB_PATH-shm" ]; then
        echo "[entrypoint] 主库缺失但存在 -wal/-shm，清理孤儿残留（R10）"
        rm -f "$DB_PATH-wal" "$DB_PATH-shm"
    fi
    echo "[entrypoint] 未发现主库，将由应用侧按需初始化: $DB_PATH"
fi

# ── 题图卷自检（R7）────────────────────────────────────
# 挂载为空不代表可以继续：题目详情页依赖这些图，缺了就是全站裂图。
STATIC_COUNT=$(ls -A "$APP_DIR/app/static" 2>/dev/null | wc -l | tr -d ' ')
echo "[entrypoint] app/static 条目数: $STATIC_COUNT"
if [ "$STATIC_COUNT" -eq 0 ]; then
    echo "[entrypoint] ⚠️  题图卷为空 —— 题目图片将全部 404。"
    echo "[entrypoint]     本地开发请改用源码目录启动；生产部署请先填充 qimg 卷。"
fi

# ── 凭据不在镜像内，必须由编排层注入 ───────────────────
# .dockerignore 已排除 .env*。此处只做存在性提醒，不打印任何值。
if [ -f "$APP_DIR/.env" ]; then
    echo "[entrypoint] 使用注入的 .env"
else
    echo "[entrypoint] 未挂载 .env，将回落到 app/core/config.py 的默认值"
fi

echo "[entrypoint] 启动 uvicorn 0.0.0.0:8000"

# exec 保证 uvicorn 成为 PID 1 的子进程，tini 负责信号转发
exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level "${UVICORN_LOG_LEVEL:-info}" \
    --proxy-headers \
    --forwarded-allow-ips '*'