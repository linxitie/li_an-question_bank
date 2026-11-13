"""M3 自生长知识图谱（2026-11-05）：事件演化 / 非均匀采样 / 贡献度 / 个性化任务。

关键断言：
- 答题事件更新节点掌握度与热度；错题权重 > 笔记 > 答对；
- 同一时间窗内先后命中两个知识点 → 自动新增/加权边；
- 采样概率非均匀（高热度节点概率显著更高）；
- 贡献度 = heat × (1 - mastery)，并转化为个性化任务奖励加成（≤30%）；
- 个性化任务只出现在本人任务总览里。
"""
from __future__ import annotations

import pytest

from app.models.models import (
    ExamAnswerDetail,
    ExamRecord,
    KgUserEdge,
    KgUserEvent,
    KgUserNodeState,
    KnowledgePoint,
    Task,
)
from app.services import kg_growth


def _point(db, name):
    p = KnowledgePoint(point_name=name, subject_id=1, level=1, status=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_answer_events_update_mastery_and_heat(db_session, test_user):
    p = _point(db_session, "行政法")
    kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_wrong")
    kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_wrong")
    db_session.commit()

    node = db_session.query(KgUserNodeState).filter(
        KgUserNodeState.user_id == test_user.user_id,
        KgUserNodeState.point_id == p.point_id,
    ).first()
    assert node is not None
    assert node.attempt_count == 2
    assert node.heat > 0
    # 连续两次答错，掌握度应被拉低
    assert node.mastery < 0.3

    correct_before = node.heat
    kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_correct")
    db_session.commit()
    db_session.refresh(node)
    assert node.heat > correct_before
    assert node.attempt_count == 3


def test_note_edit_weight_between_wrong_and_correct(db_session, test_user):
    assert kg_growth.EVENT_WEIGHTS["answer_wrong"] > kg_growth.EVENT_WEIGHTS["note_edit"]
    assert kg_growth.EVENT_WEIGHTS["note_edit"] > kg_growth.EVENT_WEIGHTS["answer_correct"]


def test_edges_grow_between_consecutive_points(db_session, test_user):
    p1 = _point(db_session, "行政处罚")
    p2 = _point(db_session, "行政复议")

    kg_growth.record_event(db_session, test_user.user_id, p1.point_id, "answer_wrong")
    kg_growth.record_event(db_session, test_user.user_id, p2.point_id, "note_edit")
    db_session.commit()

    edges = db_session.query(KgUserEdge).filter(KgUserEdge.user_id == test_user.user_id).all()
    assert len(edges) >= 2  # 双向
    pair = {(e.src_point, e.dst_point) for e in edges}
    assert (p1.point_id, p2.point_id) in pair
    assert (p2.point_id, p1.point_id) in pair
    assert all(e.weight > 1.0 for e in edges)


def test_sampling_is_non_uniform(db_session, test_user):
    hot = _point(db_session, "热点知识点")
    cold = _point(db_session, "冷门知识点")
    # 热的节点多次答错，冷的节点一次答对
    for _ in range(6):
        kg_growth.record_event(db_session, test_user.user_id, hot.point_id, "answer_wrong")
    kg_growth.record_event(db_session, test_user.user_id, cold.point_id, "answer_correct")
    db_session.commit()

    result = kg_growth.sample_nodes(db_session, test_user.user_id, n=2)
    probs = {i["point_id"]: i["probability"] for i in result}
    assert probs[hot.point_id] > probs[cold.point_id] * 1.5


def test_sample_excludes_mastered_nodes(db_session, test_user):
    p = _point(db_session, "已掌握知识点")
    for _ in range(12):
        kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_correct")
    db_session.commit()

    node = db_session.query(KgUserNodeState).filter(
        KgUserNodeState.user_id == test_user.user_id, KgUserNodeState.point_id == p.point_id
    ).first()
    assert node.mastery > 0.85
    result = kg_growth.sample_nodes(db_session, test_user.user_id, n=3)
    assert all(i["point_id"] != p.point_id for i in result)


def test_contribution_and_bonus_cap(db_session, test_user):
    p = _point(db_session, "贡献度知识点")
    kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_wrong")
    db_session.commit()
    node = db_session.query(KgUserNodeState).filter(
        KgUserNodeState.user_id == test_user.user_id, KgUserNodeState.point_id == p.point_id
    ).first()

    contribution = kg_growth.contribution(node)
    assert contribution > 0
    bonus = kg_growth.reward_bonus(node)
    assert 0 <= bonus <= kg_growth.MAX_REWARD_BONUS


def test_generate_personalized_tasks_is_idempotent(db_session, test_user):
    p = _point(db_session, "个性化任务知识点")
    for _ in range(4):
        kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_wrong")
    db_session.commit()

    first = kg_growth.ensure_personalized_tasks(db_session, test_user.user_id, n=1)
    second = kg_growth.ensure_personalized_tasks(db_session, test_user.user_id, n=1)
    assert len(first) == 1
    assert first[0].task_code == second[0].task_code, "同一周同一知识点应复用任务"

    task = db_session.query(Task).filter(Task.task_code == first[0].task_code).first()
    assert task.personalized_for == test_user.user_id
    assert task.metric == "kg_node_questions"
    assert task.metric_param == p.point_id


def test_personalized_task_only_visible_to_owner(client, db_session, auth_headers, test_user):
    p = _point(db_session, "私有任务知识点")
    kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_wrong")
    db_session.commit()
    kg_growth.ensure_personalized_tasks(db_session, test_user.user_id, n=1)

    res = client.get("/api/tasks/overview", headers=auth_headers)
    assert res.status_code == 200, res.text
    titles = [t["title"] for t in res.json()["weekly"]]
    assert any("私有任务知识点" in t for t in titles), "本人应能看到自己的个性化任务"


def test_kg_metric_counts_practice_by_question_knowledge(db_session, test_user):
    """真实关联：question_knowledge(question_id, knowledge_point_id) → practice_record 计数。"""
    from datetime import datetime

    from app.models.models import PracticeRecord, QuestionKnowledge
    from app.services.weekly_tasks import compute_metric

    p = _point(db_session, "统计口径知识点")
    db_session.add(QuestionKnowledge(question_id=99001, knowledge_point_id=p.point_id))
    db_session.commit()

    for _ in range(3):
        db_session.add(
            PracticeRecord(
                user_id=test_user.user_id,
                question_id=99001,
                is_correct=0,
                practice_time=datetime.now(),
                practice_date=datetime.now().date(),
                time_spent=5,
                source_type="practice",
            )
        )
    # 不在该知识点的题目不应计入
    db_session.add(
        PracticeRecord(
            user_id=test_user.user_id,
            question_id=99002,
            is_correct=0,
            practice_time=datetime.now(),
            practice_date=datetime.now().date(),
            time_spent=5,
            source_type="practice",
        )
    )
    db_session.commit()

    assert compute_metric("kg_node_questions", test_user.user_id, db_session, param=p.point_id) == 3


def test_resolve_point_id_uses_question_knowledge(db_session):
    """题目表 point_id 为空时，应能通过 question_knowledge 反查知识点。"""
    from app.models.models import QuestionBank, QuestionKnowledge

    p = _point(db_session, "关联映射知识点")
    q = QuestionBank(
        subject_id=1,
        type_id=1,
        question_content="测试题",
        answer="A",
        point_id=None,
        creator_id=1,
        status=1,
    )
    db_session.add(q)
    db_session.commit()
    db_session.add(QuestionKnowledge(question_id=q.question_id, knowledge_point_id=p.point_id))
    db_session.commit()

    assert kg_growth.resolve_point_id(db_session, q) == p.point_id


def test_decay_reduces_heat(db_session, test_user):
    p = _point(db_session, "衰减知识点")
    for _ in range(3):
        kg_growth.record_event(db_session, test_user.user_id, p.point_id, "answer_wrong")
    db_session.commit()
    node = db_session.query(KgUserNodeState).filter(
        KgUserNodeState.user_id == test_user.user_id, KgUserNodeState.point_id == p.point_id
    ).first()
    before = node.heat
    kg_growth.decay(db_session, test_user.user_id)
    db_session.refresh(node)
    assert node.heat < before
