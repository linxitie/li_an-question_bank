# 学习周报与方案快照接口集成测试（模块4 · 4-6 / 7-4）
import asyncio
from datetime import datetime, timedelta

from app.api.v1.growth.plan_snapshot import capture, diff, list_versions
from app.api.v1.growth.weekly_report import weekly_report
from app.models.models import FocusRecord, StudyGoal, WrongQuestionPersonal


def _run(coro):
    return asyncio.run(coro)


def _goal(db, user, title, plan_id=888, done=0, task_date=None):
    g = StudyGoal(
        user_id=user.user_id,
        title=title,
        goal_type="DAILY",
        target_count=10,
        current_count=0,
        subject_mode=0,
        expected_minutes=30,
        priority=1,
        is_completed=done,
        plan_id=plan_id,
        sort_order=1,
        task_date=task_date or datetime.now().strftime("%Y-%m-%d"),
        plan_meta='{"summary": "本周方案", "phases": [{"name": "基础阶段"}], "tips": ""}',
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def test_weekly_report_counts_focus_and_tasks(db_session, test_user):
    now = datetime.now()
    db_session.add(FocusRecord(user_id=test_user.user_id, started_at=now, ended_at=now, minutes=30, mode="focus", source="test"))
    _goal(db_session, test_user, "任务一", done=1)
    _goal(db_session, test_user, "任务二", done=0)
    db_session.commit()

    data = _run(weekly_report(weeks_ago=0, current_user=test_user, db=db_session))
    assert data["focus"]["minutes"] >= 30
    assert data["tasks"]["total"] >= 2
    assert data["tasks"]["done"] >= 1
    assert 0 <= data["tasks"]["completion"] <= 100
    assert data["has_data"] is True


def test_weekly_report_empty_is_honest(db_session, test_user):
    data = _run(weekly_report(weeks_ago=0, current_user=test_user, db=db_session))
    assert data["has_data"] is False
    assert "还没有记录" in data["comment"]


def test_snapshot_capture_and_diff(db_session, test_user):
    _goal(db_session, test_user, "任务A", done=0)
    _goal(db_session, test_user, "任务B", done=0)
    db_session.commit()

    v1 = _run(capture(current_user=test_user, db=db_session))
    assert v1["version"] == 1
    assert v1["task_count"] == 2

    # 改方案：A 完成、删 B、加 C
    rows = db_session.query(StudyGoal).filter(StudyGoal.user_id == test_user.user_id).all()
    for r in rows:
        if r.title == "任务A":
            r.is_completed = 1
        if r.title == "任务B":
            db_session.delete(r)
    _goal(db_session, test_user, "任务C", done=0)
    db_session.commit()

    v2 = _run(capture(current_user=test_user, db=db_session))
    assert v2["version"] == 2

    result = _run(diff(from_version=1, to_version=2, current_user=test_user, db=db_session))
    assert result["counts"]["added"] == 1
    assert result["counts"]["removed"] == 1
    assert result["counts"]["changed"] == 1
    assert result["added"][0]["title"] == "任务C"
    assert result["removed"][0]["title"] == "任务B"


def test_snapshot_list_returns_history(db_session, test_user):
    _goal(db_session, test_user, "任务A")
    db_session.commit()
    _run(capture(current_user=test_user, db=db_session))
    _run(capture(current_user=test_user, db=db_session))
    data = _run(list_versions(current_user=test_user, db=db_session))
    assert len(data["items"]) == 2
    assert data["items"][0]["version"] == 2   # 倒序
