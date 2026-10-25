"""MinerU 超时预算（2026-10-25 性能恢复回归）。

背景：MinerU CPU pipeline 实测 71.2s/页，固定 600s 超时使 24 页答案卷
必然被强杀 → MinerU 永远被跳过。本组用例锁定按页放大的预算规则。
"""
from app.services import mineru_service as ms

DEFAULTS = {
    'MINERU_TIMEOUT': 600,
    'MINERU_SECONDS_PER_PAGE': 75,
    'MINERU_TIMEOUT_MAX': 3600,
}


def _patch_cfg(monkeypatch):
    monkeypatch.setattr(ms, '_cfg', lambda name, default=None: DEFAULTS.get(name, default))


def test_unknown_pages_uses_base_timeout(monkeypatch):
    _patch_cfg(monkeypatch)
    assert ms.compute_timeout_seconds(0) == 600


def test_timeout_scales_by_page_count(monkeypatch):
    _patch_cfg(monkeypatch)
    # 24 页答案卷：120 + 75*24 = 1920s，远超固定 600s
    assert ms.compute_timeout_seconds(24) == 1920
    assert ms.compute_timeout_seconds(1) == 600  # 单页仍按 base 600，不缩水


def test_timeout_capped(monkeypatch):
    _patch_cfg(monkeypatch)
    assert ms.compute_timeout_seconds(1000) == 3600
