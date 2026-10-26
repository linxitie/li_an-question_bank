"""
WebSocket通信模块 - 支持实时问答、考试监控、消息推送
"""
import json
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Iterable
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....models.models import SysUser, ExamRecord
from ....core.security import get_current_user,Permission, require_permission
from ....schemas.schemas import SuccessResponse
from ....core.monitoring import metrics_collector

router = APIRouter(prefix="/ws", tags=["WebSocket通信"])
logger = logging.getLogger(__name__)

class MessageType(str, Enum):
    HEARTBEAT = "heartbeat"
    EXAM_START = "exam_start"
    EXAM_PROGRESS = "exam_progress"
    EXAM_SUBMIT = "exam_submit"
    EXAM_RESULT = "exam_result"
    QUESTION_ANSWER = "question_answer"
    NOTIFICATION = "notification"
    CHAT_MESSAGE = "chat_message"
    SYSTEM_ALERT = "system_alert"
    IMPORT_PROGRESS = "import_progress"
    IMPORT_QUESTION = "import_question"
    IMPORT_COMPLETED = "import_completed"
    IMPORT_FAILED = "import_failed"
    DATA_CHANGED = "data-changed"

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[str, WebSocket]] = {}
        self.user_rooms: Dict[str, List[int]] = {}
        # 用于心跳超时判定：记录每条连接最后一次收/发消息的单调时钟
        self.last_seen: Dict[WebSocket, float] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int, room: Optional[str] = None) -> None:
        # 连接已在 websocket_connect 中 accept，此处仅做注册
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = {}

            connection_id = f"{user_id}_{datetime.now().timestamp()}"
            self.active_connections[user_id][connection_id] = websocket
            self.last_seen[websocket] = time.monotonic()

            if room:
                if room not in self.user_rooms:
                    self.user_rooms[room] = []
                if user_id not in self.user_rooms[room]:
                    self.user_rooms[room].append(user_id)

    async def disconnect(self, websocket: WebSocket, user_id: int, room: Optional[str] = None) -> None:
        async with self._lock:
            if user_id in self.active_connections:
                for conn_id, conn in list(self.active_connections[user_id].items()):
                    if conn == websocket:
                        del self.active_connections[user_id][conn_id]
                        break

                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

            self.last_seen.pop(websocket, None)

            if room and room in self.user_rooms:
                if user_id in self.user_rooms[room]:
                    self.user_rooms[room].remove(user_id)

    async def send_personal_message(self, message: Dict[str, Any], user_id: int) -> bool:
        async with self._lock:
            if user_id not in self.active_connections:
                return False

            try:
                for connection in self.active_connections[user_id].values():
                    await connection.send_json(message)
                return True
            except Exception:
                return False

    async def broadcast_to_room(self, message: Dict[str, Any], room: str) -> int:
        count = 0
        async with self._lock:
            if room not in self.user_rooms:
                return 0

            user_ids = self.user_rooms[room].copy()

        for user_id in user_ids:
            if await self.send_personal_message(message, user_id):
                count += 1

        return count

    async def broadcast_all(self, message: Dict[str, Any]) -> int:
        count = 0
        async with self._lock:
            user_ids = list(self.active_connections.keys())

        for user_id in user_ids:
            if await self.send_personal_message(message, user_id):
                count += 1

        return count

    def touch(self, websocket: WebSocket) -> None:
        """收到任何客户端消息（含心跳）即刷新活跃时间。"""
        self.last_seen[websocket] = time.monotonic()

    async def close_idle(self, timeout_seconds: float) -> int:
        """关闭超过 timeout_seconds 无消息的连接（码 4008，客户端自动重连）。"""
        now = time.monotonic()
        async with self._lock:
            stale = [
                (user_id, websocket)
                for user_id, connections in self.active_connections.items()
                for websocket in connections.values()
                if now - self.last_seen.get(websocket, now) > timeout_seconds
            ]
        for user_id, websocket in stale:
            try:
                await websocket.close(code=4008, reason="heartbeat timeout")
            except Exception as exc:  # 对端已断开时 close 也会抛，照常清理
                logger.debug("关闭空闲 WS 连接失败: %s", exc)
            await self.disconnect(websocket, user_id)
        return len(stale)

    async def watchdog(self, timeout_seconds: float, interval: float = 30.0) -> None:
        """长驻巡检：每 interval 秒清理一次空闲连接。"""
        while True:
            await asyncio.sleep(interval)
            try:
                await self.close_idle(timeout_seconds)
            except Exception as exc:  # 单轮失败不能中断后续巡检
                logger.warning("WS 心跳巡检失败: %s", exc)

    def get_online_users(self) -> List[int]:
        return list(self.active_connections.keys())

    def get_room_users(self, room: str) -> List[int]:
        return self.user_rooms.get(room, [])

ws_connection_manager = ConnectionManager()


async def publish_data_changed(
    user_ids: Iterable[int],
    domain: str,
    type: str,
    id: int | str,
) -> int:
    """向指定在线用户推送 `data-changed` 通知。

    载荷仍只携带 `{domain, type, id}`，接收端按 id 回源拉取；v2 追加
    `seq/scope` 供客户端去重，旧字段位置不变。发送统一走 ws_relay，
    多 worker 时由 Redis 中继转发到其他进程的连接。
    """
    from ....foundation.ws_relay import ws_relay

    sent = ws_relay.emit(
        MessageType.DATA_CHANGED.value,
        data={"domain": domain, "type": type, "id": id},
        domain=domain,
        entity=type,
        entity_id=id,
        scope=f"{domain}.{type}",
        user_ids=user_ids,
    )
    return 1 if sent else 0


