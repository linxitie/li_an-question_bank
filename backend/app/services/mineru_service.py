"""MinerU 扫描件PDF解析服务 —— 独立venv子进程封装层。

设计规格: docs/superpowers/specs/2026-08-22-mineru-scanned-pdf-ocr-design.md §5.1
实施计划: docs/superpowers/plans/2026-08-22-mineru-scanned-pdf-ocr.md

核心契约（三级回退链的第一级）:
    本模块任何函数**绝不向上抛异常**——失败一律返回 None / available=False
    并记录 `[mineru]` 前缀日志，调用方（question_import._extract_text_from_pdf）
    据此静默回退到既有 PaddleOCR 逐页路径，保证"最差不比现状差"。

环境约束:
    主后端 Python 3.13.5 无法安装 MinerU（其 Windows 上限为 3.12），
    因此通过 MINERU_PYTHON 指向的独立 venv 以子进程方式调用，
    主后端依赖零变更，互不影响。
"""
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import glob

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GPU 串行锁：并发上传扫描件时排队执行，防止显存争抢 OOM。
# 排队等待超过 _SEM_WAIT_SECONDS 直接放弃并回退旧路径（防雪崩）。
# ---------------------------------------------------------------------------
_sem = threading.Semaphore(1)
_SEM_WAIT_SECONDS = 60

# ---------------------------------------------------------------------------
# 健康检查 TTL 缓存：避免每次上传都做一次 --version 子进程探测。
# ---------------------------------------------------------------------------
_health_cache = {'ts': 0.0, 'data': None}
_HEALTH_TTL_SECONDS = 600.0


def _cfg(name: str, default=None):
    """读取 MINERU_* 配置。

    通过 app.core.config.settings 单例（pydantic BaseSettings）读取，
    与项目其他配置保持同一来源；getattr 兜底保证配置键缺失时服务仍可导入。
    """
    try:
        from ..core.config import settings
        return getattr(settings, name, default)
    except Exception as e:  # noqa: BLE001 — 配置系统异常也不允许影响导入链
        logger.warning(f"[mineru] 读取配置 {name} 失败: {type(e).__name__}: {e}")
        return default


def _parser_url() -> str:
    """parser sidecar 地址，未配置时返回空串。"""
    return str(_cfg('PARSER_URL', '') or '').strip()


def is_enabled() -> bool:
    """双重校验：开关开启 且（解释器路径真实存在 或 已配置 parser sidecar）。

    任一不满足即视为禁用——调用方将直接走旧 PaddleOCR 路径（零行为变化）。

    容器化后 MinerU 不在主进程内（Python 3.13 无法安装，Windows 上限 3.12），
    故新增 PARSER_URL 分支：配置了 sidecar 地址即视为可用，
    由 call_parser_http 承担实际调用。未配置时行为与改造前逐字节一致。
    """
    if not _cfg('MINERU_ENABLED', False):
        return False
    if _parser_url():
        return True
    py = _cfg('MINERU_PYTHON', '') or ''
    if not py or not os.path.isfile(py):
        return False
    return True


def call_parser_http(buf: bytes) -> str | None:
    """走 parser sidecar 的 HTTP 路径。

    与 extract_text_sync 相同的失败契约：任何失败返回 None，调用方静默回退。
    这里额外保留 GPU 串行锁 —— 锁虽已跨进程失效，但串行化请求仍能避免
    sidecar 被并发推理请求打爆显存。
    """
    url = _parser_url()
    if not url:
        return None

    timeout = int(_cfg('MINERU_TIMEOUT', 300) or 300)
    endpoint = url.rstrip('/') + '/parse'

    if not _sem.acquire(timeout=_SEM_WAIT_SECONDS):
        logger.warning(
            f'[mineru] GPU锁排队超过{_SEM_WAIT_SECONDS}s，放弃本次sidecar解析'
            f'（将回退旧OCR路径）')
        return None

    try:
        import requests  # 延迟导入：保持模块顶层 import 面最小
    except ImportError as e:
        logger.warning(f'[mineru] requests 不可用({e}) → 回退旧OCR路径')
        _sem.release()
        return None

    try:
        t0 = time.time()
        resp = requests.post(
            endpoint,
            files={'file': ('input.pdf', buf, 'application/pdf')},
            timeout=(15, timeout),
        )
        if resp.status_code != 200:
            logger.warning(
                f'[mineru] sidecar HTTP {resp.status_code} '
                f'body={resp.text[:200]} → 回退旧OCR路径')
            return None

        try:
            data = resp.json()
        except ValueError:
            logger.warning('[mineru] sidecar 返回非 JSON → 回退旧OCR路径')
            return None

        content = str(data.get('markdown') or '').strip()
        if not content:
            logger.warning('[mineru] sidecar markdown 为空 → 回退旧OCR路径')
            return None

        dur = time.time() - t0
        logger.info(f'[mineru] sidecar success chars={len(content)} dur={dur:.1f}s')
        return content

    except Exception as e:  # noqa: BLE001 — 兜底契约：绝不上抛
        logger.warning(
            f'[mineru] sidecar 异常 {type(e).__name__}: {e} → 回退旧OCR路径')
        return None
    finally:
        _sem.release()


