#!/usr/bin/env bash
# 生产发布/回滚入口（P6）：preflight → checkpoint → backup → pull/up → healthy → 烟测；失败回滚上一 tag。
# 不执行 docker compose down -v；业务数据全部在宿主 bind 目录。
set -euo pipefail
# Git Bash 会把容器内绝对路径参数改写成 Windows 路径，必须关闭 MSYS 路径转换。
export MSYS_NO_PATHCONV=1

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEPLOY_DIR="$ROOT/deploy"

usage() {
  echo "用法: deploy/release.sh [--dry-run] [--build] [--no-pull] [--skip-backup] [--with-ocr] [--tag <版本>]"
  echo "  --dry-run      只跑 preflight 与配置检查，不备份/不拉取/不启动"
  echo "  --build        本地构建镜像（默认只 pull 远端镜像）"
  echo "  --no-pull      不拉取远端镜像（离线/已 load 场景）"
  echo "  --skip-backup  跳过发布前备份（不建议）"
  echo "  --with-ocr     同时启动 parser profile"
  echo "  --tag <版本>   覆盖环境文件中的 IMAGE_TAG"
}
for arg in "$@"; do
  case "$arg" in -h|--help) usage; exit 0 ;; esac
done

ENV_FILE=${ENV_FILE:-.env.production}

case "$ENV_FILE" in
  /*) ENV_PATH="$ENV_FILE" ;;
  *)  ENV_PATH="$DEPLOY_DIR/${ENV_FILE#./}" ;;
esac
if [ ! -f "$ENV_PATH" ]; then echo "[release] 环境文件不存在: $ENV_PATH" >&2; exit 2; fi
set -a; . "$ENV_PATH"; set +a

to_win() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
COMPOSE=(docker compose -f "$(to_win "$DEPLOY_DIR/docker-compose.yml")" --env-file "$(to_win "$ENV_PATH")")

DRY=0; BUILD=0; NO_PULL=0; SKIP_BACKUP=0; WITH_OCR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --build) BUILD=1; shift ;;
    --no-pull) NO_PULL=1; shift ;;
    --skip-backup) SKIP_BACKUP=1; shift ;;
    --with-ocr) WITH_OCR=1; shift ;;
    --tag) IMAGE_TAG="${2:-}"; export IMAGE_TAG; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[release] 未知参数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$IMAGE_TAG" in
  ''|latest) echo "[release] IMAGE_TAG 必须显式填写且不能是 latest" >&2; exit 2 ;;
  CHANGE_ME*|REPLACE_*) echo "[release] IMAGE_TAG 仍是模板占位符" >&2; exit 2 ;;
esac
PORT=${HTTP_PORT:-8080}
SMOKE_BASE="http://127.0.0.1:$PORT"

run_py() {
  if [ -n "$("${COMPOSE[@]}" ps -q backend 2>/dev/null || true)" ]; then
    "${COMPOSE[@]}" exec -T backend python "$@"
  else
    "${COMPOSE[@]}" run --rm --no-deps --entrypoint python backend "$@"
  fi
}

current_tag() {
  local cid img
  cid=$("${COMPOSE[@]}" ps -q web 2>/dev/null || true)
  [ -n "$cid" ] || return 0
  img=$(docker inspect -f '{{.Config.Image}}' "$cid" 2>/dev/null || true)
  printf '%s' "${img##*:}"
}

http_code() { curl -sS -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || true; }
smoke() {
  local code
  for path in /healthz /health '/api/questions/?page=1&page_size=1'; do
    code=$(http_code "$SMOKE_BASE$path")
    echo "[release] GET $path -> ${code:-curl失败}"
    [ "$code" = 200 ] || return 1
  done
  return 0
}
wait_healthy() {
  local svc cid status i
  for svc in web backend; do
    cid=$("${COMPOSE[@]}" ps -q "$svc" || true)
    [ -n "$cid" ] || { echo "[release] $svc 容器不存在" >&2; return 1; }
    status=unknown
    for i in $(seq 1 60); do
      status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo unknown)
      [ "$status" = healthy ] && break
      sleep 2
    done
    echo "[release] $svc health=$status"
    [ "$status" = healthy ] || return 1
  done
}

echo "[release] IMAGE_TAG=$IMAGE_TAG PORT=$PORT"
APP_ENV_FILE="$ENV_PATH" bash "$DEPLOY_DIR/preflight.sh"
if [ "$DRY" -eq 1 ]; then
  echo "[release] --dry-run：preflight 通过；未备份、未拉取、未启动。"
  exit 0
fi

PREV=$(current_tag); echo "[release] 当前 web tag: ${PREV:-无}"
ENV_FILE="$ENV_PATH" bash "$DEPLOY_DIR/checkpoint.sh"
if [ "$SKIP_BACKUP" -eq 0 ]; then
  ENV_FILE="$ENV_PATH" bash "$DEPLOY_DIR/backup.sh" --label "release-$IMAGE_TAG"
else
  echo "[release] 已跳过发布前备份（--skip-backup）" >&2
fi

PROFILE_ARGS=()
[ "$WITH_OCR" -eq 1 ] && PROFILE_ARGS=(--profile ocr)
if [ "$BUILD" -eq 1 ]; then
  "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" build
elif [ "$NO_PULL" -eq 0 ]; then
  "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" pull web backend
  [ "$WITH_OCR" -eq 1 ] && "${COMPOSE[@]}" --profile ocr pull parser || true
fi

deploy() {
  local args=(up -d --remove-orphans)
  [ "$BUILD" -eq 1 ] && args+=(--build) || args+=(--no-build)
  "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" "${args[@]}" web backend
  [ "$WITH_OCR" -eq 1 ] && "${COMPOSE[@]}" --profile ocr up -d --no-build parser
  wait_healthy && smoke
}

rollback() {
  [ -n "$PREV" ] || { echo "[release] 没有可回滚的上一 tag" >&2; return 1; }
  echo "[release] 发布失败，回滚到 $PREV" >&2
  IMAGE_TAG="$PREV" "${COMPOSE[@]}" "${PROFILE_ARGS[@]}" up -d --no-build --remove-orphans web backend || true
  IMAGE_TAG="$PREV" wait_healthy || true
  IMAGE_TAG="$PREV" smoke || true
}

if ! deploy; then
  rollback || true
  echo "[release] 失败：已尝试回滚；请查看 deploy/runtime/logs/backend 与 docker logs" >&2
  exit 1
fi
echo "[release] OK：$IMAGE_TAG 已发布并通过烟测"
