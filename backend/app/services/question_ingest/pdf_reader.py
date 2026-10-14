"""pdf 读取 — pdfplumber 主干（文本层 + [IMAGE:x_y] 占位符 + 原位表格行）→ MinerU → PaddleOCR 三级回退。

I-6：pure move 自 backend/app/api/v1/question_import.py（任务 41）。
六个函数体与全部相关常量（_PDF_* / _norm_for_dedup / _last_extract_engine）
逐字节原样搬迁，**零逻辑变更**；question_import.py 改为从本模块导入并 re-export，
外部调用方（gate_l1/l2、verify_* 脚本、tests、image_service）零改动。

红线（742 题 100% 匹配依赖，只可搬不可改）：
  · pdfplumber 主干含 2026-09-29「全文翻倍」修复、J-2-1 原位表格行、J-2-3 图片前瞻归属
  · _PDF_QN_LINE 的小数排除（任务 35/补修）已含在搬迁文本内
  · 函数内 __file__ 相对推导（图片暂存目录 3 级、ocr-worker cwd 4 级）在本模块
    深度下解析结果与原位置完全一致：
    app/api/v1 与 app/services/question_ingest 同为 app 下 2 级 / 3 级
"""
import io
import json
import logging
import os
import re
import uuid
from typing import Dict, Optional

from fastapi import HTTPException

from ...core.config import settings
from .. import text_cache
from ..mineru_service import (
    extract_text_sync as mineru_extract_text_sync,
    is_enabled as mineru_is_enabled,
)

logger = logging.getLogger(__name__)

def _norm_for_dedup(s: str) -> str:
    """归一化文本用于重复比对：去除所有空白与表格分隔符。

    pdfplumber 的 ``extract_text()`` 与 ``extract_tables()`` 对同一批内容的
    呈现不同：前者用换行分隔单元格，后者用 ``' | '`` 连接。直接字符串比较
    必然漏判，因此两侧统一去空白与分隔符后再比对，才能稳定识别「已存在」的内容。
    """
    return re.sub(r'[\s|\u3000]+', '', s or '')


# PDF 图片占位符提取所需常量（2026-09-29）
# 行首题号：用于判定图片归属的哪一道题
_PDF_QN_LINE = re.compile(r'^\s*(\d{1,3})\s*[．.、](?!\d)')
# 页面噪声行：页眉/页脚/水印，占位符绝不能挂在这些行上（会被清洗整行删掉）
_PDF_NOISE_LINE = re.compile(
    r'^\s*第\s*\d+\s*页'                       # 页脚/页码
    r'|^[\s\w\u4e00-\u9fff]{0,6}(?:小绵羊上岸店|上岸店)'  # 水印
    r'|^\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\S*国家公务员'  # 页眉标题
)
# PDF 色彩空间 → (PIL mode, 通道数)
# 键为「去非字母数字后小写」的形式：pdfminer 返回的名称形如 /'DeviceRGB'
# （斜杠后带 PDF 名引号），直接 strip("'") 剥不掉内层引号，必须先清洗再查表。
_PDF_CS_SPEC = {
    'devicergb': ('RGB', 3), 'rgb': ('RGB', 3),
    'devicegray': ('L', 1), 'g': ('L', 1), 'calgray': ('L', 1),
    'devicecmyk': ('CMYK', 4), 'cmyk': ('CMYK', 4),
}
# 图片最小边长：过滤碎片。实测行测答案文档公式符号图（逻辑符号→∨∧、分式、根号）
# srcsize 高度仅 9~39px（如 18x9、54x15、100x34），40px 阈值会误过滤 94% 的答案解析图。
# 故下调到 8（语料最小边 min=8），保留公式符号；真碎片由 image_filters 无关图过滤兜底。
_PDF_MIN_IMG_DIM = 8
#
# ── 任务 13：以下全部为**新增行**，上方两行保持字节不变 ──────────────
# （红线要求 `git diff -U0` 的删除行数为 0。首版曾把上一行注释覆写成
#   多行说明，diff 出现 1 个 `-` 行，已还原为纯追加。）
#
# 行测语料实测（scripts/probe_xingce_image_stats.py + probe_xingce_image_geom.py，
# 85 份题本 / 3125 张可解码图 / 1010 个含图页）：
#   最小边分布  min=8  p10=15  p25=17  median=132  p75=282  p90=393  max=700
#   总像素分布  p50=28,320  p90=228,520  p99=343,470  max=517,300 (0.5MP)
# 呈明显**双峰**：约 1335 张是 max<100 的近方碎片（15x33 / 22x33 / 9x18…），
# 1681 张真实内容图全部 min边 >= 100。
#
# 关键复核：`min<40 且 总像素>=2万` 的图 **0 张** —— 即不存在「一边小但像素很多」
# 的合法宽扁图表，故只看最小边长不会误杀图表；20-29 区间 398 张里 max>=100 的
# 仅 16 张，且全是 137x22 细线条（总像素 3014，属装饰分隔线而非图表）。
# 因此 40 恰好切在两峰之间的空谷，**维持 40 不下调**（下调到 20 会引入 398 张碎片）。
#
# 图片总像素上限（GAP-13 解压炸弹防护）。原实现只滤最小边、无上限，
# 恶意 PDF 只需声明 srcsize=100000x100000 即可让 stream.get_data()
# 试图分配 3e10 字节拖垮进程。实测行测最大仅 0.5MP，故 4MP 有约 7.7 倍余量，
# 真实语料 0 张超限；与 MAX_IMAGE_SIZE（落盘字节上限）构成两道独立防线。
_PDF_MAX_IMG_PIXELS = 4_000_000
_last_extract_engine = 'unknown'  # ★ 记录最近一次文本提取使用的引擎
_last_ocr_failure = ''            # ★ 记录最近一次 OCR 失败的具体原因（供前端可操作提示）


