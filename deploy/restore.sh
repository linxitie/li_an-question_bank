#!/usr/bin/env bash
# 恢复 / 回滚 SQLite（P5）。停 backend，保留 web；恢复后自动起 backend 并烟测。
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
if [ ! -f "$ENV_PATH" ]; then echo "[restore] 环境文件不存在: $ENV_PATH" >&2; exit 2; fi
set -a; . "$ENV_PATH"; set +a

to_win() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
COMPOSE=(docker compose -f "$(to_win "$DEPLOY_DIR/docker-compose.yml")" --env-file "$(to_win "$ENV_PATH")")
run_backend_py() {
  if [ -n "$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)" ]; then
    "${COMPOSE[@]}" exec -T backend python "$@"
  else
    "${COMPOSE[@]}" run --rm --no-deps --entrypoint python backend "$@"
  fi
}
resolve_dir() { case "$1" in /*) printf '%s' "$1" ;; *) printf '%s/%s' "$DEPLOY_DIR" "${1#./}" ;; esac; }

DATA_DIR=$(resolve_dir "${DATA_ROOT:-./runtime/data}")
BACKUP_DIR="$DATA_DIR/${BACKUP_SUBDIR:-backups}"
BACKUP=""; LATEST=0; DRY=0; YES=0
usage() {
  echo "用法: deploy/restore.sh --backup <文件>|--latest [--dry-run] [--yes]"
  echo "  --latest   取 $BACKUP_DIR 下最新的 question_bank_*.db"
  echo "  --dry-run  只校验备份，不停服务、不落盘"
  echo "  --yes      跳过交互确认（脚本/自动化必填）"
}
while [ $# -gt 0 ]; do
  case "$1" in
    --backup) BACKUP="${2:-}"; shift 2 ;;
    --latest) LATEST=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --yes) YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[restore] 未知参数: $1" >&2; usage >&2; exit 2 ;;
  esac
done
if [ "$LATEST" -eq 1 ]; then
  BACKUP=$(ls -1t "$BACKUP_DIR"/question_bank_*.db 2>/dev/null | head -1 || true)
fi
if [ -z "$BACKUP" ] || [ ! -f "$BACKUP" ]; then echo "[restore] 备份文件不存在: ${BACKUP:-<空>}" >&2; exit 2; fi
if [ ! -f "$DATA_DIR/question_bank.db" ]; then echo "[restore] 主库不存在: $DATA_DIR/question_bank.db" >&2; exit 2; fi

mkdir -p "$DATA_DIR/restore"
DEST="$DATA_DIR/restore/$(basename "$BACKUP")"
cp -p "$BACKUP" "$DEST"
echo "[restore] 备份: $BACKUP"
echo "[restore] 容器内副本: /app/data/restore/$(basename "$BACKUP")"

echo "[restore] 校验备份 ..."
run_backend_py scripts/admin/restore_db.py --backup "/app/data/restore/$(basename "$BACKUP")" --db /app/data/question_bank.db --dry-run

if [ "$DRY" -eq 1 ]; then echo "[restore] --dry-run：未停服务、未落盘"; exit 0; fi
if [ "$YES" -ne 1 ]; then
  printf '[restore] 将停止 backend 并覆盖 /app/data/question_bank.db，输入 yes 继续: '
  read -r ans
  [ "$ans" = yes ] || { echo "[restore] 已取消"; exit 1; }
fi

echo "[restore] 停止 backend（web 保留）..."
"${COMPOSE[@]}" stop backend >/dev/null
echo "[restore] 执行恢复 ..."
set +e
run_backend_py scripts/admin/restore_db.py --backup "/app/data/restore/$(basename "$BACKUP")" --db /app/data/question_bank.db --yes
RC=$?
set -e

echo "[restore] 启动 backend ..."
"${COMPOSE[@]}" up -d backend >/dev/null
CID=$("${COMPOSE[@]}" ps -q backend || true)
STATUS=unknown
for _ in $(seq 1 60); do
  STATUS=$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || echo unknown)
  [ "$STATUS" = healthy ] && break
  sleep 2
done
echo "[restore] backend health=$STATUS"
if [ "$RC" -ne 0 ]; then echo "[restore] 恢复失败（exit $RC），请检查日志" >&2; exit "$RC"; fi
if [ "$STATUS" != healthy ]; then echo "[restore] backend 未 healthy" >&2; exit 1; fi

PORT=${HTTP_PORT:-8080}
CODE=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" || true)
echo "[restore] /health HTTP $CODE"
[ "$CODE" = 200 ] || { echo "[restore] 烟测失败" >&2; exit 1; }
run_backend_py -c "import sqlite3;c=sqlite3.connect('/app/data/question_bank.db');print({t:c.execute('select count(*) from '+t).fetchone()[0] for t in ('sys_user','question_bank','exam_paper','paper_question_relation')});c.close()"
echo "[restore] OK（覆盖前自动快照见 restore_db.py 输出）"