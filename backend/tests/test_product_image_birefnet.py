"""商品图抠像引擎选择（2026-11-18）。

覆盖：
1. auto + 模型就绪 → 走 BiRefNet；
2. auto + BiRefNet 报错 → 退回经典算法（GrabCut/洪泛）；
3. birefnet（强制）+ 报错 → 直接失败，不再静默降级；
4. classic 模式不碰 rembg（测试默认）。
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from app.services import product_image


def _sample() -> Image.Image:
    img = Image.new("RGB", (320, 320), (240, 240, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle((80, 80, 240, 240), fill=(40, 90, 180))
    return img


def test_auto_uses_birefnet_when_ready(monkeypatch):
    monkeypatch.setattr(product_image, "CUTOUT_ENGINE", "auto")
    monkeypatch.setattr(product_image, "_ai_ready_cache", True)
    monkeypatch.setattr(
        product_image,
        "_remove_background_birefnet",
        lambda img: Image.new("RGBA", img.size, (10, 20, 30, 255)),
    )
    rgba, engine = product_image._remove_background(_sample())
    assert engine == "birefnet"
    assert rgba.mode == "RGBA"


def test_auto_falls_back_when_birefnet_errors(monkeypatch):
    monkeypatch.setattr(product_image, "CUTOUT_ENGINE", "auto")
    monkeypatch.setattr(product_image, "_ai_ready_cache", True)

    def boom(img):
        raise RuntimeError("onnx 崩了")

    monkeypatch.setattr(product_image, "_remove_background_birefnet", boom)
    rgba, engine = product_image._remove_background(_sample())
    assert engine in ("grabcut", "flood")
    assert rgba.size == (320, 320)


def test_forced_birefnet_error_is_raise(monkeypatch):
    monkeypatch.setattr(product_image, "CUTOUT_ENGINE", "birefnet")
    monkeypatch.setattr(product_image, "_ai_ready_cache", True)

    def boom(img):
        raise RuntimeError("模型缺失")

    monkeypatch.setattr(product_image, "_remove_background_birefnet", boom)
    try:
        product_image._remove_background(_sample())
    except RuntimeError as exc:
        assert "BiRefNet" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("强制 birefnet 时应抛错")


def test_classic_engine_never_touches_rembg(monkeypatch):
    monkeypatch.setattr(product_image, "CUTOUT_ENGINE", "classic")
    monkeypatch.setattr(product_image, "_ai_ready_cache", None)
    monkeypatch.setattr(
        product_image,
        "_remove_background_birefnet",
        lambda img: (_ for _ in ()).throw(AssertionError("classic 不应调用 rembg")),
    )
    _, engine = product_image._remove_background(_sample())
    assert engine in ("grabcut", "flood")
    assert product_image.cutout_engine() == "classic"
