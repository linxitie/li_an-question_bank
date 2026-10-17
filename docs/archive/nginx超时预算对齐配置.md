# nginx 超时预算对齐配置（生产环境）

> 关联：题目导入 OCR 长耗时链路
> 分支：`feat/question-import-composite-image-optimization`

## 为什么必须改

后端单份 PDF 的**最坏耗时**（非典型值，但必须覆盖）：

| 阶段 | 预算 | 出处 |
|---|---:|---|
| GPU 串行锁排队 | 60s | `backend/app/services/mineru_service.py:32` `_SEM_WAIT_SECONDS=60`（`Semaphore(1)`） |
| MinerU 子进程 | 600s | `backend/app/core/config.py:72` `MINERU_TIMEOUT=600` → `mineru_service.py:132,155` |
| PaddleOCR 兜底（仅 MinerU 超时/失败时） | 240s | `backend/app/core/config.py:86` `OCR_SUBPROCESS_TIMEOUT=240` |
| **合计最坏** | **900s** | 60 + 600 + 240 |

nginx 的 `proxy_read_timeout` / `proxy_send_timeout` **默认均为 60s**。
若沿用默认值，扫描件 OCR 会在 60s 处被代理层掐断——**比任何应用层超时都更早**，
且表现为无明确报错的连接中断，极难排查。

已对齐的三层预算（自上而下必须递减）：

```
前端 fetchWithRetry      960s   (.vtj/vue/question_import.vue PDF_OCR_TIMEOUT_MS)
  └─ nginx proxy_*       1000s  ← 本文件（须 ≥ 前端预算）
       └─ 后端最坏合计     900s   (60+600+240)
            └─ MinerU     600s
```

## 配置片段

在既有 `server` 块内，为 API 路径添加/覆盖：

```nginx
# ===== 题目导入：长耗时 OCR 链路 =====
# 预算依据：后端最坏 900s(GPU排队60 + MinerU600 + PaddleOCR兜底240)
# 代理层须 ≥ 前端预算(960s)，留 40s 余量
location /api/ {
    proxy_pass         http://127.0.0.1:8000;
    proxy_http_version 1.1;

    # --- 超时预算（默认值 60s 会掐断 OCR，必须显式放大）---
    proxy_connect_timeout 60s;    # 建连，够用
    proxy_send_timeout    1000s;  # 上传：≤50MB 大文件 + 后端读取
    proxy_read_timeout    1000s;  # 响应：覆盖后端最坏 900s

    # 长响应不缓冲，避免 nginx 攒完才吐给前端（否则前端看起来"卡住"）
    proxy_buffering off;

    # 上传体积须 ≥ 后端 MAX_FILE_SIZE(50MB)，默认 1m 会直接 413
    client_max_body_size 60m;
    client_body_timeout  1000s;
}

# 静态资源（图/音视频）单独走短超时，避免污染上面的长预算
location /static/ {
    proxy_pass       http://127.0.0.1:8000;
    proxy_read_timeout 60s;
    client_max_body_size 60m;
}
```

## 部署后必须验证

```bash
# 1) 确认实际生效值（不是模板值）
nginx -T | grep -E "proxy_read_timeout|proxy_send_timeout|client_max_body_size"

# 2) 实测长请求是否被掐断：用一份大扫描件走 /api/questions/import/upload，
#    观察是否撑过 60s（若恰好 ~60s 断开 → 代理层未生效，回到第1步）
```

## 后续（尚未实施，本次仅止血）

当前方案仍是**同步阻塞请求**，最长可达 16 分钟。已知局限：

- 用户等待期间无进度反馈，只能看到"正在解析…请耐心等待"
- 代理层/负载均衡/CDN 若有独立超时，仍可能更早掐断
- `Semaphore(1)` 意味着并发导入时 59/60 请求先排 60s 队，队列不可见

**正解是异步 + 轮询**：`backend/app/api/v1/question_import.py` 已有完整状态机
（`PARSING` → `PREVIEW` → `COMPLETED`，含 `preview_data` / `error_messages` 字段，
`/records` 支持按 `import_status` 过滤），复用它即可让 `/upload` 立即返回
`import_id`、后台执行提取、前端轮询状态，彻底消除超时并暴露进度。
