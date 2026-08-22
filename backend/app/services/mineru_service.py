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
import subprocess
import threading
import time

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


def is_enabled() -> bool:
    """双重校验：开关开启 且 解释器路径真实存在。

    任一不满足即视为禁用——调用方将直接走旧 PaddleOCR 路径（零行为变化）。
    """
    if not _cfg('MINERU_ENABLED', False):
        return False
    py = _cfg('MINERU_PYTHON', '') or ''
    if not py or not os.path.isfile(py):
        return False
    return True


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
                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
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
