# MinerU 扫描件PDF OCR集成 — 设计规格文档

- **日期**: 2026-08-22
- **状态**: 已批准（方案A：MinerU子进程集成 + 仅扫描件回退）
- **关联**: `solve_problems_files/教师端各模块优化.md` §2.2.3 批量导入功能增强

---

## 一、背景与问题

系统批量导入功能对**扫描件PDF**（无文本层的图片型PDF，公安联考真题常见形态）识别能力严重不足：

1. **现有路径**：`_extract_text_from_scanned_pdf`（`backend/app/api/v1/question_import.py` line 591）使用 PyPDF2 提取页面 XObject 内嵌图片 → PaddleOCR 逐页裸识别 → 合并纯文本。
2. **核心缺陷**：PaddleOCR 裸 OCR 输出是**无序纯文本**——没有阅读顺序、没有版面结构（标题层级/表格/多栏），导致题目编号与选项错乱、内容缺失，"只能读取部分"。
3. **附带隐患**：`_extract_text_from_pdf`（sync 函数，line 534）被 async 端点 `upload_file_for_import` 在 line 1556 **直接调用**，OCR 路径运行期间会阻塞整个 FastAPI 事件循环。

## 二、目标与非目标

### 目标
1. 集成开源项目 **MinerU**（opendatalab/MinerU v3.x）作为扫描件 PDF 的高精度解析引擎，利用其版面分析（DocLayout-YOLO）、阅读顺序排序、PP-OCRv6 中文 OCR、表格转 HTML 能力。
2. **仅扫描件回退触发**：文本层 PDF 保持 pdfplumber 快路径不变；检测到扫描件才启用 MinerU。
3. 三级回退链保证降级安全：MinerU 失败 → 现有 PaddleOCR 路径 → 空字符串（现状行为），**最差不比现状差**。
4. 主后端零依赖变更：MinerU 部署在独立 Python 3.12 venv，通过子进程调用。

### 非目标
- ❌ 不替换图片导入路径的 PaddleOCR 服务（`backend/app/services/ocr.py`，职责互补不冲突）
- ❌ 不做异步 job 队列/轮询机制（同步等待 + 前端长超时即可满足教师低频导入场景）
- ❌ 不改 docx/xlsx 解析路径
- ❌ MinerU 版本升级维护不在本次范围（仅锁定版本，记录 `pip freeze` 基线）

## 三、技术选型对比（已评估并否决的备选）

| 候选 | 结论 | 否决理由 |
|------|------|---------|
| **MinerU** ✅ | 采用 | 25k+ stars、v3.4.5 活跃维护、PP-OCRv6 中文 OCR、版面分析、本地 GPU 免费、PDF/DOCX/图片全支持 |
| DocSlight | 否决 | 仅 51 星、2026-07 创建（1个月大）、商业云 API 导流性质，生产风险高 |
| pdf-converter-mineru / markdown-converter | 否决 | MinerU 包装器或纯文本层转换工具；直接集成 MinerU 原生更干净 |
| MinerU HTTP 微服务 | 否决 | 多一个常驻服务要运维，显存常驻占用，部署复杂度高于子进程方案 |
| 直接 pip 装进主后端 | 否决 | **硬约束**：主后端 Python 3.13.5，MinerU 在 Windows 仅支持 ≤3.12（ray 依赖），物理不可行 |

### 关键技术约束（已验证）
1. 主后端 Python **3.13.5** → 独立 venv 从"推荐"升级为**强制**。
2. MinerU GPU 加速需 CUDA torch（cu124）；模型约 3-5GB 从 ModelScope 下载；RTX 3050 6GB 即可跑 `pipeline` 后端。
3. 插入点精确定位：line 581-583 OCR 回退段，位于旧 PaddleOCR 调用之前。

## 四、架构设计

```
D:\砺安题库\砺安题库\
├── backend\                          ← 主后端 Python 3.13.5（依赖不动）
│   ├── app\services\mineru_service.py   ★ 新增：子进程封装层
│   └── app\api\v1\question_import.py    ★ 修改：两处插入点
└── D:\mineru-env\                    ← 独立环境 Python 3.12（新增，路径可配）
    ├── Scripts\python.exe
    └── Lib\site-packages\mineru\     ← mineru[all] + CUDA torch cu124
```

### 三级回退处理管线

```
async upload_file_for_import (line 1510)
  └─ text = await asyncio.to_thread(_extract_text_from_pdf, buf)   ← 改动①：修复事件循环阻塞
        └─ _extract_text_from_pdf 内部 OCR 回退段（改动②，line 581 前）:
             ├─ ① mineru_service.is_enabled() 且 extract_text_sync(buf) 非 None
             │      → logger.info("[mineru] 解析成功") → return markdown文本
             ├─ ② 失败/超时/禁用 → logger.warning → 走原有
             │      _extract_text_from_scanned_pdf(buf)（PaddleOCR逐页，一字不改）
             └─ ③ 均失败 → return ''（现状行为）
```

