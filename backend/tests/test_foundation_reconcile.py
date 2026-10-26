"""F1 Step 7：对账验收——篡改一条投影 → sample 发现 drift → rebuild 修复。"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.foundation import reconcile
from app.foundation import schema as fs
from app.foundation.dispatcher import Dispatcher
from app.foundation.outbox import emit

EVENT = "catalog.question.imported"


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in fs.ddl_statements():
            conn.exec_driver_sql(stmt)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


def _append(factory, n=3):
    with factory() as s:
        for i in range(n):
            emit(
                s,
                event_name=EVENT,
                aggregate_type="question",
                aggregate_id=f"q{i}",
                payload={"i": i},
                producer="catalog.unit_test",
            )
        s.commit()


def test_drift_detected_then_rebuilt(factory):
    _append(factory)
    assert Dispatcher(factory).run_once().processed == 3
    with factory() as s:
        first = reconcile.sample(s)
        reconcile.record(s, first)
        s.commit()
    assert first.checked == 3 and first.drifted == 0 and first.status == "ok"

    # 人为篡改一条投影：checksum 与最新事件不一致。
    with factory() as s:
        s.execute(text(
            "UPDATE foundation_projection_state SET checksum='deadbeef' "
            "WHERE aggregate_id='q1'"))
        s.commit()
    with factory() as s:
        drifted = reconcile.sample(s)
        reconcile.record(s, drifted)
        s.commit()
    assert drifted.drifted == 1 and drifted.status == "drift"

    with factory() as s:
        fixed = reconcile.rebuild(s)
        reconcile.record(s, fixed)
        s.commit()
    assert fixed.repaired == 1

    with factory() as s:
        final = reconcile.sample(s)
        reconcile.record(s, final)
        s.commit()
    assert final.drifted == 0 and final.status == "ok"
    with factory() as s:
        runs = s.execute(text(
            "SELECT status FROM foundation_reconcile_run ORDER BY started_at")).scalars().all()
    assert runs == ["ok", "drift", "ok", "ok"]
