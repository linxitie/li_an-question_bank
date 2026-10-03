# -*- coding: utf-8 -*-
"""
image_filters.py — 题目图片无关性判定共享模块（问题2-R2）

供两处复用（同一判定标准，防止"清完又进"）：
  1. 导入管线 question_import.py::_is_irrelevant_image（入库前过滤）
  2. 存量清理脚本 scripts/clean_irrelevant_images_v2.py（历史数据清洗）

三级判定（返回 (是否无关, 命中原因)）：
  L1 QR 解码：OpenCV QRCodeDetector 解码成功或检出定位图案 → qr_code/qr_pattern
  L2 推广横幅：宽高比≥2.5 的横幅 + 上部高对比红/黑文字块特征 → promo_banner
  L3 像素统计降级（无 OpenCV 时）：黑白模块密度接近二维码特征 → qr_likely（仅标记）
  L4 尺寸启发式（沿用既有行为）：过小图标/极端宽高比扫描条/近纯色边距 → tiny/extreme_ratio/blank

设计原则：
  - 判定失败不抛异常（不阻塞导入），返回 (False, '')
  - qr_likely 属"疑似"，调用方应只标记不自动删除
  - OpenCV 缺失时自动降级，打 warning 日志
"""
import io
import json
import logging
import hashlib
import os

logger = logging.getLogger(__name__)

# L0: 已确认推广图 md5 黑名单（数据驱动、零误杀）。
# 维护方式：人工确认新推广图后把文件名中的 8 位 md5 追加进 JSON 即可。
_BLACKLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'promo_md5_blacklist.json')


def _load_blacklist():
    try:
        with open(_BLACKLIST_PATH, encoding='utf-8') as f:
            return set(x.lower() for x in json.load(f))
    except Exception:
        return set()


try:
    import cv2
    import numpy as np
    _QR_DETECTOR = cv2.QRCodeDetector()
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False
    logger.warning("[image_filters] OpenCV 未安装，二维码检测降级为像素统计模式")

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


def _detect_qr_enhanced(img_bytes: bytes):
    """L1 增强: OpenCV 二维码解码 + 颜色特征分析"""
    if not _HAS_CV2:
        return None
    try:
        buf = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        # 尝试解码（内容为推广文案/链接即实锤）
        try:
            data, points, _ = _QR_DETECTOR.detectAndDecode(img)
            if data:
                return ('qr_code', f'二维码解码成功: {data[:40]}')
            if points is not None:
                # 增强: 检查是否为正方形且尺寸合理
                h, w = img.shape[:2]
                if 120 <= w <= 800 and 120 <= h <= 800 and abs(w - h) / max(w, h) < 0.15:
                    return ('qr_pattern', '检出二维码定位图案（正方形）')
        except cv2.error:
            pass
        return None
    except Exception as e:  # noqa: BLE001 — 判定失败不阻塞
        logger.debug(f"[image_filters] QR检测异常: {e}")
        return None


def _detect_qr(img_bytes: bytes):
    """L1: OpenCV 二维码解码。返回 (level, reason) 或 None"""
    return _detect_qr_enhanced(img_bytes)


def _detect_promo_banner(img) -> bool:
    """L2: 推广横幅特征（img 为 PIL Image 或 None）。

    校准结论（2026-08，真实样本）：
      推广横幅 = 宽横幅(ratio≥2.5) + 密集文字行结构（80x30 缩略图中
      行方差>200 的"文字行"≥15 条）。正常宽图表文字行 ≤10，可干净区分。
    另保留红黑配色密集的旧特征作为 OR 分支（覆盖红字横幅变体）。
    """
    if img is None:
        return False
    try:
        import statistics
        w, h = img.size
        if h == 0 or w / h < 2.5:
            return False
        gray = img.convert('L').resize((80, 30))
        px = list(gray.getdata())
        n = len(px)
        if not n:
            return False
        # 特征A：文字行结构密度
        structured_rows = 0
        for ry in range(30):
            row = px[ry * 80:(ry + 1) * 80]
            if statistics.pvariance(row) > 200:
                structured_rows += 1
        if structured_rows >= 15:
            return True
        # 特征B：红黑配色密集（红标识+黑字，旧逻辑保留）
        rgb = img.convert('RGB').resize((60, 20))
        pixels = list(rgb.getdata())
        red_like = sum(1 for p in pixels if p[0] > 170 and p[1] < 90 and p[2] < 90)
        dark = sum(1 for p in pixels if p[0] < 80 and p[1] < 80 and p[2] < 80)
        return (red_like + dark) / len(pixels) > 0.18
    except Exception:
        return False


def _detect_qr_pixel_pattern(img) -> bool:
    """L3: 像素统计降级——黑白模块密度接近二维码特征（仅标记用）"""
    if img is None:
        return False
    try:
        w, h = img.size
        if not (120 <= w <= 800 and 120 <= h <= 800):
            return False
        if abs(w - h) / max(w, h) > 0.15:
            return False  # 二维码近似正方形
        gray = img.convert('L').resize((40, 40))
        pixels = list(gray.getdata())
        dark = sum(1 for p in pixels if p < 100) / len(pixels)
        # 二维码黑白模块密度典型 0.35~0.65
        return 0.30 <= dark <= 0.70
    except Exception:
        return False


