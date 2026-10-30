"""F1 Step 2：发件箱与业务写同事务（原子、去重、版本递增）。"""
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.foundation import schema as fs
from app.foundation.outbox import emit, next_aggregate_version

BIZ_DDL = "CREATE TABLE biz_note (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL)"


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.exec_driver_sql(BIZ_DDL)
        for stmt in fs.ddl_statements():
            conn.exec_driver_sql(stmt)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _count(session, sql, **kw):
    return session.execute(text(sql), kw).scalar_one()


def test_business_write_and_event_commit_together(session):
    session.execute(text("INSERT INTO biz_note (body) VALUES ('q1')"))
    event_id = emit(
        session,
        event_name="catalog.question.imported",
        aggregate_type="question",
        aggregate_id=1042,
        payload={"question_id": 1042},
        producer="catalog.question_import",
        trace_id="t-1",
    )
    session.commit()

    assert event_id and len(event_id) == 32
    assert _count(session, "SELECT COUNT(*) FROM biz_note") == 1
    row = session.execute(
        text("SELECT status, aggregate_ver, payload, trace_id FROM foundation_outbox")
    ).one()
    assert row.status == "pending"
    assert row.aggregate_ver == 0
    assert json.loads(row.payload) == {"question_id": 1042}
    assert row.trace_id == "t-1"


def test_rollback_keeps_both_zero(session):
    session.execute(text("INSERT INTO biz_note (body) VALUES ('q2')"))
    emit(
        session,
        event_name="catalog.question.updated",
        aggregate_type="question",
        aggregate_id=7,
        payload={"v": 1},
        producer="catalog.unit_test",
    )
    session.rollback()

    assert _count(session, "SELECT COUNT(*) FROM biz_note") == 0
    assert _count(session, "SELECT COUNT(*) FROM foundation_outbox") == 0


def test_dedupe_key_returns_none_and_writes_once(session):
    kw = dict(
        event_name="catalog.question.imported",
        aggregate_type="question",
        aggregate_id=1,
        payload={"v": 1},
        producer="catalog.unit_test",
        dedupe_key="import:42:question:1",
    )
    first = emit(session, **kw)
    second = emit(session, **kw)
    session.commit()

    assert first is not None
    assert second is None
    assert _count(session, "SELECT COUNT(*) FROM foundation_outbox") == 1


def test_aggregate_version_increments(session):
    for expected in (0, 1, 2):
        assert next_aggregate_version(session, "question", "9") == expected
        emit(
            session,
            event_name="catalog.question.updated",
            aggregate_type="question",
            aggregate_id="9",
            payload={"v": expected},
            producer="catalog.unit_test",
        )
    other = next_aggregate_version(session, "question", "10")
    session.commit()

    versions = session.execute(
        text("SELECT aggregate_ver FROM foundation_outbox WHERE aggregate_id='9' ORDER BY id")
    ).scalars().all()
    assert versions == [0, 1, 2]
    assert other == 0, "不同聚合的版本号互不影响"


def test_invalid_json_payload_rejected(session):
    with pytest.raises(ValueError):
        emit(
            session,
            event_name="catalog.bad",
            aggregate_type="question",
            aggregate_id=1,
            payload="{not-json",
            producer="catalog.unit_test",
        )
    session.rollback()
    assert _count(session, "SELECT COUNT(*) FROM foundation_outbox") == 0


def test_duplicate_event_id_raises(session):
    import uuid

    from app.foundation import outbox as ob

    fixed = uuid.uuid4().hex
    with pytest.raises(IntegrityError):
        for _ in range(2):
            session.execute(
                ob._INSERT,
                {
                    "event_id": fixed,
                    "event_name": "x",
                    "schema_version": 1,
                    "aggregate_type": "a",
                    "aggregate_id": "1",
                    "aggregate_ver": 0,
                    "dedupe_key": None,
                    "payload": "{}",
                    "producer": "p",
                    "trace_id": None,
                    "occurred_at": "2026-10-26T20:00:00+08:00",
                },
            )
    session.rollback()