@router.websocket("/connect")
async def websocket_connect(
    websocket: WebSocket,
    token: Optional[str] = None,
    room: Optional[str] = None
):
    # 先接受连接，再校验 token（避免 accept 前 close 导致握手异常断开/RST）
    await websocket.accept()

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        from ....core.security import decode_token, TokenType
        payload = decode_token(token)

        if payload.get("type") != TokenType.ACCESS.value:
            await websocket.close(code=4002, reason="Invalid token type")
            return

        user_id = payload.get("user_id")
        if not user_id:
            await websocket.close(code=4003, reason="Invalid token payload")
            return

    except Exception as e:
        await websocket.close(code=4004, reason="Token validation failed")
        return

    await ws_connection_manager.connect(websocket, user_id, room)

    metrics_collector.increment_counter("websocket_connections_total", tags={"room": room or "default"})

    try:
        await websocket.send_json({
            "type": MessageType.NOTIFICATION.value,
            "data": {"message": "连接成功", "user_id": user_id},
            "timestamp": datetime.utcnow().isoformat()
        })

        while True:
            data = await websocket.receive_json()
            ws_connection_manager.touch(websocket)
            await handle_websocket_message(websocket, user_id, data, room)

    except WebSocketDisconnect:
        await ws_connection_manager.disconnect(websocket, user_id, room)
        metrics_collector.increment_counter("websocket_disconnections_total", tags={"room": room or "default"})

    except Exception as e:
        await ws_connection_manager.disconnect(websocket, user_id, room)

async def handle_websocket_message(
    websocket: WebSocket,
    user_id: int,
    data: Dict[str, Any],
    room: Optional[str]
) -> None:
    message_type = data.get("type")
    payload = data.get("data", {})

    if message_type == MessageType.HEARTBEAT.value:
        await websocket.send_json({
            "type": MessageType.HEARTBEAT.value,
            "timestamp": datetime.utcnow().isoformat()
        })

    elif message_type == MessageType.EXAM_PROGRESS.value:
        record_id = payload.get("record_id")
        if record_id:
            await broadcast_exam_progress(user_id, record_id, room)

    elif message_type == MessageType.QUESTION_ANSWER.value:
        question_id = payload.get("question_id")
        answer = payload.get("answer")
        if question_id and answer:
            await broadcast_question_answer(user_id, question_id, answer, room)

    elif message_type == MessageType.CHAT_MESSAGE.value:
        content = payload.get("content")
        if content and room:
            await ws_connection_manager.broadcast_to_room({
                "type": MessageType.CHAT_MESSAGE.value,
                "data": {
                    "user_id": user_id,
                    "content": content,
                    "room": room
                },
                "timestamp": datetime.utcnow().isoformat()
            }, room)

async def broadcast_exam_progress(user_id: int, record_id: int, room: Optional[str]) -> None:
    from ....core.database import SessionLocal

    db = SessionLocal()
    try:
        record = db.query(ExamRecord).filter(ExamRecord.record_id == record_id).first()
        if not record or record.user_id != user_id:
            return

        answered_count = len(record.answers) if hasattr(record, 'answers') else 0

        await ws_connection_manager.send_personal_message({
            "type": MessageType.EXAM_PROGRESS.value,
            "data": {
                "record_id": record_id,
                "answered_count": answered_count,
                "is_completed": bool(record.is_completed)
            },
            "timestamp": datetime.utcnow().isoformat()
        }, user_id)

    finally:
        db.close()

async def broadcast_question_answer(user_id: int, question_id: int, answer: str, room: Optional[str]) -> None:
    await ws_connection_manager.send_personal_message({
        "type": MessageType.QUESTION_ANSWER.value,
        "data": {
            "question_id": question_id,
            "answer": answer,
            "answered_by": user_id
        },
        "timestamp": datetime.utcnow().isoformat()
    }, user_id)

@router.get("/online_users", summary="获取在线用户列表")
async def get_online_users(current_user: SysUser = Depends(get_current_user)) -> SuccessResponse:
    online_users = ws_connection_manager.get_online_users()
    return SuccessResponse(data={"online_users": online_users, "count": len(online_users)})

@router.get("/room/{room_name}", summary="获取房间用户列表")
async def get_room_users(
    room_name: str,
    current_user: SysUser = Depends(get_current_user)
) -> SuccessResponse:
    users = ws_connection_manager.get_room_users(room_name)
    return SuccessResponse(data={"room": room_name, "users": users, "count": len(users)})

@router.post("/notify/{user_id}", summary="发送用户通知")
async def send_user_notification(
    user_id: int,
    message: str,
    current_user: SysUser = Depends(get_current_user)
) -> SuccessResponse:
    success = await ws_connection_manager.send_personal_message({
        "type": MessageType.NOTIFICATION.value,
        "data": {"message": message, "from": current_user.user_id},
        "timestamp": datetime.utcnow().isoformat()
    }, user_id)

    if success:
        return SuccessResponse(message="通知已发送")
    else:
        raise HTTPException(status_code=404, detail="用户不在线")

@router.post("/broadcast", summary="广播消息")
async def broadcast_message(
    message: str,
    message_type: MessageType = MessageType.SYSTEM_ALERT,
    room: Optional[str] = None,
    current_user: SysUser = Depends(require_permission(Permission.SYSTEM_CONFIG))
) -> SuccessResponse:
    if room:
        count = await ws_connection_manager.broadcast_to_room({
            "type": message_type.value,
            "data": {"message": message, "from": current_user.user_id},
            "timestamp": datetime.utcnow().isoformat()
        }, room)
    else:
        count = await ws_connection_manager.broadcast_all({
            "type": message_type.value,
            "data": {"message": message, "from": current_user.user_id},
            "timestamp": datetime.utcnow().isoformat()
        })

    return SuccessResponse(message=f"广播已发送至{count}个用户")