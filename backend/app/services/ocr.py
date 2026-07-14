"""
PaddleOCR 服务 — 图片文字识别，支持印刷体中文题目
增强版：图像预处理、版式感知、可配置阈值
"""
import logging
import io
import base64
import numpy as np
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ============ 配置 ============
OCR_CONFIDENCE_THRESHOLD = 0.5       # 置信度阈值（提高以减少噪声文字）
ENABLE_PREPROCESS = True              # 是否启用图像预处理
PREPROCESS_METHOD = 'adaptive'        # 预处理方法: 'adaptive' | 'otsu' | 'simple'

# ============ 全局 OCR 实例（懒加载） ============
_ocr_instance = None


def _get_or_create_ocr():
    """
    Lazy-load PaddleOCR 实例，避免启动时就加载大型模型。
    首次调用时初始化，后续复用。
    """
    global _ocr_instance
    if _ocr_instance is not None:
        return _ocr_instance
    try:
        from paddleocr import PaddleOCR
        # 使用新版 PaddleOCR 参数：方向分类器 + 文本检测优化
        _ocr_instance = PaddleOCR(
            lang='ch',
            use_angle_cls=True,        # 启用文字方向分类器（处理旋转文字）
            det_db_thresh=0.5,         # 检测阈值（提高以减少误检）
            det_db_box_thresh=0.3,     # 检测框阈值
            rec_batch_num=6,           # 识别批处理数
        )
        logger.info("PaddleOCR 实例化成功（增强配置）")
        return _ocr_instance
    except ImportError:
        logger.error("PaddleOCR 未安装，请运行: pip install paddleocr paddlepaddle")
        raise RuntimeError("PaddleOCR 未安装")
    except Exception as e:
        logger.error(f"PaddleOCR 初始化失败: {e}")
        raise


def preprocess_image(img_array: np.ndarray) -> np.ndarray:
    """
    图像预处理，提升OCR识别准确率。
    策略（修正版）：
    1. 转为灰度图
    2. 轻微锐化（在二值化前，避免伪影）
    3. 中值滤波去噪
    4. 自适应二值化（adaptive threshold）
    返回 RGB 格式的 numpy 数组。
    """
    try:
        import cv2
    except ImportError:
        logger.warning("opencv-python-headless 未安装，跳过图像预处理")
        return img_array

    try:
        # 1. 转灰度
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # 2. 轻微锐化（在灰度图上执行，二值化前）
        kernel_sharpen = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(gray, -1, kernel_sharpen)

        # 3. 中值滤波去噪
        denoised = cv2.medianBlur(sharpened, 3)

        # 4. 自适应二值化（在锐化+去噪后的灰度图上）
        if PREPROCESS_METHOD == 'adaptive':
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        elif PREPROCESS_METHOD == 'otsu':
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, binary = cv2.threshold(denoised, 127, 255, cv2.THRESH_BINARY)

        # 转回 RGB（二值图直接转，不再锐化）
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        logger.debug(f"图像预处理完成: {img_array.shape} → {result.shape}")
        return result
    except Exception as e:
        logger.warning(f"图像预处理失败，使用原图: {e}")
        return img_array


