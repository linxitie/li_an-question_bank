"""F2b：事务性事件、幂等收件、定向路由与单写者锁。"""
import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import trigger_types as tt
from app.foundation import schema as fs
from app.foundation.dispatcher_lock import DispatcherLock
from app.foundation.event_routes import ALL_ROLES, missing_triggers, route_for
from app.foundation.inbox import claim
from app.foundation.stores.base import OutboxEvent


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE biz_note (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT)")
        for stmt in fs.ddl_statements():
            conn.exec_driver_sql(stmt)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _event(event_id="e1", name="user.action.v1", payload=None):
    return OutboxEvent(
        id=1,
        event_id=event_id,
        event_name=name,
        schema_version=1,
        aggregate_type="user_action",
        aggregate_id="u-7",
        aggregate_ver=0,
        payload=payload or {"user_id": 7, "trigger_type": tt.TRIGGER_PRACTICE_SUBMIT},
        producer="user_action",
        trace_id=None,
        occurred_at="2026-10-27T10:00:00+08:00",
        attempts=0,
    )


def _count(db, table):
    return db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_route_table_covers_every_trigger():
    assert missing_triggers() == []
    assert set(route_for(t).type for t in tt.ALL_TRIGGER_TYPES) == set(tt.ALL_TRIGGER_TYPES)


def test_private_route_only_notifies_self():
    route = route_for(tt.TRIGGER_NOTE_CREATED)
    assert route.domain == "note"
    assert route.self_only is True
    assert route.recipients(7) == ([7], ())


def test_learning_and_forum_routes_add_roles():
    users, roles = route_for(tt.TRIGGER_PRACTICE_SUBMIT).recipients(7)
    assert users == [7] and roles == ("teacher", "admin")
    users, roles = route_for(tt.TRIGGER_FORUM_POSTED).recipients(7)
    assert users == [7] and roles == ALL_ROLES


def test_unknown_trigger_falls_back_to_self():
    route = route_for("not.registered")
    assert route.domain == "user" and route.self_only is True


def test_inbox_claim_is_idempotent(session):
    event = _event()
    assert claim(session, "c1", event) is True
    assert claim(session, "c1", event) is False
    assert claim(session, "c2", event) is True
    session.commit()
    assert _count(session, "foundation_inbox") == 2


def test_handler_claims_once_and_pushes_targeted(session, monkeypatch):
    from app.services import event_handlers

    calls = []
    monkeypatch.setattr(
        "app.services.achievement_judge.judge_action",
        lambda *a, **kw: {"newly_unlocked": []},
    )
    monkeypatch.setattr(
        "app.api.v1.platform.websocket.publish_data_changed_sync",
        lambda users, **kw: calls.append((users, kw)),
    )
    event = _event()
    event_handlers.handle_user_action(session, event)
    event_handlers.handle_user_action(session, event)
    session.commit()

    assert _count(session, "foundation_inbox") == 1
    assert len(calls) == 1
    users, kw = calls[0]
    assert users == [7]
    assert kw["domain"] == "exam"
    assert kw["roles"] == ("teacher", "admin")


def test_paper_handler_broadcasts_all_roles(session, monkeypatch):
    from app.services import event_handlers

    calls = []
    monkeypatch.setattr(
        "app.api.v1.platform.websocket.publish_data_changed_sync",
        lambda users, **kw: calls.append((users, kw)),
    )
    event = _event(
        event_id="p1",
        name="catalog.paper.published",
        payload={"paper_id": 42},
    )
    event_handlers.handle_paper_published(session, event)
    session.commit()
    assert calls == [(None, {"domain": "exam", "type": "paper.published",
                              "id": 42, "roles": ALL_ROLES})]