def _pdf_image_to_png(im) -> Optional[bytes]:
    """把 PDF 内嵌图片的原始像素封装为 PNG 字节；不支持/异常返回 None。

    pdfplumber 的 ``stream.get_data()`` 返回的是**未编码**的原始采样值
    （实测 DeviceRGB 8bit 图像恰好等于 w*h*3 字节），并非可直接保存的图片文件，
    因此必须按色彩空间与位深还原成像素数组后再由 PIL 编码为 PNG。
    ``get_rawdata()`` 仅对 JPEG(DCTDecode) 流有效，此处不可用。
    """
    try:
        cs = im.get('colorspace')
        if not cs:
            return None
        # pdfminer 返回形如 /'DeviceRGB'（斜杠 + PDF 名引号），先清洗为 devicergb 再查表
        key = re.sub(r'[^A-Za-z0-9]', '', str(cs[0])).lower()
        spec = _PDF_CS_SPEC.get(key)
        if not spec:
            logger.debug(f"[pdf-images] 暂不支持的色彩空间 {cs[0]!r} -> {key}，跳过该图")
            return None
        if im.get('bits') != 8:
            logger.debug(f"[pdf-images] 暂不支持的位深 {im.get('bits')}，跳过该图")
            return None
        srcsize = im.get('srcsize') or (0, 0)
        sw, sh = int(srcsize[0]), int(srcsize[1])
        if sw < _PDF_MIN_IMG_DIM or sh < _PDF_MIN_IMG_DIM:
            logger.debug(f"[pdf-images] 碎片图 {sw}x{sh} 低于 {_PDF_MIN_IMG_DIM}px，跳过")
            return None
        # GAP-13 解压炸弹防护：srcsize 是 PDF 自述尺寸，恶意文件可任意虚报。
        # 必须在 get_data() **之前**判定，否则 stream 已被解压到内存。
        total_px = sw * sh
        if total_px > _PDF_MAX_IMG_PIXELS:
            logger.warning(
                f"[pdf-images] 超大图 {sw}x{sh}={total_px}px 超过上限 "
                f"{_PDF_MAX_IMG_PIXELS}px，跳过（防解压炸弹）")
            return None
        mode, nch = spec
        data = im['stream'].get_data()
        if len(data) != sw * sh * nch:
            logger.debug(f"[pdf-images] 数据长度 {len(data)} != {sw}x{sh}x{nch}，跳过该图")
            return None
        from PIL import Image
        buf = io.BytesIO()
        img = Image.frombytes(mode, (sw, sh), data)
        # A 修复：SMask 软掩码合成。公式图（分数式等）是「透明底+黑字」，
        # 主数据全黑、可见像素由 /SMask 掩码流定义；不合成则整图全黑。
        # 掩码从底层 pdfminer PDFStream 的原始字典取（pdfplumber 剥离了 smask）。
        try:
            _smask_obj = None
            _attrs = getattr(im['stream'], 'attrs', None)
            if _attrs:
                _smask_ref = _attrs.get('SMask')
                if _smask_ref is not None:
                    _smask_obj = (_smask_ref.resolve()
                                  if hasattr(_smask_ref, 'resolve') else _smask_ref)
            if _smask_obj is not None and hasattr(_smask_obj, 'get_data'):
                _sdata = _smask_obj.get_data()
                if _sdata and len(_sdata) >= sw * sh:
                    _mask = Image.frombytes('L', (sw, sh), _sdata[:sw * sh])
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    _canvas = Image.new('RGB', (sw, sh), 'white')
                    _canvas.paste(img, (0, 0), _mask)
                    img = _canvas
        except Exception as _sme:  # noqa: BLE001 — 掩码合成失败用原图
            logger.debug(f"[pdf-images] SMask 合成失败: {_sme}")
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as e:
        logger.debug(f"[pdf-images] 图片转换失败: {type(e).__name__}: {e}")
        return None


