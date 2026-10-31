#!/usr/bin/env bash
# 仅用于 staging 自签验证；生产请使用学校签发的证书。
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p certs
if [[ -f certs/server.crt && -f certs/server.key ]]; then
  echo "certs/server.crt 已存在，跳过生成"
  exit 0
fi
command -v openssl >/dev/null 2>&1 || { echo "缺少 openssl，无法生成自签证书"; exit 1; }
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout certs/server.key -out certs/server.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
# nginx-unprivileged 以 uid 101 运行；私钥必须容器内可读。仅限 staging 自签。
chmod 644 certs/server.crt certs/server.key
echo "已生成 deploy/certs/server.crt 与 server.key（staging 自签）"