# MinerU 扫描件PDF OCR集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 集成 MinerU 作为扫描件PDF高精度解析引擎（独立venv子进程），三级回退保证零风险降级，修复既有事件循环阻塞隐患

**Architecture:** 主后端(Python 3.13.5) --asyncio.to_thread--> mineru_service.py(信号量+超时+临时目录) --subprocess--> D:\mineru-env(Python 3.12 venv, GPU pipeline后端) --> 结构化Markdown --> 复用现有智能匹配管线；失败链：MinerU → PaddleOCR逐页(原路径不动) → 空

**Tech Stack:** Python 3.13 FastAPI（主）、Python 3.12 venv + mineru[all] + CUDA torch cu124（隔离环境）、PowerShell（运维脚本）、VTJ Vue3 raw页（前端）

**Spec:** `docs/superpowers/specs/2026-08-22-mineru-scanned-pdf-ocr-design.md`

---

## 文件结构映射

### 后端文件

| 文件路径 | 职责 | 操作 |
|---------|------|------|
| `backend/app/services/mineru_service.py` | 子进程封装层（开关/健康检查/核心解析/信号量） | 创建 |
| `backend/config.py` | MINERU_* 四个配置项读取 | 修改 |
| `backend/app/api/v1/question_import.py` | line 1556 to_thread卸载 + line 581前插入三级回退链 + health端点 | 修改 |
| `scripts/setup_mineru_env.ps1` | 一键建venv装依赖下模型（幂等） | 创建 |
| `backend/scripts/test_mineru.py` | 环境自检脚本 | 创建 |

### 前端文件

| 文件路径 | 职责 | 操作 |
|---------|------|------|
| `.vtj/vue/question_import.vue` | 扫描件上传超时提升至420s + 提示文案（仅改script） | 修改 |

### 测试文件

| 文件路径 | 职责 | 操作 |
|---------|------|------|
| `backend/tests/test_mineru_service.py` | 服务层单测（mock subprocess 五条路径） | 创建 |

---

## Task 1: 配置项与服务骨架（is_enabled / health_check）

**Files:**
- Modify: `backend/config.py`
- Create: `backend/app/services/mineru_service.py`
- Test: `backend/tests/test_mineru_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_mineru_service.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import patch
import pytest

class TestIsEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setenv('MINERU_ENABLED', 'false')
        from app.services import mineru_service as ms
        assert ms.is_enabled() is False

    def test_enabled_but_venv_missing(self, monkeypatch):
        monkeypatch.setenv('MINERU_ENABLED', 'true')
        monkeypatch.setenv('MINERU_PYTHON', r'Z:\nonexistent\python.exe')
        from app.services import mineru_service as ms
        assert ms.is_enabled() is False

    def test_enabled_and_venv_exists(self, monkeypatch, tmp_path):
        fake_py = tmp_path / "python.exe"; fake_py.write_text("")
        monkeypatch.setenv('MINERU_ENABLED', 'true')
        monkeypatch.setenv('MINERU_PYTHON', str(fake_py))
        from app.services import mineru_service as ms
        assert ms.is_enabled() is True

class TestHealthCheck:
    def test_unavailable_when_disabled(self, monkeypatch):
        monkeypatch.setenv('MINERU_ENABLED', 'false')
        from app.services import mineru_service as ms
        ms._health_cache['ts'] = 0; ms._health_cache['data'] = None
        r = ms.health_check(force=True)
        assert r['available'] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_mineru_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.mineru_service'`

- [ ] **Step 3: Implement config + service skeleton**

`backend/config.py` 追加：
```python
# ==================== MinerU 扫描件OCR（默认关闭，灰度启用）====================
MINERU_ENABLED = os.getenv('MINERU_ENABLED', 'false').lower() == 'true'
MINERU_PYTHON = os.getenv('MINERU_PYTHON', r'D:\mineru-env\Scripts\python.exe')
MINERU_TIMEOUT = int(os.getenv('MINERU_TIMEOUT', '300'))
MINERU_BACKEND = os.getenv('MINERU_BACKEND', 'pipeline')
```

