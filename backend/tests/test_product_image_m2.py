"""商品图处理测试（2026-11-05）：抠像白底 / 模糊拒绝 / 尺寸拒绝。"""
from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.services import product_image


def _product_photo(size=600, *, solid_bg=True, blur=0):
    """造一张"商品照"：浅灰背景 + 中央深色圆形主体。"""
    img = Image.new("RGB", (size, size), (240, 240, 240) if solid_bg else (200, 210, 220))
    d = ImageDraw.Draw(img)
    d.ellipse((size * 0.3, size * 0.3, size * 0.7, size * 0.7), fill=(40, 80, 140))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_process_produces_white_background(tmp_path, monkeypatch):
    monkeypatch.setattr(product_image, "SHOP_DIR", tmp_path)
    raw = _product_photo()

    result = product_image.process_product_image(raw)
    assert result["url"].startswith(product_image.SHOP_URL_PREFIX)
    assert result["width"] == product_image.OUTPUT_SIZE

    files = list(tmp_path.glob("*.png"))
    assert len(files) == 1
    out = Image.open(files[0]).convert("RGB")
    # 四角应为白底
    for xy in ((0, 0), (out.width - 1, 0), (0, out.height - 1), (out.width - 1, out.height - 1)):
        r, g, b = out.getpixel(xy)
        assert r > 245 and g > 245 and b > 245, f"角落不是白底: {out.getpixel(xy)}"


def test_blurry_photo_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(product_image, "SHOP_DIR", tmp_path)
    raw = _product_photo(blur=12)
    with pytest.raises(ValueError) as exc:
        product_image.process_product_image(raw)
    assert "清晰" in str(exc.value)


def test_small_photo_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(product_image, "SHOP_DIR", tmp_path)
    raw = _product_photo(size=120)
    with pytest.raises(ValueError) as exc:
        product_image.process_product_image(raw)
    assert "尺寸" in str(exc.value)


def test_invalid_bytes_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(product_image, "SHOP_DIR", tmp_path)
    with pytest.raises(ValueError):
        product_image.process_product_image(b"not an image")


def test_upload_endpoint_requires_admin(client, auth_headers):
    res = client.post(
        "/api/admin/shop/upload-image",
        files={"file": ("a.png", _product_photo(), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code in (401, 403), res.text


def test_upload_endpoint_rejects_blurry(client, admin_headers):
    res = client.post(
        "/api/admin/shop/upload-image",
        files={"file": ("blur.png", _product_photo(blur=14), "image/png")},
        headers=admin_headers,
    )
    assert res.status_code == 400, res.text
    assert "清晰" in res.json()["detail"]


def test_options_defaults_and_custom(client, admin_headers):
    res = client.get("/api/admin/shop/options?kind=category", headers=admin_headers)
    assert res.status_code == 200, res.text
    values = [i["value"] for i in res.json()["items"]]
    for name in ("专属头像框", "限定称号", "文具", "习题册", "警大文创"):
        assert name in values

    created = client.post(
        "/api/admin/shop/options",
        json={"kind": "category", "value": "测试自定义类型"},
        headers=admin_headers,
    )
    assert created.status_code == 200, created.text

    after = client.get("/api/admin/shop/options?kind=category", headers=admin_headers)
    assert "测试自定义类型" in [i["value"] for i in after.json()["items"]]

    dup = client.post(
        "/api/admin/shop/options",
        json={"kind": "category", "value": "测试自定义类型"},
        headers=admin_headers,
    )
    assert dup.json()["duplicated"] is True


def test_options_deliverable_types(client, admin_headers):
    res = client.get("/api/admin/shop/options?kind=deliverable_type", headers=admin_headers)
    values = [i["value"] for i in res.json()["items"]]
    assert {"title", "avatar_frame", "code", "manual"} <= set(values)
