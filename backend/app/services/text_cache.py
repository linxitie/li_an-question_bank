# -*- coding: utf-8 -*-
"""
text_cache.py — 文档提取文本缓存（按文件内容 md5）

动机（20 份真实语料实测）：
    解析计算      0.10–0.22 s / 100 题
    文本层 PDF    5–9 s / 17 页
    扫描件 PDF    260 s / 24 页   ← 唯一数量级瓶颈（MinerU OCR）
重复导入同一份文件时，耗时 99.6% 都在提取层，且每次全额重付。
按文件内容 md5 缓存提取文本后，命中耗时 ~0.02s（4 个数量级）。

设计约束：
    1. 纯加速层，不是正确性依赖 —— 任何异常一律吞掉并降级为"无缓存"，
       绝不影响导入主流程。
    2. 只缓存成功产出的文本 —— 空结果不写，否则会把一次偶发失败
       固化成"永久失败"（每次导入都命中这个空缓存）。
    3. 原子写（临时文件 + os.replace）—— 避免并发导入时读到半截文件。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _setting(name: str, default: Any = None) -> Any:
    """安全读取 settings 属性（配置缺失/导入期异常时返回默认值）。"""
    try:
        from ..core.config import settings
        return getattr(settings, name, default)
    except Exception:  # noqa: BLE001 — 配置不可用时按未启用处理
        return default


def _cache_dir() -> str:
    raw = str(_setting("TEXT_CACHE_DIR", "./data/text_cache") or "./data/text_cache")
    if not os.path.isabs(raw):
        # 相对路径以 backend/ 为基准（与 SQLITE_PATH=./data/... 的约定一致）
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        raw = os.path.join(backend_root, raw)
    return os.path.normpath(raw)


def enabled() -> bool:
    return bool(_setting("TEXT_CACHE_ENABLED", True))


def cache_key(buf: bytes, scope: str = '') -> str:
    """文件内容 md5 + 引擎作用域，带版本前缀。

    版本前缀（2026-10-13 SMask 修复）：提取算法升级后旧缓存必须整体失效——
    旧缓存的 [IMAGE:marker] 指向修复前生成的黑图文件，命中即黑块再现。

    scope（2026-10-25）：MinerU 与 PaddleOCR 的识别质量不同，同一份 PDF
    在「启用 MinerU」与「只用 Paddle」下必须各自缓存。否则关掉 MinerU 后
    仍会命中 MinerU 的旧结果（反过来也一样），表现为"配置改了没生效"。
    """
    suffix = ('_' + scope) if scope else ''
    return 'v3' + suffix + '_' + hashlib.md5(buf or b"").hexdigest()


def _paths(key: str):
    d = _cache_dir()
    return os.path.join(d, f'{key}.txt'), os.path.join(d, f'{key}.json')


def _read_legacy(buf: bytes, scope: str) -> Optional[str]:
    """兼容旧的无作用域缓存（v3_<md5>），但只在引擎一致时放行。

    旧条目写入时 meta 里带 `engine`；若与当前 scope 不符，说明这份文本是
    另一种引擎产出的，宁可重跑也不能错用。
    """
    txt_path, meta_path = _paths(cache_key(buf))
    if not os.path.exists(txt_path):
        return None
    engine = ''
    try:
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as fh:
                engine = str(json.load(fh).get('engine') or '')
    except Exception:  # noqa: BLE001
        engine = ''
    if scope and engine and engine != scope:
        return None
    with open(txt_path, 'r', encoding='utf-8') as fh:
        text = fh.read()
    if not text.strip():
        return None
    logger.info(f"[text-cache] 命中旧缓存 {cache_key(buf)[:12]} engine={engine or '-'}")
    return text


def get(buf: bytes, scope: str = '') -> Optional[str]:
    """命中返回提取文本；未命中或任何异常返回 None（调用方走原路径）。"""
    if not enabled() or not buf:
        return None
    try:
        txt_path, _ = _paths(cache_key(buf, scope))
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as fh:
                text = fh.read()
            if text.strip():
                logger.info(f"[text-cache] 命中 {cache_key(buf, scope)[:12]} ({len(text)} 字符)")
                return text
        if scope:
            legacy = _read_legacy(buf, scope)
            if legacy:
                return legacy
        return None
    except Exception as e:  # noqa: BLE001 — 缓存是纯加速层，失败即降级
        logger.warning(f"[text-cache] 读取失败（降级为无缓存）: {e}")
        return None


def put(buf: bytes, text: str, meta: Optional[Dict[str, Any]] = None,
        scope: str = '') -> bool:
    """写入缓存。空文本不写（避免固化偶发失败）。返回是否成功写入。"""
    if not enabled() or not buf or not text or not text.strip():
        return False
    try:
        d = _cache_dir()
        os.makedirs(d, exist_ok=True)
        key = cache_key(buf, scope)
        txt_path, meta_path = _paths(key)

        payload = {
            'key': key,
            'bytes': len(buf),
            'chars': len(text),
            'cached_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        if meta:
            try:
                payload.update({k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))})
            except Exception:  # noqa: BLE001
                pass

        # 原子写：同目录临时文件 + os.replace，避免并发读到半截内容
        for path, content in (
            (txt_path, text),
            (meta_path, json.dumps(payload, ensure_ascii=False, indent=1)),
        ):
            fd, tmp = tempfile.mkstemp(dir=d, prefix='.tmp_', suffix='.part')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                os.replace(tmp, path)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

        logger.info(f"[text-cache] 已缓存 {key[:12]} ({len(text)} 字符)")
        return True
    except Exception as e:  # noqa: BLE001 — 写缓存失败不影响本次导入
        logger.warning(f"[text-cache] 写入失败（已忽略）: {e}")
        return False


def stats() -> Dict[str, Any]:
    """缓存概况（便于排查，不参与导入主流程）。"""
    out = {'enabled': enabled(), 'dir': _cache_dir(), 'entries': 0, 'bytes': 0}
    try:
        d = _cache_dir()
        if not os.path.isdir(d):
            return out
        for name in os.listdir(d):
            if name.endswith('.txt'):
                out['entries'] += 1
                try:
                    out['bytes'] += os.path.getsize(os.path.join(d, name))
                except OSError:
                    pass
    except Exception as e:  # noqa: BLE001
        out['error'] = str(e)
    return out
