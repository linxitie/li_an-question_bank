"""向量构建/回填核心逻辑测试（F6）。"""
from __future__ import annotations

import pytest

from app.foundation.ports.ai import HashEmbedding
from app.foundation.stores.local_vector import LocalVectorStore
from app.foundation.vector_builder import (
    apply_plan,
    build_vector_plan,
    content_hash,
    expected_records,
)
from app.models.models import QuestionBank


def _question(db_session, test_user, test_subject, test_question_type, qid, text, status=1):
    row = QuestionBank(
        question_id=qid, subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id, question_content=text,
        answer="A", creator_id=test_user.user_id, status=status, difficulty=3,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_expected_records_only_active_with_content(db_session, test_user,
                                                   test_subject, test_question_type):
    _question(db_session, test_user, test_subject, test_question_type, 1, "  题干一  ")
    _question(db_session, test_user, test_subject, test_question_type, 2, "   ", status=1)
    _question(db_session, test_user, test_subject, test_question_type, 3, "停用题干", status=0)
    records = expected_records(db_session)
    assert [record.id for record in records] == ["1"]
    assert records[0].text == "  题干一  "
    assert records[0].meta == {
        "subjectId": test_subject.subject_id,
        "typeId": test_question_type.type_id,
        "pointId": None,
        "difficulty": 3,
        "status": 1,
        "contentHash": content_hash("  题干一  "),
    }
    assert len(records[0].meta["contentHash"]) == 16


def test_build_and_apply_plan_is_idempotent(tmp_path, db_session, test_user,
                                            test_subject, test_question_type):
    _question(db_session, test_user, test_subject, test_question_type, 10, "第一题")
    _question(db_session, test_user, test_subject, test_question_type, 11, "第二题")
    embedding = HashEmbedding(dim=8)
    plan = build_vector_plan(db_session, embedding, collection="text_questions")
    assert plan.planned == 2
    assert len(plan.items) == 2
    store = LocalVectorStore(tmp_path, dim=8)
    stats = apply_plan(store, plan, reset=True)
    assert stats == {"planned": 2, "written": 2, "skipped": 0}
    assert store.count("text_questions") == 2

    again = build_vector_plan(db_session, embedding, collection="text_questions")
    assert apply_plan(store, again) == {"planned": 2, "written": 2, "skipped": 0}
    assert store.count("text_questions") == 2

    limited = build_vector_plan(db_session, embedding, collection="text_questions", limit=1)
    assert limited.planned == 1
    assert apply_plan(store, limited, reset=True) == {
        "planned": 1, "written": 1, "skipped": 0
    }
    assert store.count("text_questions") == 1
