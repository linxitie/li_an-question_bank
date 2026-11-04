"""内部向量检索测试（F6）。"""
from __future__ import annotations

import pytest

from app.foundation.ports.ai import HashEmbedding, OffEmbedding
from app.foundation.retrieval import search_questions
from app.foundation.stores.local_vector import LocalVectorStore
from app.foundation.vector_builder import apply_plan, build_vector_plan
from app.models.models import QuestionBank


def _seed(db_session, test_user, test_subject, test_question_type):
    for qid, text in ((1, "公安机关的性质是什么"), (2, "行政处罚的种类有哪些")):
        db_session.add(QuestionBank(
            question_id=qid, subject_id=test_subject.subject_id,
            type_id=test_question_type.type_id, question_content=text,
            answer="A", creator_id=test_user.user_id, status=1, difficulty=3,
        ))
    db_session.commit()


def test_search_returns_hits(tmp_path, db_session, test_user, test_subject,
                             test_question_type):
    _seed(db_session, test_user, test_subject, test_question_type)
    embedding = HashEmbedding(dim=16)
    store = LocalVectorStore(tmp_path, dim=16)
    apply_plan(store, build_vector_plan(db_session, embedding))
    hits = search_questions(
        "公安机关的性质是什么", top_k=2, store=store, embedding=embedding
    )
    assert hits[0]["id"] == "1"
    assert hits[0]["meta"]["subjectId"] == test_subject.subject_id
    assert 0.0 <= hits[0]["score"] <= 1.0
    only = search_questions(
        "公安机关的性质是什么", top_k=2, where={"typeId": test_question_type.type_id},
        store=store, embedding=embedding,
    )
    assert len(only) == 2


def test_search_validates_input(tmp_path):
    store = LocalVectorStore(tmp_path, dim=8)
    with pytest.raises(ValueError):
        search_questions("", store=store, embedding=HashEmbedding(8))
    with pytest.raises(ValueError):
        search_questions("x", top_k=0, store=store, embedding=HashEmbedding(8))
    with pytest.raises(Exception):
        search_questions("x", store=store, embedding=OffEmbedding(8))
