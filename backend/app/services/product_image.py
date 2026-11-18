"""商品图处理（2026-11-05，2026-11-18 升级）：抠像 + 白底 + 清晰度校验。

抠像引擎（按优先级）：
1. **BiRefNet**（深度学习，rembg 调用）：商品边缘/透明材质保留最好，默认用 birefnet-general；
   模型权重约 973MB，放在 %USERPROFILE%\.rembg\models\birefnet-general\；
2. GrabCut（OpenCV，本地算法）：BiRefNet 不可用/失败时的兜底；
3. 边缘洪泛：最后兜底（纯色背景）。

为什么 auto 模式不自动下载权重：900MB+ 在管理员上传请求里下载会让请求卡死几分钟；
部署时预先下载（scripts/shop/fetch_cutout_model.ps1），没有权重就自动走经典算法。

清晰度校验用拉普拉斯方差（越小越糊），低于阈值直接拒绝，满足"照片不清晰要求重传"。
"""
from __future__ import annotations

import io
import logging
import os
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

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

# ===== BiRefNet 深度学习抠图（2026-11-18）=====
# SHOP_CUTOUT_ENGINE: auto（默认，有模型就用）/ birefnet（强制，失败即报错）/ classic（本地算法）
# SHOP_CUTOUT_MODEL: birefnet-general（质量最好）/ birefnet-general-lite（快，但实测对书本类商品会错位）
# SHOP_CUTOUT_ALLOW_DOWNLOAD=1 时允许首次上传时在线下载权重（默认禁止）
CUTOUT_ENGINE = os.getenv("SHOP_CUTOUT_ENGINE", "auto").strip().lower()
CUTOUT_MODEL = os.getenv("SHOP_CUTOUT_MODEL", "birefnet-general").strip()
CUTOUT_MAX_INPUT = int(os.getenv("SHOP_CUTOUT_MAX_INPUT", "1024"))
CUTOUT_THREADS = int(os.getenv("SHOP_CUTOUT_THREADS", str(min(16, os.cpu_count() or 4))))
# 异步队列：上传立即返回占位图，后台线程抠完覆盖同一个文件（默认开启；SHOP_CUTOUT_ASYNC=0 关闭）
ASYNC_ENABLED = os.getenv("SHOP_CUTOUT_ASYNC", "1").strip() not in ("0", "false", "no", "off")

# 任务状态：key = 文件名（与 /api/shop/images/<name> 一致）
_JOB_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_EXECUTOR = None
_EXECUTOR_LOCK = threading.Lock()


def _executor():
    global _EXECUTOR
    if _EXECUTOR is None:
        with _EXECUTOR_LOCK:
            if _EXECUTOR is None:
                from concurrent.futures import ThreadPoolExecutor

                # 抠像是 CPU 密集且会话常驻约 1GB，串行处理最稳；队列让上传立即返回
                _EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="shop-cutout")
    return _EXECUTOR


def _job_snapshot(name: str) -> dict | None:
    with _JOB_LOCK:
        job = _JOBS.get(name)
        return dict(job) if job else None


def _job_update(name: str, **fields) -> None:
    with _JOB_LOCK:
        job = _JOBS.setdefault(name, {})
        job.update(fields)
        job["updated_at"] = time.time()


