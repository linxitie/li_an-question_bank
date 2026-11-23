# BiRefNet 通用模型跨设备使用流程 v1

> 适用范围：商品图抠像（商城后台）在**新电脑 / 新服务器 / Docker 部署 / 内网离线机**上启用 BiRefNet。
> 事实源：`backend/app/services/product_image.py`、`scripts/shop/fetch_cutout_model.py(.ps1)`、
> `docs/superpowers/specs/商品图BiRefNet抠图_2026-11-18.md` §7。
> 本文 2026-11-23 按本机实测整理；模型权重不进 Git。

## 0. 本机当前状态（2026-11-23 实测）

| 项 | 实测值 |
|---|---|
| 引擎 | `cutout_engine() = birefnet` |
| 模型 | `birefnet-general` |
| 权重 | `C:\Users\31127\.rembg\models\birefnet-general\birefnet-general.onnx`（973MB） |
| 校验 | `fetch_cutout_model.py --check` → `OK`，exit 0 |
| 异步 | `SHOP_CUTOUT_ASYNC` 默认开启（上传立即返回占位图，后台抠完覆盖） |

## 1. 新设备四步

### 第 1 步：Python 与依赖

- Python **3.11–3.13**（rembg 2.0.87 要求 `>=3.11,<4`；CI 用 3.13）。
- 安装依赖（含 rembg、onnxruntime、Pillow）：

```powershell
cd <仓库根>
pip install -r backend/requirements.txt
```

> 国内网络慢时可用清华镜像；onnxruntime 只装 CPU 版即可，本项目不依赖 CUDA。

### 第 2 步：下载权重（两种脚本任选）

```powershell
# Windows 一键（默认 general 973MB）
powershell -ExecutionPolicy Bypass -File scripts/shop/fetch_cutout_model.ps1

# 跨平台 Python（Windows/Linux/macOS 通用）
python scripts/shop/fetch_cutout_model.py
```

- 默认落位：`%USERPROFILE%\.rembg\models\birefnet-general\birefnet-general.onnx`（Windows）；
  Linux/macOS 为 `~/.rembg/models/birefnet-general/birefnet-general.onnx`。
- 需要 lite（224MB、快但质量差）：`--variant lite` / `-Variant lite`。
- 内网镜像/加速源：`--url <镜像地址>`。
- 校验值：general MD5 `7a35a0141cbbc80de11d9c9a28f52697`，大小 972,666,916 字节；
  lite MD5 `4fab47adc4ff364be1713e97b7e66334`，大小 224,005,088 字节。
- 断点续传：脚本写 `*.part`，中断重跑带 Range 续传；urllib 失败自动切系统 `curl -C -`。

### 第 3 步：告诉 rembg 权重在哪（默认路径可跳过）

rembg 的模型目录由环境变量决定（本机实测）：

| 变量 | 实际查找目录 |
|---|---|
| 默认 | `~/.rembg/models/<session>/` |
| `U2NET_HOME` | `<U2NET_HOME>/models/<session>/` |
| `REMBG_HOME` | `<REMBG_HOME>/models/<session>/` |
| `XDG_DATA_HOME` | `<XDG_DATA_HOME>/rembg/models/<session>/` |

> 注意：变量指向的是“home/数据根”，rembg 会再拼 `models/<session>`。
> 用 `--out` 下载时，参数应是**会话目录本身**，例如
> `--out /data/rembg/models/birefnet-general`，文件为 `/data/rembg/models/birefnet-general/birefnet-general.onnx`。

### 第 4 步：验证（必须做）

```powershell
# 1) 权重完整性（exit 0=OK，2=缺失/损坏）
python scripts/shop/fetch_cutout_model.py --check

# 2) 引擎选择（在 backend 目录执行，需要能 import app）
cd backend
python -c "from app.services import product_image as m; print(m.cutout_engine())"
# 期望输出：birefnet
```

- 启动后端日志应出现 `商品图抠像引擎: birefnet`；首次启动会后台预热（实测冷启动 5–50s）。
- 上传一张商品图：异步模式先返回占位图，轮询状态接口直到 `status=done / engine=birefnet`。
- 如果输出 `classic`：看第 6 节排查。

## 2. 环境变量速查

| 变量 | 默认 | 说明 |
|---|---|---|
| `SHOP_CUTOUT_ENGINE` | `auto` | auto=有模型就用；birefnet=强制（失败报错）；classic=只用 GrabCut |
| `SHOP_CUTOUT_MODEL` | `birefnet-general` | 必须与权重会话目录名一致 |
| `SHOP_CUTOUT_MAX_INPUT` | `1024` | 推理最长边；大图先缩再推理 |
| `SHOP_CUTOUT_THREADS` | `min(16, CPU)` | onnxruntime 线程数 |
| `SHOP_CUTOUT_ASYNC` | `1` | 异步队列；`0` 关闭 |
| `SHOP_CUTOUT_ALLOW_DOWNLOAD` | 未设置 | `1` 才允许首次调用在线下载（默认禁止，避免上传卡 973MB） |

