# AI 学习计划任务 被"刷题量"误判完成 —— 回归测试（2026-11-23）
#
# 现象（秉瑞反馈）：AI 生成的自定义任务（plan_id 非空、target_count=1）根本没做，
# 却显示"已完成 / 完成进度 100%"。根因：goal_progress.sync_goal_progress 把 CUSTOM
# 与 DAILY 同口径（按当天刷题量），target_count=1 时做一道题就顶满。
#
# 修复口径：plan_id 非空的计划任务只由用户勾选（/api/plan/task/{id}/toggle）完成，
# 刷题同步不再改动它们；用户手动创建的自定义目标（plan_id 为空）仍按刷题量推进。
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.models import PracticeRecord, StudyGoal  # noqa: E402
from app.services.goal_progress import sync_goal_progress  # noqa: E402

TODAY = date.today()


def _plan_task(db, user_id, title="[睡前] 错题复盘-公式默写"):
    row = StudyGoal(
        user_id=user_id,
        title=title,
        goal_type="CUSTOM",
        target_count=1,
        current_count=0,
        is_completed=0,
        status=1,
        plan_id=1,
        plan_meta=json.dumps({"summary": "x"}, ensure_ascii=False),
        task_date=TODAY.strftime("%Y-%m-%d"),
        deadline=datetime.now() + timedelta(days=60),
        coin_reward=10,
        coin_claimed=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _manual_goal(db, user_id, target=3):
    row = StudyGoal(
        user_id=user_id,
        title="每日完成 3 题",
        goal_type="CUSTOM",
        target_count=target,
        current_count=0,
        is_completed=0,
        status=1,
        plan_id=None,
        coin_reward=5,
        coin_claimed=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _practice(db, user_id, n=1, subject_id=1):
    for _ in range(n):
        db.add(
            PracticeRecord(
                user_id=user_id,
                question_id=1,
                subject_id=subject_id,
                is_correct=1,
                practice_time=datetime.now(),
                practice_date=TODAY,
                source_type="随机练习",
            )
        )
    db.commit()


def test_plan_task_not_completed_by_practice(db_session, test_user):
    task = _plan_task(db_session, test_user.user_id)
    _practice(db_session, test_user.user_id, n=5)

    sync_goal_progress(test_user.user_id, db_session)

    db_session.expire_all()
    row = db_session.get(StudyGoal, task.goal_id)
    assert row.current_count == 0, "计划任务不能被刷题量推进"
    assert row.is_completed == 0, "计划任务不能被刷题同步判完成"
    assert row.completed_time is None
    assert (row.reward_coins or 0) == 0


def test_manual_goal_still_advances_by_practice(db_session, test_user):
    goal = _manual_goal(db_session, test_user.user_id, target=3)
    _practice(db_session, test_user.user_id, n=2)

    sync_goal_progress(test_user.user_id, db_session)

    db_session.expire_all()
    row = db_session.get(StudyGoal, goal.goal_id)
    assert row.current_count == 2, "手动目标仍按真实刷题量推进"
    assert row.is_completed == 0

    _practice(db_session, test_user.user_id, n=1)
    sync_goal_progress(test_user.user_id, db_session)
    db_session.expire_all()
    row = db_session.get(StudyGoal, goal.goal_id)
    assert row.current_count == 3
    assert row.is_completed == 1, "达到目标量应自动完成"


def test_plan_task_still_completes_by_user_toggle(db_session, test_user, client, auth_headers):
    task = _plan_task(db_session, test_user.user_id)
    _practice(db_session, test_user.user_id, n=3)  # 先刷题，不应完成

    resp = client.post(f"/api/plan/task/{task.goal_id}/toggle", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_completed"] == 1

    db_session.expire_all()
    row = db_session.get(StudyGoal, task.goal_id)
    assert row.is_completed == 1 and row.current_count == 1
    assert row.completed_time is not None


def test_sync_ignores_completed_plan_tasks(db_session, test_user):
    task = _plan_task(db_session, test_user.user_id)
    task.is_completed = 1
    task.current_count = 1
    task.completed_time = datetime.now()
    db_session.commit()
    _practice(db_session, test_user.user_id, n=2)

    changed = sync_goal_progress(test_user.user_id, db_session)

    assert task.goal_id not in changed
    db_session.expire_all()
    assert db_session.get(StudyGoal, task.goal_id).is_completed == 1
