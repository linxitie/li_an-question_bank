"""F3 写路径接线测试：头像与论坛附件落到 media_assets 并返回 /media URL。"""
from __future__ import annotations

from app.foundation import config as fcfg
from app.foundation.stores import object as object_store
from app.models.media_asset import MediaAsset
from app.services import media_service as ms

PNG = b"\x89PNG\r\n\x1a\n" + b"endpoint-test" * 32
PDF = b"%PDF-1.4\n" + b"y" * 256


def _enable_media(monkeypatch, tmp_path):
    monkeypatch.setattr(fcfg, "OBJECT_STORE_ROOT", str(tmp_path / "objects"))
    monkeypatch.setattr(ms.settings, "FOUNDATION_ENABLED", False)
    monkeypatch.setattr(ms.settings, "MEDIA_STORE_ENABLED", True)
    object_store.reset_object_store()


def test_student_avatar_uses_media_asset(client, db_session, test_user, auth_headers, tmp_path, monkeypatch):
    _enable_media(monkeypatch, tmp_path)
    r = client.post(
        "/api/auth/avatar",
        files={"file": ("me.png", PNG, "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    url = r.json()["avatar_url"]
    assert url.startswith("/media/")
    asset_id = url.rsplit("/", 1)[-1]
    asset = db_session.get(MediaAsset, asset_id)
    assert asset is not None
    assert asset.kind == "avatar"
    assert asset.created_by == test_user.user_id
    assert client.get(url).content == PNG


def test_media_store_disabled_falls_back_to_uploads(client, db_session, auth_headers, tmp_path, monkeypatch):
    """A15：开关关闭时回到旧 uploads 路径，不新增媒体行。"""
    monkeypatch.setattr(ms.settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(ms.settings, "MEDIA_STORE_ENABLED", False)
    r = client.post(
        "/api/auth/avatar",
        files={"file": ("legacy.png", PNG, "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    url = r.json()["avatar_url"]
    assert url.startswith("/uploads/avatars/")
    assert db_session.query(MediaAsset).count() == 0
    saved = tmp_path / "uploads" / "avatars" / url.rsplit("/", 1)[-1]
    assert saved.read_bytes() == PNG


def test_student_avatar_rejects_fake_image(client, db_session, auth_headers):
    r = client.post(
        "/api/auth/avatar",
        files={"file": ("evil.png", b"not-a-png", "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert db_session.query(MediaAsset).count() == 0


def test_upload_returns_503_when_object_store_down(client, db_session, auth_headers, tmp_path, monkeypatch):
    """A13：存储不可达时上传明确失败，且不留下媒体行。"""
    monkeypatch.setattr(ms.settings, "MEDIA_STORE_ENABLED", True)

    class DownStore:
        backend = "minio"

        def put(self, *args, **kwargs):
            raise ms.ObjectStoreUnavailable("connection refused")

    monkeypatch.setattr(ms, "build_object_store", lambda: DownStore())
    r = client.post(
        "/api/auth/avatar",
        files={"file": ("me.png", PNG, "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 503, r.text
    assert db_session.query(MediaAsset).count() == 0


def test_forum_attachment_uses_media_asset(client, db_session, test_user, auth_headers, tmp_path, monkeypatch):
    _enable_media(monkeypatch, tmp_path)
    r = client.post(
        "/api/forum/upload",
        files={"file": ("note.pdf", PDF, "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"].startswith("/media/")
    assert body["name"] == "note.pdf"
    assert body["size"] == len(PDF)
    asset_id = body["url"].rsplit("/", 1)[-1]
    assert db_session.get(MediaAsset, asset_id).kind == "forum"

    got = client.get(body["url"])
    assert got.status_code == 200
    assert got.headers["content-type"] == "application/pdf"
    assert "attachment" in got.headers["content-disposition"]


def test_forum_dedupes_bytes_but_keeps_two_urls(client, db_session, auth_headers, tmp_path, monkeypatch):
    _enable_media(monkeypatch, tmp_path)
    first = client.post(
        "/api/forum/upload",
        files={"file": ("a.pdf", PDF, "application/pdf")},
        headers=auth_headers,
    ).json()["url"]
    second = client.post(
        "/api/forum/upload",
        files={"file": ("b.pdf", PDF, "application/pdf")},
        headers=auth_headers,
    ).json()["url"]
    assert first != second
    rows = [a for a in db_session.query(MediaAsset).all() if a.kind == "forum"]
    assert len(rows) == 2
    files = [p for p in (tmp_path / "objects").rglob("*") if p.is_file()]
    assert len(files) == 1
    assert client.get(first).status_code == 200
    assert client.get(second).status_code == 200


def test_replacing_avatar_retires_old_media_url(client, db_session, auth_headers, tmp_path, monkeypatch):
    _enable_media(monkeypatch, tmp_path)
    first = client.post(
        "/api/auth/avatar",
        files={"file": ("a.png", PNG, "image/png")},
        headers=auth_headers,
    ).json()["avatar_url"]
    second = client.post(
        "/api/auth/avatar",
        files={"file": ("b.png", PNG, "image/png")},
        headers=auth_headers,
    ).json()["avatar_url"]
    assert client.get(first).status_code == 404
    assert client.get(second).status_code == 200


def test_material_cover_uses_media_asset(client, db_session, admin_headers, tmp_path, monkeypatch):
    _enable_media(monkeypatch, tmp_path)
    r = client.post(
        "/api/materials/admin/upload/image",
        files={"file": ("cover.png", PNG, "image/png")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("/media/")
    asset = db_session.get(MediaAsset, url.rsplit("/", 1)[-1])
    assert asset is not None and asset.kind == "material_image"
    assert client.get(url).content == PNG


def test_imported_docx_images_are_rewritten_to_media(db_session, tmp_path, monkeypatch):
    from app.api.v1.library import materials

    _enable_media(monkeypatch, tmp_path)
    tmp_dir = tmp_path / "materials-tmp"
    tmp_dir.mkdir()
    src = tmp_dir / "pic.png"
    src.write_bytes(PNG)
    monkeypatch.setattr(materials, "UPLOAD_TMP_DIR", tmp_dir)

    result = {
        "html": '<p><img src="/uploads/materials/tmp/pic.png"></p>',
        "images": [{"src_path": str(src), "name": "pic.png"}],
    }
    materials._migrate_images(7, result, db=db_session, user_id=1)
    db_session.commit()

    assert "/uploads/materials/tmp/" not in result["html"]
    assert "/media/" in result["html"]
    assert not src.exists()
    rows = [a for a in db_session.query(MediaAsset).all() if a.kind == "material_image"]
    assert len(rows) == 1
    assert result["html"].count(rows[0].asset_id) == 1

def test_video_direct_upload_stream_and_delete(client, db_session, admin_headers, tmp_path, monkeypatch):
    from app.models.models import VideoResource

    _enable_media(monkeypatch, tmp_path)
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"v" * 1024
    r = client.post(
        "/api/video/upload",
        files={"file": ("clip.mp4", mp4, "video/mp4")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["storage_path"].startswith("/media/")

    stream = client.get(f"/api/video/{body['video_id']}/stream", follow_redirects=False)
    assert stream.status_code == 307
    assert stream.headers["location"] == body["storage_path"]
    assert client.get(body["storage_path"]).content == mp4

    d = client.delete(f"/api/video/{body['video_id']}", headers=admin_headers)
    assert d.status_code == 200, d.text
    assert db_session.get(VideoResource, body["video_id"]) is None
    assert client.get(body["storage_path"]).status_code == 404


def test_video_chunk_complete_uses_media_asset(client, db_session, admin_headers, tmp_path, monkeypatch):
    _enable_media(monkeypatch, tmp_path)
    upload_id = "chunk-test-1"
    part = b"\x00\x00\x00\x18ftypmp42" + b"c" * 256
    r = client.post(
        f"/api/video/upload/chunk?upload_id={upload_id}&chunk_index=0",
        files={"file": ("part.bin", part, "application/octet-stream")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/video/upload/complete?upload_id={upload_id}&filename=joined.mp4",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["storage_path"].startswith("/media/")
    assert body["file_size"] == len(part)
    assert client.get(body["storage_path"]).content == part