创建 `backend/app/services/mineru_service.py`：
```python
"""MinerU 扫描件PDF解析服务 —— 独立venv子进程封装。
设计要点见 docs/superpowers/specs/2026-08-22-mineru-scanned-pdf-ocr-design.md §5.1
任何失败一律返回 None 并记 [mineru] 日志，绝不向上抛异常（上层据此回退旧PaddleOCR路径）。
"""
import glob, logging, os, shutil, subprocess, tempfile, threading, time

logger = logging.getLogger(__name__)
_sem = threading.Semaphore(1)                       # GPU串行锁
_health_cache = {'ts': 0.0, 'data': None}           # {available,version,message}
_HEALTH_TTL = 600.0

def _cfg(name, default=''):
    from ..config import config  # 延迟导入避免循环
    return getattr(config, name, default)

def is_enabled() -> bool:
    if not _cfg('MINERU_ENABLED'):
        return False
    py = _cfg('MINERU_PYTHON')
    return bool(py) and os.path.isfile(py)

def health_check(force: bool = False) -> dict:
    now = time.time()
    if not force and _health_cache['data'] and now - _health_cache['ts'] < _HEALTH_TTL:
        return _health_cache['data']
    data = {'available': False, 'version': None, 'message': ''}
    try:
        if not is_enabled():
            data['message'] = 'MinerU 未启用或解释器路径无效'
            return data
        proc = subprocess.run(
            [_cfg('MINERU_PYTHON'), '-m', 'mineru.cli.client', '--version'],
            capture_output=True, timeout=30,
            env={**os.environ, 'PYTHONUTF8': '1'})
        if proc.returncode == 0:
            data.update(available=True,
                        version=proc.stdout.decode('utf-8', 'ignore').strip()[:100])
        else:
            data['message'] = proc.stderr.decode('utf-8', 'ignore')[:200]
    except Exception as e:                      # noqa: BLE001
        data['message'] = f'{type(e).__name__}: {e}'[:200]
    _health_cache.update(ts=now, data=data)
    logger.info(f"[mineru] health_check: available={data['available']} {data.get('version','')}")
    return data
```

> 注：若 `backend/config.py` 无 `config` 单例对象而是散落常量，则改为 `from ... import config` 后直接取模块属性——以实际文件结构为准，保持延迟导入。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_mineru_service.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

`git add backend/config.py backend/app/services/mineru_service.py backend/tests/test_mineru_service.py && git commit -m "feat(mineru): add config keys and service skeleton with is_enabled/health_check"`

---

## Task 2: extract_text_sync 核心解析（TDD 五条路径）

**Files:**
- Modify: `backend/app/services/mineru_service.py`
- Test: `backend/tests/test_mineru_service.py`（追加）

- [ ] **Step 1: Write the failing tests（追加到同文件）**

```python
class TestExtractTextSync:
    def _buf(self): return b'%PDF-1.4 fake'

    def test_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.setenv('MINERU_ENABLED', 'false')
        from app.services import mineru_service as ms
        with patch.object(ms.subprocess, 'run') as m:
            assert ms.extract_text_sync(self._buf()) is None
            m.assert_not_called()

    def test_success_returns_md_content(self, monkeypatch, tmp_path):
        monkeypatch.setenv('MINERU_ENABLED', 'true')
        monkeypatch.setattr('app.services.mineru_service.is_enabled', lambda: True)
        from app.services import mineru_service as ms
        outdir = tmp_path / 'out'; (outdir / 'x' / 'y').mkdir(parents=True)
        (outdir / 'x' / 'y' / 'result.md').write_text('# 第1题…', encoding='utf-8')
        fake_md = [('mkdir', str(outdir)), ('mkdtemp-return', str(outdir))]
        with patch.object(ms.tempfile, 'mkdtemp', return_value=str(tmp_path / 'work')), \
             patch.object(ms.shutil, 'rmtree'), \
             patch.object(ms.glob, 'glob', return_value=[str(outdir / 'x' / 'y' / 'result.md')]), \
             patch.object(ms.subprocess, 'run') as m:
            m.return_value.returncode = 0
            text = ms.extract_text_sync(self._buf())
        assert text == '# 第1题…'

    def test_timeout_returns_none(self, monkeypatch):
        monkeypatch.setenv('MINERU_ENABLED', 'true'); monkeypatch.setenv('MINERU_TIMEOUT', '300')
        import app.services.mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)
        with patch.object(ms.tempfile, 'mkdtemp', return_value='t'), \
             patch.object(ms.shutil, 'rmtree'), \
             patch.object(ms.subprocess, 'run', side_effect=subprocess.TimeoutExpired(cmd='x', timeout=300)):
            assert ms.extract_text_sync(self._buf()) is None

    def test_empty_md_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv('MINERU_ENABLED', 'true')
        import app.services.mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)
        empty = tmp_path / 'e'; empty.mkdir()
        (empty / 'nothing.md').write_text('', encoding='utf-8')
        with patch.object(ms.tempfile, 'mkdtemp', return_value=str(empty)), \
             patch.object(ms.shutil, 'rmtree'), \
             patch.object(ms.subprocess, 'run') as m:
            m.return_value.returncode = 0
            assert ms.extract_text_sync(self._buf()) is None

    def test_generic_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv('MINERU_ENABLED', 'true')
        import app.services.mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)
        with patch.object(ms.tempfile, 'mkdtemp', side_effect=OSError('disk full')):
            assert ms.extract_text_sync(self._buf()) is None   # 不上抛
```

