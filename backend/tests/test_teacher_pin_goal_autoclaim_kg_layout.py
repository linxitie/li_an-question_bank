"""教师端置顶时长 + 学习计划自动领币 + 图谱坐标持久化（2026-11-15）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models.models import CoinRecord, ForumPost, StudyGoal, SysUser


def _post(db, user_id: int, title: str) -> ForumPost:
    post = ForumPost(
        user_id=user_id,
        title=title,
        content="内容",
        share_type="DISCUSSION",
        status="NORMAL",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def _goal(db, user_id: int, *, reward=15, completed=0, claimed=0) -> StudyGoal:
    goal = StudyGoal(
        user_id=user_id,
        title="今日刷 20 道行测题",
        plan_id=9527,
        sort_order=1,
        is_completed=completed,
        completed_time=datetime.now() if completed else None,
        status=1,
        task_date=datetime.now().strftime("%Y-%m-%d"),
        coin_reward=reward,
        coin_claimed=claimed,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def _coin_sum(db, user_id: int, related_id: int) -> int:
    db.expire_all()
    rows = (
        db.query(CoinRecord)
        .filter(CoinRecord.user_id == user_id, CoinRecord.related_id == related_id)
        .all()
    )
    return sum(r.coin_change for r in rows)


# ------------------------- 教师端置顶时长 -------------------------

def test_teacher_pin_accepts_duration(db_session, client, test_teacher, teacher_headers):
    post = _post(db_session, test_teacher.user_id, "教师公告：本周模考安排")
    res = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/pin",
        json={"pinned": True, "days": 3},
        headers=teacher_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["isTop"] is True
    assert data["pinUntil"] and data["pinDays"] == 3

    db_session.expire_all()
    row = db_session.query(ForumPost).filter(ForumPost.post_id == post.post_id).one()
    assert row.is_top == 1
    assert row.pin_until is not None
    delta = row.pin_until - datetime.now()
    assert timedelta(days=2, hours=23) < delta <= timedelta(days=3, minutes=1)

    # 取消置顶：is_top / pin_until 一起清空
    off = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/pin",
        json={"pinned": False},
        headers=teacher_headers,
    )
    assert off.status_code == 200, off.text
    assert off.json()["isTop"] is False
    db_session.expire_all()
    row = db_session.query(ForumPost).filter(ForumPost.post_id == post.post_id).one()
    assert row.is_top == 0 and row.pin_until is None


def test_teacher_pin_permanent_when_days_missing(db_session, client, test_teacher, teacher_headers):
    post = _post(db_session, test_teacher.user_id, "永久置顶")
    res = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/pin",
        json={"pinned": True},
        headers=teacher_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["pinUntil"] is None
    db_session.expire_all()
    row = db_session.query(ForumPost).filter(ForumPost.post_id == post.post_id).one()
    assert row.is_top == 1 and row.pin_until is None


def test_teacher_cannot_pin_other_class_post(db_session, client, teacher_headers):
    outsider = SysUser(
        user_no="out001",
        username="外班学生",
        password="x",
        phone="13600136000",
        user_type="student",
        role_level=1,
        status=1,
        class_name="二班",
    )
    db_session.add(outsider)
    db_session.commit()
    db_session.refresh(outsider)
    post = _post(db_session, outsider.user_id, "外班帖子")

    res = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/pin",
        json={"pinned": True, "days": 1},
        headers=teacher_headers,
    )
    assert res.status_code == 403, res.text
    db_session.expire_all()
    assert db_session.query(ForumPost).filter(ForumPost.post_id == post.post_id).one().is_top == 0


def test_student_cannot_call_teacher_pin(db_session, client, test_user, auth_headers):
    post = _post(db_session, test_user.user_id, "学生帖子")
    res = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/pin",
        json={"pinned": True, "days": 1},
        headers=auth_headers,
    )
    assert res.status_code in (401, 403), res.text


# ------------------------- 学习计划自动领币 -------------------------

def test_plan_task_toggle_grants_coins_once(db_session, client, test_user, auth_headers):
    goal = _goal(db_session, test_user.user_id, reward=15)

    first = client.post(f"/api/plan/task/{goal.goal_id}/toggle", headers=auth_headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["is_completed"] == 1
    assert body["auto_claimed_coins"] == 15
    assert body["coin_claimed"] == 1
    assert _coin_sum(db_session, test_user.user_id, goal.goal_id) == 15

    # 取消完成 → 再完成：coin_claimed 已置 1，不允许重复刷币
    client.post(f"/api/plan/task/{goal.goal_id}/toggle", headers=auth_headers)
    again = client.post(f"/api/plan/task/{goal.goal_id}/toggle", headers=auth_headers)
    assert again.status_code == 200, again.text
    assert again.json()["auto_claimed_coins"] == 0
    assert _coin_sum(db_session, test_user.user_id, goal.goal_id) == 15


def test_plan_task_without_reward_does_not_claim(db_session, client, test_user, auth_headers):
    goal = _goal(db_session, test_user.user_id, reward=0)
    res = client.post(f"/api/plan/task/{goal.goal_id}/toggle", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["auto_claimed_coins"] == 0
    db_session.expire_all()
    assert db_session.query(StudyGoal).filter(StudyGoal.goal_id == goal.goal_id).one().coin_claimed == 0


def test_auto_claim_endpoint_backfills_goal_task(db_session, client, test_user, auth_headers):
    goal = _goal(db_session, test_user.user_id, reward=8, completed=1)

    first = client.post("/api/tasks/auto-claim", headers=auth_headers)
    assert first.status_code == 200, first.text
    mine = [item for item in first.json()["granted"] if item.get("source") == "study_goal"]
    assert any(item["goal_id"] == goal.goal_id and item["reward_coins"] == 8 for item in mine)
    assert _coin_sum(db_session, test_user.user_id, goal.goal_id) == 8

    second = client.post("/api/tasks/auto-claim", headers=auth_headers)
    assert second.status_code == 200, second.text
    assert all(
        item.get("goal_id") != goal.goal_id
        for item in second.json()["granted"]
        if item.get("source") == "study_goal"
    )
    assert _coin_sum(db_session, test_user.user_id, goal.goal_id) == 8


def test_overview_bootstraps_goal_claim_without_error(db_session, client, test_user, auth_headers):
    goal = _goal(db_session, test_user.user_id, reward=6, completed=1)
    res = client.get("/api/tasks/overview", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert _coin_sum(db_session, test_user.user_id, goal.goal_id) == 6


# ------------------------- 图谱坐标持久化 -------------------------

def test_kg_layout_roundtrip_and_reset(client, auth_headers):
    put = client.put(
        "/api/knowledge/kg/layout",
        json={"mode": "mine", "nodes": [{"point_id": 11, "x": 10.5, "y": -20.25}]},
        headers=auth_headers,
    )
    assert put.status_code == 200, put.text
    assert put.json()["saved"] == 1

    got = client.get("/api/knowledge/kg/layout?mode=mine", headers=auth_headers)
    assert got.status_code == 200, got.text
    assert got.json()["nodes"] == [{"point_id": 11, "x": 10.5, "y": -20.25}]

    # 重复保存同一节点是 upsert，不会产生第二行
    client.put(
        "/api/knowledge/kg/layout",
        json={"mode": "mine", "nodes": [{"point_id": 11, "x": 1, "y": 2}]},
        headers=auth_headers,
    )
    got = client.get("/api/knowledge/kg/layout?mode=mine", headers=auth_headers)
    assert got.json()["total"] == 1
    assert got.json()["nodes"] == [{"point_id": 11, "x": 1.0, "y": 2.0}]

    # mine 与 global 分开存，互不影响
    client.put(
        "/api/knowledge/kg/layout",
        json={"mode": "global", "nodes": [{"point_id": 12, "x": 3, "y": 4}]},
        headers=auth_headers,
    )
    assert client.get("/api/knowledge/kg/layout?mode=mine", headers=auth_headers).json()["total"] == 1
    assert client.get("/api/knowledge/kg/layout?mode=global", headers=auth_headers).json()["total"] == 1

    reset = client.put(
        "/api/knowledge/kg/layout",
        json={"mode": "global", "reset": True},
        headers=auth_headers,
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["reset"] is True
    assert client.get("/api/knowledge/kg/layout?mode=global", headers=auth_headers).json()["total"] == 0


def test_kg_layout_rejects_empty_nodes(client, auth_headers):
    res = client.put(
        "/api/knowledge/kg/layout",
        json={"mode": "mine", "nodes": []},
        headers=auth_headers,
    )
    assert res.status_code == 400, res.text
