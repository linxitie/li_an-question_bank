"""F5 图对账：全量差集、抽样祖先、漂移与记录。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.foundation import graph_reconcile as gr
from app.foundation.graph_builder import apply_plan, build_graph
from app.foundation.graph_schema import read_ddl
from app.foundation.stores.local_graph import LocalGraphStore
from app.models.models import (
    KnowledgePoint,
    QuestionBank,
    QuestionKnowledge,
)


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
    root = KnowledgePoint(point_name="根", subject_id=subject_id, parent_id=0)
    db_session.add(root)
    db_session.flush()
    child = KnowledgePoint(
        point_name="子", subject_id=subject_id, parent_id=root.point_id
    )
    db_session.add(child)
    db_session.flush()
    question = QuestionBank(
        subject_id=subject_id, type_id=test_question_type.type_id,
        question_content="题干", answer="A", creator_id=test_user.user_id, status=1,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(QuestionKnowledge(
        question_id=question.question_id, knowledge_point_id=child.point_id
    ))
    db_session.commit()
    return {"root": root.point_id, "child": child.point_id,
            "question": question.question_id}


def _applied(db_session, store):
    plan = build_graph(db_session)
    apply_plan(store, plan)
    return plan


def test_full_reconcile_clean(
    db_session, test_user, test_subject, test_question_type, store
):
    _seed(db_session, test_user, test_subject, test_question_type)
    plan = _applied(db_session, store)
    run = gr.inspect(db_session, store, mode="full")

    assert run.status == "ok", run.details
    assert run.checked == len(plan.nodes) + len(plan.edges)
    assert (run.missing, run.orphan, run.mismatched) == (0, 0, 0)
    assert run.sampled == 2
    assert run.sample_mismatch == 0
    assert Path(run.report_path).exists()


def test_missing_orphan_and_mismatch(
    db_session, test_user, test_subject, test_question_type, store
):
    ids = _seed(db_session, test_user, test_subject, test_question_type)
    _applied(db_session, store)

    store.delete_node("KnowledgePoint", str(ids["child"]))
    missing = gr.inspect(db_session, store, mode="full")
    assert missing.status == "drift"
    assert missing.missing >= 2  # 节点 + 它的入边/出边

    store.clear()
    _applied(db_session, store)
    store.upsert_node("KnowledgePoint", "999", {"status": 1}, version=1)
    orphan = gr.inspect(db_session, store, mode="full")
    assert orphan.status == "drift"
    assert orphan.orphan == 1

    store.upsert_node("KnowledgePoint", str(ids["child"]), {"status": 0}, version=2)
    mismatch = gr.inspect(db_session, store, mode="full")
    assert mismatch.status == "drift"
    assert mismatch.mismatched >= 1


def test_sample_mode_detects_ancestor_mismatch(
    db_session, test_user, test_subject, test_question_type, store
):
    ids = _seed(db_session, test_user, test_subject, test_question_type)
    _applied(db_session, store)
    store.delete_edge(
        "PREREQUISITE_OF", ("KnowledgePoint", str(ids["root"])),
        ("KnowledgePoint", str(ids["child"])),
    )
    run = gr.inspect(db_session, store, mode="sample", sample=10)
    assert run.sampled == 2
    assert run.sample_mismatch >= 1
    assert run.status == "drift"


def test_record_latest_and_freshness(
    db_session, test_user, test_subject, test_question_type, store
):
    _seed(db_session, test_user, test_subject, test_question_type)
    _applied(db_session, store)
    run = gr.inspect(db_session, store, mode="full")
    gr.record(db_session, run)

    latest = gr.latest_run(db_session)
    assert latest is not None
    assert latest["run_id"] == run.run_id
    assert latest["checked"] == run.checked
    assert gr.freshness_days(latest) is not None
    future = datetime.now(timezone.utc) + timedelta(days=2)
    assert gr.freshness_days(latest, now=future) > 1.9
