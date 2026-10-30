# deploy/certs

TLS 证书目录。**证书与私钥不入 Git**（见根 .gitignore）。

生产：把学校签发的 `server.crt` / `server.key`（或完整链）放到本目录，
然后叠加 `deploy/docker-compose.tls.yml` 启动。

staging 自签：

```bash
bash deploy/gen-self-signed-cert.sh
curl -k https://127.0.0.1:8443/healthz
```

注意：web 容器是 nginx-unprivileged（uid 101），证书文件必须可读；
私钥不要用 600 root-only，否则容器内读不到、nginx 启动失败。
生产更推荐由学校网关终止 TLS，本目录仅作直连兜底。
