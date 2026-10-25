"""提取文本缓存的作用域隔离（2026-10-25 导入链路事故回归）。

事故：缓存键只含文件 md5，MinerU 与 PaddleOCR 的结果互相污染——
关掉 MinerU 仍命中 MinerU 的旧文本，表现为"配置改了没生效"。
本组用例锁定：不同引擎作用域互不可见；旧版无作用域缓存在引擎一致时仍可复用。
"""
import hashlib
import json
import os

from app.services import text_cache

BUF = b'%PDF-1.4 demo-bytes'


def _patch_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(text_cache, '_cache_dir', lambda: str(tmp_path))


def test_put_then_get_same_scope(monkeypatch, tmp_path):
    _patch_dir(monkeypatch, tmp_path)
    assert text_cache.put(BUF, 'MinerU文本', {'engine': 'mineru'}, scope='mineru')
    assert text_cache.get(BUF, scope='mineru') == 'MinerU文本'


def test_scope_isolation(monkeypatch, tmp_path):
    _patch_dir(monkeypatch, tmp_path)
    text_cache.put(BUF, 'MinerU文本', {'engine': 'mineru'}, scope='mineru')
    # 换到 Paddle 作用域：绝不能命中 MinerU 的结果
    assert text_cache.get(BUF, scope='paddle') is None


def test_cache_key_differs_by_scope():
    assert text_cache.cache_key(BUF, 'mineru') != text_cache.cache_key(BUF, 'paddle')
    assert text_cache.cache_key(BUF, 'mineru').startswith('v3_mineru_')


def test_legacy_unscoped_entry_reused_when_engine_matches(monkeypatch, tmp_path):
    _patch_dir(monkeypatch, tmp_path)
    # 模拟旧版缓存：v3_<md5>.txt + meta
    key = 'v3_' + hashlib.md5(BUF).hexdigest()
    with open(os.path.join(str(tmp_path), key + '.txt'), 'w', encoding='utf-8') as fh:
        fh.write('旧版Paddle文本')
    with open(os.path.join(str(tmp_path), key + '.json'), 'w', encoding='utf-8') as fh:
        json.dump({'engine': 'paddle'}, fh)

    assert text_cache.get(BUF, scope='paddle') == '旧版Paddle文本'
    # 引擎不一致时必须忽略旧缓存，宁可重跑
    assert text_cache.get(BUF, scope='mineru') is None
