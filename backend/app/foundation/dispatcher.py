"""Outbox 投递器：单进程 asyncio 任务，逐条一事务，崩溃可续跑。

语义：
- 成功：投影 + 游标推进 + 事件置 dispatched，同一事务；
- 失败：attempts+1；未超限留 pending 并退避，超限置 dead 并写 jsonl（可人工重放）；
- 不 claim、不加锁：F1 只允许单 worker（方案 §20.2），多 worker 在 F2 接 Redis 后启用。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.foundation.config import BACKEND_DIR, FOUNDATION_DISPATCH_MS, FOUNDATION_MAX_ATTEMPTS
from app.foundation.projection import LocalProjection
from app.foundation.stores.base import OutboxEvent
from app.foundation.stores.local import SqliteCursorStore, SqliteOutboxStore

DEFAULT_DEAD_LETTER_DIR = BACKEND_DIR / "data" / "reports" / "dead_letters"


@dataclass
class DispatchStats:
    processed: int = 0
    failed: int = 0
    dead: int = 0
    last_outbox_id: int = 0
    errors: list[str] = field(default_factory=list)


class Dispatcher:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        projection: LocalProjection | None = None,
        handlers: dict[str, Callable[[Session, OutboxEvent], None]] | None = None,
        max_attempts: int = FOUNDATION_MAX_ATTEMPTS,
        batch_size: int = 100,
        retry_base_seconds: int = 2,
        dead_letter_dir: Path | None = None,
        interval_ms: int = FOUNDATION_DISPATCH_MS,
    ):
        self.session_factory = session_factory
        self.projection = projection or LocalProjection()
        self.handlers = handlers or {}
        self.max_attempts = max(1, max_attempts)
        self.batch_size = max(1, batch_size)
        self.retry_base_seconds = max(0, retry_base_seconds)
        self.dead_letter_dir = dead_letter_dir or DEFAULT_DEAD_LETTER_DIR
        self.interval_ms = interval_ms

    def run_once(self, now: str | None = None) -> DispatchStats:
        now = now or _now()
        stats = DispatchStats()
        with self.session_factory() as session:
            events = SqliteOutboxStore(session).fetch_pending(self.batch_size, now)
        for event in events:
            outcome = self._handle(event)
            if outcome == "ok":
                stats.processed += 1
                stats.last_outbox_id = max(stats.last_outbox_id, event.id)
            else:
                stats.failed += 1
                if outcome == "dead":
                    stats.dead += 1
                stats.errors.append(f"{event.event_id}: {event.event_name}")
        return stats

    def _handle(self, event: OutboxEvent) -> str:
        with self.session_factory() as session:
            store = SqliteOutboxStore(session)
            try:
                with session.begin():
                    handler = self.handlers.get(event.event_name)
                    if handler is not None:
                        handler(session, event)
                    else:
                        self.projection.apply(session, event)
                    store.mark_dispatched(event.event_id)
                    SqliteCursorStore(session).advance(self.projection.name, event.id, event.occurred_at)
                return "ok"
            except Exception as exc:  # noqa: BLE001 - 失败必须落库，不能静默
                session.rollback()
                error = f"{type(exc).__name__}: {exc}"
                attempts = store.mark_retry(event.event_id, error, _retry_at(self.retry_base_seconds, event.attempts))
                if attempts >= self.max_attempts:
                    store.mark_dead(event.event_id, error)
                    session.commit()
                    self._write_dead_letter(event, error, attempts)
                    return "dead"
                session.commit()
                return "retry"

    def _write_dead_letter(self, event: OutboxEvent, error: str, attempts: int) -> None:
        try:
            self.dead_letter_dir.mkdir(parents=True, exist_ok=True)
            path = self.dead_letter_dir / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
            line = {
                "event_id": event.event_id,
                "event_name": event.event_name,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id,
                "aggregate_ver": event.aggregate_ver,
                "attempts": attempts,
                "error": error[:2000],
                "occurred_at": event.occurred_at,
                "dead_at": _now(),
            }
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            # 文件写失败不影响 dead 状态；L7-3 会报 dead 非 0
            pass

    async def run_forever(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - 后台任务不得因单轮异常退出
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.interval_ms / 1000)
            except asyncio.TimeoutError:
                continue


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _retry_at(base_seconds: int, attempts: int) -> str:
    delay = min(base_seconds * (2 ** attempts), 300)
    return (datetime.now().astimezone() + timedelta(seconds=delay)).isoformat(timespec="seconds")