def _extract_text_from_pdf(buf: bytes, progress_cb=None) -> str:
    """从 PDF 提取纯文本（优先使用 pdfplumber，支持表格提取；扫描件自动OCR）

    ``progress_cb(page_no, total_pages, images_on_page)`` 为可选进度回调，
    在**每页处理完后**同步触发，用于让前端展示真实递增的进度而非定时器伪造。
    回调内部异常会被吞掉——进度只是观测手段，绝不能因此中断解析。

    提取文本缓存（P0 提速）：本函数是 buf → text 的**纯函数**（无落盘等副作用），
    因此可按文件内容 md5 缓存提取结果。实测扫描件 OCR 需 260s/份，
    而解析仅 0.1s —— 重复导入的耗时 99.6% 在此，缓存命中降到 ~0.02s。

    只缓存本函数、不缓存 _extract_text_from_docx：后者除文本外还会把图片落盘，
    且文件名带每次运行唯一的 _session_id；缓存其文本会让 IMAGE 占位标记与
    实际落盘文件解耦。且 docx 提取仅 0.1~0.35s，缓存收益近零、风险非零。
    """
    import io

    # ===== 提取文本缓存：命中即返回（纯加速层，异常已在 text_cache 内降级） =====
    _cached = text_cache.get(buf)
    if _cached is not None:
        if progress_cb:
            # 缓存命中：无逐页过程可报，直接告知「文本提取已完成」
            try:
                progress_cb(1, 1, 0)
            except Exception:  # noqa: BLE001
                pass
        return _cached

    def _finish(text: str, engine: str) -> str:
        """统一出口：成功产出才写缓存（空结果不写，避免固化偶发失败）"""
        text_cache.put(buf, text, {'engine': engine})
        global _last_extract_engine
        _last_extract_engine = engine
        return text

    # 优先使用 pdfplumber（更好的中文支持和表格提取）
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(buf)) as pdf:
            parts = []
            # ===== PDF 图片占位符（2026-09-29 新增）=====
            # 与 DOCX 产出同构的 [IMAGE:{hex}_{题号}_{序号}] 占位符，并暂存为
            # {key}.png 到 static/questions/，从而 100% 复用既有下游
            # _extract_and_save_images（压缩落盘 + question_content/options 回填）。
            session_hex = uuid.uuid4().hex[:8]  # 8 位十六进制，匹配 marker_pattern 的 [a-f0-9]+
            stage_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'static', 'questions')
            try:
                os.makedirs(stage_dir, exist_ok=True)
            except Exception as e:
                logger.warning(f"[pdf-images] 无法创建暂存目录，跳过图片提取: {e}")
                stage_dir = ''
            img_seq: Dict[int, int] = {}
            cur_qn = 0   # 跨页延续的当前题号（图片可能落在题干跨页的续页上）

            for page_no, page in enumerate(pdf.pages, 1):
                # --- 取带坐标的行：既能按垂直位置定位题号，也便于按行索引插入占位符
                try:
                    tlines = page.extract_text_lines() or []
                except Exception:
                    tlines = []
                if tlines:
                    page_lines = [str(l.get('text', '')) for l in tlines]
                    line_tops = [float(l.get('top', 0.0) or 0.0) for l in tlines]
                else:
                    page_lines = (page.extract_text() or '').split('\n')
                    line_tops = [0.0] * len(page_lines)

                # --- 逐行建立「该行属于哪道题」映射 ---
                # 必须对每一页都执行（而非只在有图的页里做）：题号可能出现在
                # 没有图片的页上，而下一��的图片却属于那道跨页的题。
                # 实测漏修此点会丢掉第 6 页的两张图（其题号 40 在第 5 页）。
                carry_in_qn = cur_qn
                qn_at: Dict[int, int] = {}
                run_qn = carry_in_qn
                for i, lp in enumerate(page_lines):
                    m = _PDF_QN_LINE.match(lp)
                    if m:
                        run_qn = int(m.group(1))
                    qn_at[i] = run_qn
                cur_qn = run_qn      # 供下一页延续

                # --- 图片 → 占位符 ---
                # 归属题号 = 图片上方最近一行的所属题号。
                # 关键：占位符绝不能挂在页眉/水印/页脚行上——那些行会被
                # ContentCleaner 判为噪声整行删除，占位符随之消失导致图片静默丢失。
                for im in (getattr(page, 'images', None) or []):
                    if not stage_dir:
                        break
                    try:
                        top = float(im.get('top', 0.0) or 0.0)
                    except Exception:
                        top = 0.0
                    anchor = -1
                    qn = 0
                    for i, lt in enumerate(line_tops):
                        if lt <= top:
                            anchor = i
                            qn = qn_at.get(i, 0)
                    if qn <= 0:
                        # ★ J-2-3 修复：图片上方无题号 → 材料块图片（资料分析
                        #   「材料在前、题目在后」版式），归属后继第一个题号；
                        #   前瞻无后继题号时才回落 carry_in_qn（跨页延续）。
                        next_qn = None
                        for lp in page_lines[anchor + 1:]:
                            m = _PDF_QN_LINE.match(lp.strip())
                            if m:
                                next_qn = int(m.group(1))
                                break
                        qn = next_qn if next_qn is not None else (carry_in_qn or cur_qn)
                    if anchor < 0 or qn <= 0:
                        continue
                    # 上方最近一行是噪声行（页眉/水印/页脚）时，改挂到首个非噪声行
                    if _PDF_NOISE_LINE.match(page_lines[anchor].strip()):
                        for i, lp in enumerate(page_lines):
                            s = lp.strip()
                            if not s or _PDF_NOISE_LINE.match(s):
                                continue
                            anchor = i
                            break
                    blob = _pdf_image_to_png(im)
                    if not blob:
                        continue
                    seq = img_seq.get(qn, 0)
                    img_seq[qn] = seq + 1
                    key = f'{session_hex}_{qn}_{seq}'
                    try:
                        with open(os.path.join(stage_dir, f'{key}.png'), 'wb') as fh:
                            fh.write(blob)
                    except Exception as e:
                        logger.warning(f"[pdf-images] 暂存 {key} 失败: {e}")
                        continue
                    page_lines[anchor] = page_lines[anchor] + f' [IMAGE:{key}]'

                # 去重基准必须用 extract_text() 的原始结果：extract_text_lines()
                # 的行拼接与之存在细微空白差异，若拿它做 page_norm 会让下方的
                # 「表格行是否已在文本中」判定失效，重复内容回流（实测 +3300 字符、
                # 题号 70→84）。行坐标只用于插占位符，不参与去重。
                text_raw = page.extract_text()
                page_norm = _norm_for_dedup(text_raw) if text_raw else None
                # 提取表格
                # 2026-09-29 修复（致命缺陷）：当 pdfplumber 因版面把本页判定为表格时，
                # extract_tables() 会把已由 extract_text() 输出的同一批单元格文本
                # **再输出一遍**，导致全文精确翻倍。实测目标 PDF：14,436 → 28,873 字符、
                # 行首题号 70 → 140。修复：仅在文本层为空时全量采纳表格行；否则只补充
                # 「本页文本中确实不存在」的单元格行。
                # ★ J-2-1 修复：用 find_tables()（extract_tables 的底层，表格检测同源）
                #   获取 Table 对象的 bbox 坐标，把表格行**原位插入** page_lines，
                #   不再 parts.append 页尾追加——否则资料分析材料表内容会脱离所属材料块。
                tables = page.find_tables()
                for table in tables:
                    try:
                        tbl_top = float(table.bbox[1])  # bbox = (x0, top, x1, bottom)
                    except Exception:
                        tbl_top = None
                    for row in table.extract():
                        if not row:
                            continue
                        row_texts = [str(c) if c else '' for c in row]
                        row_text = ' | '.join(t for t in row_texts if t)
                        if not row_text:
                            continue
                        if page_norm and _norm_for_dedup(row_text) in page_norm:
                            # 本页文本已包含该单元格内容，跳过以消除重复
                            continue
                        if tbl_top is None:
                            parts.append(row_text)  # 无坐标兜底：保持原页尾追加
                            continue
                        # 按 top 坐标把表格行插入到 page_lines 的正确位置
                        insert_idx = len(page_lines)
                        for i, lt in enumerate(line_tops):
                            if lt <= tbl_top:
                                insert_idx = i + 1
                        page_lines.insert(insert_idx, row_text)
                        line_tops.insert(insert_idx, tbl_top)

                text = '\n'.join(page_lines)   # 含图片占位符 + 原位表格行的最终页文本
                if text:
                    parts.append(text)

                # 逐页上报真实进度：长文档（扫描件 OCR 可达 260s+）时前端能看到
                # 进度平滑爬升，而不是卡在某个数字再突然跳到 100。
                if progress_cb:
                    try:
                        progress_cb(page_no, len(pdf.pages),
                                    len(getattr(page, 'images', None) or []))
                    except Exception:  # noqa: BLE001
                        pass

            if parts:
                return _finish('\n'.join(parts), 'pdfplumber')
    except ImportError:
        pass

    # 回退到 PyPDF2
    try:
        import PyPDF2
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器缺少 PDF 解析库，请安装: pip install pdfplumber 或 PyPDF2")

    try:
        reader = PyPDF2.PdfReader(io.BytesIO(buf))
        text = ''
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + '\n'
        result = text.strip()
        if result:
            return _finish(result, 'pypdf2')
    except Exception as e:
        logger.warning(f"PyPDF2 解析失败: {e}")

    # === OCR 回退：检测到扫描件PDF（无文本层）→ 三级回退链 ===
    logger.info("PDF文本提取为空，尝试OCR识别扫描件...")

    # 第一级: MinerU 高精度版面解析（独立venv子进程，GPU加速）
    # 失败契约: extract_text_sync 任何失败返回 None → 继续第二级，绝不阻断
    if mineru_is_enabled():
        mineru_text = mineru_extract_text_sync(buf)
        if mineru_text:
            logger.info(f"[mineru] 解析成功: {len(mineru_text)}字符，采用MinerU结果")
            return _finish(mineru_text, 'mineru')
        _last_ocr_failure = 'MinerU 已启用但未产出有效文本（详见后端日志 [mineru]）'
        logger.warning("[mineru] 未返回有效文本，回退PaddleOCR逐页路径")
    else:
        _last_ocr_failure = 'MinerU 未启用或解释器路径无效（MINERU_ENABLED / MINERU_PYTHON）'

    # 第二级(保底): 原有 PyPDF2图片提取 + PaddleOCR逐页识别 —— 保持原逻辑一字不改
    ocr_text = _extract_text_from_scanned_pdf(buf)
    if ocr_text:
        logger.info(f"扫描件OCR成功: {len(ocr_text)} 字符")
        return _finish(ocr_text, 'paddleocr')

    # 全部失败：不写缓存（空结果会把偶发失败固化成永久失败）
    return ''


