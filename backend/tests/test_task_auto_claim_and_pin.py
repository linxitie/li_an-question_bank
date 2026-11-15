"""自动领取任务金币 + 论坛置顶时长（2026-11-10）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.api.v1.growth.tasks import _today_key
from app.models.models import (
    CoinRecord,
    ForumPost,
    PracticeRecord,
    SysUser,
    Task,
    UserTaskProgress,
)
from app.services import achievement_judge, forum_pin
from app.services.task_reward import auto_claim


def _daily_task(db, code="auto_daily_10", threshold=10, reward=20):
    task = Task(
        task_code=code,
        t_type="daily",
        title=code,
        description="完成10道题目",
        metric="today_questions",
        mode="calc",
        threshold=threshold,
        reward_coins=reward,
        reward_growth=0,
        sort_order=0,
        enabled=1,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_judge_action_grants_task_coins_on_completion(db_session, test_user):
    task = _daily_task(db_session)
    now = datetime.now()
    for index in range(10):
        db_session.add(PracticeRecord(
            user_id=test_user.user_id,
            question_id=95000 + index,
            is_correct=1,
            practice_time=now,
        ))
    db_session.commit()

    result = achievement_judge.judge_action(
        test_user.user_id,
        "practice.submit",
        db_session,
        session={"session_id": "auto-claim-1"},
    )
    update = next(item for item in result["task_progress"] if item["task_id"] == task.task_id)
    assert update["completed"] is True

    progress = (
        db_session.query(UserTaskProgress)
        .filter(UserTaskProgress.task_id == task.task_id)
        .one()
    )
    assert progress.claimed == 1
    assert progress.completed == 1

    db_session.expire_all()
    records = (
        db_session.query(CoinRecord)
        .filter(
            CoinRecord.user_id == test_user.user_id,
            CoinRecord.related_id == task.task_id,
            CoinRecord.source_type.in_(["TASK", "RANDOM_TASK"]),
        )
        .all()
    )
    assert sum(r.coin_change for r in records) == 20


def test_auto_claim_service_is_idempotent(db_session, test_user):
    task = _daily_task(db_session, code="auto_idem")
    progress = UserTaskProgress(
        user_id=test_user.user_id,
        task_id=task.task_id,
        period_key=_today_key(),
        current=10,
        completed=1,
        claimed=0,
    )
    db_session.add(progress)
    db_session.commit()

    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).one()
    first = auto_claim(db_session, user, task, progress, datetime.now())
    assert first == 20
    second = auto_claim(db_session, user, task, progress, datetime.now())
    assert second == 0
    db_session.commit()

    db_session.expire_all()
    assert db_session.query(CoinRecord).filter(CoinRecord.related_id == task.task_id).count() == 1


def test_auto_claim_endpoint_backfills_completed_task(db_session, client, auth_headers, test_user):
    task = _daily_task(db_session, code="auto_backfill", threshold=1, reward=5)
    db_session.add(
        UserTaskProgress(
            user_id=test_user.user_id,
            task_id=task.task_id,
            period_key=_today_key(),
            current=1,
            completed=1,
            claimed=0,
        )
    )
    db_session.add(
        PracticeRecord(
            user_id=test_user.user_id,
            question_id=96001,
            is_correct=1,
            practice_time=datetime.now(),
        )
    )
    db_session.commit()

    first = client.post("/api/tasks/auto-claim", headers=auth_headers)
    assert first.status_code == 200, first.text
    body = first.json()
    granted = {item["task_id"]: item["reward_coins"] for item in body["granted"]}
    assert granted.get(task.task_id) == 5

    again = client.post("/api/tasks/auto-claim", headers=auth_headers)
    assert again.status_code == 200, again.text
    assert all(item["task_id"] != task.task_id for item in again.json()["granted"])


def test_forum_pin_duration_and_expiry(db_session, client, admin_headers, test_user):
    post = ForumPost(
        user_id=test_user.user_id,
        title="置顶时长测试",
        content="内容",
        share_type="DISCUSSION",
        status="NORMAL",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    res = client.post(
        f"/api/admin/forum/posts/{post.post_id}/pin",
        json={"pinned": True, "days": 3},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["isTop"] is True
    assert data["pinUntil"]

    db_session.expire_all()
    row = db_session.query(ForumPost).filter(ForumPost.post_id == post.post_id).one()
    assert row.is_top == 1
    assert row.pin_until is not None
    delta = row.pin_until - datetime.now()
    assert timedelta(days=2, hours=23) < delta <= timedelta(days=3, minutes=1)

    # 到期后调度服务自动取消置顶
    row.pin_until = datetime.now() - timedelta(minutes=1)
    db_session.commit()
    assert forum_pin.expire_due(db_session) >= 1
    db_session.expire_all()
    row = db_session.query(ForumPost).filter(ForumPost.post_id == post.post_id).one()
    assert row.is_top == 0
    assert row.pin_until is None

