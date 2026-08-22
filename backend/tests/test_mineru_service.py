"""MinerU 扫描件OCR服务单元测试。

覆盖设计规格 docs/superpowers/specs/2026-08-22-mineru-scanned-pdf-ocr-design.md：
- is_enabled 双重校验（开关 + 解释器路径）
- health_check TTL缓存与禁用语义
- extract_text_sync 五条故障/成功路径（mock subprocess，见 Task 2）

注意：项目配置为 pydantic BaseSettings 单例（导入时读env），
因此测试通过 monkeypatch.setattr(settings, ...) 注入配置而非 setenv。
"""
import os
import subprocess
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


class TestExtractTextSync:
    """extract_text_sync 五条路径（mock subprocess，规格§5.1 / 计划Task2）。"""

    def _buf(self) -> bytes:
        return b'%PDF-1.4 fake-scanned-bytes'

    def test_returns_none_when_disabled_and_never_spawns_process(self, monkeypatch):
        _cfg(monkeypatch, MINERU_ENABLED=False)
        from app.services import mineru_service as ms
        with patch.object(ms.subprocess, 'run') as m_run:
            assert ms.extract_text_sync(self._buf()) is None
            m_run.assert_not_called()

    def test_success_returns_md_content(self, monkeypatch, tmp_path):
        _cfg(monkeypatch, MINERU_ENABLED=True)
        from app.services import mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)

        # 真实工作目录（让 input.pdf 落盘真实发生），md 产物放在外部目录
        # 注: 真实 tempfile.mkdtemp 返回"已存在"的目录，故此处须先创建
        workdir = tmp_path / 'work'
        workdir.mkdir()
        out_md = tmp_path / 'out' / 'sub' / 'result.md'
        out_md.parent.mkdir(parents=True)
        out_md.write_text('# 第1题 题干\nA. 选项', encoding='utf-8')

        with patch.object(ms.tempfile, 'mkdtemp', return_value=str(workdir)), \
             patch.object(ms.glob, 'glob',
                          return_value=[str(out_md)]) as m_glob, \
             patch.object(ms.subprocess, 'run') as m_run:
            m_run.return_value.returncode = 0
            text = ms.extract_text_sync(self._buf())

        assert text == '# 第1题 题干\nA. 选项'
        # 校验命令行构造：解释器 + -m 入口 + -p/-o/-b 参数
        argv = m_run.call_args.args[0]
        assert argv[1:3] == ['-m', 'mineru.cli.client']
        assert '-p' in argv and '-o' in argv and '-b' in argv
        assert m_glob.call_args.kwargs.get('recursive') is True
        # 工作目录已被清理（finally rmtree）
        assert not workdir.exists()
        # 信号量已释放
        assert ms._sem._value == 1

    def test_timeout_returns_none_and_cleans_up(self, monkeypatch, tmp_path):
        _cfg(monkeypatch, MINERU_ENABLED=True, MINERU_TIMEOUT=300)
        from app.services import mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)
        workdir = tmp_path / 'work'

        with patch.object(ms.tempfile, 'mkdtemp', return_value=str(workdir)), \
             patch.object(ms.subprocess, 'run',
                          side_effect=subprocess.TimeoutExpired(cmd='mineru', timeout=300)):
            assert ms.extract_text_sync(self._buf()) is None
        assert not workdir.exists()
        assert ms._sem._value == 1

    def test_empty_md_output_returns_none(self, monkeypatch, tmp_path):
        _cfg(monkeypatch, MINERU_ENABLED=True)
        from app.services import mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)
        workdir = tmp_path / 'work'
        empty_md = tmp_path / 'out' / 'empty.md'
        empty_md.parent.mkdir(parents=True)
        empty_md.write_text('   \n  ', encoding='utf-8')  # 仅空白 → 视为空

        with patch.object(ms.tempfile, 'mkdtemp', return_value=str(workdir)), \
             patch.object(ms.glob, 'glob', return_value=[str(empty_md)]), \
             patch.object(ms.subprocess, 'run') as m_run:
            m_run.return_value.returncode = 0
            assert ms.extract_text_sync(self._buf()) is None
        assert ms._sem._value == 1

    def test_generic_exception_returns_none_not_raised(self, monkeypatch):
        _cfg(monkeypatch, MINERU_ENABLED=True)
        from app.services import mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)
        with patch.object(ms.tempfile, 'mkdtemp', side_effect=OSError('disk full')):
            assert ms.extract_text_sync(b'x') is None  # 不上抛
        # mkdtemp 在 acquire 之后失败也必须释放信号量
        assert ms._sem._value == 1

    def test_semaphore_queue_timeout_returns_none(self, monkeypatch):
        """GPU锁被长期占用时，等待60s超时后放弃（防并发雪崩）。"""
        _cfg(monkeypatch, MINERU_ENABLED=True)
        from app.services import mineru_service as ms
        monkeypatch.setattr(ms, 'is_enabled', lambda: True)
        monkeypatch.setattr(ms, '_SEM_WAIT_SECONDS', 0.05)  # 缩短测试等待
        with ms._sem:  # 模拟另一份文档正在占用GPU
            assert ms.extract_text_sync(self._buf()) is None
