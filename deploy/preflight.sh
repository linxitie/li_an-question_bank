#!/usr/bin/env bash
# 部署前自检 —— 在 docker compose up 之前拦截“空题图卷/缺库/缺密钥/端口占用”。
#
# 用法：
#   bash deploy/preflight.sh
#   APP_ENV_FILE=/srv/liankao/secrets/.env.production bash deploy/preflight.sh
#
# 退出码：0 通过；1 任一硬检查失败。脚本只读，不创建目录、不写数据库、不启动容器。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT/deploy"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"
to_win() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

fail() {
  echo "[preflight] ❌ $*" >&2
  exit 1
}
ok() { echo "[preflight] ✅ $*"; }
warn() { echo "[preflight] ⚠️  $*" >&2; }

# ── 0. 定位并加载环境文件 ───────────────────────────────
ENV_FILE="${APP_ENV_FILE:-./.env.development}"
case "$ENV_FILE" in
  /*) ;;
  *) ENV_FILE="$DEPLOY_DIR/${ENV_FILE#./}" ;;
esac
[ -f "$ENV_FILE" ] || fail "环境文件不存在：$ENV_FILE（先 cp deploy/.env.example deploy/.env.development）"
# shellcheck disable=SC1090
set -a
. "$ENV_FILE"
set +a
ok "环境文件：$ENV_FILE"

# ── 1. 必填变量与密钥 ───────────────────────────────────
for name in IMAGE_TAG DATA_ROOT STATIC_ROOT UPLOAD_ROOT LOG_ROOT JWT_SECRET_KEY DB_TYPE SQLITE_PATH WEB_CONCURRENCY; do
  eval "value=\${$name:-}"
  [ -n "$value" ] || fail "缺少必填变量：$name"
done
case "$IMAGE_TAG" in
  latest) fail "IMAGE_TAG 禁止 latest，请用提交号或版本号" ;;
  CHANGE_ME*|REPLACE_*) fail "IMAGE_TAG 仍是模板占位符，请填写真实版本号" ;;
esac
case "$JWT_SECRET_KEY" in
  your-*|CHANGE_ME*|REPLACE_*) fail "JWT_SECRET_KEY 仍是示例占位符，请由用户本人生成并填写" ;;
esac
[ "${#JWT_SECRET_KEY}" -ge 32 ] || fail "JWT_SECRET_KEY 长度必须 ≥32"
[ "$DB_TYPE" = "sqlite" ] || fail "当前只支持 DB_TYPE=sqlite（本阶段不迁 PostgreSQL）"
[ "$WEB_CONCURRENCY" = "1" ] || fail "WEB_CONCURRENCY 必须为 1（SQLite 单写者）"
ok "必填变量齐全；密钥未打印"

# ── 2. 宿主目录与数据 ───────────────────────────────────
resolve_dir() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s\n' "$DEPLOY_DIR/${1#./}" ;;
  esac
}
DATA_DIR="$(resolve_dir "$DATA_ROOT")"
STATIC_DIR="$(resolve_dir "$STATIC_ROOT")"
UPLOAD_DIR="$(resolve_dir "$UPLOAD_ROOT")"
LOG_DIR="$(resolve_dir "$LOG_ROOT")"

[ -d "$DATA_DIR" ] || fail "DATA_ROOT 不存在：$DATA_DIR"
[ -f "$DATA_DIR/question_bank.db" ] || fail "主库不存在：$DATA_DIR/question_bank.db"
[ -d "$STATIC_DIR" ] || fail "STATIC_ROOT 不存在：$STATIC_DIR"
[ -d "$STATIC_DIR/questions" ] || fail "题图目录不存在：$STATIC_DIR/questions（R7：空题图会导致全站裂图）"
if ! find "$STATIC_DIR/questions" -maxdepth 1 -type f -print -quit | grep -q .; then
  fail "题图目录为空：$STATIC_DIR/questions"
fi
[ -d "$UPLOAD_DIR" ] || fail "UPLOAD_ROOT 不存在：$UPLOAD_DIR"
[ -d "$LOG_DIR/backend" ] || fail "日志目录不存在：$LOG_DIR/backend"
[ -w "$LOG_DIR/backend" ] || fail "日志目录不可写：$LOG_DIR/backend"
ok "数据/题图/上传/日志目录存在且题图非空"

# 题组图与通用图片目录允许为空，但缺失时提示（导入后才会生成）
[ -d "$STATIC_DIR/question-groups" ] || warn "题组图目录不存在（导入复合题后会生成）：$STATIC_DIR/question-groups"
[ -d "$STATIC_DIR/images" ] || warn "通用图片目录不存在：$STATIC_DIR/images"

# ── 3. 磁盘余量 ─────────────────────────────────────────
MIN_FREE_GB="${MIN_FREE_GB:-5}"
FREE_KB="$(df -Pk "$DATA_DIR" | awk 'NR==2 {print $4}')"
[ -n "$FREE_KB" ] || fail "无法读取磁盘余量：$DATA_DIR"
FREE_GB=$((FREE_KB / 1024 / 1024))
[ "$FREE_GB" -ge "$MIN_FREE_GB" ] || fail "磁盘余量不足：${FREE_GB}GB < ${MIN_FREE_GB}GB"
ok "磁盘余量：${FREE_GB}GB（要求 ≥${MIN_FREE_GB}GB）"

# ── 4. 端口占用 ─────────────────────────────────────────
PORT="${HTTP_PORT:-8080}"
if command -v ss >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$PORT$"; then
    fail "HTTP_PORT 已被占用：$PORT"
  fi
  ok "HTTP_PORT 可用：$PORT"
elif command -v netstat >/dev/null 2>&1; then
  if netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$PORT$"; then
    fail "HTTP_PORT 已被占用：$PORT"
  fi
  ok "HTTP_PORT 可用：$PORT"
else
  warn "未找到 ss/netstat，跳过端口占用检查（HTTP_PORT=$PORT）"
fi

# ── 5. Docker 与 Compose 配置 ───────────────────────────
command -v docker >/dev/null 2>&1 || fail "未找到 docker"
docker info >/dev/null 2>&1 || fail "Docker daemon 不可用"
docker compose version >/dev/null 2>&1 || fail "未找到 docker compose v2"
docker compose -f "$(to_win "$COMPOSE_FILE")" --env-file "$(to_win "$ENV_FILE")" config --quiet \
  || fail "docker compose config 校验失败"
ok "Docker daemon 可用；compose config 通过"

# ── 6. 构建上下文不含密钥 ───────────────────────────────
if [ -f "$ROOT/.dockerignore" ]; then
  grep -Eq '^\.env$' "$ROOT/.dockerignore" || warn ".dockerignore 未显式排除 .env"
  grep -Eq '^\.env\.\*$' "$ROOT/.dockerignore" || warn ".dockerignore 未显式排除 .env.*"
  ok "构建上下文密钥排除规则存在"
else
  warn "根 .dockerignore 不存在，前端构建可能带入本地文件"
fi

echo
echo "[preflight] ✅ 全部硬检查通过。下一步："
printf '  docker compose -f deploy/docker-compose.yml --env-file %q build\n' "$ENV_FILE"
printf '  docker compose -f deploy/docker-compose.yml --env-file %q up -d\n' "$ENV_FILE"
echo "  禁止执行 docker compose down -v（业务数据在宿主目录）"
