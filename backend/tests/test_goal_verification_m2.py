"""目标完成判定加固（2026-11-05）。

漏洞：原 `/complete` 与 `/progress` 接受客户端自报，用户可凭空完成目标领金币。
修复后判定只认答题事实（practice_record + exam_answer_detail）。

断言：
- 没有答题记录时：/complete 与 /confirm-complete 都返回 400，且不发币；
- 有足量答题记录时：可以完成并发放金币；
- 重复完成 / 取消后再完成：不重复发币（coin_claimed 幂等）。
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.models.models import PracticeRecord, StudyGoal


def _goal(db, user_id, *, target=5, goal_type="DAILY", base_reward=50):
    g = StudyGoal(
        user_id=user_id,
        title="今日刷题目标",
        goal_type=goal_type,
        target_count=target,
        current_count=0,
        is_completed=0,
        base_reward=base_reward,
        status=1,
        create_time=datetime.now(),
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def _practice(db, user_id, n, subject_id=1):
    for _ in range(n):
        db.add(
            PracticeRecord(
                user_id=user_id,
                question_id=1,
                subject_id=subject_id,
                is_correct=1,
                practice_time=datetime.now(),
                practice_date=datetime.now().date(),
                time_spent=10,
                source_type="practice",
            )
        )
    db.commit()


def test_complete_rejected_without_real_progress(client, db_session, auth_headers, test_user):
    goal = _goal(db_session, test_user.user_id, target=5)

    res = client.post(f"/api/goals/{goal.goal_id}/complete", headers=auth_headers)
    assert res.status_code == 400, res.text
    assert "未完成" in res.json()["detail"]

    db_session.refresh(goal)
    assert goal.is_completed == 0
    db_session.refresh(test_user)
    assert test_user.total_coins == 0, "判定失败不能发币"


def test_confirm_complete_rejected_without_real_progress(
    client, db_session, auth_headers, test_user
):
    goal = _goal(db_session, test_user.user_id, target=3)

    res = client.post(f"/api/goals/{goal.goal_id}/confirm-complete", headers=auth_headers)
    assert res.status_code == 400, res.text

    db_session.refresh(goal)
    assert goal.is_completed == 0
    assert goal.current_count == 0, "不能把进度伪造到目标值"


def test_progress_endpoint_ignores_client_increment(client, db_session, auth_headers, test_user):
    goal = _goal(db_session, test_user.user_id, target=10)

    # 客户端谎报 +9，服务端应按事实仍为 0
    res = client.post(f"/api/goals/{goal.goal_id}/progress?increment=9", headers=auth_headers)
    assert res.status_code == 200, res.text

    db_session.refresh(goal)
    assert goal.current_count == 0


def test_complete_passes_with_real_progress_and_pays(
    client, db_session, auth_headers, test_user
):
    goal = _goal(db_session, test_user.user_id, target=3, base_reward=60)
    _practice(db_session, test_user.user_id, 3)

    res = client.post(f"/api/goals/{goal.goal_id}/complete", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reward_coins"] > 0

    db_session.refresh(goal)
    assert goal.is_completed == 1
    assert getattr(goal, "coin_claimed", 0) == 1

    db_session.refresh(test_user)
    assert test_user.total_coins == body["reward_coins"]


def test_no_double_pay_after_undo(client, db_session, auth_headers, test_user):
    goal = _goal(db_session, test_user.user_id, target=2, base_reward=60)
    _practice(db_session, test_user.user_id, 2)

    first = client.post(f"/api/goals/{goal.goal_id}/complete", headers=auth_headers)
    assert first.status_code == 200, first.text
    first_reward = first.json()["reward_coins"]

    # 取消完成
    undo = client.post(f"/api/goals/{goal.goal_id}/undo-complete", headers=auth_headers)
    assert undo.status_code == 200, undo.text

    # 再次完成：不允许重复发币
    second = client.post(f"/api/goals/{goal.goal_id}/complete", headers=auth_headers)
    assert second.status_code == 200, second.text
    assert second.json()["reward_coins"] == 0
    assert second.json().get("already_claimed") is True

    db_session.refresh(test_user)
    assert test_user.total_coins == first_reward


def test_subject_mode_filters_progress(client, db_session, auth_headers, test_user):
    goal = _goal(db_session, test_user.user_id, target=3)
    goal.subject_mode = 2  # 只统计学科 2
    db_session.commit()

    _practice(db_session, test_user.user_id, 3, subject_id=1)  # 学科 1，不应计入
    res = client.post(f"/api/goals/{goal.goal_id}/complete", headers=auth_headers)
    assert res.status_code == 400

    _practice(db_session, test_user.user_id, 3, subject_id=2)
    res = client.post(f"/api/goals/{goal.goal_id}/complete", headers=auth_headers)
    assert res.status_code == 200, res.text