def health_check(force: bool = False) -> dict:
    """探测独立venv中的 MinerU 是否可用（--version），结果缓存10分钟。

    返回: {'available': bool, 'version': str|None, 'message': str}
    供运维巡检端点与 test_mineru.py 自检脚本使用；不影响导入主流程。
    """
    global _health_cache
    now = time.time()
    cached = _health_cache.get('data')
    if not force and cached and (now - _health_cache.get('ts', 0.0)) < _HEALTH_TTL_SECONDS:
        return cached

    data = {'available': False, 'version': None, 'message': ''}
    try:
        if not is_enabled():
            data['message'] = 'MinerU 未启用或解释器路径无效'
        else:
            py = str(_cfg('MINERU_PYTHON', '') or '')
            proc = subprocess.run(
                [py, '-m', 'mineru.cli.client', '--version'],
                capture_output=True,
                timeout=30,
                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                 'MINERU_MODEL_SOURCE': 'modelscope'},
            )
            if proc.returncode == 0:
                data['available'] = True
                data['version'] = proc.stdout.decode('utf-8', 'ignore').strip()[:100]
            else:
                data['message'] = (
                    'exit=' + str(proc.returncode) + ' '
                    + proc.stderr.decode('utf-8', 'ignore')[:200]
                )
    except Exception as e:  # noqa: BLE001 — 探测失败仅报告，不上抛
        data['message'] = f'{type(e).__name__}: {e}'[:200]

    _health_cache = {'ts': now, 'data': data}
    logger.info(
        f"[mineru] health_check: available={data['available']} "
        f"version={data.get('version') or '-'} msg={data['message'][:80]}"
    )
    return data


# ---------------------------------------------------------------------------
# CLI 入口说明（规格 开放问题#2）:
#   v3.x 提供 `mineru` 命令行，等价于 `-m mineru.cli.client`。
#   Phase 2 环境安装后以实测为准；若入口不同仅需修改 _CLI_MODULE 常量。
# ---------------------------------------------------------------------------
_CLI_MODULE = 'mineru.cli.client'


def extract_text_sync(buf: bytes) -> str | None:
    """核心解析：扫描件PDF字节 → MinerU结构化Markdown文本。

    失败契约：任何失败路径返回 None（禁用/排队超时/子进程超时/输出为空/任意异常），
    调用方据此回退旧 PaddleOCR 路径。GPU 串行锁保证同一时刻仅一份文档占用推理资源。

    流程: mkdtemp → 落盘input.pdf → subprocess(mineru, timeout) → 收集*.md(按序首个非空)
          → finally 释放信号量 + rmtree 清理临时目录
    """
    if not is_enabled():
        return None

    # 容器化路径：已配置 sidecar 时优先走 HTTP。未配置则此段整体跳过，
    # 行为与改造前逐字节一致。
    if _parser_url():
        content = call_parser_http(buf)
        if content:
            return content
        logger.info('[mineru] sidecar 未产出内容，改走本地子进程')

    timeout = int(_cfg('MINERU_TIMEOUT', 300) or 300)
    backend = str(_cfg('MINERU_BACKEND', 'pipeline') or 'pipeline')
    py = str(_cfg('MINERU_PYTHON', '') or '')

    # GPU 串行锁：并发扫描件上传时排队；等待超限直接放弃，避免请求堆积雪崩
    if not _sem.acquire(timeout=_SEM_WAIT_SECONDS):
        logger.warning(
            f'[mineru] GPU锁排队超过{_SEM_WAIT_SECONDS}s，放弃本次解析（将回退旧OCR路径）')
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
            [py, '-m', _CLI_MODULE,
             '-p', in_pdf, '-o', outdir, '-b', backend],
            capture_output=True,
            timeout=timeout,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                 'MINERU_MODEL_SOURCE': 'modelscope'},
        )

        md_files = sorted(glob.glob(os.path.join(outdir, '**', '*.md'), recursive=True))
        for p in md_files:
            with open(p, encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                dur = time.time() - t0
                logger.info(f"[mineru] success chars={len(content)} dur={dur:.1f}s")
                return content

        logger.warning(
            f'[mineru] 输出md为空/缺失 rc={proc.returncode} '
            f'dur={time.time() - t0:.1f}s → 回退旧OCR路径')
        return None

    except subprocess.TimeoutExpired:
        logger.warning(f'[mineru] 子进程超时({timeout}s)，已终止 → 回退旧OCR路径')
        return None
    except Exception as e:  # noqa: BLE001 — 兜底契约：绝不上抛
        logger.warning(f'[mineru] 解析异常 {type(e).__name__}: {e} → 回退旧OCR路径')
        return None
    finally:
        _sem.release()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 增强图片文字提取能力
# ---------------------------------------------------------------------------

def extract_text_from_image(image_path: str) -> str | None:
    """使用Tesseract提取图片中的文字（增强OCR能力）
    
    参数：
        image_path: 图片文件路径
    
    返回：
        提取的文字，失败返回None
    """
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageEnhance
        
        # 打开图片
        img = Image.open(image_path)
        
        # 图片预处理
        # 1. 转灰度
        img = img.convert('L')
        
        # 2. 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # 3. 锐化
        img = img.filter(ImageFilter.SHARPEN)
        
        # 4. 二值化
        threshold = 128
        img = img.point(lambda p: p > threshold and 255)
        
        # 5. 提取文字（支持中英文）
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        
        return text.strip() if text else None
        
    except ImportError:
        logger.warning("[mineru] pytesseract未安装，图片文字提取功能不可用")
        return None
    except Exception as e:
        logger.warning(f"[mineru] 图片文字提取异常: {type(e).__name__}: {e}")
        return None


def extract_text_from_image_bytes(image_bytes: bytes) -> str | None:
    """从图片字节中提取文字
    
    参数：
        image_bytes: 图片字节数据
    
    返回：
        提取的文字，失败返回None
    """
    import tempfile
    import os
    
    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp(prefix='ocr_')
        tmp_path = os.path.join(tmpdir, 'image.png')
        with open(tmp_path, 'wb') as f:
            f.write(image_bytes)
        return extract_text_from_image(tmp_path)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