def reconstruct_reading_order(results: List[Dict]) -> str:
    """
    基于文本框位置信息重建阅读顺序。
    使用Y坐标聚类分组（行），组内按X坐标排序（从左到右）。

    适用于 PaddleOCR 3.x 返回格式（含 dt_polys 位置信息）。
    """
    if not results:
        return ''

    all_text_boxes = []
    for page_result in results:
        rec_texts = page_result.get('rec_texts', [])
        rec_scores = page_result.get('rec_scores', [])
        dt_polys = page_result.get('dt_polys', [])

        for i, text in enumerate(rec_texts):
            score = rec_scores[i] if i < len(rec_scores) else 1.0
            if not text or score < OCR_CONFIDENCE_THRESHOLD:
                continue

            # 计算文本框中心Y坐标（用于行分组）
            if dt_polys and i < len(dt_polys):
                poly = dt_polys[i]
                if poly is not None and len(poly) >= 4:
                    center_y = sum(p[1] for p in poly) / len(poly)
                    center_x = sum(p[0] for p in poly) / len(poly)
                else:
                    center_y = i * 30  # 无位置信息时使用索引估算
                    center_x = 0
            else:
                center_y = i * 30
                center_x = 0

            all_text_boxes.append({
                'text': text,
                'score': score,
                'center_y': center_y,
                'center_x': center_x,
            })

    if not all_text_boxes:
        return ''

    # 按 Y 坐标分组 — 使用聚类方法替代固定阈值
    # 先按Y排序，然后用相邻Y距离的中位数作为阈值
    all_text_boxes.sort(key=lambda b: b['center_y'])

    # 计算相邻文本框的Y距离
    y_diffs = []
    for i in range(1, len(all_text_boxes)):
        diff = abs(all_text_boxes[i]['center_y'] - all_text_boxes[i-1]['center_y'])
        if diff > 0:
            y_diffs.append(diff)

    # 行间距阈值：中位数或默认20
    if y_diffs:
        y_diffs.sort()
        median_diff = y_diffs[len(y_diffs) // 2]
        line_threshold = max(median_diff * 0.8, 15)
    else:
        line_threshold = 20

    # 聚类为行
    lines = []
    current_line = [all_text_boxes[0]]
    for box in all_text_boxes[1:]:
        if abs(box['center_y'] - current_line[-1]['center_y']) < line_threshold:
            current_line.append(box)
        else:
            # 行内按 X 排序
            current_line.sort(key=lambda b: b['center_x'])
            lines.append(' '.join(b['text'] for b in current_line))
            current_line = [box]
    if current_line:
        current_line.sort(key=lambda b: b['center_x'])
        lines.append(' '.join(b['text'] for b in current_line))

    return '\n'.join(lines)


def recognize_image(image_bytes: bytes, use_preprocess: bool = ENABLE_PREPROCESS) -> str:
    """
    识别单张图片中的全部文本。

    Args:
        image_bytes: 图片二进制数据（jpg/png/bmp）
        use_preprocess: 是否启用图像预处理

    Returns:
        识别的纯文本，按版式行顺序拼接
    """
    ocr = _get_or_create_ocr()

    # 将 bytes 转为 numpy 数组供 PaddleOCR 处理
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img_array = np.array(img)

    # 图像预处理
    if use_preprocess:
        try:
            img_array = preprocess_image(img_array)
        except Exception as e:
            logger.warning(f"图像预处理跳过: {e}")

    # PaddleOCR 3.x 使用 predict 方法
    results = ocr.predict(img_array)

    if not results:
        logger.info("OCR 未识别到任何文本")
        return ''

    # 使用版式感知的文本重建
    text = reconstruct_reading_order(results)

    # 如果版式重建结果为空，回退到简单拼接
    if not text:
        lines = []
        for page_result in results:
            rec_texts = page_result.get('rec_texts', [])
            rec_scores = page_result.get('rec_scores', [])
            for i, rec_text in enumerate(rec_texts):
                score = rec_scores[i] if i < len(rec_scores) else 1.0
                if rec_text and score > OCR_CONFIDENCE_THRESHOLD:
                    lines.append(rec_text)
        text = '\n'.join(lines)

    logger.info(f"OCR 识别完成: {len(text)} 字符, {len(text.split(chr(10)))} 行")
    return text


def recognize_image_base64(image_base64: str, use_preprocess: bool = ENABLE_PREPROCESS) -> str:
    """
    识别 Base64 编码的图片中的文本。

    Args:
        image_base64: Base64 编码字符串（可含 data:image/xxx;base64, 前缀）
        use_preprocess: 是否启用图像预处理

    Returns:
        识别的纯文本
    """
    # 去除 data URL 前缀
    if ',' in image_base64 and image_base64.startswith('data:'):
        image_base64 = image_base64.split(',', 1)[1]

    image_bytes = base64.b64decode(image_base64)
    return recognize_image(image_bytes, use_preprocess)


def get_ocr_status() -> Dict[str, Any]:
    """
    检查 OCR 服务状态。
    Returns:
        {
            'available': bool,
            'model_loaded': bool,
            'version': str or None,
            'preprocessing': bool,
        }
    """
    result = {
        'available': False,
        'model_loaded': False,
        'version': None,
        'preprocessing': ENABLE_PREPROCESS,
        'confidence_threshold': OCR_CONFIDENCE_THRESHOLD,
    }

    try:
        import paddleocr
        result['version'] = getattr(paddleocr, '__version__', 'unknown')
        result['available'] = True
    except ImportError:
        return result

    try:
        _get_or_create_ocr()
        result['model_loaded'] = True
    except Exception as e:
        result['error'] = str(e)

    # 检查 opencv 是否可用
    try:
        import cv2
        result['opencv_available'] = True
    except ImportError:
        result['opencv_available'] = False

    return result
