"""成就成长枢纽测试（P2-56）。

覆盖：
- 11 个 trigger_type 字符串值（E1–E10，E5 两个值）各触发一次判据；
- 同 ``trigger_type + session`` 重复投递只计一次；
- ``badge_task`` 的 ``mode=event`` 累加与 ``mode=calc`` 历史重算；
- 成就解锁经 ``achievement_reward`` 单点发奖，重复解锁不重复发奖；
- 历史回放 ``recalculate()`` 只判定不发奖；
- 事件消费者对 10 类事件逐一调用判据，且判据异常不向外抛。
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.core import events
from app.core.trigger_types import (
    ALL_TRIGGER_TYPES,
    TRIGGER_CHECKIN_DONE,
    TRIGGER_NOTE_CREATED,
    TRIGGER_PRACTICE_SUBMIT,
)
from app.models.models import (
    Achievement,
    CoinRecord,
    PracticeRecord,
    SysUser,
    Task,
    UserAchievement,
    UserTaskProgress,
)
from app.services import (
    achievement_judge,
    achievement_reward,
    achievement_service,
    event_consumer,
)
from app.services.growth_service import GROWTH_RULES


@pytest.fixture(autouse=True)
def _clean_dedupe():
    achievement_judge.reset_dedupe()
    yield
    achievement_judge.reset_dedupe()


def _add_task(
    db_session,
    code: str,
    metric: str,
    *,
    mode: str = "event",
    threshold: int = 1,
    t_type: str = "daily",
) -> Task:
    task = Task(
        task_code=code,
        t_type=t_type,
        title=code,
        metric=metric,
        mode=mode,
        threshold=threshold,
        reward_coins=0,
        reward_growth=0,
        sort_order=0,
        enabled=1,
    )
    db_session.add(task)
    return task


def _progress_map(db_session):
    db_session.expire_all()
    return {
        row.task_id: int(row.current or 0)
        for row in db_session.query(UserTaskProgress).all()
    }


def test_all_trigger_types_are_eleven_strings():
    assert len(ALL_TRIGGER_TYPES) == 11
    assert len(set(ALL_TRIGGER_TYPES)) == 11


def test_each_trigger_updates_its_own_event_task(db_session, test_user):
    tasks = {}
    for index, trigger in enumerate(ALL_TRIGGER_TYPES):
        tasks[trigger] = _add_task(
            db_session, f"evt_{index}", trigger, mode="event", threshold=1
        )
    db_session.commit()

    for index, trigger in enumerate(ALL_TRIGGER_TYPES):
        result = achievement_judge.judge_action(
            test_user.user_id,
            trigger,
            db_session,
            session={"session_id": f"session-{index}"},
        )
        assert result["duplicate"] is False
        assert [item["task_code"] for item in result["task_progress"]] == [
            f"evt_{index}"
        ]

    progress = _progress_map(db_session)
    for trigger, task in tasks.items():
        assert progress[task.task_id] == 1, trigger


def test_same_trigger_and_session_only_counts_once(db_session, test_user):
    task = _add_task(db_session, "note_once", TRIGGER_NOTE_CREATED)
    db_session.commit()

    first = achievement_judge.judge_action(
        test_user.user_id,
        TRIGGER_NOTE_CREATED,
        db_session,
        session={"note_id": 77},
    )
    second = achievement_judge.judge_action(
        test_user.user_id,
        TRIGGER_NOTE_CREATED,
        db_session,
        session={"note_id": 77},
    )
    third = achievement_judge.judge_action(
        test_user.user_id,
        TRIGGER_NOTE_CREATED,
        db_session,
        session={"note_id": 78},
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["task_progress"] == []
    assert third["duplicate"] is False
    assert _progress_map(db_session)[task.task_id] == 2


def test_event_without_session_is_not_deduped(db_session, test_user):
    task = _add_task(db_session, "news_read", "news.read")
    db_session.commit()

    achievement_judge.judge_action(
        test_user.user_id, "news.read", db_session, session=None
    )
    achievement_judge.judge_action(
        test_user.user_id, "news.read", db_session, session=None
    )

    assert _progress_map(db_session)[task.task_id] == 2


def test_calc_task_recomputes_from_history(db_session, test_user):
    task = _add_task(
        db_session, "total_q", "total_questions", mode="calc", threshold=3
    )
    db_session.commit()

    for index in range(3):
        db_session.add(
            PracticeRecord(
                user_id=test_user.user_id,
                question_id=90000 + index,
                is_correct=1,
                practice_time=datetime.now(),
            )
        )
    db_session.commit()

    result = achievement_judge.judge_action(
        test_user.user_id,
        TRIGGER_PRACTICE_SUBMIT,
        db_session,
        session={"session_id": "calc-1", "total": 3, "correct": 3},
    )

    update = next(item for item in result["task_progress"] if item["task_id"] == task.task_id)
    assert update["mode"] == "calc"
    assert update["current"] == 3
    assert update["completed"] is True

    row = (
        db_session.query(UserTaskProgress)
        .filter(UserTaskProgress.task_id == task.task_id)
        .one()
    )
    assert row.current == 3
    assert row.completed == 1


def test_achievement_reward_is_idempotent(db_session, test_user):
    achievement = Achievement(
        category="测试",
        name="测试成就",
        icon="🏅",
        condition_desc="测试用成就",
        reward_coins=10,
        trigger_type=TRIGGER_CHECKIN_DONE,
        condition_code="first_login",
        threshold=0,
        sort_order=999,
        is_hidden=0,
    )
    db_session.add(achievement)
    db_session.commit()

    result = achievement_judge.judge_action(
        test_user.user_id,
        TRIGGER_CHECKIN_DONE,
        db_session,
        session={"date": "2026-10-18"},
    )
    newly = result["newly_unlocked"]
    assert [item["name"] for item in newly] == ["测试成就"]

    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).one()
    assert achievement_reward.grant_newly(db_session, user, newly) == 1
    db_session.commit()

    db_session.expire_all()
    assert db_session.query(UserAchievement).count() == 1
    assert db_session.query(CoinRecord).count() == 1
    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).one()
    assert user.total_coins == 10
    assert user.growth_points == GROWTH_RULES["achievement"]

    # 重复发放：同一成就同一用户只发一次
    assert achievement_reward.grant_newly(db_session, user, newly) == 0
    db_session.commit()

    db_session.expire_all()
    assert db_session.query(UserAchievement).count() == 1
    assert db_session.query(CoinRecord).count() == 1
    user = db_session.query(SysUser).filter(SysUser.user_id == test_user.user_id).one()
    assert user.total_coins == 10
    assert user.growth_points == GROWTH_RULES["achievement"]


def test_check_and_grant_still_works_through_reward(db_session, test_user):
    achievement = Achievement(
        category="测试",
        name="兼容成就",
        icon="🏅",
        condition_desc="兼容入口测试",
        reward_coins=5,
        trigger_type=TRIGGER_CHECKIN_DONE,
        condition_code="first_login",
        threshold=0,
        sort_order=998,
        is_hidden=0,
    )
    db_session.add(achievement)
    db_session.commit()

    first = achievement_service.check_and_grant(
        test_user.user_id, TRIGGER_CHECKIN_DONE, db_session
    )
    second = achievement_service.check_and_grant(
        test_user.user_id, TRIGGER_CHECKIN_DONE, db_session
    )

    assert [item["name"] for item in first] == ["兼容成就"]
    assert second == []
    db_session.expire_all()
    assert db_session.query(UserAchievement).count() == 1
    assert db_session.query(CoinRecord).count() == 1


def test_recalculate_replays_history_without_granting(db_session, test_user):
    task = _add_task(
        db_session, "replay_total", "total_questions", mode="calc", threshold=2
    )
    achievement = Achievement(
        category="测试",
        name="回放成就",
        icon="🏅",
        condition_desc="历史回放",
        reward_coins=8,
        trigger_type=TRIGGER_PRACTICE_SUBMIT,
        condition_code="total_questions",
        threshold=2,
        sort_order=997,
        is_hidden=0,
    )
    db_session.add(achievement)
    db_session.commit()

    for index in range(2):
        db_session.add(
            PracticeRecord(
                user_id=test_user.user_id,
                question_id=91000 + index,
                is_correct=1,
                practice_time=datetime.now(),
            )
        )
    db_session.commit()

    result = achievement_judge.recalculate(test_user.user_id, db_session)

    update = next(item for item in result["task_progress"] if item["task_id"] == task.task_id)
    assert update["current"] == 2
    assert [item["name"] for item in result["newly_unlocked"]] == ["回放成就"]

    # 回放只判定，不发奖
    db_session.expire_all()
    assert db_session.query(UserAchievement).count() == 0
    assert db_session.query(CoinRecord).count() == 0


@pytest.mark.parametrize("trigger_type", ALL_TRIGGER_TYPES)
def test_consumer_dispatches_every_trigger_to_judge(
    monkeypatch, db_session, test_user, trigger_type
):
    calls = []
    user_id = test_user.user_id

    def fake_judge(user_id, trigger, db, session=None):
        calls.append((user_id, trigger))
        return {
            "trigger_type": trigger,
            "duplicate": False,
            "task_progress": [],
            "newly_unlocked": [],
        }

    monkeypatch.setattr(achievement_judge, "judge_action", fake_judge)
    monkeypatch.setattr(event_consumer, "SessionLocal", lambda: db_session)

    asyncio.run(
        event_consumer._dispatch(
            events.Event(
                name=events.EV_USER_ACTION,
                payload={
                    "user_id": user_id,
                    "trigger_type": trigger_type,
                    "session": {"session_id": "dispatch-1"},
                },
            )
        )
    )

    assert calls == [(user_id, trigger_type)]


def test_consumer_catches_judge_exception(monkeypatch, db_session, test_user):
    user_id = test_user.user_id

    def boom(*args, **kwargs):
        raise RuntimeError("judge exploded")

    monkeypatch.setattr(achievement_judge, "judge_action", boom)
    monkeypatch.setattr(event_consumer, "SessionLocal", lambda: db_session)

    asyncio.run(
        event_consumer._dispatch(
            events.Event(
                name=events.EV_USER_ACTION,
                payload={
                    "user_id": user_id,
                    "trigger_type": TRIGGER_CHECKIN_DONE,
                    "session": {"date": "2026-10-18"},
                },
            )
        )
    )
