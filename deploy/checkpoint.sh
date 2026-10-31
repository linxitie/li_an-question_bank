#!/usr/bin/env bash
# 发布前把 SQLite WAL 落盘，避免 --force-recreate 丢失未 checkpoint 的提交（P5 / R10）。
set -euo pipefail
# Git Bash 会把容器内绝对路径参数改写成 Windows 路径，必须关闭 MSYS 路径转换。
export MSYS_NO_PATHCONV=1

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEPLOY_DIR="$ROOT/deploy"
ENV_FILE=${ENV_FILE:-.env.development}
case "$ENV_FILE" in
  /*) ENV_PATH="$ENV_FILE" ;;
  *)  ENV_PATH="$DEPLOY_DIR/${ENV_FILE#./}" ;;
esac
if [ ! -f "$ENV_PATH" ]; then
  echo "[checkpoint] 环境文件不存在: $ENV_PATH" >&2
  exit 2
fi
set -a
. "$ENV_PATH"
set +a

to_win() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
COMPOSE=(docker compose -f "$(to_win "$DEPLOY_DIR/docker-compose.yml")" --env-file "$(to_win "$ENV_PATH")")
run_backend_py() {
  if [ -n "$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)" ]; then
    "${COMPOSE[@]}" exec -T backend python "$@"
  else
    "${COMPOSE[@]}" run --rm --no-deps --entrypoint python backend "$@"
  fi
}

echo "[checkpoint] PRAGMA wal_checkpoint(FULL) ..."
set +e
OUT=$(run_backend_py -c "import sqlite3,sys;c=sqlite3.connect('/app/data/question_bank.db',timeout=60);r=c.execute('PRAGMA wal_checkpoint(FULL)').fetchone();c.close();print('busy=%s log=%s checkpointed=%s' % r);sys.exit(1 if r[0] else 0)" 2>&1)
RC=$?
set -e
echo "$OUT"
if [ "$RC" -ne 0 ]; then
  echo "[checkpoint] 失败：WAL 仍被占用或数据库不可写" >&2
  exit 1
fi
echo "[checkpoint] OK"