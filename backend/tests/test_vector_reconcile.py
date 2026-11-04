"""向量对账测试（F6）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.foundation import vector_reconcile as vr
from app.foundation.ports.ai import HashEmbedding
from app.foundation.stores.local_vector import LocalVectorStore
from app.foundation.vector_builder import apply_plan, build_vector_plan
from app.models.models import QuestionBank


def _seed(db_session, test_user, test_subject, test_question_type, count=3):
    for index in range(1, count + 1):
        db_session.add(QuestionBank(
            question_id=index, subject_id=test_subject.subject_id,
            type_id=test_question_type.type_id,
            question_content=f"第{index}题的题干内容", answer="A",
            creator_id=test_user.user_id, status=1, difficulty=3,
        ))
    db_session.commit()


def _prepared(tmp_path, db_session):
    embedding = HashEmbedding(dim=8)
    store = LocalVectorStore(tmp_path / "vectors", dim=8)
    plan = build_vector_plan(db_session, embedding)
    apply_plan(store, plan, reset=True)
    return store, plan


def test_inspect_full_detects_missing_and_orphan(tmp_path, monkeypatch,
                                                 db_session, test_user,
                                                 test_subject, test_question_type):
    monkeypatch.setattr(vr.cfg, "BACKEND_DIR", tmp_path)
    _seed(db_session, test_user, test_subject, test_question_type)
    store, _ = _prepared(tmp_path, db_session)
    run = vr.inspect(db_session, store=store, mode="full")
    assert run.checked == 3
    assert run.missing == 0 and run.orphan == 0 and run.mismatched == 0
    assert run.drifted == 0 and run.status == "ok"
    assert (tmp_path / "data" / "reports" / "reconcile" / f"vector_{run.run_id}.json").exists()

    store.delete("text_questions", "2")
    store.upsert("text_questions", "orphan", [1, 0, 0, 0, 0, 0, 0, 0], {})
    run = vr.inspect(db_session, store=store, mode="full")
    assert run.missing == 1 and run.orphan == 1 and run.drifted == 2
    assert run.status == "drift"
    issues = {detail.get("issue") for detail in run.details}
    assert "missing_vector" in issues and "orphan_vector" in issues


def test_inspect_sample_detects_hash_mismatch(tmp_path, monkeypatch,
                                              db_session, test_user,
                                              test_subject, test_question_type):
    monkeypatch.setattr(vr.cfg, "BACKEND_DIR", tmp_path)
    _seed(db_session, test_user, test_subject, test_question_type, count=2)
    store, plan = _prepared(tmp_path, db_session)
    item = plan.items[0]
    store.upsert("text_questions", item.id, item.vector,
                 {**item.meta, "contentHash": "deadbeefdeadbeef"})
    run = vr.inspect(db_session, store=store, mode="sample", sample=2)
    assert run.sampled == 2
    assert run.sample_mismatch == 1
    assert run.mismatched == 0
    assert run.status == "drift"


def test_record_latest_and_freshness(tmp_path, monkeypatch, db_session,
                                     test_user, test_subject, test_question_type):
    monkeypatch.setattr(vr.cfg, "BACKEND_DIR", tmp_path)
    _seed(db_session, test_user, test_subject, test_question_type, count=1)
    store, _ = _prepared(tmp_path, db_session)
    run = vr.inspect(db_session, store=store)
    vr.record(db_session, run)
    latest = vr.latest_run(db_session)
    assert latest["run_id"] == run.run_id
    assert latest["status"] == "ok"
    assert vr.freshness_days(latest) is not None
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert vr.freshness_days(latest, now=future) >= 1.0


def test_unavailable_store_is_warn_not_crash(tmp_path, monkeypatch, db_session,
                                             test_user, test_subject,
                                             test_question_type):
    monkeypatch.setattr(vr.cfg, "BACKEND_DIR", tmp_path)
    _seed(db_session, test_user, test_subject, test_question_type, count=1)

    class _Broken:
        backend = "local"

        def list_ids(self, collection):
            raise vr.VectorStoreError("boom")

    run = vr.inspect(db_session, store=_Broken())
    assert run.status == "warn"
    assert any(detail.get("issue") == "vector_store_unavailable" for detail in run.details)