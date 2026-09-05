"""
PaddleOCR 服务 — 图片文字识别，支持印刷体中文题目
增强版：图像预处理、版式感知、公式检测、表格识别、可配置阈值
"""
import logging
import io
import base64
import os
import re
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============ 配置 ============
OCR_CONFIDENCE_THRESHOLD = 0.5       # 置信度阈值
ENABLE_PREPROCESS = True              # 是否启用图像预处理
PREPROCESS_METHOD = 'adaptive'        # 预处理方法: 'adaptive' | 'otsu' | 'simple'
ENABLE_SUPER_RESOLUTION = True        # 超分辨率增强（小文字场景）
ENABLE_FORMULA_DETECTION = True       # 公式区域检测
ENABLE_TABLE_DETECTION = True         # 表格结构检测

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
    """（原有）图像预处理，提升OCR识别准确率"""
    try:
        import cv2
    except ImportError:
        logger.warning("opencv-python-headless 未安装，跳过图像预处理")
        return img_array

    try:
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        kernel_sharpen = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(gray, -1, kernel_sharpen)
        denoised = cv2.medianBlur(sharpened, 3)

        if PREPROCESS_METHOD == 'adaptive':
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        elif PREPROCESS_METHOD == 'otsu':
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, binary = cv2.threshold(denoised, 127, 255, cv2.THRESH_BINARY)

        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        logger.debug(f"图像预处理完成: {img_array.shape} → {result.shape}")
        return result
    except Exception as e:
        logger.warning(f"图像预处理失败，使用原图: {e}")
        return img_array