def test_record_user_action_writes_outbox_within_caller_transaction(session, monkeypatch):
    from app.services import event_consumer

    monkeypatch.setattr(event_consumer, "FOUNDATION_ENABLED", True)
    monkeypatch.setattr(event_consumer, "EVENT_OUTBOX_ENABLED", True)
    publish = AsyncMock()
    monkeypatch.setattr(event_consumer.events, "publish", publish)
    # 真实调用点都先有业务写，Outbox 与业务写共用同一个外层事务。
    session.execute(text("INSERT INTO biz_note (body) VALUES ('n1')"))

    assert asyncio.run(
        event_consumer.record_user_action(
            session,
            7,
            tt.TRIGGER_NOTE_CREATED,
            session={"session_id": "s-1"},
        )
    ) is True
    assert _count(session, "foundation_outbox") == 1
    publish.assert_not_awaited()

    row = session.execute(
        text("SELECT payload, dedupe_key FROM foundation_outbox")
    ).one()
    assert "note.created" in row.payload
    assert row.dedupe_key == "user_action:7:note.created:s-1"

    session.rollback()
    assert _count(session, "foundation_outbox") == 0
    assert _count(session, "biz_note") == 0


def test_record_user_action_legacy_path_when_outbox_disabled(session, monkeypatch):
    from app.services import event_consumer

    monkeypatch.setattr(event_consumer, "FOUNDATION_ENABLED", False)
    monkeypatch.setattr(event_consumer, "EVENT_OUTBOX_ENABLED", True)
    publish = AsyncMock(return_value=True)
    monkeypatch.setattr(event_consumer.events, "publish", publish)

    assert asyncio.run(
        event_consumer.record_user_action(session, 7, tt.TRIGGER_NOTE_CREATED)
    ) is True
    publish.assert_awaited_once()
    assert _count(session, "foundation_outbox") == 0


def test_dispatcher_lock_is_exclusive(tmp_path):
    path = tmp_path / "dispatcher.lock"
    first = DispatcherLock(path)
    second = DispatcherLock(path)
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_emit_failure_propagates_and_business_rolls_back(session, monkeypatch):
    from app.services import event_consumer

    monkeypatch.setattr(event_consumer, "FOUNDATION_ENABLED", True)
    monkeypatch.setattr(event_consumer, "EVENT_OUTBOX_ENABLED", True)

    def boom(*args, **kwargs):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(event_consumer.outbox, "emit", boom)
    session.execute(text("INSERT INTO biz_note (body) VALUES ('n2')"))

    with pytest.raises(RuntimeError):
        asyncio.run(
            event_consumer.record_user_action(session, 7, tt.TRIGGER_NOTE_CREATED)
        )
    session.rollback()
    assert _count(session, "biz_note") == 0
    assert _count(session, "foundation_outbox") == 0


def test_dispatcher_consumes_outbox_after_redis_outage(session, monkeypatch):
    """A2：事件不依赖 Redis；恢复后 Dispatcher 能消费并置 dispatched。"""
    from sqlalchemy.orm import sessionmaker
    from app.foundation.dispatcher import Dispatcher
    from app.foundation import outbox as ob
    from app.services import event_handlers

    monkeypatch.setattr(
        "app.services.achievement_judge.judge_action",
        lambda *a, **kw: {"newly_unlocked": []},
    )
    monkeypatch.setattr(
        "app.api.v1.platform.websocket.publish_data_changed_sync",
        lambda *a, **kw: 1,
    )
    ob.emit(
        session,
        event_name="user.action.v1",
        aggregate_type="user_action",
        aggregate_id="u-7",
        payload={"user_id": 7, "trigger_type": tt.TRIGGER_NOTE_CREATED},
        producer="user_action",
    )
    session.commit()

    factory = sessionmaker(bind=session.get_bind(), autoflush=False)
    dispatcher = Dispatcher(factory, handlers=event_handlers.build_handlers())
    stats = dispatcher.run_once()

    assert stats.processed == 1 and stats.failed == 0
    assert session.execute(
        text("SELECT status FROM foundation_outbox")
    ).scalar_one() == "dispatched"
    assert _count(session, "foundation_inbox") == 1