def _placeholder_image(text: str) -> Image.Image:
    """占位图：白底 + 灰色提示文字（用默认字体，避免服务器缺中文字体）。"""
    canvas = Image.new("RGB", (OUTPUT_SIZE, OUTPUT_SIZE), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    # 简单的灰框 + 文字，明确这是"处理中"
    draw.rectangle((18, 18, OUTPUT_SIZE - 18, OUTPUT_SIZE - 18), outline=(226, 232, 240), width=4)
    draw.text((OUTPUT_SIZE // 2 - 52, OUTPUT_SIZE // 2 - 8), text, fill=(148, 163, 184))
    return canvas


def _write_placeholder(path: Path, text: str = "AI processing...") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _placeholder_image(text).save(path, format="PNG", optimize=True)

_ai_session = None
_ai_lock = threading.Lock()
_ai_ready_cache: bool | None = None


def cutout_engine() -> str:
    """当前实际可用的引擎：birefnet / classic。"""
    return "birefnet" if _birefnet_ready() else "classic"


def _birefnet_ready() -> bool:
    """rembg 可导入 + 权重已在本机（auto 模式绝不在这里触发下载）。"""
    global _ai_ready_cache
    if _ai_ready_cache is not None:
        return _ai_ready_cache
    ready = False
    if CUTOUT_ENGINE != "classic":
        try:
            import rembg  # noqa: F401

            if os.getenv("SHOP_CUTOUT_ALLOW_DOWNLOAD") == "1":
                ready = True
            else:
                from rembg.sessions import sessions_class

                cls = next(c for c in sessions_class if c.name() == CUTOUT_MODEL)
                model_dir = Path(cls.model_dir())
                ready = model_dir.is_dir() and any(model_dir.glob("*.onnx"))
        except Exception:  # noqa: BLE001
            ready = False
    _ai_ready_cache = ready
    return ready


def _session_options():
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = max(1, CUTOUT_THREADS)
    opts.inter_op_num_threads = 1
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return opts


def _birefnet_session():
    global _ai_session
    if _ai_session is not None:
        return _ai_session
    with _ai_lock:
        if _ai_session is None:
            from rembg import new_session

            _ai_session = new_session(CUTOUT_MODEL, sess_opts=_session_options())
    return _ai_session


def warmup_background() -> None:
    """后端启动时后台预热模型（首次加载 ONNX 会话约 5~50s，不能让首个上传请求等）。"""
    if not _birefnet_ready():
        return

    def _run() -> None:
        try:
            t0 = time.time()
            _birefnet_session()
            logger.info("BiRefNet 模型预热完成（%s，%.1fs）", CUTOUT_MODEL, time.time() - t0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("BiRefNet 预热失败，将继续用经典算法兜底: %s", exc)

    threading.Thread(target=_run, daemon=True, name="shop-cutout-warmup").start()


def _remove_background_birefnet(img: Image.Image) -> Image.Image:
    """BiRefNet 抠像：内部固定 1024 输入，大图先缩到 1024 再推理，最后放回原尺寸。"""
    from rembg import remove as rembg_remove

    session = _birefnet_session()
    work = img.convert("RGB")
    scale = min(1.0, CUTOUT_MAX_INPUT / max(work.size))
    if scale < 1.0:
        work = work.resize(
            (max(1, int(work.width * scale)), max(1, int(work.height * scale))),
            Image.LANCZOS,
        )
    cut = rembg_remove(work, session=session)
    if cut.size != img.size:
        cut = cut.resize(img.size, Image.LANCZOS)
    return cut


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


def _remove_background(img: Image.Image, tolerance: int = BG_TOLERANCE):
    """抠像主入口：BiRefNet → GrabCut → 洪泛。

    返回 (RGBA 图, 实际使用的引擎名)，供上层决定是否再做灰度阴影抑制
    （BiRefNet 已经输出干净 alpha，再做阴影抑制反而可能吃掉白色书页）。
    """
    if CUTOUT_ENGINE in ("auto", "birefnet") and _birefnet_ready():
        t0 = time.time()
        try:
            rgba = _remove_background_birefnet(img)
            logger.info("抠图引擎 BiRefNet(%s) %.2fs", CUTOUT_MODEL, time.time() - t0)
            return rgba, "birefnet"
        except Exception as exc:  # noqa: BLE001
            if CUTOUT_ENGINE == "birefnet":
                raise RuntimeError(f"BiRefNet 抠图失败：{exc}") from exc
            logger.warning("BiRefNet 抠图失败，退回经典算法: %s", exc)

    try:
        return _remove_background_grabcut(img), "grabcut"
    except Exception as exc:  # noqa: BLE001
        logger.warning("GrabCut 抠像失败，退回洪泛抠像: %s", exc)
        return _remove_background_flood(img, tolerance), "flood"


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


def _render_cutout(raw: bytes, img: Image.Image) -> tuple[Image.Image, str]:
    """同步执行抠像 + 白底合成，返回 (600×600 结果, 引擎名)。"""
    try:
        rgba, engine = _remove_background(img)
        if engine != "birefnet":
            # 经典算法会把软阴影判成前景，需要额外抑制；BiRefNet 的 alpha 已干净
            rgba = _suppress_gray_shadow(rgba)
        return _compose_white(rgba), engine
    except Exception as exc:  # noqa: BLE001
        raise ValueError("抠像失败，请换一张背景更干净的照片") from exc


def _save_atomic(result: Image.Image, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    result.save(tmp, format="PNG", optimize=True)
    os.replace(tmp, out_path)


def _run_cutout_job(name: str, raw: bytes) -> None:
    """后台队列任务：抠完覆盖占位图（同一个 URL，前台刷新即可看到结果）。"""
    _job_update(name, state="running", started_at=time.time())
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
        result, engine = _render_cutout(raw, img)
        _save_atomic(result, SHOP_DIR / name)
        _job_update(name, state="done", engine=engine, finished_at=time.time(), error=None)
        logger.info("商品图异步抠像完成 %s（引擎 %s）", name, engine)
    except Exception as exc:  # noqa: BLE001
        _job_update(name, state="failed", error=str(exc), finished_at=time.time())
        logger.warning("商品图异步抠像失败 %s: %s", name, exc)
        try:
            _write_placeholder(SHOP_DIR / name, "AI failed. Try again.")
        except Exception:  # noqa: BLE001
            logger.warning("占位图更新失败 %s", name)


def image_job_status(name: str) -> dict | None:
    """查询异步抠像任务状态；未知/已重启返回 None。"""
    return _job_snapshot(name)


def process_product_image(raw: bytes, async_mode: bool | None = None) -> dict:
    """处理上传的商品图：校验 → 扣背景 → 白底 → 落盘。

    默认异步（SHOP_CUTOUT_ASYNC=1）：先写占位图并立即返回，后台线程抠完覆盖同一 URL；
    返回 {url, width, height, sharpness, engine, async?, status_url?}。
    不清晰/尺寸不足时抛 ValueError。
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

    SHOP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.png"
    base = {
        "url": f"{SHOP_URL_PREFIX}/{name}",
        "width": OUTPUT_SIZE,
        "height": OUTPUT_SIZE,
        "sharpness": round(score, 2),
    }

    if async_mode is None:
        async_mode = ASYNC_ENABLED

    if async_mode:
        _write_placeholder(SHOP_DIR / name)
        _job_update(name, state="queued", engine="queued", started_at=time.time(), error=None)
        _executor().submit(_run_cutout_job, name, raw)
        logger.info("商品图已入队 %s（清晰度 %.1f），后台抠像中", name, score)
        return {
            **base,
            "engine": "queued",
            "async": True,
            "status_url": f"/api/admin/shop/upload-image/{name}/status",
        }

    result, engine = _render_cutout(raw, img)
    _save_atomic(result, SHOP_DIR / name)
    logger.info("商品图处理完成 %s（引擎 %s，清晰度 %.1f）", name, engine, score)
    return {**base, "engine": engine, "async": False}