- [ ] **Step 2: Run to verify fail**（AttributeError: extract_text_sync 不存在）

- [ ] **Step 3: Implement extract_text_sync（含Semaphore排队）**

```python
def extract_text_sync(buf: bytes) -> str | None:
    if not is_enabled():
        return None
    timeout = int(_cfg('MINERU_TIMEOUT') or 300)
    backend = _cfg('MINERU_BACKEND') or 'pipeline'
    if not _sem.acquire(timeout=60):            # 并发排队上限60s，防GPU争抢雪崩
        logger.warning('[mineru] 并发排队超60s，放弃本次解析（将回退旧路径）')
        return None
    tmpdir = None
    try:
        t0 = time.time()
        tmpdir = tempfile.mkdtemp(prefix='mineru_')
        in_pdf = os.path.join(tmpdir, 'input.pdf')
        outdir = os.path.join(tmpdir, 'out')
        with open(in_pdf, 'wb') as f:
            f.write(buf)
        proc = subprocess.run(
            [_cfg('MINERU_PYTHON'), '-m', 'mineru.cli.client',
             '-p', in_pdf, '-o', outdir, '-b', backend],
            capture_output=True, timeout=timeout,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
        md_files = sorted(glob.glob(os.path.join(outdir, '**', '*.md'), recursive=True))
        for p in md_files:
            with open(p, encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                logger.info(f"[mineru] success chars={len(content)} dur={time.time()-t0:.1f}s")
                return content
        logger.warning(f'[mineru] 输出md为空 rc={proc.returncode} dur={time.time()-t0:.1f}s')
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f'[mineru] 子进程超时({timeout}s)，kill并回退')
        return None
    except Exception as e:                      # noqa: BLE001
        logger.warning(f'[mineru] 解析异常 {type(e).__name__}: {e}')
        return None
    finally:
        _sem.release()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
```

> 实施注意①：TimeoutExpired 时 subprocess.run 已自动 kill 子进程，无需手动进程树清理；
> 实施注意②：`-m mineru.cli.client` 入口名按开放问题#2在 Phase 2 实测校正（CLI `mineru` 等价），留注释。

- [ ] **Step 4: Run tests → 9 passed**（4旧+5新）
- [ ] **Step 5: Commit** `feat(mineru): implement extract_text_sync with semaphore, timeout and temp cleanup`

---

## Task 3: 导入管线接入（两处插入点 + 回归保护）

**Files:**
- Modify: `backend/app/api/v1/question_import.py`
- Test: `backend/tests/test_question_import.py`（追加管线级用例）

- [ ] **Step 1: Write failing test（MinerU优先路径 + 失败回退路径）**

```python
class TestScannedPdfMineruFallback:
    """通过 monkeypatch mineru_service 验证 _extract_text_from_pdf 的分支选择"""

    def test_prefers_mineru_when_available(self, monkeypatch):
        import app.api.v1.question_import as qi
        from app.services import mineru_service as ms
        monkeypatch.setattr(qi.mineru_service, 'is_enabled', lambda: True)
        monkeypatch.setattr(qi.mineru_service, 'extract_text_sync', lambda buf: 'MinerU结构化文本')
        # pdfplumber/PyPDF2 都提取不到文本的假PDF字节
        result = qi._extract_text_from_pdf(b'%PDF-1.4 empty')
        assert result == 'MinerU结构化文本'

    def test_falls_back_to_paddleocr_path(self, monkeypatch):
        import app.api.v1.question_import as qi
        monkeypatch.setattr(qi.mineru_service, 'is_enabled', lambda: False)
        monkeypatch.setattr(qi, '_extract_text_from_scanned_pdf', lambda buf: 'PADDLE_FALLBACK')
        result = qi._extract_text_from_pdf(b'%PDF-1.4 empty')
        assert result == 'PADDLE_FALLBACK'
```

