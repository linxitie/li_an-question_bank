"""商品图处理（2026-11-05）：自动抠像 + 白底 + 清晰度校验。

为什么不用 rembg 这类深度学习抠图：环境里没有模型权重，首次使用要联网下载上百 MB，
在离线/受限网络下会直接失败。这里用**边缘洪泛抠像**：
从图片四边向内扩散，把与边缘颜色相近的像素设为透明，再把主体合成到白底上。
适用于"商品摆拍 + 纯色/浅色背景"的常见情况，失败时会提示管理员重传。

清晰度校验用拉普拉斯方差（越小越糊），低于阈值直接拒绝，满足"照片不清晰要求重传"。
"""
from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
SHOP_DIR = STATIC_ROOT / "shop"
SHOP_URL_PREFIX = "/static/shop"

MIN_WIDTH = 300
MIN_HEIGHT = 300
MAX_BYTES = 8 * 1024 * 1024
# 拉普拉斯方差阈值：低于该值视为模糊（实测清晰图 ~230，高斯模糊 3px 后 <1）
MIN_SHARPNESS = 15.0
# 背景相似度容差（RGB 欧氏距离）
BG_TOLERANCE = 42
OUTPUT_SIZE = 600


def _sharpness(img: Image.Image) -> float:
    """拉普拉斯方差：越大越清晰。

    注意不能用 FIND_EDGES——它对"大块平滑色块"的边界也给出高方差，
    模糊照片依然会通过。真正的拉普拉斯核只响应高频细节。
    """
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    lap = (
        -4 * gray
        + np.roll(gray, 1, 0)
        + np.roll(gray, -1, 0)
        + np.roll(gray, 1, 1)
        + np.roll(gray, -1, 1)
    )
    return float(lap[1:-1, 1:-1].var())


def _remove_background(img: Image.Image, tolerance: int = BG_TOLERANCE) -> Image.Image:
    """边缘洪泛抠像：与边缘同色的连通区域变透明。"""
    rgb = img.convert("RGB")
    arr = np.asarray(rgb, dtype=np.int16)
    h, w, _ = arr.shape

    # 以四边像素的中位色作为背景色参考
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]], axis=0)
    bg = np.median(border, axis=0)

    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))

    # 洪泛：从四边出发，只保留与背景相近且与边缘连通的像素
    from collections import deque

    visited = np.zeros((h, w), dtype=bool)
    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if dist[y, x] <= tolerance and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if dist[y, x] <= tolerance and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))

    while queue:
        y, x = queue.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and dist[ny, nx] <= tolerance:
                visited[ny, nx] = True
                queue.append((ny, nx))

    alpha = np.where(visited, 0, 255).astype(np.uint8)
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    return Image.fromarray(rgba, mode="RGBA")


def _compose_white(rgba: Image.Image, size: int = OUTPUT_SIZE) -> Image.Image:
    """把抠像结果合成到白底，居中并留 8% 边距。"""
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    inner = int(size * 0.84)
    rgba.thumbnail((inner, inner), Image.LANCZOS)
    offset = ((size - rgba.width) // 2, (size - rgba.height) // 2)
    canvas.paste(rgba, offset, rgba)
    return canvas.convert("RGB")


def process_product_image(raw: bytes) -> dict:
    """处理上传的商品图：校验 → 扣背景 → 白底 → 落盘。

    返回 {url, width, height, sharpness}；不清晰/尺寸不足时抛 ValueError。
    """
    if not raw:
        raise ValueError("没有收到图片文件")
    if len(raw) > MAX_BYTES:
        raise ValueError("图片超过 8MB，请压缩后重传")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise ValueError("无法识别图片格式（支持 JPG/PNG/WebP）") from exc

    if img.width < MIN_WIDTH or img.height < MIN_HEIGHT:
        raise ValueError(f"图片尺寸过小（{img.width}×{img.height}），请上传至少 {MIN_WIDTH}×{MIN_HEIGHT} 的照片")

    score = _sharpness(img)
    if score < MIN_SHARPNESS:
        raise ValueError("照片不够清晰，请重新拍摄/上传（注意对焦与光线）")

    try:
        rgba = _remove_background(img)
        result = _compose_white(rgba)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("抠像失败，请换一张背景更干净的照片") from exc

    SHOP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.png"
    out_path = SHOP_DIR / name
    result.save(out_path, format="PNG", optimize=True)

    logger.info("商品图处理完成 %s（清晰度 %.1f）", name, score)
    return {
        "url": f"{SHOP_URL_PREFIX}/{name}",
        "width": result.width,
        "height": result.height,
        "sharpness": round(score, 2),
    }