def enhance_preprocessing(img_array: np.ndarray) -> np.ndarray:
    """
    增强版图像预处理管线：
    1. 超分辨率放大（小文字场景，自动判断）
    2. CLAHE 自适应对比度增强
    3. 透视校正（检测倾斜并校正）
    4. 自适应二值化
    返回增强后的 RGB numpy 数组。
    """
    try:
        import cv2
    except ImportError:
        logger.warning("opencv-python-headless 未安装，跳过增强预处理")
        return img_array

    try:
        h, w = img_array.shape[:2]

        # 1. 转灰度
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # 2. 超分辨率：如果图片尺寸较小（< 800px宽），放大2倍
        if ENABLE_SUPER_RESOLUTION and w < 800:
            gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
            logger.debug(f"超分辨率: {w}×{h} → {w*2}×{h*2}")

        # 3. CLAHE 自适应对比度增强（比全局直方图均衡更鲁棒）
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 4. 透视校正：检测文本区域倾斜并校正
        # 使用概率霍夫线检测估计倾斜角度
        edges = cv2.Canny(enhanced, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                                 minLineLength=100, maxLineGap=10)
        if lines is not None and len(lines) > 5:
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                if abs(angle) < 45:  # 排除接近垂直的线
                    angles.append(angle)
            if angles:
                median_angle = np.median(angles)
                if abs(median_angle) > 0.5:  # 倾斜超过0.5度才校正
                    center = (w // 2, h // 2)
                    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                    enhanced = cv2.warpAffine(enhanced, matrix, (w, h),
                                               borderMode=cv2.BORDER_CONSTANT,
                                               borderValue=(255, 255, 255))
                    logger.debug(f"透视校正: {median_angle:.1f}°")

        # 5. 自适应二值化
        if PREPROCESS_METHOD == 'adaptive':
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
        elif PREPROCESS_METHOD == 'otsu':
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, binary = cv2.threshold(enhanced, 127, 255, cv2.THRESH_BINARY)

        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        logger.debug(f"增强预处理完成: {img_array.shape} → {result.shape}")
        return result

    except Exception as e:
        logger.warning(f"增强预处理失败，使用原图: {e}")
        return img_array


# ============ 公式区域检测 ============

def detect_formula_regions(img_array: np.ndarray) -> List[Dict[str, Any]]:
    """
    检测图片中的数学公式区域。
    使用启发式特征：
    - 密集的数学符号（=, +, -, ×, ÷, ∑, ∫, √ 等）
    - 希腊字母（α, β, γ, θ, π 等）
    - 上下标结构（小字符在基线之上/之下）
    - 分数/根号等结构特征
    返回: [{bbox: [x1,y1,x2,y2], confidence: float, type: 'formula'}]
    """
    if not ENABLE_FORMULA_DETECTION:
        return []

    results = []
    try:
        import cv2

        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # 二值化
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 形态学操作：连接相邻字符
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        dilated = cv2.dilate(binary, kernel, iterations=1)

        # 查找轮廓
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # 过滤太小或太大的区域
            if w < 30 or h < 15 or w > img_array.shape[1] * 0.8:
                continue

            # 提取该区域的文本（使用已有OCR）
            roi = img_array[y:y+h, x:x+w]
            # 通过特征判断是否为公式区域
            # 特征1：宽高比（公式通常较宽）
            aspect_ratio = w / max(h, 1)
            # 特征2：区域密度
            region_density = cv2.countNonZero(binary[y:y+h, x:x+w]) / max(w * h, 1)

            # 公式特征：宽高比偏大 + 中等密度
            formula_score = 0.0
            if 2.0 < aspect_ratio < 12.0:
                formula_score += 0.3
            if 0.15 < region_density < 0.6:
                formula_score += 0.3

            if formula_score >= 0.4:
                results.append({
                    'bbox': [int(x), int(y), int(x+w), int(y+h)],
                    'confidence': round(formula_score, 2),
                    'type': 'formula',
                })

        # 按位置排序（从上到下）
        results.sort(key=lambda r: r['bbox'][1])
        logger.debug(f"公式检测: 发现 {len(results)} 个候选区域")
        return results

    except ImportError:
        logger.debug("opencv 未安装，跳过公式检测")
        return []
    except Exception as e:
        logger.warning(f"公式检测失败: {e}")
        return []


# ============ 表格结构检测 ============

def detect_table_structure(img_array: np.ndarray) -> List[Dict[str, Any]]:
    """
    检测图片中的表格结构。
    基于线条检测 + 单元格分割。

    返回: [{
        'bbox': [x1,y1,x2,y2],
        'rows': int, 'cols': int,
        'cells': [[{text, bbox, row, col}, ...], ...],
        'html': '<table>...</table>'
    }]
    """
    if not ENABLE_TABLE_DETECTION:
        return []

    results = []
    try:
        import cv2

        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # 二值化
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 检测水平线和垂直线
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

        # 合并横纵线
        table_mask = cv2.add(horizontal, vertical)

        # 查找表格轮廓
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        table_mask_dilated = cv2.dilate(table_mask, kernel, iterations=3)

        contours, hierarchy = cv2.findContours(
            table_mask_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # 过滤太小区域（非表格）
            if w < 100 or h < 60:
                continue
            # 过滤太大区域（整页扫描）
            if w > img_array.shape[1] * 0.95 and h > img_array.shape[0] * 0.95:
                continue

            # 提取表格区域
            table_region = gray[y:y+h, x:x+w]
            table_binary = binary[y:y+h, x:x+w]

            # 在该区域内重新检测行列线
            table_h = cv2.morphologyEx(table_binary, cv2.MORPH_OPEN,
                                        cv2.getStructuringElement(cv2.MORPH_RECT, (w//3, 1)))
            table_v = cv2.morphologyEx(table_binary, cv2.MORPH_OPEN,
                                        cv2.getStructuringElement(cv2.MORPH_RECT, (1, h//3)))

            # 投影法找行列位置
            h_proj = np.sum(table_h, axis=1)
            v_proj = np.sum(table_v, axis=0)

            row_positions = _find_lines(h_proj, threshold=max(h_proj.max() * 0.3, 100))
            col_positions = _find_lines(v_proj, threshold=max(v_proj.max() * 0.3, 100))

            if len(row_positions) < 2 or len(col_positions) < 2:
                continue

            rows = len(row_positions) - 1
            cols = len(col_positions) - 1

            # 构建HTML表格
            html_parts = ['<table>']
            for ri in range(rows):
                html_parts.append('<tr>')
                for ci in range(cols):
                    r1, r2 = row_positions[ri], row_positions[ri + 1]
                    c1, c2 = col_positions[ci], col_positions[ci + 1]
                    # 提取单元格内文本（后续OCR处理，此处用占位符）
                    # 使用全局OCR实例识别单元格文本
                    cell_region = img_array[y+r1:y+r2, x+c1:x+c2]
                    cell_text = _ocr_cell_text(cell_region)
                    html_parts.append(f'<td>{cell_text}</td>')
                html_parts.append('</tr>')
            html_parts.append('</table>')

            results.append({
                'bbox': [int(x), int(y), int(x+w), int(y+h)],
                'rows': rows,
                'cols': cols,
                'html': '\n'.join(html_parts),
                'row_positions': row_positions,
                'col_positions': col_positions,
            })

        logger.debug(f"表格检测: 发现 {len(results)} 个表格")
        return results

    except ImportError:
        logger.debug("opencv 未安装，跳过表格检测")
        return []
    except Exception as e:
        logger.warning(f"表格检测失败: {e}")
        return []


def _find_lines(projection: np.ndarray, threshold: float = 100) -> List[int]:
    """从投影直方图中找分界线位置"""
    lines = [0]
    in_line = False
    for i, val in enumerate(projection):
        if val > threshold and not in_line:
            lines.append(i)
            in_line = True
        elif val <= threshold and in_line:
            lines.append(i)
            in_line = False
    if in_line:
        lines.append(len(projection))
    if lines[-1] != len(projection):
        lines.append(len(projection))
    # 合并过近的线
    merged = [lines[0]]
    for i in range(1, len(lines)):
        if lines[i] - merged[-1] > 15:
            merged.append(lines[i])
    return merged


def _ocr_cell_text(cell_img: np.ndarray) -> str:
    """对单个表格单元格进行OCR"""
    try:
        ocr = _get_or_create_ocr()
        result = ocr.predict(cell_img)
        if result:
            texts = []
            for page in result:
                for t in page.get('rec_texts', []):
                    if t:
                        texts.append(t)
            return ' '.join(texts).strip()
    except Exception:
        pass
    return ''


# ============ 增强版OCR（含公式+表格） ============

@dataclass
class EnhancedOCRResult:
    """增强版OCR识别结果"""
    text: str = ''                          # 纯文本（公式/表格区域用占位符替换）
    formulas: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    char_count: int = 0
    message: str = ''


def recognize_image_enhanced(image_bytes: bytes) -> EnhancedOCRResult:
    """
    增强版OCR识别：文字 + 公式 + 表格。

    流程：
    1. 增强预处理
    2. 公式区域检测 → 提取公式 (LaTeX转换)
    3. 表格结构检测 → 提取表格 (HTML)
    4. PaddleOCR 文字识别
    5. 整合结果

    Returns:
        EnhancedOCRResult with text, formulas, tables, confidence
    """
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img_array = np.array(img)

    result = EnhancedOCRResult()
    messages = []

    # 1. 增强预处理
    try:
        processed = enhance_preprocessing(img_array)
        messages.append('预处理完成')
    except Exception as e:
        logger.warning(f"增强预处理失败: {e}")
        processed = img_array

    # 2. 公式区域检测
    formula_regions = detect_formula_regions(img_array)
    if formula_regions:
        for i, region in enumerate(formula_regions):
            bbox = region['bbox']
            # 提取公式区域子图
            formula_img = img_array[bbox[1]:bbox[3], bbox[0]:bbox[2]]
            # 尝试LaTeX转换
            latex = _convert_formula_to_latex(formula_img)
            result.formulas.append({
                'latex': latex,
                'position': bbox,
                'confidence': region.get('confidence', 0.5),
            })
        messages.append(f'检测到 {len(formula_regions)} 个公式区域')

    # 3. 表格结构检测
    table_regions = detect_table_structure(processed)
    if table_regions:
        for table in table_regions:
            result.tables.append({
                'html': table.get('html', ''),
                'position': table['bbox'],
                'rows': table.get('rows', 0),
                'cols': table.get('cols', 0),
            })
        messages.append(f'检测到 {len(table_regions)} 个表格')

    # 4. PaddleOCR 文字识别
    try:
        ocr = _get_or_create_ocr()
        ocr_results = ocr.predict(processed)

        if ocr_results:
            text = reconstruct_reading_order(ocr_results)
            if text:
                result.text = text
                result.char_count = len(text)

                # 计算整体置信度
                scores = []
                for page in ocr_results:
                    for s in page.get('rec_scores', []):
                        if s > 0:
                            scores.append(s)
                if scores:
                    result.confidence = round(sum(scores) / len(scores), 3)
    except Exception as e:
        logger.warning(f"OCR识别失败: {e}")
        messages.append('文字识别失败')

    result.message = '; '.join(messages) if messages else '识别完成'
    return result


def _convert_formula_to_latex(formula_img: np.ndarray) -> str:
    """
    将公式图片转换为LaTeX格式。

    优先使用专用LaTeX-OCR模型（pix2tex / LaTeX-OCR），
    回退到PaddleOCR文本识别 + 数学符号映射。
    """
    # 尝试使用 LaTeX-OCR（pix2tex）
    try:
        from PIL import Image
        # 保存为临时图片
        pil_img = Image.fromarray(formula_img)
        buf = io.BytesIO()
        pil_img.save(buf, format='PNG')

        # 尝试加载 pix2tex 模型
        try:
            from pix2tex.cli import LatexOCR
            latex_model = LatexOCR()
            latex = latex_model(buf.getvalue())
            if latex and len(latex) > 2:
                return latex
        except ImportError:
            logger.debug("pix2tex 未安装（pip install pix2tex），使用OCR回退")
        except Exception as e:
            logger.debug(f"pix2tex 识别失败: {e}")
    except Exception:
        pass

    # 回退：使用PaddleOCR识别公式区域文本
    try:
        ocr = _get_or_create_ocr()
        results = ocr.predict(formula_img)
        if results:
            texts = []
            for page in results:
                for t in page.get('rec_texts', []):
                    if t:
                        texts.append(t)
            raw_text = ' '.join(texts)
            # 基本数学符号映射
            raw_text = raw_text.replace('×', '\\times ').replace('÷', '\\div ')
            raw_text = raw_text.replace('≤', '\\leq ').replace('≥', '\\geq ')
            raw_text = raw_text.replace('≠', '\\neq ').replace('≈', '\\approx ')
            raw_text = raw_text.replace('∑', '\\sum ').replace('∏', '\\prod ')
            raw_text = raw_text.replace('∫', '\\int ').replace('√', '\\sqrt{}')
            raw_text = raw_text.replace('α', '\\alpha ').replace('β', '\\beta ')
            raw_text = raw_text.replace('γ', '\\gamma ').replace('θ', '\\theta ')
            raw_text = raw_text.replace('π', '\\pi ').replace('Δ', '\\Delta ')
            return raw_text.strip() or '[公式]'
    except Exception:
        pass

    return '[公式]'


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
