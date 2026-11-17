# 专注力接口（模块4 · 4-1）集成测试：直接调用端点函数，绕过 HTTP 与鉴权
import asyncio
from datetime import datetime, timedelta

import pytest

from app.api.v1.growth.focus import FocusRecordIn, add_record, heatmap
from app.models.models import FocusRecord


def _run(coro):
    return asyncio.run(coro)


def test_record_then_heatmap_aggregates(db_session, test_user):
    today = datetime.now().replace(minute=0, second=0, microsecond=0)
    morning = today.replace(hour=9)
    night = today.replace(hour=21)

    db_session.add(FocusRecord(user_id=test_user.user_id, started_at=morning, ended_at=morning + timedelta(minutes=25), minutes=25, mode="focus", source="test"))
    db_session.add(FocusRecord(user_id=test_user.user_id, started_at=night, ended_at=night + timedelta(minutes=50), minutes=50, mode="focus", source="test"))
    db_session.commit()

    data = _run(heatmap(weeks=4, current_user=test_user, db=db_session))
    assert data["total_minutes"] == 75
    assert data["session_count"] == 2
    wd = today.weekday()
    assert data["matrix"][wd][9] == 25
    assert data["matrix"][wd][21] == 50
    assert data["best_slot"]["minutes"] == 50
    assert data["daily"][today.strftime("%Y-%m-%d")] == 75


def test_break_records_are_excluded(db_session, test_user):
    now = datetime.now()
    db_session.add(FocusRecord(user_id=test_user.user_id, started_at=now, ended_at=now, minutes=5, mode="break", source="test"))
    db_session.commit()
    data = _run(heatmap(weeks=1, current_user=test_user, db=db_session))
    assert data["total_minutes"] == 0
    assert data["session_count"] == 0


def test_add_record_normalises_timezone(db_session, test_user):
    payload = FocusRecordIn(minutes=25, mode="focus", source="test", started_at=datetime.now().astimezone())
    result = _run(add_record(payload=payload, current_user=test_user, db=db_session))
    assert result["minutes"] == 25
    row = db_session.query(FocusRecord).order_by(FocusRecord.record_id.desc()).first()
    # 带时区的入参必须落成本地 naive，否则热力图整体偏 8 小时
    assert row.started_at.tzinfo is None
    assert abs((row.started_at - datetime.now()).total_seconds()) < 120


def test_records_outside_window_are_ignored(db_session, test_user):
    old = datetime.now() - timedelta(weeks=10)
    db_session.add(FocusRecord(user_id=test_user.user_id, started_at=old, ended_at=old, minutes=30, mode="focus", source="test"))
    db_session.commit()
    data = _run(heatmap(weeks=4, current_user=test_user, db=db_session))
    assert data["total_minutes"] == 0