**设计理由**：
- `asyncio.to_thread` 卸载使 3 分钟级解析期间整个 API 服务保持响应（顺手修复存量阻塞隐患）；
- MinerU 层内部吞掉所有异常返回 `None`，绝不向上抛——上层逻辑无需感知新组件的存在即可获得回退保障。

## 五、详细设计

### 5.1 后端新增：`backend/app/services/mineru_service.py`

```python
# 模块级状态
_sem = threading.Semaphore(1)          # GPU 串行锁
_health_cache = {"ts": 0, "data": None}  # 健康检查缓存

def is_enabled() -> bool:
    """MINERU_ENABLED=true 且 MINERU_PYTHON 指向的解释器存在 时为 True。双重校验。"""

def health_check(force: bool = False) -> dict:
    """subprocess 运行 [MINERU_PYTHON, '-m', 'mineru.cli.client', '--version']，
    结果缓存 600s（10min TTL）。返回 {available, version, message}。"""

def extract_text_sync(buf: bytes) -> str | None:
    """核心同步实现（供 asyncio.to_thread 调用）。步骤：
    1. is_enabled() 为 False → return None
    2. _sem.acquire(timeout=60) 失败（并发排队超时）→ log+return None
       （防止并发上传时 GPU 显存争抢 OOM；排队等待不计入 subprocess 超时）
    3. try:
         tmpdir = tempfile.mkdtemp(prefix='mineru_')
         写入 tmpdir/input.pdf
         proc = subprocess.run(
             [MINERU_PYTHON, '-m', 'mineru.cli.client',
              '-p', input_path, '-o', outdir, '-b', MINERU_BACKEND],
             timeout=MINERU_TIMEOUT, capture_output=True,
             env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
         md_files = glob(outdir 递归, '*.md')
         若空 → return None
         读首个 .md 全文（encoding='utf-8'），非空则返回
       except (TimeoutExpired, OSError, Exception) → logger.warning(f"[mineru] ...") → return None
       finally:
         _sem.release(); shutil.rmtree(tmpdir, ignore_errors=True)
    """

async def extract_text_async(buf: bytes) -> str | None:
    """asyncio.wait_for(asyncio.to_thread(extract_text_sync, buf), MINERU_TIMEOUT + 60)
    —— 供未来 async 场景使用；本次主调用点位于 to_thread 线程内，直接用 sync 版本。"""
```

**Windows 编码要点**：子进程 env 强制 `PYTHONUTF8=1`；读输出文件显式 `encoding='utf-8'`，避免 GBK 默认编码乱码。

### 5.2 后端修改：`backend/app/api/v1/question_import.py`

**改动①（line 1556）— 事件循环修复：**
```diff
-            text = _extract_text_from_pdf(buf)
+            text = await asyncio.to_thread(_extract_text_from_pdf, buf)
```

**改动②（line 581-583 前）— 三级回退链插入：**
```python
    # === OCR 回退：检测到扫描件PDF（无文本层）===
    logger.info("PDF文本提取为空，尝试OCR识别扫描件...")
+   # 第一优先：MinerU 高精度版面解析（独立venv子进程，GPU加速）
+   if mineru_service.is_enabled():
+       mineru_text = mineru_service.extract_text_sync(buf)
+       if mineru_text:
+           logger.info(f"[mineru] 解析成功: {len(mineru_text)}字符")
+           return mineru_text
+       logger.warning("[mineru] 解析失败/超时/空输出，回退PaddleOCR逐页路径")
    # 保底：原有PaddleOCR路径（保持一字不改）
    ocr_text = _extract_text_from_scanned_pdf(buf)
```

文件头部新增 `from ..services import mineru_service` 与 `import asyncio`。

### 5.3 可选健康巡检端点

`GET /api/questions/import/mineru-health` → 调用 `mineru_service.health_check()`，供运维巡检与前端诊断，不影响导入主流程。

### 5.4 配置项（`backend/config.py` + `.env.example` / `.env`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MINERU_ENABLED` | `false` | 总开关，默认关闭保证合入即零行为变化 |
| `MINERU_PYTHON` | `D:\mineru-env\Scripts\python.exe` | 独立 venv 解释器绝对路径 |
| `MINERU_TIMEOUT` | `300` | 单份文档子进程超时（秒） |
| `MINERU_BACKEND` | `pipeline` | MinerU 解析后端（pipeline/hybrid-auto-engine） |

config.py 以 `os.getenv` 读取并提供模块级访问函数，`.env` 缺省时不报错（开关关闭语义）。

### 5.5 运维脚本：`scripts/setup_mineru_env.ps1`

