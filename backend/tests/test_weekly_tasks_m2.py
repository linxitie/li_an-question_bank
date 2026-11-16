"""周任务 M2（2026-11-05）：奖励公式 / 置顶池 / 状态机 / 封顶 / 发券。

判定数据源为 exam 域（practice_record / exam_record），这里直接造数据验证聚合口径。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models.models import Coupon, CouponGrant, ExamRecord, PracticeRecord, Task, UserTaskProgress
from app.services import weekly_tasks as weekly


def _task(db, code, *, metric, threshold, base, difficulty=1.0, category="A", coupon=None, sort=1, pin=1):
    t = Task(
        task_code=code,
        t_type="weekly",
        title=code,
        description="",
        metric=metric,
        mode="calc",
        threshold=threshold,
        reward_coins=base,
        reward_growth=0,
        difficulty_factor=difficulty,
        scarcity_factor=1.0,
        category=category,
        coupon_code=coupon,
        pin_eligible=pin,
        sort_order=sort,
        enabled=1,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _practice(db, user_id, count, *, days_ago=0, correct=True, per_day=None):
    """造 practice_record：按天分摊 count 条。"""
    now = datetime.now()
    made = 0
    if per_day:
        for day_offset, n in per_day.items():
            d = now - timedelta(days=day_offset)
            for i in range(n):
                db.add(
                    PracticeRecord(
                        user_id=user_id,
                        question_id=1000 + i,
                        is_correct=1 if correct else 0,
                        practice_time=d,
                        practice_date=d.date(),
                        time_spent=5,
                        source_type="practice",
                    )
                )
                made += 1
    else:
        d = now - timedelta(days=days_ago)
        for i in range(count):
            db.add(
                PracticeRecord(
                    user_id=user_id,
                    question_id=1000 + i,
                    is_correct=1 if correct else 0,
                    practice_time=d,
                    practice_date=d.date(),
                    time_spent=5,
                    source_type="practice",
                )
            )
            made += 1
    db.commit()
    return made


# --------------------------- 奖励公式 ---------------------------

def test_effective_reward_applies_difficulty_and_scarcity(db_session):
    t = _task(db_session, "t_reward", metric="week_questions", threshold=1, base=200, difficulty=1.6)
    assert weekly.effective_reward(t) == 320  # 200×1.6
    assert weekly.effective_reward(t, Decimal("1.30")) == 416  # 再 ×1.30 置顶
    assert weekly.effective_reward(t, Decimal("1.50")) == 480  # 槽位 3


def test_effective_reward_capped_at_500(db_session):
    t = _task(db_session, "t_cap", metric="week_questions", threshold=1, base=400, difficulty=1.6)
    assert weekly.effective_reward(t, Decimal("1.50")) == 500  # 960 → 封顶 500


# --------------------------- 置顶池 ---------------------------

def test_ensure_week_pool_pins_three(db_session):
    for i in range(5):
        _task(db_session, f"pool_{i}", metric="week_questions", threshold=1, base=100, sort=i)
    rows = weekly.ensure_week_pool(db_session)
    slots = weekly.pinned_slots(db_session)
    assert len([s for s in slots.values() if s]) == 3
    # 幂等：再调一次不新增
    again = weekly.ensure_week_pool(db_session)
    assert len(again) == len(rows)


def test_pin_admin_moves_slot(client, db_session, admin_headers):
    t1 = _task(db_session, "pin_a", metric="week_questions", threshold=1, base=100, sort=1)
    t2 = _task(db_session, "pin_b", metric="week_questions", threshold=1, base=100, sort=2)
    weekly.ensure_week_pool(db_session)

    res = client.post(
        "/api/tasks/weekly/pool/pin",
        json={"task_id": t2.task_id, "slot": 1},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text

    pool = client.get("/api/tasks/weekly/pool", headers=admin_headers)
    assert pool.status_code == 200, pool.text
    items = {i["task_id"]: i["pinned_slot"] for i in pool.json()["items"]}
    assert items[t2.task_id] == 1


def test_pin_admin_rejects_bad_slot(client, db_session, admin_headers):
    t = _task(db_session, "pin_bad", metric="week_questions", threshold=1, base=100)
    res = client.post(
        "/api/tasks/weekly/pool/pin",
        json={"task_id": t.task_id, "slot": 9},
        headers=admin_headers,
    )
    assert res.status_code == 400


# --------------------------- 指标聚合 ---------------------------

def test_week_questions_counts_only_this_week(db_session, test_user):
    _practice(db_session, test_user.user_id, 5, days_ago=0)
    _practice(db_session, test_user.user_id, 3, days_ago=30)  # 上周以前的，不计
    assert weekly.compute_metric("week_questions", test_user.user_id, db_session) == 5


def test_week_active_days_counts_distinct_days(db_session, test_user):
    _practice(db_session, test_user.user_id, 0, per_day={0: 2, 1: 1, 3: 4})
    assert weekly.compute_metric("week_active_days", test_user.user_id, db_session) == 3


def test_week_daily_practice_days_requires_10_each(db_session, test_user):
    _practice(db_session, test_user.user_id, 0, per_day={0: 10, 1: 9, 2: 12})
    # 只有第 0、2 天达到 ≥10 题
    assert weekly.compute_metric("week_daily_practice_days", test_user.user_id, db_session) == 2


def test_week_exam_papers_counts_completed(db_session, test_user):
    now = datetime.now()
    for _ in range(2):
        db_session.add(
            ExamRecord(
                paper_id=1,
                user_id=test_user.user_id,
                exam_type="practice",
                start_time=now,
                submit_time=now,
                is_completed=1,
            )
        )
    db_session.add(
        ExamRecord(
            paper_id=1,
            user_id=test_user.user_id,
            exam_type="practice",
            start_time=now,
            is_completed=0,
        )
    )
    db_session.commit()
    assert weekly.compute_metric("week_exam_papers", test_user.user_id, db_session) == 2


# --------------------------- 领取与封顶 ---------------------------

def test_claim_weekly_uses_effective_reward_and_is_idempotent(
    client, db_session, auth_headers, test_user
):
    _task(db_session, "wk_claim", metric="week_questions", threshold=10, base=200, difficulty=1.6)
    weekly.ensure_week_pool(db_session)
    _practice(db_session, test_user.user_id, 12)

    task = db_session.query(Task).filter(Task.task_code == "wk_claim").first()
    res = client.post(f"/api/tasks/{task.task_id}/claim", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reward_coins"] >= 200  # 叠加难度/稀缺
    assert body["reward_base"] == 200

    again = client.post(f"/api/tasks/{task.task_id}/claim", headers=auth_headers)
    assert again.status_code == 400
    assert "已领取" in again.json()["detail"]


def test_weekly_reward_cap_900(client, db_session, auth_headers, test_user):
    # 三个高额任务，合计超过 900
    for i in range(3):
        _task(db_session, f"cap_{i}", metric="week_questions", threshold=1, base=500, difficulty=1.6, sort=i)
    _practice(db_session, test_user.user_id, 5)

    claimed = []
    for i in range(3):
        task = db_session.query(Task).filter(Task.task_code == f"cap_{i}").first()
        res = client.post(f"/api/tasks/{task.task_id}/claim", headers=auth_headers)
        if res.status_code == 200:
            claimed.append(res.json()["reward_coins"])

    assert sum(claimed) <= weekly.WEEKLY_REWARD_CAP


def test_coupon_task_grants_coupon(client, db_session, auth_headers, test_user):
    coupon = Coupon(
        code="WK_TEST_COUPON",
        title="周任务测试券",
        discount_type="rate",
        discount_value=0.8,
        scope="all",
        scope_value="",
        stock=10,
        status="active",
    )
    db_session.add(coupon)
    db_session.commit()

    task = _task(
        db_session,
        "wk_coupon",
        metric="week_questions",
        threshold=3,
        base=120,
        category="C",
        coupon="WK_TEST_COUPON",
    )
    _practice(db_session, test_user.user_id, 4)

    res = client.post(f"/api/tasks/{task.task_id}/claim", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["coupon_code"] == "WK_TEST_COUPON"

    held = db_session.query(CouponGrant).filter(CouponGrant.user_id == test_user.user_id).count()
    assert held == 1


def test_expire_marks_stale_weekly_progress(client, db_session, admin_headers, test_user):
    task = _task(db_session, "wk_stale", metric="week_questions", threshold=999, base=100)
    db_session.add(
        UserTaskProgress(
            user_id=test_user.user_id,
            task_id=task.task_id,
            period_key="2020-W01",
            current=1,
            completed=0,
            claimed=0,
        )
    )
    db_session.commit()

    res = client.post("/api/tasks/weekly/expire", headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["expired"] >= 1

    prog = db_session.query(UserTaskProgress).filter(UserTaskProgress.task_id == task.task_id).first()
    assert prog.expired == 1
