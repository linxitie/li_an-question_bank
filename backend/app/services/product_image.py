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
SHOP_URL_PREFIX = "/api/shop/images"

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
    """抠像主入口：优先 GrabCut（能处理纹理背景与阴影），失败退回边缘洪泛。"""
    try:
        return _remove_background_grabcut(img)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GrabCut 抠像失败，退回洪泛抠像: %s", exc)
        return _remove_background_flood(img, tolerance)


def _largest_component(mask: np.ndarray) -> np.ndarray:
    """只保留最大连通域，去掉零散噪点。"""
    import cv2

    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num <= 1:
        return mask
    # 跳过背景标签 0，取面积最大的前景
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == idx, 255, 0).astype(np.uint8)


def _remove_background_grabcut(img: Image.Image) -> Image.Image:
    """GrabCut：边缘带作为确定背景，中心矩形作为可能前景。

    相比洪泛填充的优势：
    - 木纹/布纹等**有纹理**的背景不会被"同色连通"卡住；
    - 商品下方的**软化阴影**多半被判为背景，不会留一块灰影。
    """
    import cv2

    rgb = np.asarray(img.convert("RGB"))
    h, w = rgb.shape[:2]

    # 大图先缩到 900 内，GrabCut 在 900 级别已足够，且快很多
    scale = min(1.0, 900.0 / max(h, w))
    if scale < 1.0:
        work = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        work = rgb
    wh, ww = work.shape[:2]

    mask = np.full((wh, ww), cv2.GC_PR_BGD, dtype=np.uint8)
    border = max(4, int(min(wh, ww) * 0.02))
    mask[:border, :] = cv2.GC_BGD
    mask[-border:, :] = cv2.GC_BGD
    mask[:, :border] = cv2.GC_BGD
    mask[:, -border:] = cv2.GC_BGD

    # 中心 56% 区域视为可能前景（商品一般居中）
    x0, y0 = int(ww * 0.22), int(wh * 0.22)
    x1, y1 = int(ww * 0.78), int(wh * 0.78)
    mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
    # 中心 24% 视为确定前景，给算法一个明确锚点
    mask[int(wh * 0.38) : int(wh * 0.62), int(ww * 0.38) : int(ww * 0.62)] = cv2.GC_FGD

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(work, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)

    binary = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    binary = _recover_detached_parts(binary, work)

    # 轻微羽化边缘，避免锯齿
    binary = cv2.GaussianBlur(binary, (5, 5), 1.2)

    if scale < 1.0:
        binary = cv2.resize(binary, (w, h), interpolation=cv2.INTER_LINEAR)

    rgba = np.dstack([rgb, binary])
    return Image.fromarray(rgba, mode="RGBA")


def _remove_background_flood(img: Image.Image, tolerance: int = BG_TOLERANCE) -> Image.Image:
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


def _recover_detached_parts(mask: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    """找回被 GrabCut 丢掉的小配件（如吊环、挂绳）。

    策略：保留面积占比 ≥0.15% 且**平均颜色明显不同于背景**的连通块。
    背景残片通常与边缘色很接近，会被颜色距离过滤掉；
    投影是灰色，交给后续的 _suppress_gray_shadow 处理。
    """
    import cv2

    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num <= 1:
        return mask

    h, w = mask.shape
    total = float(h * w)
    areas = stats[1:, cv2.CC_STAT_AREA]
    main_idx = 1 + int(np.argmax(areas))

    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]], axis=0)
    bg = np.median(border, axis=0)

    keep = np.zeros_like(mask)
    for idx in range(1, num):
        area = stats[idx, cv2.CC_STAT_AREA]
        if area < total * 0.0015:
            continue
        comp = labels == idx
        mean_color = rgb[comp].mean(axis=0)
        dist = float(np.linalg.norm(mean_color - bg))
        if idx == main_idx or dist >= 70.0:
            keep[comp] = 255
    return keep


def _suppress_gray_shadow(rgba: Image.Image) -> Image.Image:
    """去掉主体下方的灰色投影。

    GrabCut 会把紧贴主体的软阴影判成前景，表现为一圈灰晕。
    阴影的共同特征：**低饱和 + 中高亮度**（灰），而商品主体通常有颜色或接近纯白。
    这里把 alpha>0 区域里"低饱和且不是纯白"的像素剔除，再取最大连通域，
    避免把白色高光也一起删掉。
    """
    import cv2

    arr = np.asarray(rgba)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    saturation = hsv[:, :, 1].astype(np.float32) / 255.0
    value = hsv[:, :, 2].astype(np.float32) / 255.0

    # 灰色阴影：饱和度很低、亮度中等偏高、且不是纯白
    shadow = (saturation < 0.12) & (value > 0.55) & (value < 0.97)

    # 只处理"主体包围盒的下半部分"：投影通常在主体下方，
    # 而灰色配件（吊环、灰白高光）多在主体上半部分，避免误删。
    ys, xs = np.where(alpha > 20)
    if len(ys):
        top, bottom = int(ys.min()), int(ys.max())
        lower_start = int(top + (bottom - top) * 0.55)
        region = np.zeros_like(shadow)
        region[lower_start:, :] = True
        shadow = shadow & region

    cleaned = alpha.copy()
    cleaned[shadow & (alpha > 0)] = 0

    # 剔除后可能只剩主体 + 一些碎片，保留最大连通域
    binary = np.where(cleaned > 20, 255, 0).astype(np.uint8)
    binary = _largest_component(binary)
    binary = cv2.GaussianBlur(binary, (5, 5), 1.0)

    out = np.dstack([rgb, binary])
    return Image.fromarray(out, mode="RGBA")


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
        rgba = _suppress_gray_shadow(rgba)
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
