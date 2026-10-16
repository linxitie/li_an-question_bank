"""跨域事件契约与 Redis Stream 发布/订阅。

定位：十个业务域之间**不直接互相调用**，异步副作用一律经事件总线传递
（见设计规格 §3.2「跨域只走契约与事件」）。本模块只负责事件的
类型定义、发布与订阅，不含任何业务逻辑。

可用性契约
----------
Redis 在当前部署中**默认缺席**（`REDIS_URL` 恒有默认值，故不能靠判空识别缺席）。
因此：

- 可用性由**实际连通性探测**得出，结果按 TTL 缓存，避免每次发布都去握手；
- 探测失败时发布退化为 no-op（记日志、返回 ``False``），**绝不抛出**；
- 订阅侧在 Redis 缺席时直接返回，不阻塞调用方。

这条契约让 P5 启用事件总线之前，本模块可以安全地被导入而不产生任何副作用。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

# ── 事件名 ────────────────────────────────────────────────
# 命名域.动作，全小写点分。改动等同于改契约，须走契约评审。
EV_QUESTION_IMPORTED = "catalog.question.imported"
EV_PAPER_PUBLISHED = "catalog.paper.published"
EV_EXAM_SUBMITTED = "exam.exam.submitted"
EV_EXAM_GRADED = "exam.exam.graded"
EV_COINS_AWARDED = "reward.coins.awarded"
EV_GOAL_PROGRESSED = "growth.goal.progressed"
EV_MATERIAL_PUBLISHED = "library.material.published"
EV_USER_UPDATED = "identity.user.updated"

ALL_EVENTS = (
    EV_QUESTION_IMPORTED, EV_PAPER_PUBLISHED, EV_EXAM_SUBMITTED, EV_EXAM_GRADED,
    EV_COINS_AWARDED, EV_GOAL_PROGRESSED, EV_MATERIAL_PUBLISHED, EV_USER_UPDATED,
)

STREAM_MAXLEN = 1000
STREAM_IDLE_MS = 24 * 3600 * 1000

_PROBE_TTL_SECONDS = 30.0
_probe_cache: dict[str, tuple[bool, float]] = {}


@dataclass(frozen=True)
class Event:
    """一条跨域事件。

    ``aggregate_id`` 指向事件的主体（如 paper_id、exam_id），供订阅方按主体
    过滤，避免每个订阅者都消费全量流。
    """

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    aggregate_id: str = ""
    source: str = ""

    def to_stream_fields(self, event_id: str) -> dict[str, str]:
        return {
            "event_id": event_id,
            "name": self.name,
            "aggregate_id": self.aggregate_id,
            "source": self.source,
            "payload": json.dumps(self.payload, ensure_ascii=False, default=str),
        }

    @classmethod
    def from_stream(cls, fields: dict[str, str]) -> Optional["Event"]:
        name = fields.get("name") or ""
        if name not in ALL_EVENTS:
            return None
        try:
            payload = json.loads(fields.get("payload") or "{}")
        except (TypeError, ValueError):
            payload = {}
        return cls(
            name=name,
            payload=payload if isinstance(payload, dict) else {},
            aggregate_id=fields.get("aggregate_id") or "",
            source=fields.get("source") or "",
        )


async def _client():
    from .redis_client import get_redis
    return await get_redis()


async def is_available(force: bool = False) -> bool:
    """探测 Redis 是否可用，结果按 TTL 缓存。"""
    now = time.time()
    if not force:
        cached = _probe_cache.get("ok")
        if cached and (now - cached[1]) < _PROBE_TTL_SECONDS:
            return cached[0]
    try:
        r = await _client()
        await r.ping()
        ok = True
    except Exception as e:  # noqa: BLE001 — 探测失败即视为缺席，不得上抛
        logger.debug(f"[events] Redis 探测失败，事件总线按缺席处理: "
                     f"{type(e).__name__}: {e}")
        ok = False
    _probe_cache["ok"] = (ok, now)
    return ok


async def publish(event: Event) -> bool:
    """发布一条事件。Redis 缺席或失败时返回 ``False``，绝不抛出。"""
    if event.name not in ALL_EVENTS:
        raise ValueError(f"未注册的事件名: {event.name}")
    if not await is_available():
        return False
    event_id = uuid.uuid4().hex
    try:
        r = await _client()
        await r.xadd(
            f"events:{event.name}",
            event.to_stream_fields(event_id),
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    except Exception as e:  # noqa: BLE001 — 事件丢失不得影响主业务事务
        logger.warning(f"[events] 发布 {event.name} 失败: {type(e).__name__}: {e}")
        return False
    logger.info(f"[events] 发布 {event.name} id={event_id} "
                f"aggregate={event.aggregate_id or '-'}")
    return True


async def subscribe(
    names: Iterable[str],
    handler: Callable[[Event], Awaitable[None]],
    *,
    idle_ms: int = STREAM_IDLE_MS,
) -> None:
    """订阅一组事件，逐条交给 handler，长驻直到取消或出错。

    Redis 缺席时立即返回，不抛异常。handler 自身异常不终止订阅，
    否则一个坏订阅者会拖垮整条流。
    """
    wanted = [n for n in names if n in ALL_EVENTS]
    if not wanted:
        return
    if not await is_available():
        return
    streams = {f"events:{n}": "0-0" for n in wanted}
    try:
        r = await _client()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[events] 订阅初始化失败: {type(e).__name__}: {e}")
        return
    while True:
        try:
            message = await r.xread(streams, block=idle_ms, count=10)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[events] 订阅中断: {type(e).__name__}: {e}")
            return
        for _stream, entries in message or []:
            for _msg_id, fields in entries:
                ev = Event.from_stream(fields)
                if ev is None:
                    continue
                try:
                    await handler(ev)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        f"[events] 处理 {ev.name} 失败: {type(e).__name__}: {e}")


def reset_probe_cache() -> None:
    """清空可用性探测缓存。仅供测试与运维排障使用。"""
    _probe_cache.clear()