def _extract_text_from_scanned_pdf(buf: bytes) -> str:
    """
    从扫描件PDF中提取图片并OCR识别文字（P1.1 子进程隔离版）。

    架构：主进程只做图片提取+预处理（纯 PIL/cv2，无崩溃风险）；
    OCR 在独立子进程执行（python -m app.services.ocr_worker）——
    子进程崩溃/超时被强杀，主进程返回明确错误，绝不拖死后端。
    （根因：本机 Python 3.13 超出 PaddleOCR 官方支持，进程内 OCR 会硬崩）
    """
    import io as _io
    import tempfile
    import subprocess
    import sys as _sys
    import shutil as _shutil
    import glob as _glob

    try:
        import PyPDF2
        from PIL import Image as PILImage
    except ImportError:
        logger.warning("PyPDF2/Pillow 未安装，无法处理扫描件PDF")
        return ''

    tmpdir = None
    try:
        reader = PyPDF2.PdfReader(_io.BytesIO(buf))
        total_pages = len(reader.pages)
        if total_pages == 0:
            return ''

        # 页数上限（可配置）：覆盖主要答案内容，超限部分明确提示
        max_pages = min(total_pages, settings.OCR_MAX_PAGES)
        logger.info(f"扫描件PDF: {total_pages} 页，OCR处理前 {max_pages} 页"
                    f"（子进程隔离，超时{settings.OCR_SUBPROCESS_TIMEOUT}秒）")

        # 1) 主进程：提取页面图片 + 预处理（放大+CLAHE），落盘临时目录
        tmpdir = tempfile.mkdtemp(prefix='ocr_pages_')
        saved = 0
        for page_idx in range(max_pages):
            page = reader.pages[page_idx]
            page_images = _extract_images_from_pdf_page(page, page_idx)
            if not page_images:
                continue
            for k, img_data in enumerate(page_images[:3]):  # 每页最多3张
                try:
                    pil_img = PILImage.open(_io.BytesIO(img_data))
                    if pil_img.mode != 'RGB':
                        pil_img = pil_img.convert('RGB')
                    # 增强预处理（限宽 + 放大 + CLAHE），失败用原图
                    # 限宽 2600px：超大扫描图会导致检测模型显存/内存分配失败
                    try:
                        import cv2
                        import numpy as np
                        arr = np.array(pil_img)
                        h, w = arr.shape[:2]
                        if w > 2600:
                            nh = int(h * 2600 / w)
                            arr = cv2.resize(arr, (2600, nh),
                                             interpolation=cv2.INTER_AREA)
                            h, w = 2600, nh
                        if w < 1000:
                            arr = cv2.resize(arr, (w * 2, h * 2),
                                             interpolation=cv2.INTER_CUBIC)
                        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
                        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                        pil_img = PILImage.fromarray(clahe.apply(gray))
                    except Exception:
                        pass
                    out = os.path.join(
                        tmpdir, f'page_{page_idx+1:03d}_{k}.jpg')
                    pil_img.save(out, format='JPEG', quality=90)
                    saved += 1
                except Exception as e:
                    logger.warning(f"第{page_idx+1}页图片预处理失败: {e}")

        if saved == 0:
            _last_ocr_failure = '扫描件无可提取图片（页面内容为空或图片格式不支持）'
            logger.info("扫描件PDF未提取到可OCR图片")
            return ''

        # 2) 子进程：OCR（崩溃/超时强杀，主进程无恙）
        out_json = os.path.join(tmpdir, 'result.json')
        # OCR 解释器：优先独立 ≤3.12 环境（settings.OCR_PYTHON），主进程 3.13 下
        # Paddle 推理会原生崩溃（0xC0000005），故默认指向独立 venv
        ocr_python = (settings.OCR_PYTHON or '').strip() or _sys.executable
        if not os.path.exists(ocr_python):
            logger.warning(f"[ocr-worker] OCR_PYTHON 不存在: {ocr_python}，"
                           "回退主解释器（3.13 下可能失败）")
            ocr_python = _sys.executable
        cmd = [ocr_python, '-m', 'app.services.ocr_worker', tmpdir, out_json]
        # cwd 必须是 backend/ 根（app 包的父目录）：本文件在 backend/app/api/v1/，向上4层
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        logger.info(f"[ocr-worker] 启动子进程OCR（{saved} 张图, python={ocr_python}）")
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=settings.OCR_SUBPROCESS_TIMEOUT,
            cwd=backend_root,
        )
        if proc.returncode != 0:
            _last_ocr_failure = 'PaddleOCR 子进程异常退出（环境不兼容或模型缺失）'
            logger.error(f"[ocr-worker] 子进程异常退出 code={proc.returncode}: "
                         f"{(proc.stderr or '')[-300:]}")
            return ''
        with open(out_json, encoding='utf-8') as f:
            result = json.load(f)
        if not result.get('ok'):
            _last_ocr_failure = f"PaddleOCR 未识别出文字: {result.get('error') or '未知原因'}"
            logger.warning(f"[ocr-worker] 未得到文本: {result.get('error')}")
            return ''
        logger.info(f"[ocr-worker] 完成: 页OK={result.get('pages_ok')} "
                    f"页失败={result.get('pages_fail')} 字符={len(result.get('text',''))}")
        return result.get('text', '')

    except subprocess.TimeoutExpired:
        _last_ocr_failure = f'OCR 超时（>{settings.OCR_SUBPROCESS_TIMEOUT}s），请拆分后导入或启用 MinerU'
        logger.error(f"[ocr-worker] OCR超时（>{settings.OCR_SUBPROCESS_TIMEOUT}s），"
                     "已终止。建议：该PDF为高清扫描件，请拆分后导入或联系管理员启用MinerU通道")
        return ''
    except Exception as e:
        _last_ocr_failure = f'扫描件处理失败: {type(e).__name__}'
        logger.error(f"扫描件PDF处理失败: {e}", exc_info=True)
        return ''
    finally:
        if tmpdir and os.path.exists(tmpdir):
            try:
                _shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def _extract_images_from_pdf_page(page, page_idx: int) -> list:
    """
    从PDF页面中提取嵌入的图片数据。
    使用 PyPDF2 的 low-level API 遍历 XObject 资源。
    返回图片字节列表。
    """
    images = []

    try:
        # 获取页面资源
        resources = None
        if '/Resources' in page:
            resources = page['/Resources']
        elif hasattr(page, 'resources'):
            resources = page.resources

        if resources is None:
            return images

        # 尝试访问 XObject
        xobject = None
        try:
            # PyPDF2 方式1: 字典访问
            if '/XObject' in resources:
                xobject = resources['/XObject']
        except Exception:
            pass

        if xobject is None:
            try:
                # PyPDF2 方式2: get_object
                xobj_ref = resources.get('/XObject')
                if xobj_ref:
                    xobject = xobj_ref.get_object()
            except Exception:
                pass

        if xobject is None:
            return images

        # 遍历XObject中的每个对象
        for obj_name in xobject:
            try:
                xobj = xobject[obj_name]
                if xobj is None:
                    continue

                # 获取实际对象
                if hasattr(xobj, 'get_object'):
                    xobj = xobj.get_object()

                # 检查是否为图片
                subtype = xobj.get('/Subtype', '') if isinstance(xobj, dict) else ''
                if subtype == '/Image':
                    img_data = _decode_pdf_image(xobj)
                    if img_data and len(img_data) > 100:  # 过滤太小的图片
                        images.append(img_data)
                        logger.debug(f"第{page_idx+1}页提取图片: {obj_name}, {len(img_data)} bytes")
            except Exception as e:
                logger.debug(f"跳过XObject {obj_name}: {e}")
                continue

    except Exception as e:
        logger.warning(f"提取PDF页面图片失败: {e}")

    return images


