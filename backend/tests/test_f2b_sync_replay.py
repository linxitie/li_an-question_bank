"""F2b-2：断线重连增量补发、可见性、截断与 WS 协议。"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import events
from app.core import trigger_types as tt
from app.foundation import outbox as ob
from app.foundation import schema as fs
from app.foundation import ws_sync
from app.foundation.event_routes import ALL_ROLES


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in fs.ddl_statements():
            conn.exec_driver_sql(stmt)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _emit(db, payload, *, name=events.EV_USER_ACTION, occurred_at=None):
    event_id = ob.emit(
        db,
        event_name=name,
        aggregate_type="user_action",
        aggregate_id=str(payload.get("user_id", 0)),
        payload=payload,
        producer="test",
        occurred_at=occurred_at,
    )
    db.commit()
    return event_id


def _oid(db, event_id):
    return int(
        db.execute(
            text("SELECT id FROM foundation_outbox WHERE event_id=:e"), {"e": event_id}
        ).scalar_one()
    )


def _note(db, user_id=7, occurred_at=None):
    event_id = _emit(
        db,
        {"user_id": user_id, "trigger_type": tt.TRIGGER_NOTE_CREATED},
        occurred_at=occurred_at,
    )
    return event_id, _oid(db, event_id)


def _practice(db, user_id=7):
    event_id = _emit(
        db, {"user_id": user_id, "trigger_type": tt.TRIGGER_PRACTICE_SUBMIT}
    )
    return event_id, _oid(db, event_id)


def _paper(db, paper_id=42):
    event_id = _emit(
        db,
        {"paper_id": paper_id},
        name=events.EV_PAPER_PUBLISHED,
    )
    return event_id, _oid(db, event_id)


def _marker(db, user_id=999):
    """插入一条对被测用户不可见的私有事件，提供合法的 since 起点。"""
    _, oid = _note(db, user_id)
    return oid


def _replay(db, since, role="student", user_id=7, **kwargs):
    return ws_sync.replay(
        db,
        since=since,
        limit=kwargs.pop("limit", 200),
        viewer_user_id=user_id,
        viewer_role=role,
        **kwargs,
    )


def test_private_event_visible_only_to_owner(session):
    since = _marker(session)
    event_id, oid = _note(session, 7)
    owner = _replay(session, since, role="student", user_id=7)
    assert owner.truncated is False
    assert owner.events == [{"domain": "note", "type": tt.TRIGGER_NOTE_CREATED,
                             "id": event_id, "oid": oid}]
    # 教师/其他学生都不能通过补发读到别人的私有笔记
    assert _replay(session, since, role="teacher", user_id=8).events == []
    assert _replay(session, since, role="student", user_id=9).events == []


def test_learning_event_visible_to_teacher_and_admin_only(session):
    since = _marker(session)
    _, oid = _practice(session, 7)
    teacher = _replay(session, since, role="teacher", user_id=8)
    admin = _replay(session, since, role="admin", user_id=9)
    other_student = _replay(session, since, role="student", user_id=10)
    assert [e["oid"] for e in teacher.events] == [oid]
    assert [e["oid"] for e in admin.events] == [oid]
    assert other_student.events == []


@pytest.mark.parametrize("role", ALL_ROLES)
def test_paper_published_visible_to_every_role(session, role):
    since = _marker(session)
    _, oid = _paper(session, 42)
    result = _replay(session, since, role=role, user_id=99)
    assert [e["oid"] for e in result.events] == [oid]
    assert result.events[0]["type"] == "paper.published"


def test_only_since_events_are_replayed_in_order(session):
    _, first = _note(session, 7)
    _, second = _note(session, 7)
    _, third = _note(session, 7)
    result = _replay(session, second, role="student", user_id=7)
    assert [e["oid"] for e in result.events] == [third]
    assert result.latest_oid == third
    assert first < second < third


def test_limit_exceeded_truncates_without_partial_events(session):
    since = _marker(session)
    for _ in range(3):
        _note(session, 7)
    result = _replay(session, since, role="student", user_id=7, limit=2)
    assert result.truncated is True
    assert result.reason == "replay-truncated"
    assert result.events == []


def test_scan_cap_truncates_even_if_limit_allows(session, monkeypatch):
    monkeypatch.setattr(ws_sync, "_MAX_SCAN", 2)
    since = _marker(session)
    for _ in range(3):
        _note(session, 7)
    result = _replay(session, since, role="student", user_id=7, limit=200)
    assert result.truncated is True and result.events == []


def test_event_older_than_retention_truncates(session):
    _, since = _note(session, 999)
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    _note(session, 7, occurred_at=old)
    result = _replay(session, since, role="student", user_id=7)
    assert result.truncated is True and result.reason == "replay-truncated"


def test_invalid_since_is_bad_request(session):
    for value in (0, -1, True, "12", None):
        result = _replay(session, value, role="student", user_id=7)
        assert result.truncated is True
        assert result.reason == "bad-request"


def test_disabled_switch_degrades_to_full_sync(session):
    since = _marker(session)
    _note(session, 7)
    result = _replay(session, since, role="student", user_id=7, enabled=False)
    assert (result.reason, result.truncated, result.events) == ("disabled", True, [])


def test_latest_oid_ignores_dead_rows(session):
    _, first = _note(session, 7)
    _, second = _note(session, 7)
    session.execute(
        text("UPDATE foundation_outbox SET status='dead' WHERE id=:i"), {"i": second}
    )
    session.commit()
    result = _replay(session, first, role="student", user_id=7)
    assert result.latest_oid == first
    assert result.events == []


def test_unknown_event_name_is_not_exposed(session):
    since = _marker(session)
    _emit(session, {"user_id": 7, "trigger_type": "x"}, name="unknown.event")
    assert _replay(session, since, role="admin", user_id=7).events == []


def test_reply_shape_has_no_seq_and_scope_sync(session):
    since = _marker(session)
    _note(session, 7)
    reply = ws_sync.build_sync_reply(_replay(session, since, role="student", user_id=7))
    assert reply["type"] == "sync" and reply["scope"] == "sync"
    assert "seq" not in reply
    assert reply["data"]["truncated"] is False
    assert reply["data"]["reason"] == "replay"


def test_publish_data_changed_carries_oid_only_when_known(monkeypatch):
    from app.api.v1.platform import websocket as ws

    calls = []
    monkeypatch.setattr(
        "app.foundation.ws_relay.ws_relay.emit", lambda *a, **kw: calls.append(kw) or True
    )
    ws.publish_data_changed_sync([7], domain="note", type="note.created", id="e1", outbox_id=12)
    ws.publish_data_changed_sync([7], domain="note", type="note.created", id="e2")
    assert calls[0]["data"] == {
        "domain": "note", "type": "note.created", "id": "e1", "oid": 12
    }
    assert "oid" not in calls[1]["data"]


def test_websocket_sync_branch_sends_degraded_reply(session):
    from app.api.v1.platform import websocket as ws

    _note(session, 7)
    sent = []

    class FakeWs:
        async def send_json(self, payload):
            sent.append(payload)

    factory = sessionmaker(bind=session.get_bind(), autoflush=False)
    import app.core.database as dbmod

    original = dbmod.SessionLocal
    dbmod.SessionLocal = factory
    try:
        asyncio.run(
            ws.handle_websocket_message(
                FakeWs(), 7, {"type": "sync", "data": {"since": 0, "limit": 200}}, None,
                role="student",
            )
        )
    finally:
        dbmod.SessionLocal = original
    assert sent[0]["type"] == "sync"
    assert sent[0]["data"]["reason"] == "bad-request"

def test_more_than_limit_candidates_truncates(session):
    since = _marker(session)
    for _ in range(201):
        _note(session, 7)
    result = _replay(session, since, role="student", user_id=7, limit=200)
    assert result.truncated is True and result.reason == "replay-truncated"
    assert result.events == []


def test_since_ahead_of_latest_returns_empty(session):
    _, oid = _note(session, 7)
    result = _replay(session, oid + 100, role="student", user_id=7)
    assert result.events == []
    assert result.truncated is False
    assert result.latest_oid == oid


def test_malformed_payload_is_skipped_without_error(session):
    since = _marker(session)
    _emit(session, {})
    result = _replay(session, since, role="admin", user_id=7)
    assert result.events == []
    assert result.truncated is False


ROLES = ("student", "teacher", "admin")
DEVICES = ("pc", "tablet", "mobile")
SCENARIOS = ("S1-online", "S2-reconnect", "S3-degraded")


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("role", ROLES)
def test_9x3_protocol_matrix(session, monkeypatch, role, device, scenario):
    """3 角色 × 3 设备 × 3 场景；设备不参与协议，仅作为承载页标签。"""
    assert device in DEVICES
    since = _marker(session)
    event_id, oid = _practice(session, 7)

    if scenario == "S1-online":
        from app.api.v1.platform import websocket as ws

        calls = []
        monkeypatch.setattr(
            "app.foundation.ws_relay.ws_relay.emit",
            lambda *a, **kw: calls.append(kw) or True,
        )
        ws.publish_data_changed_sync(
            [7], domain="exam", type=tt.TRIGGER_PRACTICE_SUBMIT, id=event_id, outbox_id=oid
        )
        assert calls[-1]["data"]["oid"] == oid
        return

    if scenario == "S2-reconnect":
        result = _replay(session, since, role=role, user_id=8)
        if role in ("teacher", "admin"):
            assert [e["oid"] for e in result.events] == [oid]
        else:
            assert result.events == []
        assert result.truncated is False
        return

    result = _replay(session, since, role=role, user_id=8, enabled=False)
    assert result.truncated is True and result.events == []
    assert result.reason == "disabled"

