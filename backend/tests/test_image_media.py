"""图片上传 P1 测试。"""
import io

from PIL import Image


def _png_bytes(size=(12, 12)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_png_returns_url(client, auth_headers):
    files = {"file": ("a.png", _png_bytes(), "image/png")}
    resp = client.post("/api/media/image", headers=auth_headers, files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"].startswith("/uploads/forum/")
    assert body["type"] == "image/png"
    assert body["width"] == 12
    assert body["height"] == 12


def test_reject_fake_extension(client, auth_headers):
    files = {"file": ("a.png", b"not-an-image", "image/png")}
    resp = client.post("/api/media/image", headers=auth_headers, files=files)
    assert resp.status_code == 400


def test_reject_empty_file(client, auth_headers):
    files = {"file": ("a.png", b"", "image/png")}
    resp = client.post("/api/media/image", headers=auth_headers, files=files)
    assert resp.status_code == 400


def test_reject_oversize(client, auth_headers):
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.png", big, "image/png")}
    resp = client.post("/api/media/image", headers=auth_headers, files=files)
    assert resp.status_code == 413
