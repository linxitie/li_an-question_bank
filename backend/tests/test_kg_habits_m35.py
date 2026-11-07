"""M3.5 做题习惯维度（2026-11-05）：时段/学科/时长/稳定性 → 采样温度。

断言：
- 习惯画像字段完整，能从 practice_record 聚合出时段与学科偏好；
- 稳定性高 → 温度低（聚焦），稳定性低 → 温度高（探索）；
- 样本量小时向默认温度回归；
- 采样接口默认使用习惯温度，可手动覆盖。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models.models import PracticeRecord
from app.services import kg_habits


def _practice_at(db, user_id, when: datetime, subject_id=1, time_spent=20):
    db.add(
        PracticeRecord(
            user_id=user_id,
            question_id=1,
            subject_id=subject_id,
            is_correct=1,
            practice_time=when,
            practice_date=when.date(),
            time_spent=time_spent,
            source_type="practice",
        )
    )


def test_empty_profile_returns_default_temperature(db_session, test_user):
    profile = kg_habits.build_habit_profile(db_session, test_user.user_id)
    assert profile["total_records"] == 0
    assert profile["preferred_slot"] is None
    assert profile["temperature"] == kg_habits.BASE_TEMPERATURE
    assert "数据不足" in profile["habit_summary"]


def test_profile_detects_slot_and_subject(db_session, test_user):
    base = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
    for i in range(8):
        _practice_at(db_session, test_user.user_id, base - timedelta(days=i), subject_id=3)
    # 少量上午、其它学科
    _practice_at(db_session, test_user.user_id, base.replace(hour=9) - timedelta(days=1), subject_id=1)
    _practice_at(db_session, test_user.user_id, base.replace(hour=9) - timedelta(days=2), subject_id=1)
    db_session.commit()

    profile = kg_habits.build_habit_profile(db_session, test_user.user_id)
    assert profile["preferred_slot"] == "evening"
    assert profile["preferred_subject"] == 3
    assert profile["slot_distribution"]["evening"] == 8
    assert profile["active_days"] >= 8
    assert profile["avg_time_spent"] > 0


def test_stable_habit_lowers_temperature(db_session, test_user):
    base = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
    # 每天固定 3 条，节奏稳定
    for day in range(20):
        for k in range(3):
            _practice_at(db_session, test_user.user_id, base - timedelta(days=day, minutes=k))
    db_session.commit()

    profile = kg_habits.build_habit_profile(db_session, test_user.user_id)
    assert profile["stability"] > 0.5
    assert profile["temperature"] < kg_habits.BASE_TEMPERATURE


def test_unstable_habit_raises_temperature(db_session, test_user):
    base = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
    # 忽多忽少：1 天 20 条、1 天 1 条交替
    for day in range(20):
        n = 20 if day % 2 == 0 else 1
        for k in range(n):
            _practice_at(db_session, test_user.user_id, base - timedelta(days=day, minutes=k))
    db_session.commit()

    profile = kg_habits.build_habit_profile(db_session, test_user.user_id)
    assert profile["stability"] < 0.5
    assert profile["temperature"] > kg_habits.BASE_TEMPERATURE


def test_temperature_regresses_with_small_sample():
    high_conf = kg_habits.temperature_for(0.95, 200)
    low_conf = kg_habits.temperature_for(0.95, 2)
    assert abs(low_conf - kg_habits.BASE_TEMPERATURE) < abs(high_conf - kg_habits.BASE_TEMPERATURE)


def test_habits_endpoint(client, db_session, auth_headers, test_user):
    base = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    for day in range(10):
        _practice_at(db_session, test_user.user_id, base - timedelta(days=day), subject_id=2)
    db_session.commit()

    res = client.get("/api/knowledge/kg/habits/mine?days=30", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_records"] == 10
    assert body["preferred_slot"] == "morning"
    assert body["preferred_subject"] == 2
    assert 0.4 <= body["temperature"] <= 1.3


def test_sample_endpoint_uses_habit_temperature(client, db_session, auth_headers, test_user):
    from app.services import kg_growth
    from app.models.models import KnowledgePoint

    point = KnowledgePoint(point_name="习惯调温知识点", subject_id=1, level=1, status=1)
    db_session.add(point)
    db_session.commit()
    kg_growth.record_event(db_session, test_user.user_id, point.point_id, "answer_wrong")
    db_session.commit()

    res = client.get("/api/knowledge/kg/sample?n=1", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["temperature_source"] == "habit_profile"

    manual = client.get("/api/knowledge/kg/sample?n=1&temperature=1.1", headers=auth_headers)
    assert manual.status_code == 200
    assert manual.json()["temperature_source"] == "manual"

    # 手动覆盖时才使用传入温度
    assert abs(manual.json()["temperature"] - 1.1) < 0.01
