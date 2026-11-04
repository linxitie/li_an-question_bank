"""F2b-2：断线重连的 Outbox 增量补发。

设计边界：
- 只读 foundation_outbox，不写库、不新增表；
- 入参 since 是客户端已见的最大 oid（foundation_outbox.id）；
- 只返回该用户/角色在 F2b 路由表中可见的 data-changed 事件；
- 超过单次上限、超过保留期或扫描上限时返回 truncated，由前端回退一次全量；
- 补发响应不参与 WS seq 去重，避免点对点消息污染广播序号。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import events
from app.foundation.config import (
    WS_SYNC_MAX_AGE_HOURS,
    WS_SYNC_MAX_EVENTS,
    WS_SYNC_REPLAY_ENABLED,
)
from app.foundation.event_routes import route_for
from app.foundation.ws_protocol import WS_PROTOCOL_VERSION

logger = logging.getLogger(__name__)

ALL_ROLES = ("student", "teacher", "admin")
# 防止异常积压导致一次补发扫描过多行；达到上限即截断，让前端全量兜底。
_MAX_SCAN = 2000


@dataclass(frozen=True)
class SyncResult:
    reason: str
    events: list[dict[str, Any]]
    latest_oid: int
    truncated: bool


def _parse_since(value: Any) -> Optional[int]:
    """since 必须是正整数；0 表示尚未见过任何事件，不允许作为补发起点。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _payload(row: Any) -> dict[str, Any]:
    raw = row.payload
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw) if isinstance(raw, str) else {}
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _visible(row: Any, viewer_user_id: int, viewer_role: Optional[str]) -> Optional[dict[str, Any]]:
    """把 Outbox 行映射为可见事件；不可见返回 None。

    可见性必须与 F2b 实时推送同一套路由表，否则补发会成为越权读取通道。
    """
    payload = _payload(row)
    event_name = row.event_name

    if event_name == events.EV_USER_ACTION:
        owner = payload.get("user_id")
        trigger = payload.get("trigger_type")
        if not isinstance(owner, int) or not isinstance(trigger, str):
            return None
        route = route_for(trigger)
        allowed = owner == viewer_user_id
        if not route.self_only and viewer_role in route.roles:
            allowed = True
        if not allowed:
            return None
        return {
            "domain": route.domain,
            "type": route.type,
            "id": row.event_id,
            "oid": int(row.id),
        }

    if event_name == events.EV_PAPER_PUBLISHED:
        if viewer_role not in ALL_ROLES:
            return None
        paper_id = payload.get("paper_id")
        if not isinstance(paper_id, (int, str)):
            return None
        return {
            "domain": "exam",
            "type": "paper.published",
            "id": paper_id,
            "oid": int(row.id),
        }

    return None


def _latest_oid(session: Session) -> int:
    value = session.execute(
        text("SELECT COALESCE(MAX(id), 0) FROM foundation_outbox WHERE status != 'dead'")
    ).scalar_one()
    return int(value or 0)


def replay(
    session: Session,
    *,
    since: Any,
    limit: Any,
    viewer_user_id: int,
    viewer_role: Optional[str],
    now: Optional[datetime] = None,
    enabled: Optional[bool] = None,
    max_events: Optional[int] = None,
    max_age_hours: Optional[int] = None,
) -> SyncResult:
    """按 since 补发可见事件；任何不确定都返回 truncated 而不是猜。"""
    if enabled is None:
        enabled = WS_SYNC_REPLAY_ENABLED
    latest = _latest_oid(session)
    if not enabled:
        return SyncResult("disabled", [], latest, True)

    since_int = _parse_since(since)
    if since_int is None:
        return SyncResult("bad-request", [], latest, True)

    try:
        requested = int(limit) if limit is not None else max_events or WS_SYNC_MAX_EVENTS
    except (TypeError, ValueError):
        requested = WS_SYNC_MAX_EVENTS
    cap = max(1, int(max_events or WS_SYNC_MAX_EVENTS))
    limit_int = min(max(1, requested), cap)
    age_hours = max(0, int(max_age_hours if max_age_hours is not None else WS_SYNC_MAX_AGE_HOURS))
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(hours=age_hours)

    rows = session.execute(
        text(
            """SELECT id, event_id, event_name, payload, occurred_at
               FROM foundation_outbox
               WHERE id > :since AND status != 'dead'
               ORDER BY id
               LIMIT :scan"""
        ),
        {"since": since_int, "scan": _MAX_SCAN + 1},
    ).all()

    # 扫描被截断说明无法证明“已覆盖 since 之后全部可见事件”，直接降级全量。
    if len(rows) > _MAX_SCAN:
        return SyncResult("replay-truncated", [], latest, True)

    visible: list[dict[str, Any]] = []
    for row in rows:
        occurred = _parse_time(row.occurred_at)
        if occurred is None or occurred < cutoff:
            return SyncResult("replay-truncated", [], latest, True)
        item = _visible(row, viewer_user_id, viewer_role)
        if item is not None:
            visible.append(item)

    if len(visible) > limit_int:
        return SyncResult("replay-truncated", [], latest, True)

    return SyncResult("replay", visible, latest, False)


def build_sync_reply(result: SyncResult) -> dict[str, Any]:
    """补发回复：不带 seq，客户端不得把它送进 acceptSeq。"""
    return {
        "v": WS_PROTOCOL_VERSION,
        "type": "sync",
        "scope": "sync",
        "data": {
            "reason": result.reason,
            "events": result.events,
            "latest_oid": result.latest_oid,
            "truncated": result.truncated,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
