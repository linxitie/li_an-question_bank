#!/usr/bin/env bash
# SQLite 在线备份 + 资产清单 + 可选资产副本/异地副本（P5）。
# 关键约束：数据库只用 sqlite3.backup()（R10），禁止 cp/copy2 主库。
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
if [ ! -f "$ENV_PATH" ]; then echo "[backup] 环境文件不存在: $ENV_PATH" >&2; exit 2; fi
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

resolve_dir() {
  case "$1" in
    /*) printf '%s' "$1" ;;
    *)  printf '%s/%s' "$DEPLOY_DIR" "${1#./}" ;;
  esac
}

DATA_DIR=$(resolve_dir "${DATA_ROOT:-./runtime/data}")
STATIC_DIR=$(resolve_dir "${STATIC_ROOT:-./runtime/static}")
UPLOAD_DIR=$(resolve_dir "${UPLOAD_ROOT:-./runtime/uploads}")
FOUNDATION_DIR="$DATA_DIR/foundation"
BACKUP_SUBDIR=${BACKUP_SUBDIR:-backups}
BACKUP_DIR="$DATA_DIR/$BACKUP_SUBDIR"

LABEL=""; DO_ASSETS=0; DO_OFFSITE=0; SKIP_CHECKPOINT=0
usage() {
  echo "用法: deploy/backup.sh [--label 文本] [--assets] [--offsite] [--no-checkpoint]"
  echo "  --assets       用 rsync 额外复制 static/uploads/foundation（支持 LINK_DEST）"
  echo "  --offsite      复制到 OFFSITE_ROOT（环境变量必填）"
}
while [ $# -gt 0 ]; do
  case "$1" in
    --label) LABEL="${2:-}"; shift 2 ;;
    --assets) DO_ASSETS=1; shift ;;
    --offsite) DO_OFFSITE=1; shift ;;
    --no-checkpoint) SKIP_CHECKPOINT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[backup] 未知参数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ ! -f "$DATA_DIR/question_bank.db" ]; then echo "[backup] 主库不存在: $DATA_DIR/question_bank.db" >&2; exit 2; fi
mkdir -p "$BACKUP_DIR"

if [ "$SKIP_CHECKPOINT" -eq 0 ]; then
  "$DEPLOY_DIR/checkpoint.sh"
fi

echo "[backup] sqlite3.backup -> $BACKUP_DIR"
if [ -n "$LABEL" ]; then
  run_backend_py scripts/admin/backup_db.py --db /app/data/question_bank.db --out-dir "/app/data/$BACKUP_SUBDIR" --label "$LABEL"
else
  run_backend_py scripts/admin/backup_db.py --db /app/data/question_bank.db --out-dir "/app/data/$BACKUP_SUBDIR"
fi

BAK=$(ls -1t "$BACKUP_DIR"/question_bank_*.db 2>/dev/null | head -1 || true)
if [ -z "$BAK" ] || [ ! -f "$BAK" ]; then echo "[backup] 未找到刚生成的备份" >&2; exit 1; fi
echo "[backup] 备份文件: $BAK ($(du -h "$BAK" | awk '{print $1}'))"
sha256sum "$BAK" > "$BAK.sha256"

MAN="${BAK%.db}.manifest.txt"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  echo "backup=$(basename "$BAK")"
  echo "created_at=$TS"
  echo "label=$LABEL"
} > "$MAN"
manifest_one() {
  local name="$1" path="$2" bytes files
  if [ ! -d "$path" ]; then echo "$name files=0 bytes=0 path=$path (missing)" >> "$MAN"; return; fi
  # 7GB/15 万文件的统计在 Windows bind mount 上可达数分钟；默认只登记路径，深统计显式开启。
  if [ "${MANIFEST_DEEP:-0}" != "1" ]; then
    echo "$name path=$path deep=0 (set MANIFEST_DEEP=1 for files/bytes)" >> "$MAN"
    return
  fi
  bytes=$(du -sb "$path" 2>/dev/null | awk '{print $1}')
  files=$(find "$path" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "$name files=$files bytes=$bytes path=$path deep=1" >> "$MAN"
}
manifest_one static "$STATIC_DIR"
manifest_one uploads "$UPLOAD_DIR"
manifest_one foundation "$FOUNDATION_DIR"
echo "[backup] 清单: $MAN"

if [ "$DO_ASSETS" -eq 1 ]; then
  ASSET_DIR="$BACKUP_DIR/assets-$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$ASSET_DIR"
  if command -v rsync >/dev/null 2>&1; then
    COPY_MODE=rsync
  else
    COPY_MODE=cp
    echo "[backup] 未找到 rsync，退化为 cp -a（无硬链接增量；LINK_DEST 忽略）" >&2
  fi
  for name in static uploads foundation; do
    case "$name" in static) src="$STATIC_DIR" ;; uploads) src="$UPLOAD_DIR" ;; foundation) src="$FOUNDATION_DIR" ;; esac
    [ -d "$src" ] || continue
    echo "[backup] $COPY_MODE $src -> $ASSET_DIR/$name"
    if [ "$COPY_MODE" = rsync ]; then
      OPTS=(-a)
      if [ -n "${LINK_DEST:-}" ] && [ -d "$LINK_DEST/$name" ]; then OPTS+=(--link-dest="$LINK_DEST/$name"); fi
      rsync "${OPTS[@]}" "$src/" "$ASSET_DIR/$name/"
    else
      mkdir -p "$ASSET_DIR/$name"
      cp -a "$src/." "$ASSET_DIR/$name/"
    fi
  done
  echo "[backup] 资产副本: $ASSET_DIR"
fi

cat > "$BACKUP_DIR/latest.json" <<EOF
{
  "backup": "$(basename "$BAK")",
  "backup_path": "$BAK",
  "sha256_file": "$(basename "$BAK").sha256",
  "manifest": "$(basename "$MAN")",
  "created_at": "$TS",
  "label": "$LABEL"
}
EOF

if [ "$DO_OFFSITE" -eq 1 ]; then
  if [ -z "${OFFSITE_ROOT:-}" ]; then echo "[backup] --offsite 需要 OFFSITE_ROOT" >&2; exit 3; fi
  mkdir -p "$OFFSITE_ROOT"
  cp -p "$BAK" "$BAK.sha256" "$MAN" "$BACKUP_DIR/latest.json" "$OFFSITE_ROOT/"
  echo "[backup] 异地副本: $OFFSITE_ROOT"
fi
echo "[backup] OK"