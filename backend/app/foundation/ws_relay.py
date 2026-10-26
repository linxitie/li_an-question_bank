"""跨 worker WebSocket 中继。

单进程时 `deliver()` 直接本地扇出；`WS_RELAY=redis` 时额外 PUBLISH 到
`foundation:ws`，由各 worker 的订阅循环接收后本地扇出。

为什么发布者也要本地发一次：Redis 订阅是 at-most-once 且订阅端会跳过
`origin == 自己` 的消息（否则单 worker 会收到两份）。发布者本地直发 +
其他 worker 订阅转发，正好每个 worker 各发一次。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, Iterable, Optional

from app.foundation.ws_protocol import SeqAllocator

logger = logging.getLogger(__name__)

CHANNEL = "foundation:ws"
RELAY_MODE_REDIS = "redis"


def validate_worker_config(
    web_concurrency: Optional[int] = None,
    relay_mode: Optional[str] = None,
) -> None:
    """多 worker 却没有中继时直接拒绝启动。

    静默启动的后果是每个 worker 只持有自己进程内的 WS 连接：A worker 的
    业务写入推送不到 B worker 的用户，表现为「有时能收到、刷新才更新」。
    这种缺陷在线下极难复现，所以选择启动即失败。
    """
    if web_concurrency is None:
        try:
            web_concurrency = int(os.environ.get("WEB_CONCURRENCY", "1") or "1")
        except ValueError:
            web_concurrency = 1
    if relay_mode is None:
        relay_mode = os.environ.get("WS_RELAY", "")
    if web_concurrency > 1 and (relay_mode or "").strip().lower() != RELAY_MODE_REDIS:
        raise RuntimeError(
            f"WEB_CONCURRENCY={web_concurrency} 需要 WS_RELAY=redis 才能跨 worker 推送；"
            "请设置 WS_RELAY=redis 并把并发降为 1。"
        )


class WsRelay:
    def __init__(
        self,
        manager: Any = None,
        worker_id: Optional[str] = None,
        seq_allocator: Optional[SeqAllocator] = None,
    ) -> None:
        self._manager = manager
        self.worker_id = worker_id or uuid.uuid4().hex[:12]
        self._seq = seq_allocator or SeqAllocator()
        self._mode = "local"
        self._state = "ok"
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_redis: Any = None
        self._sync_redis: Any = None
        self._pubsub: Any = None
        self._task: Optional[asyncio.Task] = None
        self._last_error: Optional[str] = None

    # ---------- 生命周期 ----------
    async def start(self, relay_mode: str = "", redis_url: str = "") -> None:
        self._loop = asyncio.get_running_loop()
        self._mode = RELAY_MODE_REDIS if (relay_mode or "").strip().lower() == RELAY_MODE_REDIS else "local"
        if self._mode != RELAY_MODE_REDIS:
            self._state = "ok"
            return
        try:
            import redis.asyncio as aioredis

            self._async_redis = aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True,
                socket_connect_timeout=2.0, socket_timeout=2.0,
            )
            await self._async_redis.ping()
            self._pubsub = self._async_redis.pubsub()
            await self._pubsub.subscribe(CHANNEL)
            self._task = asyncio.create_task(self._consume(), name="ws-relay-consume")
            self._state = "ok"
            logger.info("WS 中继已启用（worker=%s）", self.worker_id)
        except Exception as exc:
            # 中继不可用不等于业务不可用：退回本地扇出，health 报 degraded。
            self._state = "degraded"
            self._last_error = str(exc)
            logger.warning("WS 中继启动失败，退回本地扇出: %s", exc)
            await self._cleanup_redis()

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("WS 中继订阅任务已取消")
            except Exception as exc:
                logger.warning("WS 中继订阅循环退出异常: %s", exc)
            self._task = None
        await self._cleanup_redis()

    async def _cleanup_redis(self) -> None:
        pubsub, async_redis = self._pubsub, self._async_redis
        self._pubsub = self._async_redis = None
        self._sync_redis = None
        for client in (pubsub, async_redis):
            if client is None:
                continue
            try:
                await client.close()
            except Exception:
                logger.warning("关闭 WS 中继 Redis 连接失败", exc_info=True)

    # ---------- 发送 ----------
    def emit(
        self,
        message_type: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        domain: Optional[str] = None,
        entity: Optional[str] = None,
        entity_id: Any = None,
        scope: Optional[str] = None,
        user_ids: Optional[Iterable[int]] = None,
        room: Optional[str] = None,
    ) -> bool:
        """构造 v2 信封后投递；业务侧只描述「发生了什么」，不碰 seq/scope。"""
        from app.foundation.ws_protocol import build_envelope

        envelope = build_envelope(
            message_type,
            seq=self._seq.next(),
            data=data,
            domain=domain,
            entity=entity,
            entity_id=entity_id,
            scope=scope,
        )
        return self.deliver(envelope, user_ids=user_ids, room=room)

    def deliver(
        self,
        message: Dict[str, Any],
        *,
        user_ids: Optional[Iterable[int]] = None,
        room: Optional[str] = None,
    ) -> bool:
        """同步入口：发布给其他 worker，并在本 worker 本地扇出一次。"""
        ids = sorted({int(u) for u in user_ids}) if user_ids is not None else None
        envelope = dict(message)
        envelope["origin"] = self.worker_id
        if self._mode == RELAY_MODE_REDIS:
            body = {"origin": self.worker_id, "users": ids, "room": room, "message": envelope}
            try:
                self._sync_client().publish(CHANNEL, json.dumps(body, ensure_ascii=False))
            except Exception as exc:
                self._state = "degraded"
                self._last_error = str(exc)
                logger.warning("WS 中继发布失败，仅本地投递: %s", exc)
        self._dispatch_local(envelope, ids, room)
        return True

    async def _send_local(
        self,
        message: Dict[str, Any],
        user_ids: Optional[Iterable[int]] = None,
        room: Optional[str] = None,
    ) -> int:
        manager = self._get_manager()
        if manager is None:
            return 0
        if user_ids is not None:
            delivered = 0
            for user_id in dict.fromkeys(int(u) for u in user_ids):
                if await manager.send_personal_message(message, user_id):
                    delivered += 1
            return delivered
        if room:
            return await manager.broadcast_to_room(message, room)
        return await manager.broadcast_all(message)

    def _dispatch_local(
        self,
        message: Dict[str, Any],
        user_ids: Optional[Iterable[int]],
        room: Optional[str],
    ) -> None:
        coro = self._send_local(message, user_ids, room)
        loop = self._loop
        if loop is None or not loop.is_running():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning("WS 本地投递缺少事件循环，消息丢弃")
                return
        asyncio.run_coroutine_threadsafe(coro, loop)

    # ---------- 订阅 ----------
    async def _consume(self) -> None:
        assert self._pubsub is not None
        async for raw in self._pubsub.listen():
            if raw.get("type") != "message":
                continue
            body = self._decode(raw.get("data"))
            if body is None or not self.should_apply(body):
                continue
            try:
                await self._send_local(body.get("message") or {}, body.get("users"), body.get("room"))
            except Exception:
                logger.warning("WS 中继消息本地扇出失败", exc_info=True)

    @staticmethod
    def _decode(raw: Any) -> Optional[Dict[str, Any]]:
        if raw is None:
            return None
        try:
            body = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return body if isinstance(body, dict) else None

    def should_apply(self, body: Dict[str, Any]) -> bool:
        """跳过自己发布的消息，避免单 worker 重复投递；无 origin 视为外部消息。"""
        return (body.get("origin") or "") != self.worker_id

    # ---------- 辅助 ----------
    def _get_manager(self) -> Any:
        if self._manager is None:
            from app.api.v1.platform.websocket import ws_connection_manager

            self._manager = ws_connection_manager
        return self._manager

    def _sync_client(self) -> Any:
        if self._sync_redis is None:
            import redis as sync_redis

            self._sync_redis = sync_redis.Redis.from_url(
                self._redis_url, decode_responses=True,
                socket_connect_timeout=1.0, socket_timeout=1.0,
            )
            self._seq = SeqAllocator(increment=lambda key: self._sync_redis.incr(key))
        return self._sync_redis

    _redis_url = ""

    def configure(self, relay_mode: str = "", redis_url: str = "") -> None:
        """记录配置，真正的连接在 start() 建立；便于单测直接构造。"""
        self._redis_url = redis_url or self._redis_url

    def health(self) -> Dict[str, Any]:
        return {
            "mode": self._mode,
            "state": self._state,
            "worker_id": self.worker_id,
            "seq_degraded": self._seq.degraded,
            "last_error": self._last_error,
        }


ws_relay = WsRelay()