def is_irrelevant_image(img_data: bytes):
    """统一判定入口。返回 (is_irrelevant: bool, reason: str)。

    reason 前缀约定：
      qr_code / qr_pattern  — 实锤，可直接清理
      promo_banner          — 强特征，可直接清理
      qr_likely             — 疑似（无 OpenCV 降级判定），调用方只标记不自动删
      tiny / extreme_ratio / blank — 尺寸启发式（沿用既有行为）
    """
    if not img_data:
        return False, ''
    try:
        # L0: md5 黑名单（人工确认过的推广图，精确命中）
        md5 = hashlib.md5(img_data).hexdigest()[:8]
        if md5 in _load_blacklist():
            return 'promo_banner', f'推广图黑名单命中 md5={md5}'

        pil_img = None
        if _HAS_PIL:
            try:
                pil_img = Image.open(io.BytesIO(img_data))
                pil_img.load()
            except Exception:
                pil_img = None

        # L1: QR 解码（OpenCV 可用时）
        # ★ 仅"解码出内容"算实锤；仅检出定位图案可能是图表矩形框误报
        #   （真实事故：处置方案图/图标选项条被 qr_pattern 误杀），降级为疑似
        qr_hit = _detect_qr(img_data)
        if qr_hit:
            level, reason = qr_hit
            if level == 'qr_code':
                return level, reason
            if level == 'qr_pattern':
                return 'qr_likely', f'{reason}（疑似，需人工复核）'

        # L2: 推广横幅结构/配色特征 → 一律疑似级（目检证实会误杀
        # 图标选项条/嵌套图选项/警务照片序列等核心内容）
        if _detect_promo_banner(pil_img):
            return 'promo_likely', '推广横幅特征（疑似，需人工复核）'

        # L3: 像素统计降级（仅无 OpenCV 时启用，避免误杀正方形图表）
        if not _HAS_CV2 and _detect_qr_pixel_pattern(pil_img):
            return 'qr_likely', '疑似二维码（像素统计，需人工复核）'

        # L4: 尺寸启发式（沿用 question_import 既有行为）
        if pil_img is not None:
            w, h = pil_img.size
            if w < 100 and h < 100:
                return 'tiny', f'过小图片 {w}x{h}'
            ratio = max(w, h) / max(min(w, h), 1)
            if ratio > 8 and min(w, h) < 60:
                return 'extreme_ratio', f'极端宽高比 {w}x{h}'
            if w > 200 and 50 < h < 100:
                small = pil_img.convert('L').resize((20, 20))
                pixels = list(small.getdata())
                if pixels:
                    avg = sum(pixels) / len(pixels)
                    var = sum((p - avg) ** 2 for p in pixels) / len(pixels)
                    if var < 50:
                        return 'blank', '近纯色扫描边距'
        return False, ''
    except Exception as e:  # noqa: BLE001 — 判定失败不阻塞
        logger.debug(f"[image_filters] 判定异常: {e}")
        return False, ''


# 实锤级 reason（可直接清理）：QR 解码出内容 / 黑名单 md5 命中
_BLOCK_REASONS = {'qr_code', 'promo_banner'}
# 疑似级 reason（需人工复核，不自动删除）
_SUSPECT_REASONS = {'qr_likely', 'promo_likely', 'qr_pattern', 'tiny', 'extreme_ratio', 'blank'}


def is_trailing_irrelevant(img_bytes: bytes, position_ratio: float) -> tuple:
    """文末推广图/二维码的**位置规则**（与内容规则正交的第二道防线）。

    position_ratio：图片在全文中的相对位置（0=开头，1=结尾）

    真实事故：2019 新疆兵团卷末题尾部出现 `[IMAGE:72648561_90_0]`、
    `[IMAGE:72648561_90_1]` 两张推广二维码。它们印刷模糊/带 logo，
    OpenCV 解不出内容（`qr_code` 分支不命中），`qr_pattern` 又是"疑似"级，
    于是 block 级规则全部漏过，二维码被当成题目图片入库。

    本规则不看图片内容，**只看位置**：文末区间的图无论能否解码一律丢弃。
    调用方（text_parser._strip_trailing_images）已在解析层做了结构级剥离，
    本函数是导入侧的兜底，两者不冲突。

    返回 (是否无关, 原因)；不抛异常。
    """
    try:
        if position_ratio is None:
            return False, ''
        r = float(position_ratio)
    except (TypeError, ValueError):
        return False, ''
    # 阈值 0.985：最后 1.5% 区域。真题配图位于题干内，位置不会贴到文末。
    if r >= 0.985:
        return True, f'trailing_zone(ratio={r:.4f}>=0.985)'
    return False, ''


def classify_image(img_data: bytes, position_ratio: 'float | None' = None):
    """P2-1 三级判定：返回 (decision, reason)。

    position_ratio 可选，传入时启用"文末推广图"位置规则（见 is_trailing_irrelevant）。

    decision 取值：
      'block'   — 实锤无关图（QR 解码成功 / 黑名单 md5 命中），可自动拦截删除
      'suspect' — 疑似无关图（推广横幅/疑似二维码/尺寸启发式），放行但标记人工复核
      'keep'    — 正常内容图

    与 is_irrelevant_image 的关系：本函数是其"分级"封装，供导入侧（block 拦截、
    suspect 标记）与存量清理脚本（仅 block 删除、suspect 列出）复用同一判定标准。
    """
    # 位置规则优先：文末推广图无论内容如何一律 block（与内容规则正交）
    if position_ratio is not None:
        tail_hit, tail_reason = is_trailing_irrelevant(img_data, position_ratio)
        if tail_hit:
            return 'block', tail_reason

    hit, reason = is_irrelevant_image(img_data)
    if not hit:
        return 'keep', ''
    if hit in _BLOCK_REASONS:
        return 'block', reason
    if hit in _SUSPECT_REASONS:
        return 'suspect', reason
    return 'suspect', reason  # 未知 reason 保守按疑似处理
