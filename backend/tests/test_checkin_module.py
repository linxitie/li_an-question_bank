"""每日签到（E10）模块测试（P2-50）。

覆盖：
- 一天一次：重复 POST 只写一条 daily_checkin、只发一次奖励、只发一次事件；
- 连续天数推导：昨日有记录则 +1，断签则回到 1；
- 奖励复用 badge_task 的 daily_checkin 任务（reward_coins / reward_growth）；
- 并发两次签到仅一个成功（唯一约束 + INSERT OR IGNORE 抢占）；
- 路由可见性与状态查询。
"""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.growth import checkin as checkin_api
from app.core.database import Base
from app.core.trigger_types import TRIGGER_CHECKIN_DONE
from app.models.models import CoinRecord, DailyCheckin, SysUser, Task
from app.services import checkin_service

CHECKIN_PATH = "/api/v1/growth/checkin"
STATUS_PATH = "/api/v1/growth/checkin/status"


@pytest.fixture
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append(
            {
                "user_id": user_id,
                "trigger_type": trigger_type,
                "session": session,
            }
        )
        return True

    monkeypatch.setattr(checkin_api, "record_user_action", fake_record)
    return events


@pytest.fixture
def checkin_task(db_session):
    task = Task(
        task_code=checkin_service.CHECKIN_TASK_CODE,
        t_type="daily",
        title="每日签到",
        metric="checkin",
        mode="event",
        threshold=1,
        reward_coins=12,
        reward_growth=7,
        sort_order=1,
        enabled=1,
    )
    db_session.add(task)
    db_session.commit()
    return task


def _yesterday_str() -> str:
    return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def _post_checkin(client, auth_headers):
    return client.post(CHECKIN_PATH, headers=auth_headers)


def _events(events, trigger_type):
    return [e for e in events if e["trigger_type"] == trigger_type]


def test_checkin_routes_are_registered():
    from app.main import app

    paths = [route.path for route in app.routes if "checkin" in route.path]
    assert CHECKIN_PATH in paths
    assert STATUS_PATH in paths


def test_second_checkin_same_day_is_idempotent(
    client, auth_headers, test_user, checkin_task, published, db_session
):
    first = _post_checkin(client, auth_headers)
    second = _post_checkin(client, auth_headers)

    assert first.status_code == 200
    first_body = first.json()
    assert first_body["is_today_first"] is True
    assert first_body["continuous_days"] == 1
    assert first_body["today_reward"] == 12
    assert first_body["reward_growth"] == 7

    assert second.status_code == 200
    second_body = second.json()
    assert second_body["is_today_first"] is False
    assert second_body["today_reward"] == 12
    assert second_body["reward_growth"] == 0

    db_session.expire_all()
    assert db_session.query(DailyCheckin).count() == 1
    assert db_session.query(CoinRecord).count() == 1
    record = db_session.query(CoinRecord).one()
    assert record.coin_change == 12
    assert record.source_type == "CHECKIN"

    user = db_session.query(SysUser).filter_by(user_id=test_user.user_id).one()
    assert user.total_coins == 12
    assert user.growth_points == 7
    assert user.continuous_checkin_days == 1
    assert user.total_checkin_days == 1

    assert len(_events(published, TRIGGER_CHECKIN_DONE)) == 1


def test_status_reflects_today_state(
    client, auth_headers, checkin_task
):
    before = client.get(STATUS_PATH, headers=auth_headers)
    assert before.status_code == 200
    before_body = before.json()
    assert before_body["checked_in"] is False
    assert before_body["today_reward"] == 0
    assert before_body["next_reward"] == {"coins": 12, "growth": 7}

    _post_checkin(client, auth_headers)

    after = client.get(STATUS_PATH, headers=auth_headers)
    assert after.status_code == 200
    after_body = after.json()
    assert after_body["checked_in"] is True
    assert after_body["continuous_days"] == 1
    assert after_body["today_reward"] == 12


def test_streak_continues_from_yesterday(
    client, auth_headers, test_user, checkin_task, published, db_session
):
    yesterday = DailyCheckin(
        user_id=test_user.user_id,
        checkin_date=_yesterday_str(),
        checkin_time=datetime.now() - timedelta(days=1),
        continuous_days=3,
        total_days=4,
        has_makeup=0,
        coin_reward=5,
        streak_bonus=0,
    )
    db_session.add(yesterday)
    test_user.continuous_checkin_days = 3
    test_user.total_checkin_days = 4
    db_session.commit()

    response = _post_checkin(client, auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["continuous_days"] == 4
    assert body["is_today_first"] is True

    db_session.expire_all()
    today_record = db_session.query(DailyCheckin).filter_by(
        user_id=test_user.user_id, checkin_date=_today_str()
    ).one()
    assert today_record.continuous_days == 4
    assert today_record.total_days == 5


def test_missed_yesterday_resets_streak(
    client, auth_headers, test_user, checkin_task, published, db_session
):
    test_user.continuous_checkin_days = 6
    test_user.total_checkin_days = 10
    db_session.commit()

    response = _post_checkin(client, auth_headers)

    assert response.status_code == 200
    assert response.json()["continuous_days"] == 1


def test_default_reward_when_task_missing(
    client, auth_headers, test_user, published, db_session
):
    response = _post_checkin(client, auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["today_reward"] == checkin_service.DEFAULT_CHECKIN_COINS
    assert body["reward_growth"] == checkin_service.DEFAULT_CHECKIN_GROWTH

    db_session.expire_all()
    user = db_session.query(SysUser).filter_by(user_id=test_user.user_id).one()
    assert user.total_coins == checkin_service.DEFAULT_CHECKIN_COINS
    assert user.growth_points == checkin_service.DEFAULT_CHECKIN_GROWTH


def test_concurrent_checkin_only_one_reward(tmp_path):
    db_path = tmp_path / "checkin_concurrency.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(
        bind=engine,
        tables=[
            SysUser.__table__,
            Task.__table__,
            DailyCheckin.__table__,
            CoinRecord.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)

    with Session() as seed:
        user = SysUser(
            user_no="concurrent001",
            username="并发用户",
            password="x",
            phone="13800138001",
            user_type="student",
            role_level=1,
            status=1,
        )
        seed.add(user)
        seed.add(
            Task(
                task_code=checkin_service.CHECKIN_TASK_CODE,
                t_type="daily",
                title="每日签到",
                metric="checkin",
                mode="event",
                threshold=1,
                reward_coins=12,
                reward_growth=7,
                sort_order=1,
                enabled=1,
            )
        )
        seed.commit()
        user_id = user.user_id

    barrier = threading.Barrier(2)
    results = []
    errors = []

    def worker():
        session = Session()
        try:
            barrier.wait(timeout=10)
            results.append(checkin_service.perform_checkin(session, user_id))
        except Exception as exc:  # noqa: BLE001 - 收集线程异常供断言
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert errors == []
    assert sum(1 for item in results if item["is_today_first"]) == 1
    assert sum(1 for item in results if not item["is_today_first"]) == 1

    with Session() as verify:
        assert verify.query(DailyCheckin).count() == 1
        assert verify.query(CoinRecord).count() == 1
        user = verify.query(SysUser).filter_by(user_id=user_id).one()
        assert user.total_coins == 12
        assert user.growth_points == 7

    engine.dispose()