```powershell
# 1. 建 Python 3.12 venv（py launcher 定位）
py -3.12 -m venv D:\mineru-env
# 2. 安装 mineru[all]（含CPU torch）
D:\mineru-env\Scripts\pip install uv
D:\mineru-env\Scripts\uv pip install -U "mineru[all]"
# 3. 强制覆盖为 CUDA 12.4 版 torch（关键步骤，否则仅CPU模式）
D:\mineru-env\Scripts\pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
# 4. ModelScope 下载模型（约3-5GB，一次性）
$env:PYTHONUTF8='1'; D:\mineru-env\Scripts\mineru-models-download -s modelscope -m all
# 5. 自检
& D:\mineru-env\Scripts\python.exe -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

脚本需幂等可重复执行，逐步骤打印进度与失败提示。

### 5.6 自检脚本：`backend/scripts/test_mineru.py`

依次执行：① config 读取校验 ② venv 解释器存在性 ③ `health_check(force=True)` ④ 用仓库内真实扫描样例（或生成简易图片PDF）走 `extract_text_sync` ⑤ 打印字符数与耗时结论。退出码非零表示环境未就绪。

### 5.7 前端修改：`.vtj/vue/question_import.vue`

该页为 VTJ raw 页面（`raw: true`），按规范仅修改 `<script>` 部分：

1. 扫描件相关上传调用的 `fetchWithRetry(..., timeoutMs)` 提升至 `420000`ms（> 300s 子进程超时 + Semaphore 排队缓冲）；
2. 扫描件提示文案（`ocr_hint` 渲染处及上传前提示）更新为："检测到扫描版PDF，正在使用高精度MinerU引擎解析（约1-3分钟），请耐心等待…"；
3. 复用既有 `state.loading` 进度反馈，不新增组件、不动 `<template>` 结构。

### 5.8 测试：`backend/tests/test_mineru_service.py`

mock `subprocess.run`，覆盖五条单测路径：

| 用例 | mock 行为 | 断言 |
|------|----------|------|
| enabled 且成功 | 返回码0 + 产出md | 返回md全文 |
| disabled | 开关false | 直接None，未调用subprocess |
| timeout | 抛 TimeoutExpired | None + warning日志 |
| md空 | 无*.md产物 | None |
| 异常兜底 | 抛任意OSError | None（不上抛） |

另加 `@pytest.mark.slow` 集成测试（默认 skip）：真实扫描PDF完整管线。

## 六、故障矩阵

| 故障场景 | 系统行为 | 影响 |
|---------|---------|------|
| 开关关闭 / venv 缺失 / 模型未下载 | `is_enabled()`=False，静默走旧 PaddleOCR 路径 | 零影响 |
| 子进程超时 300s | TimeoutExpired 捕获 → kill 进程树 → 回退旧路径 | 该文档降级 |
| 输出 md 空/缺失 | 判定失败 → 回退旧路径 | 该文档降级 |
| 并发多份扫描件 | Semaphore(1) 排队；60s 等不到放弃回退 | 后到者降级，防雪崩 |
| 显存不足 OOM | pipeline 后端自动 CPU 降级可用（慢但成功）；Semaphore 防并发 OOM | 性能降级 |

## 七、测试策略汇总

1. **单元**（CI 常跑）：上表五条 mock 路径 + config 解析。
2. **集成**（手动/slow 标记）：真实扫描样例端到端。
3. **回归**：既有 70 个匹配引擎测试不受影响（未触碰 text_parser/matcher）；Playwright 导入流程脚本回归。
4. **验收自检**：`test_mineru.py` 一键环境自检。

## 八、分阶段上线计划

| 阶段 | 动作 | 风险控制 |
|------|------|---------|
| Phase 1 | 合入全部代码，`MINERU_ENABLED=false` | 零行为变化，随时可回滚 |
| Phase 2 | 运维执行 `setup_mineru_env.ps1`（一次性 3-5GB 模型下载） | 独立目录，不触碰主环境 |
| Phase 3 | `test_mineru.py` 自检通过 → 置 `MINERU_ENABLED=true` 重启 | 灰度开关 |
| Phase 4 | 监控日志指标：`[mineru] success/fallback/duration` 计数 | 持续评估，异常即关开关 |

## 九、安全与运维考量

- **注入面**：subprocess 参数全部来自服务端配置与环境内临时文件路径，用户输入（PDF字节流）只落盘为临时文件不进入命令行参数 → 无命令注入面。
- **资源治理**：子进程 timeout 熔断防 worker 挂死；临时目录 finally 必清；Semaphore 防 GPU 并发 OOM。
- **可观测性**：统一 `[mineru]` 日志前缀便于 grep 巡检；health_check TTL 缓存避免探测风暴；可选 health HTTP 端点。
- **版本锁定**：部署完成后在 `docs/` 记录 `D:\mineru-env\Scripts\pip freeze` 输出基线，便于故障复现与升级评估。
- **合规提示**：MinerU 因 PyMuPDF 依赖整体标记 AGPL——本项目主后端已在用 PyMuPDF/fitz 读取 PDF，本集成不新增合规暴露面（内部部署、不分发）。

## 十、开放问题

1. 生产服务器 GPU 具体型号/驱动版本未知——Phase 2 安装时以 `nvidia-smi` 实测为准；若无 NVIDIA GPU，pipeline 后端 CPU 模式仍可用（10页约2-5分钟，需相应调大 `MINERU_TIMEOUT`）。
2. `mineru.cli.client` 模块入口名以实际安装版本的 `--help` 输出为准（v3.x CLI 为 `mineru` 命令，等价 `-m` 调用）；实施时以实测为准并在代码中留注释。
