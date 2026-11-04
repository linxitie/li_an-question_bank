"""四库知识图谱 P1：题目图片引用提取与 media_assets 登记。"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.foundation import config as fcfg
from app.foundation.media_schema import ensure_media_schema
from app.foundation.schema import ensure_schema
from app.foundation.stores import object as object_store
from app.models import models as orm_models  # noqa: F401  确保题目表已注册
from app.models.media_asset import MediaAsset
from app.services import media_service as ms
from app.services import question_media as qm

PNG = b"\x89PNG\r\n\x1a\n" + b"p1-media" * 16
PNG2 = b"\x89PNG\r\n\x1a\n" + b"p1-media-2" * 16


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _ref(static_root: Path, raw: str, *, loc: str = "stem", owner_id: int = 1):
    return qm.resolve_media_ref(
        raw, loc=loc, owner_type="question", owner_id=owner_id,
        static_root=static_root,
    )


def test_extract_and_resolve_variants(tmp_path):
    static = tmp_path / "static"
    _write(static / "questions" / "a.png", PNG)
    _write(static / "questions" / "f2570544_70_0.png", PNG2)

    text_value = (
        '<p><img src="/static/questions/a.png"></p>'
        "<p>[IMAGE:f2570544_70_0]</p>"
        '<img src="/static/questions/a.png">'
    )
    assert qm.extract_media_refs(text_value) == [
        "/static/questions/a.png",
        "f2570544_70_0",
    ]

    explicit = _ref(static, "/static/questions/a.png")
    assert explicit.status == "resolved"
    assert explicit.canonical == "questions/a.png"
    assert explicit.path == (static / "questions" / "a.png").resolve()

    marker = _ref(static, "f2570544_70_0")
    assert marker.status == "resolved"
    assert marker.path.name == "f2570544_70_0.png"

    legacy = _ref(static, "45_0")
    assert legacy.status == "missing"
    assert legacy.reason == "legacy_marker_unresolved"

    traversal = _ref(static, "/static/../app/main.py")
    assert traversal.status == "missing"
    assert traversal.reason == "path_traversal"

    external = _ref(static, "https://example.com/a.png")
    assert external.status == "missing"
    assert external.reason == "external_url"


def test_data_uri_is_inline_and_deduped(tmp_path):
    static = tmp_path / "static"
    encoded = base64.b64encode(PNG).decode("ascii")
    ref = _ref(static, f"data:image/png;base64,{encoded}")
    assert ref.status == "resolved"
    assert ref.inline == PNG
    assert ref.content_type == "image/png"
    assert ref.canonical.startswith("inline:")


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'media.db'}")
    Base.metadata.create_all(engine)
    raw = engine.raw_connection()
    ensure_schema(raw.driver_connection)
    ensure_media_schema(raw.driver_connection)
    raw.commit()
    raw.close()
    monkeypatch.setattr(fcfg, "OBJECT_STORE_ROOT", str(tmp_path / "objects"))
    monkeypatch.setattr(ms.settings, "FOUNDATION_ENABLED", True)
    object_store.reset_object_store()
    session = sessionmaker(bind=engine)()
    try:
        yield session, tmp_path / "objects"
    finally:
        session.close()
        object_store.reset_object_store()


def test_collect_and_register_is_idempotent(db, tmp_path):
    session, objects = db
    static = tmp_path / "static"
    _write(static / "questions" / "a.png", PNG)
    _write(static / "questions" / "b.png", PNG)
    _write(static / "questions" / "analysis.png", PNG2)
    _write(static / "question-groups" / "9" / "m.jpg", PNG2)

    session.execute(text(
        "INSERT INTO question_bank "
        "(question_id, subject_id, type_id, question_content, options, answer, "
        "answer_analysis, creator_id, group_id) VALUES "
        "(1, 1, 1, :stem, :options, 'A', :analysis, 1, 0)"
    ), {
        "stem": '<img src="/static/questions/a.png">',
        "options": json.dumps(
            [{"key": "A", "value": '<img src="/static/questions/b.png">'}]
        ),
        "analysis": '<img src="/static/questions/analysis.png">',
    })
    session.execute(text(
        "INSERT INTO question_groups (id, shared_content, shared_content_images) "
        "VALUES (9, :content, :images)"
    ), {
        "content": '<img src="/static/question-groups/9/m.jpg">',
        "images": '["/static/question-groups/9/m.jpg"]',
    })
    session.commit()

    refs = qm.collect_db_refs(session, static_root=static)
    assert len(refs) == 5
    assert sum(1 for ref in refs if ref.status == "resolved") == 5

    first = qm.register_media_refs(session, refs, apply=True)
    session.commit()
    assert first.active_assets == 2
    assert first.inserted == 2
    assert session.query(MediaAsset).filter(MediaAsset.status == "active").count() == 2
    rows = session.query(MediaAsset).all()
    assert len({row.sha256 for row in rows}) == 2
    for row in rows:
        blob = objects / row.object_key
        assert blob.is_file()

    second = qm.register_media_refs(
        session, qm.collect_db_refs(session, static_root=static), apply=True,
    )
    session.commit()
    assert second.inserted == 0
    assert second.reused == 2
    assert session.query(MediaAsset).count() == 2


def test_missing_refs_are_registered_and_reused(db, tmp_path):
    session, _ = db
    static = tmp_path / "static"
    refs = [_ref(static, "/static/questions/nope.png")]
    first = qm.register_media_refs(session, refs, apply=True)
    session.commit()
    assert first.missing_assets == 1
    assert first.inserted == 1
    row = session.query(MediaAsset).one()
    assert row.status == "missing"
    assert row.size_bytes == 0
    assert row.original_name == "questions/nope.png"

    second = qm.register_media_refs(session, refs, apply=True)
    session.commit()
    assert second.inserted == 0
    assert second.reused == 1
    assert session.query(MediaAsset).count() == 1
