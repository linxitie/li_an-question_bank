"""F1 Step 3：投递/投影——续跑、重放幂等、乱序守卫、死信。"""
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.foundation import schema as fs
from app.foundation import reconcile
from app.foundation.dispatcher import Dispatcher
from app.foundation.health import snapshot
from app.foundation.outbox import emit
from app.foundation.projection import LocalProjection, payload_checksum

EVENT = "catalog.question.imported"


@pytest.fixture()
def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in fs.ddl_statements():
            conn.exec_driver_sql(stmt)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


def _emit_many(factory, n, aggregate_prefix="q"):
    with factory() as s:
        for i in range(n):
            emit(
                s,
                event_name=EVENT,
                aggregate_type="question",
                aggregate_id=f"{aggregate_prefix}{i}",
                payload={"i": i},
                producer="catalog.unit_test",
            )
        s.commit()


def _count(factory, sql, **kw):
    with factory() as s:
        return s.execute(text(sql), kw).scalar_one()


def test_run_once_projects_all(factory):
    _emit_many(factory, 100)
    stats = Dispatcher(factory).run_once()

    assert stats.processed == 100 and stats.failed == 0 and stats.dead == 0
    assert _count(factory, "SELECT COUNT(*) FROM foundation_projection_state") == 100
    assert _count(factory, "SELECT COUNT(*) FROM foundation_outbox WHERE status='dispatched'") == 100
    assert _count(factory, "SELECT last_outbox_id FROM foundation_projection_cursor") == 100


def test_resume_after_crash_at_50(factory):
    _emit_many(factory, 100)
    calls = {"n": 0}
    projection = LocalProjection()

    def flaky(session, event):
        calls["n"] += 1
        if calls["n"] == 51:
            raise RuntimeError("simulated crash at 51")
        projection.apply(session, event)

    dispatcher = Dispatcher(factory, handlers={EVENT: flaky}, retry_base_seconds=0)
    first = dispatcher.run_once()
    # 单条失败不阻塞后续：99 成功 + 1 待重试
    assert first.processed == 99 and first.failed == 1
    assert _count(factory, "SELECT COUNT(*) FROM foundation_outbox WHERE status='pending'") == 1

    second = dispatcher.run_once()
    assert second.processed == 1 and second.failed == 0
    assert _count(factory, "SELECT COUNT(*) FROM foundation_projection_state") == 100
    assert _count(factory, "SELECT COUNT(*) FROM foundation_outbox WHERE status='pending'") == 0


def test_replay_10x_idempotent(factory):
    _emit_many(factory, 100)
    dispatcher = Dispatcher(factory)
    dispatcher.run_once()
    assert _count(factory, "SELECT COUNT(*) FROM foundation_projection_state") == 100

    with factory() as s:
        s.execute(text("UPDATE foundation_outbox SET status='pending', next_retry_at=NULL"))
        s.execute(text("UPDATE foundation_projection_cursor SET last_outbox_id=0"))
        s.commit()

    for _ in range(10):
        dispatcher.run_once()

    assert _count(factory, "SELECT COUNT(*) FROM foundation_projection_state") == 100
    assert _count(factory, "SELECT COUNT(*) FROM foundation_outbox WHERE status='dispatched'") == 100


def test_out_of_order_v5_wins_and_v3_cannot_downgrade(factory):
    with factory() as s:
        emit(
            s, event_name=EVENT, aggregate_type="question", aggregate_id="x",
            payload={"v": 5}, producer="t", aggregate_ver=5,
        )
        emit(
            s, event_name=EVENT, aggregate_type="question", aggregate_id="x",
            payload={"v": 3}, producer="t", aggregate_ver=3,
        )
        s.commit()

    Dispatcher(factory).run_once()
    with factory() as s:
        row = s.execute(
            text(
                """SELECT source_version, checksum FROM foundation_projection_state
                   WHERE aggregate_type='question' AND aggregate_id='x'"""
            )
        ).one()
    assert row.source_version == 5
    assert row.checksum == payload_checksum({"v": 5})


def test_reconcile_detects_drift_and_rebuild_repairs(factory):
    _emit_many(factory, 5)
    Dispatcher(factory).run_once()
    with factory() as s:
        s.execute(text("UPDATE foundation_projection_state SET checksum='tampered'"))
        s.commit()

    with factory() as s:
        run = reconcile.sample(s)
        reconcile.record(s, run)
    assert run.status == "drift" and run.drifted == 5

    with factory() as s:
        repaired = reconcile.rebuild(s)
        assert repaired.repaired == 5
    with factory() as s:
        assert reconcile.sample(s).drifted == 0

    with factory() as s:
        assert s.execute(text("SELECT status FROM foundation_reconcile_run")).scalar_one() == "drift"


def test_health_snapshot_ok_and_degraded(factory):
    _emit_many(factory, 3)
    Dispatcher(factory).run_once()
    engine = factory.kw["bind"]
    ok = snapshot(engine)
    assert ok["status"] == "ok" and ok["dead"] == 0 and ok["schema"] == "ok"

    with factory() as s:
        s.execute(text("UPDATE foundation_outbox SET status='dead' WHERE id=1"))
        s.commit()
    assert snapshot(engine)["status"] == "degraded"


def test_permanent_failure_goes_dead_with_jsonl(factory, tmp_path):
    with factory() as s:
        emit(
            s, event_name=EVENT, aggregate_type="question", aggregate_id="bad",
            payload={"i": -1}, producer="t",
        )
        s.commit()

    def boom(session, event):
        raise ValueError("permanent")

    dispatcher = Dispatcher(
        factory,
        handlers={EVENT: boom},
        max_attempts=1,
        retry_base_seconds=0,
        dead_letter_dir=tmp_path,
    )
    stats = dispatcher.run_once()

    assert stats.dead == 1
    assert _count(factory, "SELECT status FROM foundation_outbox") == "dead"
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    line = json.loads(files[0].read_text(encoding="utf-8").strip().splitlines()[0])
    assert line["event_name"] == EVENT and "permanent" in line["error"]
