"""F5 图构建：节点/边派生口径与回填幂等。"""
from __future__ import annotations

import sqlite3

import pytest

from app.foundation.graph_builder import apply_plan, build_graph
from app.foundation.graph_schema import read_ddl
from app.models.models import QuestionKnowledge
from app.foundation.stores.local_graph import LocalGraphStore
from app.models.models import KnowledgePoint, QuestionBank


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "graph.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(read_ddl())
    finally:
        conn.close()
    return LocalGraphStore(db)


def _seed(db_session, test_user, test_subject, test_question_type):
    subject_id = test_subject.subject_id
    root = KnowledgePoint(
        point_name="根", subject_id=subject_id, parent_id=0, level=1, status=1
    )
    db_session.add(root)
    db_session.flush()
    child_a = KnowledgePoint(
        point_name="子A", subject_id=subject_id, parent_id=root.point_id, level=2, status=1
    )
    child_b = KnowledgePoint(
        point_name="子B", subject_id=subject_id, parent_id=root.point_id, level=2, status=0
    )
    db_session.add_all([child_a, child_b])
    db_session.flush()
    grand = KnowledgePoint(
        point_name="孙", subject_id=subject_id, parent_id=child_a.point_id,
        level=3, status=1,
    )
    db_session.add(grand)
    db_session.flush()

    question = QuestionBank(
        subject_id=subject_id,
        type_id=test_question_type.type_id,
        question_content="题干",
        answer="A",
        creator_id=test_user.user_id,
        difficulty=2,
        status=1,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add_all([
        QuestionKnowledge(question_id=question.question_id, knowledge_point_id=child_a.point_id),
        QuestionKnowledge(question_id=question.question_id, knowledge_point_id=grand.point_id),
    ])
    db_session.commit()
    return {
        "root": root.point_id, "a": child_a.point_id,
        "b": child_b.point_id, "grand": grand.point_id,
        "question": question.question_id,
    }


def test_build_graph_counts_and_edges(
    db_session, test_user, test_subject, test_question_type
):
    ids = _seed(db_session, test_user, test_subject, test_question_type)
    plan = build_graph(db_session)

    assert plan.node_counts() == {"KnowledgePoint": 4, "Question": 1}
    assert plan.edge_counts() == {
        "PREREQUISITE_OF": 3, "PARALLEL_WITH": 1, "INSTANCE_OF": 2,
    }

    prereq = {
        (int(e.src_key), int(e.dst_key)) for e in plan.edges if e.rel == "PREREQUISITE_OF"
    }
    assert (ids["root"], ids["a"]) in prereq
    assert (ids["root"], ids["b"]) in prereq
    assert (ids["a"], ids["grand"]) in prereq

    parallel = [e for e in plan.edges if e.rel == "PARALLEL_WITH"]
    assert len(parallel) == 1
    src, dst = int(parallel[0].src_key), int(parallel[0].dst_key)
    assert src < dst
    assert {src, dst} == {ids["a"], ids["b"]}

    instance = {
        (int(e.src_key), int(e.dst_key)) for e in plan.edges if e.rel == "INSTANCE_OF"
    }
    assert instance == {
        (ids["question"], ids["a"]), (ids["question"], ids["grand"]),
    }
    assert next(n for n in plan.nodes if n.label == "KnowledgePoint" and
                n.key == str(ids["b"])).props["status"] == 0


def test_apply_plan_idempotent_and_reset(
    db_session, test_user, test_subject, test_question_type, store
):
    _seed(db_session, test_user, test_subject, test_question_type)
    plan = build_graph(db_session)

    first = apply_plan(store, plan)
    assert first["nodes_written"] == 5
    assert first["edges_written"] == 6
    assert store.counts()["nodes"] == 5

    second = apply_plan(store, plan)
    assert second["nodes_written"] == 0
    assert second["nodes_skipped"] == 5

    reset = apply_plan(store, plan, reset=True)
    assert reset["nodes_written"] == 5
    assert store.counts()["nodes"] == 5


def test_limit_only_links_loaded_nodes(
    db_session, test_user, test_subject, test_question_type
):
    _seed(db_session, test_user, test_subject, test_question_type)
    plan = build_graph(db_session, limit=2)
    assert sum(plan.node_counts().values()) <= 3
    loaded = {(n.label, n.key) for n in plan.nodes}
    for edge in plan.edges:
        assert (edge.src_label, edge.src_key) in loaded
        assert (edge.dst_label, edge.dst_key) in loaded
