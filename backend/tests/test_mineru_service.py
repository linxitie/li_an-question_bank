"""MinerU 扫描件OCR服务单元测试。

覆盖设计规格 docs/superpowers/specs/2026-08-22-mineru-scanned-pdf-ocr-design.md：
- is_enabled 双重校验（开关 + 解释器路径）
- health_check TTL缓存与禁用语义
- extract_text_sync 五条故障/成功路径（mock subprocess，见 Task 2）

注意：项目配置为 pydantic BaseSettings 单例（导入时读env），
因此测试通过 monkeypatch.setattr(settings, ...) 注入配置而非 setenv。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from unittest.mock import patch

import pytest


def _cfg(monkeypatch, **kwargs):
    """向 settings 单例注入 MINERU_* 配置（测试结束自动还原）。"""
    from app.core.config import settings
    defaults = {
        'MINERU_ENABLED': False,
        'MINERU_PYTHON': r'D:\mineru-env\Scripts\python.exe',
        'MINERU_TIMEOUT': 300,
        'MINERU_BACKEND': 'pipeline',
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        monkeypatch.setattr(settings, k, v, raising=False)
    return settings


class TestIsEnabled:
    def test_disabled_by_default(self, monkeypatch):
        _cfg(monkeypatch, MINERU_ENABLED=False)
        from app.services import mineru_service as ms
        assert ms.is_enabled() is False

    def test_enabled_but_interpreter_missing(self, monkeypatch, tmp_path):
        _cfg(monkeypatch, MINERU_ENABLED=True,
             MINERU_PYTHON=str(tmp_path / 'nonexistent' / 'python.exe'))
        from app.services import mineru_service as ms
        assert ms.is_enabled() is False

    def test_enabled_and_interpreter_exists(self, monkeypatch, tmp_path):
        fake_py = tmp_path / 'python.exe'
        fake_py.write_text('', encoding='utf-8')
        _cfg(monkeypatch, MINERU_ENABLED=True, MINERU_PYTHON=str(fake_py))
        from app.services import mineru_service as ms
        assert ms.is_enabled() is True

    def test_enabled_with_empty_path(self, monkeypatch):
        _cfg(monkeypatch, MINERU_ENABLED=True, MINERU_PYTHON='')
        from app.services import mineru_service as ms
        assert ms.is_enabled() is False


class TestHealthCheck:
    def setup_method(self):
        # 每条用例前清空TTL缓存，避免用例间串扰
        from app.services import mineru_service as ms
        ms._health_cache['ts'] = 0.0
        ms._health_cache['data'] = None

    def test_unavailable_when_disabled(self, monkeypatch):
        _cfg(monkeypatch, MINERU_ENABLED=False)
        from app.services import mineru_service as ms
        r = ms.health_check(force=True)
        assert r['available'] is False
        assert not r['version']

    def test_available_when_version_ok(self, monkeypatch, tmp_path):
        fake_py = tmp_path / 'python.exe'
        fake_py.write_text('', encoding='utf-8')
        _cfg(monkeypatch, MINERU_ENABLED=True, MINERU_PYTHON=str(fake_py))
        from app.services import mineru_service as ms

        proc = type('P', (), {})()
        proc.returncode = 0
        proc.stdout = b'mineru 3.4.5'
        proc.stderr = b''
        with patch.object(ms.subprocess, 'run', return_value=proc) as m:
            r = ms.health_check(force=True)
        assert r['available'] is True
        assert r['version'] == 'mineru 3.4.5'
        m.assert_called_once()

    def test_ttl_cache_prevents_repeat_probe(self, monkeypatch):
        from app.services import mineru_service as ms
        ms._health_cache['ts'] = __import__('time').time()  # 刚刚探测过
        ms._health_cache['data'] = {'available': True, 'version': 'cached', 'message': ''}
        r = ms.health_check(force=False)  # 不force → 直接命中缓存
        assert r['version'] == 'cached'

    def test_probe_exception_reported_not_raised(self, monkeypatch, tmp_path):
        fake_py = tmp_path / 'python.exe'
        fake_py.write_text('', encoding='utf-8')
        _cfg(monkeypatch, MINERU_ENABLED=True, MINERU_PYTHON=str(fake_py))
        from app.services import mineru_service as ms
        with patch.object(ms.subprocess, 'run',
                          side_effect=OSError('spawn failed')):
            r = ms.health_check(force=True)
        assert r['available'] is False
        assert 'OSError' in r['message']
