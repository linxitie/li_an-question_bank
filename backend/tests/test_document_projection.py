"""F4 文档投影 handler 测试（Outbox 消费侧）。"""
from datetime import datetime

import pytest

from app.foundation import config as foundation_config
from app.foundation import document_projection as projection
from app.foundation.stores.base import OutboxEvent
from app.foundation.stores.document import (
    DocumentStoreUnavailable,
    build_document_store,
    reset_document_store,
)
from app.models.models import ExamPaper, ForumPost, MaterialImportRecord


@pytest.fixture
def doc_store(tmp_path, monkeypatch):
    monkeypatch.setattr(foundation_config, "DOC_STORE_ENABLED", True)
    monkeypatch.setattr(foundation_config, "DOC_STORE_BACKEND", "local")
    monkeypatch.setattr(foundation_config, "DOC_STORE_ROOT", str(tmp_path / "docs"))
    reset_document_store()
    yield build_document_store()
    reset_document_store()


def _event(event_id: int, name: str, payload: dict) -> OutboxEvent:
    return OutboxEvent(
        id=event_id,
        event_id=f"evt-{event_id}",
        event_name=name,
        schema_version=1,
        aggregate_type="test",
        aggregate_id=str(payload.get("paper_id") or payload.get("post_id") or "1"),
        aggregate_ver=1,
        payload=payload,
        producer="test",
        trace_id=None,
        occurred_at=datetime.now().isoformat(),
        attempts=0,
    )


def _paper(db_session) -> ExamPaper:
    paper = ExamPaper(
        paper_name="快照卷",
        paper_code="SNAP-001",
        subject_id=1,
        composition_method="MANUAL",
        creator_id=1,
        duration=60,
        total_score=50,
        question_count=0,
    )
    db_session.add(paper)
    db_session.commit()
    return paper


def test_exam_snapshot_written_with_outbox_version(db_session, doc_store):
    paper = _paper(db_session)
    event = _event(42, "exam.paper.snapshot", {"paper_id": paper.paper_id})

    projection.handle_exam_snapshot(db_session, event)
    db_session.commit()

    doc = doc_store.get("exam_resources", str(paper.paper_id))
    assert doc is not None
    assert doc["version"] == 42
    assert doc["payload"]["name"] == "快照卷"


def test_duplicate_event_does_not_write_again(db_session, doc_store):
    paper = _paper(db_session)
    event = _event(7, "exam.paper.snapshot", {"paper_id": paper.paper_id})
    projection.handle_exam_snapshot(db_session, event)
    db_session.commit()

    doc_store.delete("exam_resources", str(paper.paper_id))
    projection.handle_exam_snapshot(db_session, event)
    db_session.commit()

    assert doc_store.get("exam_resources", str(paper.paper_id)) is None


def test_store_unavailable_propagates_for_outbox_retry(db_session, monkeypatch):
    paper = _paper(db_session)
    monkeypatch.setattr(foundation_config, "DOC_STORE_ENABLED", True)
    monkeypatch.setattr(foundation_config, "DOC_STORE_BACKEND", "mongo")
    monkeypatch.setattr(foundation_config, "DOC_STORE_MONGO_URI", "")
    reset_document_store()
    try:
        with pytest.raises(DocumentStoreUnavailable):
            projection.handle_exam_snapshot(
                db_session, _event(8, "exam.paper.snapshot", {"paper_id": paper.paper_id})
            )
    finally:
        reset_document_store()


def test_disabled_store_is_noop(db_session, monkeypatch, tmp_path):
    paper = _paper(db_session)
    monkeypatch.setattr(foundation_config, "DOC_STORE_ENABLED", False)
    monkeypatch.setattr(foundation_config, "DOC_STORE_ROOT", str(tmp_path / "off"))
    reset_document_store()

    projection.handle_exam_snapshot(
        db_session, _event(9, "exam.paper.snapshot", {"paper_id": paper.paper_id})
    )
    db_session.commit()

    assert not (tmp_path / "off").exists()


def test_material_processing_snapshot_is_skipped_but_claimed(db_session, doc_store):
    record = MaterialImportRecord(
        file_name="x.pdf", parse_status="processing",
        parse_result='{"pages": [{"path": "_tmp/x.png"}]}',
    )
    db_session.add(record)
    db_session.commit()

    projection.handle_material_import_snapshot(
        db_session,
        _event(10, "material.import.snapshot", {"import_id": record.import_id}),
    )
    db_session.commit()

    assert doc_store.get(
        "import_snapshots", projection.import_key("material_import_record", record.import_id)
    ) is None


def test_forum_changed_writes_post_document(db_session, doc_store):
    post = ForumPost(user_id=1, title="帖子", content="正文", status="NORMAL")
    db_session.add(post)
    db_session.commit()

    projection.handle_forum_changed(
        db_session, _event(11, "forum.content.changed", {"post_id": post.post_id})
    )
    db_session.commit()

    doc = doc_store.get("forum_contents", str(post.post_id))
    assert doc is not None
    assert doc["payload"]["title"] == "帖子"
    assert doc["version"] == 11