## 3. Docker / 服务器部署

容器 `HOME=/tmp` 且根文件系统 `read_only`，**不能**把权重放在容器临时目录，必须挂卷并显式指路。

推荐做法（宿主机先下载好，再挂载）：

```yaml
# docker-compose.yml backend 服务
environment:
  U2NET_HOME: /models
volumes:
  - ${MODEL_ROOT:?MODEL_ROOT required}:/models
```

宿主机目录结构：

```text
${MODEL_ROOT}/
  models/
    birefnet-general/
      birefnet-general.onnx
```

因为 `U2NET_HOME=/models` 时 rembg 查找 `/models/models/birefnet-general/`，所以宿主机 `MODEL_ROOT` 下要保留 `models/birefnet-general/...` 这一层。

容器内下载（构建期/首次启动）时：

```bash
python scripts/shop/fetch_cutout_model.py --out /models/models/birefnet-general
python scripts/shop/fetch_cutout_model.py --check   # 容器内应 exit 0
```

> 也可挂载宿主机的 `~/.rembg` 到容器 `/tmp/.rembg`（compose 的 `HOME=/tmp`），此时无需设置 `U2NET_HOME`。
> 生产镜像 `backend/Dockerfile` 已装 `requirements.txt`（含 rembg/onnxruntime），但 `deploy/docker-compose.yml` 目前**没有**模型卷；需要按上面的方式补一条 volume，否则线上会静默退回 classic。

## 4. 离线 / 内网 / 弱网

- 离线机：在任一已下载机器上打包整个会话目录：
  `~/.rembg/models/birefnet-general/`（Windows 为 `%USERPROFILE%\.rembg\models\birefnet-general\`），
  拷到目标机相同相对路径；保留文件名 `birefnet-general.onnx`。
- 只传文件不传目录、或目录名与 `SHOP_CUTOUT_MODEL` 不一致 → 会判为未就绪。
- 代理：脚本支持 `HTTPS_PROXY`；也可 `--url` 指向内网镜像。
- CI/构建缓存：缓存模型目录，构建时先 `--check`，命中即跳过下载。

## 5. 多设备矩阵

| 场景 | 做法 |
|---|---|
| Windows 本机开发 | 默认 `%USERPROFILE%\.rembg`，下载后重启后端 |
| Linux/macOS 开发/服务器 | 默认 `~/.rembg`，或 `U2NET_HOME` 指到数据盘 |
| Docker | 挂卷 + `U2NET_HOME`（见第 3 节），容器重建不重下 |
| 内网离线 | 拷贝会话目录；不要提交 Git |
| 低配机器 | `SHOP_CUTOUT_ENGINE=classic` 或 `SHOP_CUTOUT_MODEL=birefnet-general-lite` |

## 6. 故障排查

| 现象 | 原因/处理 |
|---|---|
| `cutout_engine()=classic` | rembg 未安装；或权重目录不对/文件名不对；或 `SHOP_CUTOUT_ENGINE=classic`。先跑 `--check` |
| 上传报 “BiRefNet 不可用” | 强制 `SHOP_CUTOUT_ENGINE=birefnet` 时不降级；改 auto 或修好权重 |
| 首次上传很慢 | 模型会话冷加载（5–50s）；启动后已后台预热，等预热完成再测 |
| 内存被打满 | 会话常驻约 1GB；限制 `SHOP_CUTOUT_THREADS` 或改 classic |
| 下载反复失败 | 用 `--url` 镜像；确认磁盘 ≥1.2GB；重跑会续传 |
| `--check` 报 MISS | 路径按第 1 节核对；`--out` 要指到会话目录；MD5 不符会自动重下 |
| 线上仍 classic | compose 没挂模型卷/没设 `U2NET_HOME`；容器 `HOME=/tmp` 会丢临时文件 |

## 7. 安全与许可

- 权重不进 Git（`*.onnx`、`**/.rembg/` 已忽略）；GitHub 单文件 100MB 限制也不允许直接提交。
- Licenses：BiRefNet MIT、rembg MIT、onnxruntime MIT；商用以各自仓库 LICENSE 为准。
- 商品图输出目录 `backend/app/static/shop/` 同样不入 Git，换机后历史商品图需单独拷贝或重传。

## 8. 一页验收清单

- [ ] `python -V`：3.11–3.13
- [ ] `pip install -r backend/requirements.txt` 成功
- [ ] `fetch_cutout_model.py --check` exit 0
- [ ] `cutout_engine()` = birefnet
- [ ] 后端启动日志出现 `商品图抠像引擎: birefnet`
- [ ] 上传商品图后状态 done 且 engine=birefnet
- [ ] Docker：模型卷已挂载、容器重建后仍 birefnet