def _decode_pdf_image(xobj: dict) -> Optional[bytes]:
    """
    解码PDF图片对象为PNG字节。
    处理 FlateDecode、DCTDecode(JPEG) 等滤镜。
    PyPDF2的get_data()已自动解压FlateDecode。
    """
    import zlib
    import io as _io

    try:
        width = xobj.get('/Width', 0)
        height = xobj.get('/Height', 0)
        if width < 20 or height < 20:
            return None

        filter_type = xobj.get('/Filter', None)
        bits = xobj.get('/BitsPerComponent', 8)
        color_space = xobj.get('/ColorSpace', '')

        # PyPDF2's get_data() already decompresses FlateDecode
        raw_data = None
        try:
            raw_data = xobj.get_data()
        except Exception:
            try:
                raw_data = xobj._data
            except Exception:
                pass

        if raw_data is None or len(raw_data) == 0:
            return None

        # JPEG (DCTDecode) — return as-is
        if filter_type == '/DCTDecode':
            return raw_data

        # For raw pixel data (FlateDecode already decompressed)
        try:
            from PIL import Image as PILImage

            if color_space == '/DeviceRGB':
                mode = 'RGB'
                expected = width * height * 3
            elif color_space == '/DeviceGray':
                mode = 'L'
                expected = width * height
            else:
                mode = 'RGB'
                expected = width * height * 3

            if len(raw_data) >= expected:
                img = PILImage.frombytes(mode, (width, height), raw_data[:expected])
                # A 修复：SMask 软掩码合成。公式图（分数式等）是「透明底+黑字」，
                # 主数据是全黑文字色、可见像素由 /SMask 掩码流定义。不合成则整图
                # 全黑（前端深色背景显示黑块）。合成到白底 = 与 PDF 原文一致。
                _smask_ref = xobj.get('/SMask')
                if _smask_ref is not None:
                    try:
                        _smask_obj = (_smask_ref.get_object()
                                      if hasattr(_smask_ref, 'get_object') else _smask_ref)
                        _mask_data = _smask_obj.get_data() if hasattr(_smask_obj, 'get_data') else None
                        if _mask_data and len(_mask_data) >= width * height:
                            _mask = PILImage.frombytes(
                                'L', (width, height), _mask_data[:width * height])
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            _canvas = PILImage.new('RGB', (width, height), 'white')
                            _canvas.paste(img, (0, 0), _mask)
                            img = _canvas
                    except Exception as _sme:  # noqa: BLE001 — 掩码合成失败用原图
                        logger.debug(f"[pdf-images] SMask 合成失败: {_sme}")
                buf = _io.BytesIO()
                img.save(buf, format='PNG')
                return buf.getvalue()
            else:
                # Data too small — try as raw compressed
                if len(raw_data) > 500:
                    buf = _io.BytesIO()
                    buf.write(raw_data)
                    buf.seek(0)
                    try:
                        img = PILImage.open(buf)
                        out = _io.BytesIO()
                        img.save(out, format='PNG')
                        return out.getvalue()
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"PDF图片像素转换失败: {e}")

    except Exception as e:
        logger.debug(f"PDF图片解码失败: {e}")

    return None


def _pdf_has_images_only(buf: bytes) -> bool:
    """快速检测PDF是否为纯扫描件（仅有图片、无文本层）"""
    try:
        import PyPDF2, io as _io
        reader = PyPDF2.PdfReader(_io.BytesIO(buf))
        if len(reader.pages) == 0:
            return False
        page = reader.pages[0]
        resources = None
        if '/Resources' in page:
            resources = page['/Resources']
        if resources is None:
            return False
        has_images = '/XObject' in resources
        # 快速检测：尝试提取文本
        text_sample = page.extract_text() or ''
        has_text = len(text_sample.strip()) > 20
        return has_images and not has_text
    except Exception:
        return False
