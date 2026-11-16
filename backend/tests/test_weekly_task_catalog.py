"""周任务供给感知：题库真实题量 → startable / blocked_reason。"""
from app.api.v1.growth.weekly_task_catalog import (
    _available_count,
    _kp_ids,
    _task_payload,
)
from app.models.models import (
    KnowledgePoint,
    QuestionBank,
    QuestionKnowledge,
    QuestionSubject,
    QuestionType,
)
from app.models.weekly_task import WeeklyTaskInstance


def _seed_questions(db, count=3):
    db.add(QuestionSubject(subject_id=1, subject_name="行测", subject_code="XC", status=1))
    db.add(QuestionType(type_id=1, type_name="单选题", type_code="SINGLE", is_objective=1))
    db.add(KnowledgePoint(point_id=14, point_name="片段阅读", subject_id=1, status=1))
    db.add(KnowledgePoint(point_id=15, point_name="逻辑填空", subject_id=1, status=1))
    db.flush()
    for i in range(1, count + 1):
        db.add(
            QuestionBank(
                question_id=i,
                subject_id=1,
                type_id=1,
                question_content=f"题目{i}",
                answer="A",
                creator_id=1,
                status=1,
            )
        )
        db.add(QuestionKnowledge(question_id=i, knowledge_point_id=14))
    db.commit()


def test_kp_ids_and_available_count(db_session):
    _seed_questions(db_session, 3)
    ids = _kp_ids(db_session, 1, "言语理解与表达")
    assert 14 in ids
    assert _available_count(db_session, 1, ids) == 3
    assert _available_count(db_session, 1, set()) == 0
    # 同题多挂点只算一次（q1 同时挂片段阅读与逻辑填空）
    db_session.add(QuestionKnowledge(question_id=1, knowledge_point_id=15))
    db_session.commit()
    assert _available_count(db_session, 1, _kp_ids(db_session, 1, "言语理解与表达")) == 3


def test_task_payload_blocks_when_question_short(db_session):
    _seed_questions(db_session, 3)
    row = WeeklyTaskInstance(
        instance_id="周任-测试-01",
        plan_id="周计划-测试",
        week_no=1,
        task_date="2026-11-09",
        weekday="周一",
        subject="行测",
        domain="言语理解与表达",
        theme_id="主题-测试",
        template_id="模板-测试",
        title="片段阅读·限时专项",
        form="限时专项",
        difficulty=3,
        qty=18,
        unit="题",
        minutes=30,
        coins=15,
        supply="可试点",
        status="待发布",
        anchors='["知-行测-0001"]',
    )
    blocked = _task_payload(row, 3)
    assert blocked["startable"] is False
    assert blocked["blocked_reason"] == "题库不足（现有 3 / 需 18）"
    assert blocked["available_qty"] == 3

    row.qty = 2
    assert _task_payload(row, 3)["startable"] is True
    assert _task_payload(row, 3)["blocked_reason"] is None

    row.supply = "待补题"
    pending = _task_payload(row, 100)
    assert pending["startable"] is False
    assert pending["blocked_reason"] == "待补题"
