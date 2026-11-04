"""F3 /media 读取契约测试：200/206/304/HEAD/404/附件头。"""
from __future__ import annotations

from app.foundation import config as fcfg
from app.foundation import media_health
from app.foundation.stores import object as object_store
from app.foundation.stores.object import ObjectStoreUnavailable
from app.services import media_service as ms

PNG = b"\x89PNG\r\n\x1a\n" + b"api-test" * 64
PDF = b"%PDF-1.4\n" + b"x" * 512


def _store(db_session, tmp_path, monkeypatch, data, **kw):
    monkeypatch.setattr(fcfg, "OBJECT_STORE_ROOT", str(tmp_path / "objects"))
    monkeypatch.setattr(ms.settings, "FOUNDATION_ENABLED", False)
    object_store.reset_object_store()
    asset = ms.store_bytes(db_session, data, **kw)
    db_session.commit()
    return asset


def test_get_full_and_head(client, db_session, tmp_path, monkeypatch):
    asset = _store(
        db_session, tmp_path, monkeypatch, PNG, kind="avatar", original_name="头像.png"
    )
    r = client.get(f"/media/{asset.asset_id}")
    assert r.status_code == 200
    assert r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["etag"] == f'"{asset.sha256}"'
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["content-length"] == str(len(PNG))

    h = client.head(f"/media/{asset.asset_id}")
    assert h.status_code == 200
    assert h.content == b""
    assert h.headers["content-length"] == str(len(PNG))


def test_range_and_not_modified(client, db_session, tmp_path, monkeypatch):
    asset = _store(
        db_session, tmp_path, monkeypatch, PNG, kind="avatar", original_name="a.png"
    )
    r = client.get(f"/media/{asset.asset_id}", headers={"Range": "bytes=0-3"})
    assert r.status_code == 206
    assert r.content == PNG[:4]
    assert r.headers["content-range"] == f"bytes 0-3/{len(PNG)}"

    r = client.get(f"/media/{asset.asset_id}", headers={"Range": f"bytes=-4"})
    assert r.status_code == 206
    assert r.content == PNG[-4:]

    r = client.get(f"/media/{asset.asset_id}", headers={"Range": "bytes=99-1"})
    assert r.status_code == 416
    assert r.headers["content-range"] == f"bytes */{len(PNG)}"

    r = client.get(
        f"/media/{asset.asset_id}", headers={"If-None-Match": f'"{asset.sha256}"'}
    )
    assert r.status_code == 304
    assert r.content == b""


def test_forum_attachment_disposition(client, db_session, tmp_path, monkeypatch):
    asset = _store(
        db_session, tmp_path, monkeypatch, PDF, kind="forum", original_name="资料 1.pdf"
    )
    r = client.get(f"/media/{asset.asset_id}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert "UTF-8''" in r.headers["content-disposition"]


def test_missing_and_deleted_are_404(client, db_session, tmp_path, monkeypatch):
    assert client.get("/media/" + "0" * 32).status_code == 404
    asset = _store(
        db_session, tmp_path, monkeypatch, PNG, kind="avatar", original_name="a.png"
    )
    ms.delete_asset(db_session, asset.asset_id)
    db_session.commit()
    assert client.get(f"/media/{asset.asset_id}").status_code == 404

class _DownStore:
    backend = "local"

    def open(self, key):
        raise ObjectStoreUnavailable("down")

    def stream(self, key, start=0, end=None):
        raise ObjectStoreUnavailable("down")


def test_store_unavailable_is_503(client, db_session, tmp_path, monkeypatch):
    asset = _store(
        db_session, tmp_path, monkeypatch, PNG, kind="avatar", original_name="a.png"
    )
    monkeypatch.setattr(ms, "build_object_store", lambda: _DownStore())
    r = client.get(f"/media/{asset.asset_id}")
    assert r.status_code == 503
    assert r.headers["retry-after"] == "5"


def test_missing_blob_is_404_and_marks_health(
    client, db_session, tmp_path, monkeypatch
):
    media_health.reset_cache()
    asset = _store(
        db_session, tmp_path, monkeypatch, PNG, kind="avatar", original_name="a.png"
    )
    path = tmp_path / "objects" / asset.sha256[:2] / asset.sha256
    path.unlink()
    assert client.get(f"/media/{asset.asset_id}").status_code == 404
    assert client.head(f"/media/{asset.asset_id}").status_code == 404
    assert media_health.recent_missing() >= 1
    media_health.reset_cache()
