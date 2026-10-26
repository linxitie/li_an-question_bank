"""WS 中继单测：配置矩阵、本地扇出、origin 去重（不依赖真实 Redis）。"""
import asyncio

import pytest

from app.foundation.ws_relay import WsRelay, validate_worker_config


class FakeManager:
    def __init__(self):
        self.personal = []
        self.rooms = []
        self.broadcasts = []

    async def send_personal_message(self, message, user_id):
        self.personal.append((user_id, message))
        return True

    async def broadcast_to_room(self, message, room):
        self.rooms.append((room, message))
        return 1

    async def broadcast_all(self, message):
        self.broadcasts.append(message)
        return 1


@pytest.mark.parametrize(
    "workers,relay",
    [(1, ""), (1, "redis"), (2, "redis"), (2, " REDIS ")],
)
def test_worker_config_allows(workers, relay):
    validate_worker_config(workers, relay)


def test_worker_config_rejects_multi_worker_without_relay():
    with pytest.raises(RuntimeError, match="WS_RELAY=redis"):
        validate_worker_config(2, "")


def test_local_delivery_dedupes_users():
    manager = FakeManager()
    relay = WsRelay(manager=manager)

    asyncio.run(relay._send_local({"v": 2}, [3, 3, 5]))

    assert [uid for uid, _ in manager.personal] == [3, 5]


def test_room_and_broadcast_paths():
    manager = FakeManager()
    relay = WsRelay(manager=manager)

    asyncio.run(relay._send_local({"v": 2}, None, "exam"))
    asyncio.run(relay._send_local({"v": 2}))

    assert manager.rooms[0][0] == "exam"
    assert len(manager.broadcasts) == 1


def test_should_apply_skips_own_origin():
    relay = WsRelay(manager=FakeManager(), worker_id="worker-a")
    assert relay.should_apply({"origin": "worker-b"}) is True
    assert relay.should_apply({"origin": "worker-a"}) is False
    assert relay.should_apply({}) is True


def test_deliver_local_mode_sends_once():
    manager = FakeManager()
    relay = WsRelay(manager=manager)
    captured = []
    relay._dispatch_local = lambda message, users, room: captured.append((users, room))

    relay.deliver({"v": 2}, user_ids=[1])

    assert captured == [([1], None)]
    assert relay.health()["mode"] == "local"


def test_decode_rejects_garbage():
    assert WsRelay._decode("{bad") is None
    assert WsRelay._decode("[]") is None
    assert WsRelay._decode('{"origin":"x"}') == {"origin": "x"}