> 注：假PDF字节会使 pdfplumber 抛非ImportError异常——实施时确认 `_extract_text_from_pdf` 对损坏字节的现有行为（pdfplumber 异常未被捕获会冒泡）。若如此，用例改走 `patch qi.pdfplumber` 或调整 `_extract_text_from_pdf` 内层捕获范围并在计划执行时如实修正断言。**以"不改变现有非扫描件行为"为最高优先。**

- [ ] **Step 2: Verify fail → Implement 两处改动（严格按规格§5.2 diff）**
  - line 1556: `text = await asyncio.to_thread(_extract_text_from_pdf, buf)`（文件头补 `import asyncio`、`from ..services import mineru_service`）
  - line 581 前：插入 MinerU 优先调用块（规格§5.2 改动②原文）
- [ ] **Step 3: 全量回归**：`python -m pytest tests/ -q` → 既有70+新用例全绿（证明未破坏合并/分离/图片三模式）
- [ ] **Step 4: Commit** `feat(import): route scanned PDFs through MinerU with three-tier fallback`

---

## Task 4: 运维脚本与健康端点

**Files:**
- Create: `scripts/setup_mineru_env.ps1`、`backend/scripts/test_mineru.py`
- Modify: `backend/app/api/v1/question_import.py`（health 端点）

- [ ] **Step 1: setup_mineru_env.ps1（幂等五步，规格§5.5原文，逐步骤echo进度+失败即停）**
- [ ] **Step 2: test_mineru.py 自检五连**：config读取→解释器存在→health_check(force)→样例PDF解析→耗时报告；任一步失败 `sys.exit(1)`
- [ ] **Step 3: health端点**
```python
@router.get('/mineru-health', summary='MinerU引擎健康巡检')
async def mineru_health():
    from ..services import mineru_service
    return mineru_service.health_check(force=False)
```
- [ ] **Step 4: 手动验证**：`python scripts/test_mineru.py`（当前环境预期 exit 1——开关关/venv缺，属正确行为）；pytest 回归全绿
- [ ] **Step 5: Commit** `feat(mineru): add setup script, self-check tool and health endpoint`

---

## Task 5: 前端适配（VTJ raw页规范内）

**Files:**
- Modify: `.vtj/vue/question_import.vue`（仅 `<script>`）

- [ ] **Step 1**: 定位扫描件上传相关 `fetchWithRetry(...)` 调用（分离/合并两处PDF上传），timeoutMs 提升至 `420000`；其余模式超时不动
- [ ] **Step 2**: 扫描件提示文案统一为："检测到扫描版PDF，正在使用高精度MinerU引擎解析（约1-3分钟），请耐心等待…"（含上传中 loading 提示与 `ocr_hint` 渲染分支）
- [ ] **Step 3**: `vtj_vtj_check_consistency(id=question_import)` → versionMatch 必须 true；不一致则 `vtj_vtj_sync_vue_to_dsl` 同步
- [ ] **Step 4: Commit** `feat(frontend): extend scan-PDF upload timeout and MinerU progress hint`

---

## Task 6: 终验与上线交接

- [ ] **Step 1**: 后端全量 `python -m pytest tests/ -q` 全绿；LSP 对新增文件无新增错误
- [ ] **Step 2**: 模拟演练（不开真环境）：置 `MINERU_ENABLED=true` 但指向不存在解释器 → 上传文本层PDF正常快路径；上传扫描件日志出现 `[mineru]` 回退warning且接口不报错 → 还原配置
- [ ] **Step 3**: 更新规格文档附录：记录实测 CLI 入口结论占位（待Phase 2）、`pip freeze` 基线登记位置约定
- [ ] **Step 4**: 最终 Commit + 向用户交付《Phase 2 运维操作手册摘要》（setup脚本用法、开关位置、监控关键字 `[mineru]`、回滚方法=关闭开关重启）

## 验证标准（Definition of Done）
1. 默认配置（开关关）下系统行为与现状 100% 一致（全量回归绿）
2. mock 层面五条故障路径全部返回None并正确回退
3. `to_thread` 卸载后事件循环不再被 OCR 阻塞（Task 3 diff 即证据）
4. VTJ 版本一致性检查通过，前端提示文案可见
5. 运维可依 setup 脚本独立完成环境搭建（幂等）
