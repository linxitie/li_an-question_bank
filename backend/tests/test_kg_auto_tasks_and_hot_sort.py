"""知识图谱个性化周任务自动生成 + 奖励下调 + 热门榜新排序（2026-11-17）。

覆盖三件事：
1. 图谱个性化任务基础金币从 150 降到 40（生效值 = 基础 × 难度 1.2）；
2. 进入任务中心（GET /api/tasks/overview）即自动生成，无需点「生成个性化任务」；
3. 论坛热门榜支持 sort_by=favorites / replies（收藏量、回复量）。
"""
from __future__ import annotations

from app.models.models import (
    ForumFavorite,
    ForumPost,
    KgUserNodeState,
    KnowledgePoint,
    QuestionSubject,
    Task,
)
from app.services import kg_growth
from app.services.weekly_tasks import week_key


def _seed_subject(db) -> QuestionSubject:
    subject = db.query(QuestionSubject).filter(QuestionSubject.subject_name == "行测").first()
    if subject:
        return subject
    subject = QuestionSubject(subject_name="行测", status=1)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


def _seed_kg_nodes(db, user_id: int, n: int = 2) -> list[int]:
    subject = _seed_subject(db)
    point_ids = []
    for i in range(n):
        point = KnowledgePoint(
            point_name=f"图谱自动生成测试考点{i}",
            subject_id=subject.subject_id,
            level=1,
            status=1,
        )
        db.add(point)
        db.commit()
        db.refresh(point)
        point_ids.append(point.point_id)
        state = db.query(KgUserNodeState).filter(
            KgUserNodeState.user_id == user_id,
            KgUserNodeState.point_id == point.point_id,
        ).first()
        if not state:
            db.add(
                KgUserNodeState(
                    user_id=user_id,
                    point_id=point.point_id,
                    mastery=0.1,
                    heat=1.0,
                    attempt_count=10,
                    correct_count=1,
                )
            )
    db.commit()
    return point_ids


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


def test_kg_personalized_reward_lowered_to_40(db_session, test_user):
    """基础金币 40：生效值 = 40 × 1.2 = 48，最多 40×1.3×1.2 ≈ 63。"""
    _seed_kg_nodes(db_session, test_user.user_id, n=2)
    created = kg_growth.ensure_personalized_tasks(db_session, test_user.user_id, week=week_key(), n=2)
    assert created, "应至少生成 1 条个性化周任务"
    for task in created:
        assert task.personalized_for == test_user.user_id
        assert task.metric == "kg_node_questions"
        assert 40 <= int(task.reward_coins) <= 52, f"基础金币应为 40~52，实际 {task.reward_coins}"


def test_overview_auto_creates_kg_personalized_tasks(db_session, client, test_user, auth_headers):
    """不点「生成个性化任务」，进任务中心就应该看到 kg 任务，且标注 is_kg_generated。"""
    _seed_kg_nodes(db_session, test_user.user_id, n=2)
    week = week_key()
    db_session.query(Task).filter(
        Task.personalized_for == test_user.user_id,
        Task.task_code.like(f"kg_{week}_%"),
    ).delete(synchronize_session=False)
    db_session.commit()

    res = client.get("/api/tasks/overview", headers=auth_headers)
    assert res.status_code == 200, res.text

    weekly = res.json().get("weekly") or []
    kg_tasks = [t for t in weekly if t.get("is_kg_generated")]
    assert kg_tasks, "任务中心自动生成后应出现 is_kg_generated 任务"
    for t in kg_tasks:
        assert 47 <= int(t.get("reward_coins") or 0) <= 63, t.get("reward_coins")
        assert t.get("metric") == "kg_node_questions"


def test_forum_hot_sort_by_favorites(db_session, client, test_user):
    """sort_by=favorites：被收藏的帖子必须排在没被收藏的帖子前面。"""
    low = _post(db_session, test_user.user_id, "热门排序-没有收藏的帖子")
    high = _post(db_session, test_user.user_id, "热门排序-被收藏的帖子")
    db_session.add(ForumFavorite(post_id=high.post_id, user_id=test_user.user_id))
    db_session.commit()

    res = client.get("/api/forum/posts", params={"sort_by": "favorites", "limit": 50})
    assert res.status_code == 200, res.text
    ids = [p["id"] for p in res.json().get("posts", [])]
    assert high.post_id in ids and low.post_id in ids, ids
    assert ids.index(high.post_id) < ids.index(low.post_id)


def test_forum_hot_sort_by_replies_and_views_ok(client):
    for sort_by in ("replies", "comments", "likes", "views", "time"):
        res = client.get("/api/forum/posts", params={"sort_by": sort_by, "limit": 5})
        assert res.status_code == 200, (sort_by, res.text)
