#!/usr/bin/env bash
# 容器化巡检（P5）：容器健康、API、磁盘、备份年龄、DB 完整性、日志体积。
# 退出码：0 正常；1 有硬失败；2 参数/环境错误。可直接接 cron/systemd timer。
set -uo pipefail
# Git Bash 会把容器内绝对路径参数改写成 Windows 路径，必须关闭 MSYS 路径转换。
export MSYS_NO_PATHCONV=1

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEPLOY_DIR="$ROOT/deploy"
ENV_FILE=${ENV_FILE:-.env.development}
case "$ENV_FILE" in
  /*) ENV_PATH="$ENV_FILE" ;;
  *)  ENV_PATH="$DEPLOY_DIR/${ENV_FILE#./}" ;;
esac
if [ ! -f "$ENV_PATH" ]; then echo "[inspect] FAIL 环境文件不存在: $ENV_PATH"; exit 2; fi
set -a; . "$ENV_PATH"; set +a
to_win() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
COMPOSE=(docker compose -f "$(to_win "$DEPLOY_DIR/docker-compose.yml")" --env-file "$(to_win "$ENV_PATH")")
resolve_dir() { case "$1" in /*) printf '%s' "$1" ;; *) printf '%s/%s' "$DEPLOY_DIR" "${1#./}" ;; esac; }
DATA_DIR=$(resolve_dir "${DATA_ROOT:-./runtime/data}")
LOG_DIR=$(resolve_dir "${LOG_ROOT:-./runtime/logs}")
BACKUP_DIR="$DATA_DIR/${BACKUP_SUBDIR:-backups}"
PORT=${HTTP_PORT:-8080}
FAIL=0; WARN=0
ok() { echo "[inspect] OK   $*"; }
warn() { echo "[inspect] WARN $*"; WARN=$((WARN+1)); }
bad() { echo "[inspect] FAIL $*"; FAIL=$((FAIL+1)); }

for svc in web backend; do
  CID=$("${COMPOSE[@]}" ps -q "$svc" 2>/dev/null || true)
  if [ -z "$CID" ]; then bad "$svc 容器未运行"; continue; fi
  STATUS=$(docker inspect -f '{{.State.Status}}' "$CID" 2>/dev/null || echo unknown)
  HEALTH=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CID" 2>/dev/null || echo unknown)
  if [ "$STATUS" = running ] && { [ "$HEALTH" = healthy ] || [ "$HEALTH" = none ]; }; then ok "$svc status=$STATUS health=$HEALTH"; else bad "$svc status=$STATUS health=$HEALTH"; fi
done

for path in /healthz /health /health/foundation; do
  CODE=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$path" 2>/dev/null || true)
  [ "$CODE" = 200 ] && ok "GET $path -> $CODE" || bad "GET $path -> ${CODE:-curl失败}"
done

AVAIL_KB=$(df -Pk "$DATA_DIR" 2>/dev/null | awk 'NR==2 {print $4}')
if [ -n "${AVAIL_KB:-}" ] && [ "$AVAIL_KB" -ge 5242880 ]; then ok "磁盘可用 $((AVAIL_KB/1024)) MB"; else bad "磁盘可用不足 5GB（${AVAIL_KB:-未知} KB）"; fi

LATEST=$(ls -1t "$BACKUP_DIR"/question_bank_*.db 2>/dev/null | head -1 || true)
if [ -z "$LATEST" ]; then
  warn "尚无备份（$BACKUP_DIR）"
else
  MTIME=$(stat -c %Y "$LATEST" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  AGE_H=$(( (NOW - MTIME) / 3600 ))
  MAX_AGE=${MAX_BACKUP_AGE_HOURS:-48}
  if [ "$AGE_H" -le "$MAX_AGE" ]; then ok "最新备份 ${AGE_H}h 前: $(basename "$LATEST")"; else bad "最新备份已 ${AGE_H}h（阈值 ${MAX_AGE}h）"; fi
fi

if [ -n "$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)" ]; then
  INTEG=$("${COMPOSE[@]}" exec -T backend python -c "import sqlite3;c=sqlite3.connect('/app/data/question_bank.db');print(c.execute('PRAGMA integrity_check').fetchone()[0]);c.close()" 2>/dev/null | tr -d '\r')
  [ "$INTEG" = ok ] && ok "SQLite integrity_check=ok" || bad "SQLite integrity_check=${INTEG:-未知}"
else
  bad "backend 未运行，跳过 DB 完整性检查"
fi

if [ -d "$LOG_DIR" ]; then
  LOG_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | awk '{print $1}')
  ok "日志目录 $LOG_SIZE"
else
  warn "日志目录不存在: $LOG_DIR"
fi

echo "[inspect] 汇总: FAIL=$FAIL WARN=$WARN"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1