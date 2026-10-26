"""WS 协议 v2 单测：序号、作用域、信封兼容性与去重判定。"""
import pytest

from app.foundation.ws_protocol import (
    GLOBAL_SCOPE,
    SEQ_KEY,
    SeqAllocator,
    build_envelope,
    derive_scope,
    is_newer,
)


def test_fallback_seq_is_monotonic_for_1000_calls():
    ticks = iter([1000.0] * 1000)  # 时钟不前进也不能产生重复序号
    alloc = SeqAllocator(clock=lambda: next(ticks))
    seqs = [alloc.next() for _ in range(1000)]

    assert seqs == sorted(seqs)
    assert len(set(seqs)) == 1000


def test_redis_increment_is_used_and_failure_degrades():
    calls = []

    def incr(key):
        calls.append(key)
        return 42

    alloc = SeqAllocator(increment=incr)
    assert alloc.next() == 42
    assert calls == [SEQ_KEY]
    assert alloc.degraded is False

    def broken(key):
        raise ConnectionError("redis down")

    alloc = SeqAllocator(increment=broken, clock=lambda: 1.0)
    assert alloc.next() == 1000
    assert alloc.degraded is True


def test_scope_derivation():
    assert derive_scope() == GLOBAL_SCOPE
    assert derive_scope("exam") == "exam"
    assert derive_scope("exam", "paper") == "exam.paper"
    assert derive_scope("exam", "paper", 7) == "exam.paper.7"
    assert derive_scope(explicit="global") == "global"


def test_envelope_keeps_legacy_fields_and_adds_v2():
    msg = build_envelope(
        "data-changed",
        seq=9,
        data={"domain": "exam", "type": "paper.published", "id": 7},
        domain="exam",
        entity="paper.published",
        entity_id=7,
        scope="exam.paper.published",
        origin="worker-a",
        timestamp="2026-10-26T00:00:00",
    )

    assert msg["v"] == 2
    assert msg["type"] == "data-changed"
    assert msg["seq"] == 9
    assert msg["scope"] == "exam.paper.published"
    assert msg["domain"] == "exam"
    assert msg["entity"] == "paper.published"
    assert msg["id"] == 7
    assert msg["origin"] == "worker-a"
    # 旧客户端依赖的三个键
    assert msg["data"] == {"domain": "exam", "type": "paper.published", "id": 7}
    assert msg["timestamp"] == "2026-10-26T00:00:00"


def test_sync_envelope_scope_falls_back_to_global():
    msg = build_envelope("sync", seq=1, data={"message": "刷新"})
    assert msg["scope"] == GLOBAL_SCOPE
    assert msg["data"] == {"message": "刷新"}


def test_is_newer():
    assert is_newer(None, 1) is True
    assert is_newer(1, 2) is True
    assert is_newer(2, 2) is False
    assert is_newer(2, 1) is False
    assert is_newer(2, "bad") is False
    assert is_newer(2, "3") is True
