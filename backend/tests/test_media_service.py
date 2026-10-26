"""F3 媒体服务单测：去重、事务边界、tombstone、旧 URL 隔离。"""
from __future__ import annotations

import io

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.foundation import config as fcfg
from app.foundation.media_schema import ensure_media_schema
from app.foundation.schema import ensure_schema
from app.foundation.stores import object as object_store
from app.services import media_service as ms

PNG = b"\x89PNG\r\n\x1a\n" + b"f3-test" * 32


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'media.db'}")
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


def _blob_path(root, sha):
    return root / sha[:2] / sha


def test_store_bytes_same_content_dedups_blob(db):
    session, root = db
    a = ms.store_bytes(session, PNG, kind="avatar", original_name="me.png", created_by=1)
    b = ms.store_bytes(session, PNG, kind="avatar", original_name="copy.png", created_by=2)
    session.commit()

    assert a.asset_id != b.asset_id
    assert a.sha256 == b.sha256
    assert a.object_key == f"{a.sha256[:2]}/{a.sha256}"
    assert a.content_type == "image/png"
    assert a.size_bytes == len(PNG)
    assert _blob_path(root, a.sha256).read_bytes() == PNG
    assert len([p for p in root.rglob("*") if p.is_file()]) == 1
    events = session.execute(text("SELECT COUNT(*) FROM foundation_outbox")).scalar_one()
    assert events == 2


def test_store_file_reports_limit_without_row(db):
    session, _ = db
    with pytest.raises(ms.MediaTooLarge):
        ms.store_file(
            session, io.BytesIO(PNG), kind="forum", original_name="a.pdf", max_bytes=3
        )
    session.rollback()
    assert session.execute(text("SELECT COUNT(*) FROM media_assets")).scalar_one() == 0


def test_delete_tombstones_and_keeps_shared_blob(db):
    session, root = db
    a = ms.store_bytes(session, PNG, kind="avatar", original_name="a.png")
    b = ms.store_bytes(session, PNG, kind="avatar", original_name="b.png")
    session.commit()

    assert ms.delete_asset(session, a.asset_id) is True
    session.commit()
    assert _blob_path(root, a.sha256).exists()
    with pytest.raises(ms.MediaNotFound):
        ms.get_asset(session, a.asset_id)

    ms.delete_asset(session, b.asset_id)
    session.commit()
    assert not _blob_path(root, a.sha256).exists()


def test_retire_url_only_touches_media_urls(db):
    session, _ = db
    ms.retire_url(session, "/uploads/avatars/old.png")
    old = ms.store_bytes(session, PNG, kind="avatar", original_name="old.png")
    session.commit()
    ms.retire_url(session, f"/media/{old.asset_id}")
    session.commit()
    with pytest.raises(ms.MediaNotFound):
        ms.get_asset(session, old.asset_id)


def test_content_type_is_server_side(db):
    with pytest.raises(ms.MediaValidationError):
        ms.content_type_for("avatar", "evil.exe")
    with pytest.raises(ms.MediaValidationError):
        ms.content_type_for("unknown", "a.png")
    assert ms.content_type_for("video", "A.MP4") == "video/mp4"


def test_bad_asset_id_rejected_before_query(db):
    session, _ = db
    for bad in ["../etc/passwd", "A" * 32, "0" * 31, ""]:
        with pytest.raises(ms.MediaNotFound):
            ms.get_asset(session, bad)
