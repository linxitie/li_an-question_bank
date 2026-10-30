"""WS 协议 v2：统一信封与序号。

只增不删：旧客户端只认 `type` / `data` / `timestamp`，v2 在这三个键之外
追加 `v/seq/scope/domain/entity/id`。这样升级期间新旧前端可共存，
不会出现「服务端改协议、旧页面静默失效」。

序号只用于「同一 scope 内丢弃旧消息」，不承担可靠投递职责：
Redis 不可达时退回进程内单调序号，跨 worker 可能重复，此时由客户端
重连后的全量重同步兜底（见 F2 计划 D19）。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

WS_PROTOCOL_VERSION = 2
SEQ_KEY = "foundation:ws:seq"
GLOBAL_SCOPE = "global"


def derive_scope(
    domain: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Any = None,
    explicit: Optional[str] = None,
) -> str:
    """推导消息作用域，粒度从粗到细：domain → domain.entity → domain.entity.id。"""
    if explicit:
        return explicit
    parts = [p for p in (domain, entity, entity_id) if p not in (None, "")]
    if not parts:
        return GLOBAL_SCOPE
    return ".".join(str(p) for p in parts)


class SeqAllocator:
    """序号分配器。

    increment 传入同步 Redis 的 INCR（保证多 worker 全局单调）；未配置或
    Redis 抛错时退回「毫秒时间戳 + 自增」，只保证单进程单调，不阻塞推送。
    """

    def __init__(
        self,
        increment: Optional[Callable[[str], Any]] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._increment = increment
        self._clock = clock
        self._last = 0
        self._degraded = False
        self._lock = threading.Lock()

    @property
    def degraded(self) -> bool:
        """True 表示至少一次回落到进程内序号（health 可据此告警）。"""
        return self._degraded

    def next(self) -> int:
        with self._lock:
            if self._increment is not None:
                try:
                    value = int(self._increment(SEQ_KEY))
                    self._last = max(self._last, value)
                    return value
                except Exception as exc:  # Redis 断连不应阻断业务推送
                    if not self._degraded:
                        logger.warning("WS seq 退化到进程内序号: %s", exc)
                    self._degraded = True
            return self._fallback_locked()

    def _fallback_locked(self) -> int:
        value = int(self._clock() * 1000)
        if value <= self._last:
            value = self._last + 1
        self._last = value
        return value


def build_envelope(
    message_type: str,
    *,
    seq: int,
    data: Optional[Dict[str, Any]] = None,
    domain: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Any = None,
    scope: Optional[str] = None,
    origin: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """构造 v2 信封；旧字段 type/data/timestamp 的位置与含义保持不变。"""
    from datetime import datetime

    payload: Dict[str, Any] = dict(data or {})
    message: Dict[str, Any] = {
        "v": WS_PROTOCOL_VERSION,
        "type": message_type,
        "seq": seq,
        "scope": derive_scope(domain, entity, entity_id, explicit=scope),
        "domain": domain,
        "entity": entity,
        "id": entity_id,
        "data": payload,
        "timestamp": timestamp or datetime.utcnow().isoformat(),
    }
    if origin:
        message["origin"] = origin
    return message


def is_newer(last_seq: Optional[int], incoming_seq: Any) -> bool:
    """同一 scope 内判断是否比已处理序号更新；无法解析的序号按「旧消息」丢弃。"""
    try:
        seq = int(incoming_seq)
    except (TypeError, ValueError):
        return False
    return last_seq is None or seq > int(last_seq)
