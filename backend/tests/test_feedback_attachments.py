"""反馈附件与视频上传校验（2026-11-23）。"""
import pytest

from app.api.v1.platform.feedback import _validate_attachments
from app.api.v1.library.image_media import _video_magic_ok


def _img(i: int = 1) -> dict:
    return {"name": f"a{i}.png", "url": f"/uploads/a{i}.png", "size": 100, "type": "image/png"}


def _video() -> dict:
    return {"name": "v.mp4", "url": "/uploads/v.mp4", "size": 1000, "type": "video/mp4"}


def test_accepts_images_and_one_video():
    items = _validate_attachments([_img(1), _img(2), _video()])
    assert [i["kind"] for i in items] == ["image", "image", "video"]


def test_rejects_second_video():
    with pytest.raises(Exception):
        _validate_attachments([_video(), {**_video(), "url": "/uploads/v2.mp4"}])


def test_rejects_more_than_five_images():
    with pytest.raises(Exception):
        _validate_attachments([_img(i) for i in range(6)])


def test_infers_kind_for_legacy_payload():
    items = _validate_attachments([{"name": "a.png", "url": "/uploads/a.png", "type": "image/png"}])
    assert items[0]["kind"] == "image"


def test_video_magic():
    assert _video_magic_ok(".mp4", b"\x00\x00\x00\x18ftypisom")
    assert _video_magic_ok(".webm", b"\x1aE\xdf\xa3rest")
    assert not _video_magic_ok(".mp4", b"<html>not video</html>")
    assert not _video_magic_ok(".webm", b"plain")
