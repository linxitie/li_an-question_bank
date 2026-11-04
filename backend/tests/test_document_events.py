"""F4 业务侧事件入口测试：只写 Outbox，不直接写文档库。"""
from sqlalchemy import text

from app.core import events
from app.foundation import config as foundation_config
from app.foundation import document_events


def _outbox_rows(db):
    return db.execute(
        text(
            "SELECT event_name, aggregate_type, aggregate_id, payload "
            "FROM foundation_outbox ORDER BY id"
        )
    ).all()


def test_emit_exam_snapshot_writes_outbox_row(db_session):
    event_id = document_events.emit_exam_snapshot(db_session, 123)
    db_session.commit()

    assert event_id
    rows = _outbox_rows(db_session)
    assert len(rows) == 1
    assert rows[0][0] == events.EV_PAPER_SNAPSHOT
    assert rows[0][1] == "exam_paper"
    assert rows[0][2] == "123"
    assert '"paper_id":123' in rows[0][3]


def test_emit_import_snapshot_selects_event_by_source(db_session):
    document_events.emit_import_snapshot(
        db_session, "question_import_record", 7, producer="test"
    )
    document_events.emit_import_snapshot(
        db_session, "material_import_record", 8, producer="test"
    )
    db_session.commit()

    names = [row[0] for row in _outbox_rows(db_session)]
    assert names == [
        events.EV_QUESTION_IMPORT_SNAPSHOT,
        events.EV_MATERIAL_IMPORT_SNAPSHOT,
    ]


def test_emit_forum_content_writes_row(db_session):
    document_events.emit_forum_content(db_session, 5)
    db_session.commit()

    rows = _outbox_rows(db_session)
    assert rows[0][0] == events.EV_FORUM_CONTENT_CHANGED
    assert rows[0][1] == "forum_post"
    assert rows[0][2] == "5"


def test_emit_is_noop_when_event_bus_disabled(db_session, monkeypatch):
    monkeypatch.setattr(foundation_config, "EVENT_OUTBOX_ENABLED", False)
    monkeypatch.setattr(foundation_config, "DOC_STORE_ENABLED", True)

    assert document_events.emit_exam_snapshot(db_session, 123) is None
    db_session.commit()
    assert _outbox_rows(db_session) == []
