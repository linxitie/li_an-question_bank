"""商品图异步抠像队列（2026-11-18）。

覆盖：
1. 上传立即返回 queued + status_url，占位图已落盘；
2. 轮询状态到 done 后，文件被覆盖为处理结果；
3. 未知任务返回 404。
"""
from __future__ import annotations

import io
import time

from PIL import Image, ImageDraw

from app.services import product_image


def _jpeg_bytes() -> bytes:
    img = Image.new("RGB", (400, 400), (238, 240, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle((90, 90, 310, 310), fill=(30, 80, 170))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_async_upload_queues_then_finishes(monkeypatch, tmp_path, client, admin_headers):
    monkeypatch.setattr(product_image, "SHOP_DIR", tmp_path)
    monkeypatch.setattr(product_image, "ASYNC_ENABLED", True)
    # 用经典算法跑后台任务，避免测试依赖 973MB 模型
    monkeypatch.setattr(product_image, "CUTOUT_ENGINE", "classic")
    monkeypatch.setattr(product_image, "_ai_ready_cache", None)

    files = {"file": ("probe.jpg", _jpeg_bytes(), "image/jpeg")}
    res = client.post("/api/admin/shop/upload-image", files=files, headers=admin_headers)
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["async"] is True
    assert d["engine"] == "queued"
    assert d["status_url"].endswith("/status")

    name = d["url"].rsplit("/", 1)[-1]
    assert (tmp_path / name).exists(), "占位图应先落盘"

    deadline = time.time() + 30
    state = None
    while time.time() < deadline:
        s = client.get(f"/api/admin/shop/upload-image/{name}/status", headers=admin_headers)
        assert s.status_code == 200, s.text
        state = s.json()["state"]
        if state in ("done", "failed"):
            break
        time.sleep(0.3)
    assert state == "done", state

    final = Image.open(tmp_path / name)
    assert final.size == (product_image.OUTPUT_SIZE, product_image.OUTPUT_SIZE)


def test_status_unknown_returns_404(client, admin_headers):
    res = client.get("/api/admin/shop/upload-image/deadbeef.png/status", headers=admin_headers)
    assert res.status_code == 404
