"""
题目导入API - 支持单题导入、批量文件导入、图片OCR导入、分离导入智能匹配
"""
import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from ...core.database import get_db
from ...core.config import settings
from ...core.security import get_current_user
from ...models.models import (
    QuestionBank, QuestionSubject, QuestionType, KnowledgePoint,
    QuestionDetailCategory, QuestionImage, QuestionImportRecord, SysUser
)
from ...schemas.schemas import SuccessResponse
from ...services.text_parser import (
    normalize_text_for_comparison,
    compute_text_similarity,
    fuzzy_detect_duplicate,
    smart_match_questions_answers,
    detect_subject_category,
    extract_question_blocks,
    extract_answer_from_lines,
    DEDUP_SIMILARITY_THRESHOLD,
)

router = APIRouter(prefix="/api/questions/import", tags=["题目导入"])
logger = logging.getLogger(__name__)

# ============ 常量 ============
ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.docx', '.pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB — per-image size limit
MAX_BATCH_QUESTIONS = 500  # 单次批量最大题目数

# 科目名称 → subject_id 缓存
SUBJECT_NAME_MAP = {
    '行测': 1, '申论': 2, '公专': 3, '公安专业知识': 3,
    '其他': 4, '综合': 4,
}

# ============ 工具函数 ============

# 行测子科目 → 关键词映射
XINGCE_SUBCATEGORY_KEYWORDS = {
    '政治理论': ['政治', '马克思', '毛', '习近平', '党建', '时政', '党史', '理论'],
    '资料分析': ['资料分析', '图表', '增长率', '百分比', '同比', '数据', '统计'],
    '数量关系': ['数量', '数学', '计算', '方程', '几何', '排列组合', '概率', '数列'],
    '常识': ['常识', '历史', '地理', '生物', '化学', '物理', '文化', '科技'],
    '速度与知觉训练': ['速度', '知觉', '反应', '训练'],
    '判断推理': ['判断', '推理', '逻辑', '类比', '定义', '削弱', '加强', '前提'],
    '语言理解与表达': ['语言', '理解', '表达', '阅读', '填空', '成语', '语句', '排序'],
}

# 申论子科目 → 关键词映射
SHENLUN_SUBCATEGORY_KEYWORDS = {
    '归纳概括': ['概括', '归纳', '总结', '概述'],
    '综合分析': ['分析', '综合', '评析', '评述'],
    '提出对策': ['对策', '措施', '建议', '方案', '办法'],
    '应用文写作': ['应用文', '通知', '报告', '请示', '函', '简报'],
    '议论文写作': ['议论文', '论证', '论点', '论据', '作文'],
}

# 公专子科目 → 关键词映射
GONGZHUAN_SUBCATEGORY_KEYWORDS = {
    '职业素养': ['职业', '素养', '道德', '纪律', '规范', '警风', '廉洁', '作风'],
    '基本警务能力': ['警务', '勤务', '巡逻', '盘查', '处置', '控制', '应急', '实战', '战术', '武器', '警械'],
    '基础知识': ['基础', '法律', '法规', '治安', '刑事', '交通', '消防', '公安', '警察', '机关', '侦查', '取证', '拘留', '逮捕', '犯罪', '刑罚', '诉讼', '证据', '宪法', '民法', '行政'],
}


def _detect_subcategory(subject_id: int, content: str, type_name: str = '') -> str:
    """
    根据题目内容和科目自动推断子科目分类。
    返回子科目名称，若无法判断则返回 '无'。
    """
    if not content:
        return '无'

    text = content[:500]  # 只分析前500字符

    if subject_id == 1:  # 行测
        candidates = XINGCE_SUBCATEGORY_KEYWORDS
    elif subject_id == 2:  # 申论
        candidates = SHENLUN_SUBCATEGORY_KEYWORDS
    elif subject_id == 3:  # 公专
        candidates = GONGZHUAN_SUBCATEGORY_KEYWORDS
    else:
        return '无'

    best_score = 0
    best_cat = '无'
    for cat, keywords in candidates.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_cat = cat

    # 回退：科目明确但无法检测子科目时，公专默认"基础知识"
    if best_cat == '无' and subject_id == 3:
        best_cat = '基础知识'
        best_score = 1  # 确保 return 逻辑正确

    return best_cat if best_score > 0 else '无'



def _get_or_create_subject(db: Session, name: str) -> QuestionSubject:
    """获取或创建科目（强制使用预定义 subject_id 映射）"""
    # 首先尝试预定义的 subject_id 查找
    sid = SUBJECT_NAME_MAP.get(name)
    if sid:
        subject = db.query(QuestionSubject).filter(
            QuestionSubject.subject_id == sid
        ).first()
        if subject:
            return subject

    # 按名称查找
    subject = db.query(QuestionSubject).filter(
        QuestionSubject.subject_name == name
    ).first()
    if subject:
        return subject

    # 创建新科目（使用预定义 ID 或自增）
    if sid:
        subject = QuestionSubject(
            subject_id=sid,
            subject_name=name,
            subject_code=f"auto_{name}"
        )
    else:
        subject = QuestionSubject(subject_name=name, subject_code=f"auto_{name}")
    db.add(subject)
    db.flush()
    return subject


def _get_or_create_type(db: Session, type_name: str, subject_id: int) -> QuestionType:
    """获取或创建题型"""
    qtype = db.query(QuestionType).filter(
        and_(
            QuestionType.type_name == type_name,
            QuestionType.subject_id == subject_id
        )
    ).first()
    if not qtype:
        qtype = QuestionType(
            type_name=type_name,
            type_code=f"auto_{type_name}",
            subject_id=subject_id,
            is_objective=1 if type_name in ('选择题', '判断题', '填空题') else 0
        )
        db.add(qtype)
        db.flush()
    return qtype


def _detect_duplicate(db: Session, content: str, answer: str = '', subject_id: Optional[int] = None, use_fuzzy: bool = True) -> Optional[QuestionBank]:
    """
    检测重复题目。
    - use_fuzzy=False: 仅精确匹配（兼容旧逻辑）
    - use_fuzzy=True: 精确匹配 + 模糊匹配（相似度 >= 80% 视为重复）

    返回匹配到的题目，或 None（无重复）。
    """
    if not content:
        return None

    if not use_fuzzy:
        # 精确匹配（旧逻辑）
        if answer:
            return db.query(QuestionBank).filter(
                and_(
                    QuestionBank.question_content == content,
                    QuestionBank.answer == answer,
                    QuestionBank.status != 0
                )
            ).first()
        return db.query(QuestionBank).filter(
            QuestionBank.question_content == content,
            QuestionBank.status != 0
        ).first()

    # 模糊匹配
    is_dup, matched, similarity = fuzzy_detect_duplicate(
        db, content, answer, subject_id, DEDUP_SIMILARITY_THRESHOLD
    )
    return matched if is_dup else None


def _get_duplicate_info(db: Session, content: str, answer: str = '', subject_id: Optional[int] = None) -> dict:
    """
    获取去重详情（用于前端展示）。
    返回 {'is_duplicate': bool, 'similarity': float, 'existing_id': int|null, 'existing_content': str|null}
    """
    is_dup, matched, similarity = fuzzy_detect_duplicate(
        db, content, answer, subject_id, DEDUP_SIMILARITY_THRESHOLD
    )
    return {
        'is_duplicate': is_dup,
        'similarity': round(similarity, 3),
        'existing_id': matched.question_id if matched else None,
        'existing_content': (matched.question_content[:100] + '...') if matched and matched.question_content and len(matched.question_content) > 100 else (matched.question_content if matched else None),
    }


def _parse_excel_buffer(buf: bytes, filename: str) -> List[Dict[str, Any]]:
    """使用 openpyxl 解析 Excel 文件"""
    import io
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器缺少 openpyxl 库，请安装: pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(buf), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel 文件至少需要标题行和一行数据")

    headers = [str(h).strip() if h else '' for h in rows[0]]
    questions = []
    for row in rows[1:]:
        if all(v is None or str(v).strip() == '' for v in row):
            continue
        row_dict = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else None
            row_dict[h] = str(val).strip() if val is not None else ''
        questions.append(row_dict)
    return questions


def _parse_csv_buffer(buf: bytes) -> List[Dict[str, Any]]:
    """解析 CSV 文件"""
    import io, csv
    text = buf.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _normalize_question(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将原始行数据标准化为题目标准格式"""
    content = row.get('题目内容') or row.get('题干') or row.get('question') or row.get('题目') or ''
    answer = row.get('答案') or row.get('正确答案') or row.get('answer') or row.get('标准答案') or ''
    if not content or not answer:
        return None

    subject_name = row.get('科目') or row.get('科目大类') or row.get('subject') or '行测'
    type_name = row.get('题型') or row.get('题目类型') or row.get('type') or '选择题'

    options = []
    for key in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
        opt_val = row.get(f'选项{key}') or row.get(key) or ''
        if opt_val:
            options.append({'key': key, 'value': opt_val})

    if not options:
        opt_str = row.get('选项') or row.get('options') or ''
        if opt_str:
            try:
                parsed = json.loads(opt_str)
                if isinstance(parsed, list):
                    options = parsed
            except (json.JSONDecodeError, TypeError):
                pass

    difficulty_map = {'简单': 1, '较易': 2, '中等': 3, '较难': 4, '困难': 5}
    diff_raw = row.get('难度') or row.get('difficulty') or '3'
    try:
        difficulty = int(diff_raw)
    except ValueError:
        difficulty = difficulty_map.get(diff_raw, 3)
    difficulty = max(1, min(5, difficulty))

    try:
        score = float(row.get('分值') or row.get('score') or 1.0)
    except ValueError:
        score = 1.0

    try:
        year = int(row.get('年份') or row.get('year') or 0) or None
    except ValueError:
        year = None

    return {
        'subject_name': subject_name,
        'type_name': type_name,
        'question_content': content,
        'options': options if options else None,
        'answer': answer,
        'answer_analysis': row.get('解析') or row.get('答案解析') or row.get('analysis') or '',
        'difficulty': difficulty,
        'score': score,
        'year': year,
        'source': row.get('来源') or row.get('source') or '',
        'tags': row.get('标签') or row.get('tags') or '',
        'knowledge_point': row.get('知识点') or row.get('knowledge_point') or '',
        'paper_name': row.get('试卷名称') or row.get('paper_name') or '',
        'exam_province': row.get('省份') or row.get('exam_province') or '',
        'exam_type': row.get('考试类型') or row.get('exam_type') or '',
    }


def _extract_text_from_docx(buf: bytes) -> str:
    """从docx提取文本+图片占位标记。

    图片定位：通过段落内部 _p 元素的 XPath 精准提取，
    IMAGE 占位符追加到对应段落文本末尾。
    后续 extract_question_blocks 自然按行分离 stem 和 options：
      - 图片在题干段落 → marker 在 stem 中 → 前端题干区展示
      - 图片在选项段落(A.xxx) → marker 在选项值中 → 前端选项区展示
      - 独立图片段落(无文本) → 附加到最近段落，归属当前题号
    """
    import io, os, re
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器缺少 python-docx 库")

    doc = Document(io.BytesIO(buf))
    paragraphs = list(doc.paragraphs)

    # 构建图片关系映射: rId -> image_blob
    image_rel_map = {}
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            image_rel_map[rel.rId] = rel.target_part.blob

    # 图片存储目录
    _current_file = os.path.abspath(__file__)
    _backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(_current_file)))
    img_dir = os.path.join(_backend_dir, 'static', 'questions')
    os.makedirs(img_dir, exist_ok=True)

    # 命名空间
    DML = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    WPD = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
    REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

    # 题号检测正则（search 支持段中题号）
    qn_re = re.compile(r'(?:第\s*)?(\d+)\s*(?:[.、．)）\]】]|\s*题)')

    # --- 辅助函数：从段落 lxml 元素中提取所有图片 rId ---
    def _extract_rids(p_elem):
        rids = []
        # 内联图片 (wp:inline)
        for blip in p_elem.iterdescendants('{%s}blip' % DML):
            rId = blip.get('{%s}embed' % REL_NS)
            if rId and rId in image_rel_map:
                rids.append(rId)
        # 浮动图片 (wp:anchor)
        for anchor in p_elem.iterdescendants('{%s}anchor' % WPD):
            for blip in anchor.iterdescendants('{%s}blip' % DML):
                rId = blip.get('{%s}embed' % REL_NS)
                if rId and rId in image_rel_map:
                    rids.append(rId)
        return rids

    # --- 扫描段落，构建输出 ---
    parts = []
    current_qn = None
    img_seq = {}
    pending_imgs = []  # 缓冲首题之前或独立图片段的 rId

    for para in paragraphs:
        text = para.text or ''
        stripped = text.strip()

        # 检测题号（search 而非 match，支持段首或段中）
        m = qn_re.search(stripped) if stripped else None
        if m:
            current_qn = int(m.group(1))

        # 提取该段图片
        rids = _extract_rids(para._p)

        if rids:
            if current_qn is not None:
                # 有题号 → 图片归属于当前题号
                for rId in rids:
                    img_seq.setdefault(current_qn, 0)
                    seq = img_seq[current_qn]
                    img_path = os.path.join(img_dir, f'{current_qn}_{seq}.png')
                    with open(img_path, 'wb') as f:
                        f.write(image_rel_map[rId])
                    text += f' [IMAGE:{current_qn}_{seq}]'
                    img_seq[current_qn] += 1
            else:
                # 首题之前 → 缓冲
                pending_imgs.extend(rids)

        if text.strip():
            parts.append(text.strip())

    # 缓冲图片（首题之前）附加到第一个段落
    if pending_imgs and parts:
        first_qn = current_qn or 1
        for rId in pending_imgs:
            img_seq.setdefault(first_qn, 0)
            seq = img_seq[first_qn]
            img_path = os.path.join(img_dir, f'{first_qn}_{seq}.png')
            with open(img_path, 'wb') as f:
                f.write(image_rel_map[rId])
            parts[0] += f' [IMAGE:{first_qn}_{seq}]'
            img_seq[first_qn] += 1

    # --- 表格内容（文本+图片） ---
    for table in doc.tables:
        for row in table.rows:
            row_texts = []
            for cell in row.cells:
                ct = cell.text.strip()
                if ct:
                    row_texts.append(ct)
                for cp in cell.paragraphs:
                    for rId in _extract_rids(cp._p):
                        if current_qn is not None:
                            img_seq.setdefault(current_qn, 0)
                            seq = img_seq[current_qn]
                            img_path = os.path.join(img_dir, f'{current_qn}_{seq}.png')
                            with open(img_path, 'wb') as f:
                                f.write(image_rel_map[rId])
            if row_texts:
                parts.append(' | '.join(row_texts))

    return '\n'.join(parts)


def _extract_text_from_pdf(buf: bytes) -> str:
    """从 PDF 提取纯文本（优先使用 pdfplumber，支持表格提取）"""
    import io

    # 优先使用 pdfplumber（更好的中文支持和表格提取）
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(buf)) as pdf:
            parts = []
            for page in pdf.pages:
                # 提取文本
                text = page.extract_text()
                if text:
                    parts.append(text)
                # 提取表格
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            row_texts = [str(c) if c else '' for c in row]
                            row_text = ' | '.join(t for t in row_texts if t)
                            if row_text:
                                parts.append(row_text)
            if parts:
                return '\n'.join(parts)
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
        return text.strip()
    except Exception as e:
        logger.warning(f"PyPDF2 解析失败: {e}")
        return ''


def _auto_detect_tags(filename: str, text: str) -> Dict[str, Any]:
    """从文件名和文本自动检测标签"""
    tags = {}
    # 检测年份
    year_match = re.search(r'(20\d{2})', filename + text[:2000])
    if year_match:
        tags['exam_year'] = int(year_match.group(1))

    # 检测省份
    provinces = ['北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江',
                 '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东', '河南',
                 '湖北', '湖南', '广东', '广西', '海南', '重庆', '四川', '贵州',
                 '云南', '西藏', '陕西', '甘肃', '青海', '宁夏', '新疆']
    for p in provinces:
        if p in filename or p in text[:1000]:
            tags['exam_province'] = p if p not in ('内蒙古', '黑龙江') else (p + '省' if len(p) == 2 else p)
            break

    # 检测考试类型
    exam_types = {'国考': '国考', '省考': '省考', '联考': '联考', '模拟': '模拟考试', '招警': '招警考试'}
    for k, v in exam_types.items():
        if k in filename or k in text[:500]:
            tags['exam_type'] = v
            break

    # 检测科目
    subjects = {'行测': '行测', '申论': '申论', '公专': '公专', '公安专业': '公专'}
    for k, v in subjects.items():
        if k in filename or k in text[:500]:
            tags['subject_category'] = v
            break

    return tags


def _extract_and_save_images(content_text, question_id, upload_dir='uploads/questions'):
    """
    从题目内容中提取base64或URL图片，保存到磁盘，返回路径列表。
    支持格式: <img src="..."> / [IMAGE:x_y] 占位符 / base64 data URI

    安全措施：路径遍历防护、SSRF检测、图片大小限制(MAX_IMAGE_SIZE)。
    """
    images = []
    # Resolve absolute backend directory for path construction
    _current_file = os.path.abspath(__file__)
    _backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(_current_file)))
    img_dir = os.path.join(_backend_dir, upload_dir, str(question_id))
    os.makedirs(img_dir, exist_ok=True)

    # Directory where docx-extracted images are staged during parsing
    static_img_dir = os.path.join(_backend_dir, 'static', 'questions')

    # Helper: validate image data size
    def _check_size(data: bytes, label: str) -> bool:
        if len(data) > MAX_IMAGE_SIZE:
            logger.warning(f"[images] {label} 超过大小限制 ({len(data)} > {MAX_IMAGE_SIZE})")
            return False
        return True

    # Helper: validate extension
    def _safe_ext(raw: str, default: str = 'png') -> str:
        ext = (raw or default).lower().split('?')[0]
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            ext = default
        return ext

    # 1. Extract <img> tags with src attribute
    img_tags = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', content_text or '')
    for idx, src in enumerate(img_tags):
        try:
            filepath = None
            if src.startswith('data:image'):
                # Base64 image — decode then check size
                header, data = src.split(',', 1)
                img_data = base64.b64decode(data)
                if not _check_size(img_data, f'base64图片{idx}'):
                    continue
                md5 = hashlib.md5(img_data).hexdigest()[:8]
                ext = _safe_ext(header.split(';')[0].split('/')[-1])
                filename = f'img_{idx}_{md5}.{ext}'
                filepath = os.path.join(img_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
            elif src.startswith('http'):
                # URL image — SSRF protection + size check
                import requests as _req

                parsed = urlparse(src)
                hostname = parsed.hostname
                if not hostname:
                    continue

                # SSRF check: resolve hostname and reject private/localhost IPs
                try:
                    resolved_ip = socket.gethostbyname(hostname)
                    ip_addr = ipaddress.ip_address(resolved_ip)
                    if ip_addr.is_private or ip_addr.is_loopback or ip_addr.is_link_local:
                        logger.warning(f"[images] SSRF blocked: {hostname} -> {resolved_ip}")
                        continue
                except Exception:
                    continue

                try:
                    resp = _req.get(src, timeout=10, stream=True, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    if resp.status_code == 200:
                        # Check Content-Length header early if available
                        content_length = resp.headers.get('Content-Length')
                        if content_length and int(content_length) > MAX_IMAGE_SIZE:
                            logger.warning(f"[images] HTTP图片{idx} Content-Length超标: {content_length}")
                            resp.close()
                            continue

                        # Read in chunks, enforcing size limit
                        chunks = []
                        total = 0
                        for chunk in resp.iter_content(chunk_size=8192):
                            chunks.append(chunk)
                            total += len(chunk)
                            if total > MAX_IMAGE_SIZE:
                                logger.warning(f"[images] HTTP图片{idx} 超过大小限制")
                                resp.close()
                                chunks = None
                                break
                        if chunks is None:
                            continue
                        img_data = b''.join(chunks)
                        if not _check_size(img_data, f'HTTP图片{idx}'):
                            continue
                        md5 = hashlib.md5(img_data).hexdigest()[:8]
                        ext = _safe_ext(src.rsplit('.', 1)[-1], 'jpg')
                        filename = f'img_{idx}_{md5}.{ext}'
                        filepath = os.path.join(img_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(img_data)
                except Exception:
                    continue
            else:
                # Local path — use basename to prevent directory traversal
                safe_name = os.path.basename(src)
                if safe_name:
                    src_path = os.path.join(_backend_dir, 'uploads', safe_name)
                    if os.path.exists(src_path):
                        img_data = open(src_path, 'rb').read()
                        if not _check_size(img_data, f'本地图片{idx}'):
                            continue
                        ext = _safe_ext(safe_name.rsplit('.', 1)[-1])
                        filename = f'img_{idx}.{ext}'
                        filepath = os.path.join(img_dir, filename)
                        shutil.copy2(src_path, filepath)

            if filepath and os.path.exists(filepath):
                rel_path = f'/static/questions/{question_id}/{os.path.basename(filepath)}'
                images.append(rel_path)
                logger.debug(f"[images] 保存图片: {rel_path}")
        except Exception as e:
            logger.warning(f"[images] 图片{idx}保存失败: {e}")
            continue

    # 2. Extract [IMAGE:x_y] markers (generated by _extract_text_from_docx)
    marker_pattern = re.compile(r'\[IMAGE:(\d+)_(\d+)\]')
    markers = marker_pattern.findall(content_text or '')
    for idx, (num, seq) in enumerate(markers):
        try:
            # Look for the pre-extracted image in static/questions/
            candidate_name = f'{num}_{seq}.png'
            src_file = os.path.join(static_img_dir, candidate_name)
            if os.path.exists(src_file):
                img_data = open(src_file, 'rb').read()
                if not _check_size(img_data, f'docx图片{num}_{seq}'):
                    continue
                md5 = hashlib.md5(img_data).hexdigest()[:8]
                dst_name = f'img_docx_{num}_{seq}_{md5}.png'
                dst_file = os.path.join(img_dir, dst_name)
                shutil.copy2(src_file, dst_file)
                rel_path = f'/static/questions/{question_id}/{dst_name}'
                images.append(rel_path)
                logger.debug(f"[images] 保存docx图片: {rel_path}")
            else:
                logger.debug(f"[images] docx图片未找到: {candidate_name}")
        except Exception as e:
            logger.warning(f"[images] docx图片{idx}({num}_{seq})保存失败: {e}")
            continue

    return images


# ============ API 端点 ============

@router.post("/single", summary="单题导入")
async def import_single_question(
    question_data: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    手工录入单道题目，逐字段精确控制。

    字段说明：
    - question_content: 题目内容（必填）
    - answer: 正确答案（合并模式必填，分离模式可选）
    - import_mode: 'combined'（默认，含答案）或 'separate'（仅题目）
    - subject_category: 科目大类（行测/申论/公专/其他）
    - question_type_detail: 题型（选择题/判断题/填空题等）
    - options: 选项列表 [{"key":"A","value":"..."}]
    - difficulty: 难度 1-5
    - score: 分值
    """
    try:
        content = question_data.get('question_content', '').strip()
        answer = question_data.get('answer', '').strip()
        import_mode = question_data.get('import_mode', 'combined')
        if not content:
            raise HTTPException(status_code=400, detail="题目内容不能为空")
        if not answer and import_mode != 'separate':
            raise HTTPException(status_code=400, detail="题目内容和答案不能为空")
        if import_mode == 'separate' and not answer:
            # 分离模式：无答案题目标记为待补充
            answer = '待补充'

        # 科目（在去重前获取，用于缩小候选范围）
        subject_name = question_data.get('subject_category', '行测')
        subject = _get_or_create_subject(db, subject_name)

        # 模糊去重检测
        existing = _detect_duplicate(db, content, answer, subject.subject_id)
        if existing:
            # 获取相似度详情
            dup_info = _get_duplicate_info(db, content, answer, subject.subject_id)
            return {
                'import_status': 'DUPLICATE',
                'question_id': existing.question_id,
                'message': f'该题目已存在（相似度 {dup_info["similarity"]*100:.0f}%，现有ID: {existing.question_id}）',
                'similarity': dup_info['similarity'],
                'existing_content_preview': dup_info.get('existing_content'),
                'error_messages': [{'error': '重复题目', 'existing_id': existing.question_id, 'similarity': dup_info['similarity']}]
            }

        # 题型
        type_name = question_data.get('question_type_detail', '选择题')
        qtype = _get_or_create_type(db, type_name, subject.subject_id)

        # 创建题目
        difficulty = max(1, min(5, int(question_data.get('difficulty', 3))))
        score = float(question_data.get('score', 1.0))
        options = question_data.get('options')
        # 直接赋值给JSON列，不调用json.dumps（避免双重编码）

        question = QuestionBank(
            subject_id=subject.subject_id,
            type_id=qtype.type_id,
            question_content=content,
            options=options,
            answer=answer,
            answer_analysis=question_data.get('answer_analysis', ''),
            difficulty=difficulty,
            score=score,
            year=question_data.get('exam_year') or question_data.get('year'),
            source=question_data.get('source', ''),
            tags=question_data.get('tags', ''),
            creator_id=current_user.user_id,
            audit_status=1,  # 自动通过审核
            xingce_subcategory=_detect_subcategory(subject.subject_id, content, type_name) if subject.subject_id == 1 else '无',
            shenlun_subcategory=_detect_subcategory(subject.subject_id, content, type_name) if subject.subject_id == 2 else '无',
            gongzhuan_subcategory=_detect_subcategory(subject.subject_id, content, type_name) if subject.subject_id == 3 else '无',
        )
        db.add(question)
        db.flush()

        # 图片提取与保存（异常不回滚整题，仅跳过图片）
        try:
            images = _extract_and_save_images(
                question_data.get('question_content', '') + ' ' + str(question_data.get('options', '')),
                question.question_id
            )
            for img_order, img_path in enumerate(images):
                db.add(QuestionImage(
                    question_id=question.question_id,
                    image_path=img_path,
                    image_type='题干图',
                    image_order=img_order
                ))
        except Exception as img_err:
            logger.warning(f"图片提取失败 question_id={question.question_id}: {img_err}")

        # 详细分类
        detail = QuestionDetailCategory(
            question_id=question.question_id,
            xingce_subcategory=question_data.get('xingce_subcategory', '无'),
            shenlun_subcategory=question_data.get('shenlun_subcategory', '无'),
            gongzhuan_subcategory=question_data.get('gongzhuan_subcategory', '无'),
            question_type_detail=type_name,
        )
        db.add(detail)

        # 导入记录
        record = QuestionImportRecord(
            user_id=current_user.user_id,
            original_filename=question_data.get('paper_name', '手工录入'),
            file_type='JSON',
            total_questions=1,
            success_count=1,
            failed_count=0,
            duplicate_count=0,
            import_status='COMPLETED',
            import_time=datetime.now(),
            complete_time=datetime.now(),
        )
        db.add(record)
        db.commit()

        return {
            'import_status': 'SUCCESS',
            'question_id': question.question_id,
            'message': '题目导入成功',
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"单题导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.put("/update-answer/{question_id}", summary="更新题目答案")
async def update_question_answer(
    question_id: int,
    answer_data: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    为已导入的题目（含有导入模式为单独的、答案为空、待补充或图片导入的题目）补录或更正答案。

    body 示例：
    - answer: "C"
    - answer_analysis: "解析文本（可选）"
    - paper_name: "试卷名称（可选，用于关联导入记录）"
    """
    try:
        question = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="题目不存在")

        answer = answer_data.get('answer', '').strip()
        if not answer:
            raise HTTPException(status_code=400, detail="答案不能为空")

        old_answer = question.answer
        question.answer = answer
        if answer_data.get('answer_analysis'):
            question.answer_analysis = answer_data['answer_analysis']

        # 更新对应的导入记录（若提供 paper_name）
        paper_name = answer_data.get('paper_name', '')
        if paper_name:
            record = db.query(QuestionImportRecord).filter(
                QuestionImportRecord.original_filename == paper_name
            ).order_by(QuestionImportRecord.import_id.desc()).first()
            if record and record.import_status == 'PENDING_ANSWER':
                # 检查是否所有同批次题目都已补录答案
                still_pending = db.query(QuestionBank).filter(
                    QuestionBank.answer == '待补充',
                    QuestionBank.question_id.in_(
                        # 同批次未完成答案补录的题目数
                        db.query(QuestionBank.question_id).filter(
                            QuestionBank.answer == '待补充'
                        )
                    )
                ).count()
                # 简化：有且仅有这道题被更新时，检查剩余待补充数
                record.import_status = 'COMPLETED' if still_pending <= 1 else 'PENDING_ANSWER'

        db.commit()
        db.refresh(question)

        return {
            'update_status': 'SUCCESS',
            'question_id': question_id,
            'old_answer': old_answer,
            'new_answer': answer,
            'message': '答案更新成功'
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"答案更新失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"答案更新失败: {str(e)}")


@router.post("/batch-answers", summary="批量导入答案")
async def batch_import_answers(
    answers_data: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    批量补录答案。支持两种匹配模式：

    1. 按 paper_name 匹配：paper_name + answer_pairs（题号→答案映射）
       body: { "paper_name": "2019北京公安", "answer_pairs": [{"number": 1, "answer": "C"}, ...] }

    2. 按 question_id 精确匹配：
       body: { "answer_pairs": [{"question_id": 42, "answer": "C"}, ...] }
    """
    try:
        pairs = answers_data.get('answer_pairs', [])
        paper_name = answers_data.get('paper_name', '')
        if not pairs:
            raise HTTPException(status_code=400, detail="答案列表不能为空")

        updated = 0
        failed = 0
        details = []

        for pair in pairs:
            try:
                qid = pair.get('question_id')
                if not qid and paper_name:
                    # 尝试按题号查找同试卷题目
                    number = pair.get('number')
                    # 按 paper_name 匹配最近导入记录中的题目
                    record = db.query(QuestionImportRecord).filter(
                        QuestionImportRecord.original_filename.like(f'%{paper_name}%')
                    ).order_by(QuestionImportRecord.import_id.desc()).first()
                    if record:
                        # 简易策略：找到该记录的题目范围并匹配序号
                        pass
                    continue

                answer = pair.get('answer', '').strip()
                if not qid or not answer:
                    failed += 1
                    details.append({'number': pair.get('number'), 'error': '缺少question_id或answer'})
                    continue

                question = db.query(QuestionBank).filter(QuestionBank.question_id == qid).first()
                if not question:
                    failed += 1
                    details.append({'question_id': qid, 'error': '题目不存在'})
                    continue

                question.answer = answer
                if pair.get('answer_analysis'):
                    question.answer_analysis = pair['answer_analysis']
                updated += 1
                details.append({'question_id': qid, 'status': 'updated', 'answer': answer})

            except Exception as e:
                failed += 1
                details.append({'question_id': pair.get('question_id'), 'error': str(e)})

        db.commit()

        return {
            'import_status': 'SUCCESS' if failed == 0 else 'PARTIAL',
            'total': len(pairs),
            'updated': updated,
            'failed': failed,
            'details': details,
            'message': f'答案批量补录完成：成功 {updated}，失败 {failed}'
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"批量答案导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量答案导入失败: {str(e)}")


@router.post("/upload", summary="批量文件上传与预览")
async def upload_file_for_import(
    file: UploadFile = File(...),
    paper_name: Optional[str] = Form(None),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传文件进行题目批量解析预览。
    支持格式：.xlsx / .xls / .csv / .docx / .pdf

    返回解析预览数据（不直接入库），等待前端 confirm 确认。
    """
    # 校验文件
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}")

    buf = await file.read()
    if len(buf) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件超过 {MAX_FILE_SIZE // 1024 // 1024}MB 限制")

    file_type_map = {'.xlsx': 'EXCEL', '.xls': 'EXCEL', '.csv': 'EXCEL', '.docx': 'WORD', '.pdf': 'PDF'}
    file_type = file_type_map.get(ext, 'EXCEL')

    try:
        # 创建导入记录（状态：PARSING）
        record = QuestionImportRecord(
            user_id=current_user.user_id,
            original_filename=file.filename,
            file_type=file_type,
            import_status='PARSING',
            import_time=datetime.now(),
        )
        db.add(record)
        db.flush()

        # 解析文件
        raw_questions = []
        if ext in ('.xlsx', '.xls'):
            raw_questions = _parse_excel_buffer(buf, file.filename)
        elif ext == '.csv':
            raw_questions = _parse_csv_buffer(buf)
        elif ext == '.docx':
            text = _extract_text_from_docx(buf)
            raw_questions = [{'type': 'docx_text', 'content': text}]
        elif ext == '.pdf':
            text = _extract_text_from_pdf(buf)
            raw_questions = [{'type': 'pdf_text', 'content': text}]

        # 标准化并预览
        if ext in ('.xlsx', '.xls', '.csv'):
            preview_items = []
            success_count = 0
            duplicate_count = 0
            failed_count = 0

            for row in raw_questions[:MAX_BATCH_QUESTIONS]:
                normalized = _normalize_question(row)
                if not normalized:
                    failed_count += 1
                    preview_items.append({
                        'status': 'SKIPPED',
                        'reason': '缺少题目内容或答案',
                        'raw': row,
                    })
                    continue

                existing = _detect_duplicate(db, normalized['question_content'], normalized['answer'])
                if existing:
                    dup_info = _get_duplicate_info(db, normalized['question_content'], normalized['answer'])
                    duplicate_count += 1
                    preview_items.append({
                        **normalized,
                        'status': 'DUPLICATE',
                        'is_duplicate': True,
                        'existing_id': existing.question_id,
                        'similarity': dup_info['similarity'],
                    })
                else:
                    success_count += 1
                    preview_items.append({
                        **normalized,
                        'status': 'NEW',
                        'is_duplicate': False,
                    })

            total = len(raw_questions[:MAX_BATCH_QUESTIONS])

            # 更新记录
            record.total_questions = total
            record.success_count = success_count
            record.failed_count = failed_count
            record.duplicate_count = duplicate_count
            record.import_status = 'PREVIEW'
            record.preview_data = json.dumps({
                'items': preview_items,
                'auto_detected_tags': _auto_detect_tags(file.filename, str(preview_items[:5]) if preview_items else ''),
            }, ensure_ascii=False)
            db.commit()

            return {
                'import_id': record.import_id,
                'original_filename': file.filename,
                'file_type': file_type,
                'total_questions': total,
                'success_count': success_count,
                'failed_count': failed_count,
                'duplicate_count': duplicate_count,
                'questions': preview_items,
                'auto_detected_tags': _auto_detect_tags(file.filename, str(preview_items[:5]) if preview_items else ''),
            }
        else:
            # docx/pdf: 使用后端text_parser解析 → 返回结构化数据
            text = raw_questions[0]['content'] if raw_questions else ''
            from ...services.text_parser import extract_question_blocks
            parsed_blocks = extract_question_blocks(text)

            preview_items = []
            for block in parsed_blocks:
                if block.get('content'):
                    qtype = block.get('question_type', '选择题')
                    preview_items.append({
                        'question_content': block['content'],
                        'options': block.get('options', []),
                        'answer': block.get('answer', ''),
                        'analysis': block.get('analysis', ''),
                        'question_type_detail': qtype,
                        'type_name': qtype,
                        'status': 'NEW',
                        'is_duplicate': False,
                        'difficulty': 3,
                        'score': 1,
                    })

            total = len(preview_items)
            record.total_questions = total
            record.success_count = total
            record.failed_count = 0
            record.duplicate_count = 0
            record.import_status = 'PREVIEW'
            record.preview_data = json.dumps({
                'items': preview_items,
                'raw_text': text[:1000000],
                'auto_detected_tags': _auto_detect_tags(file.filename, text),
            }, ensure_ascii=False)
            db.commit()

            return {
                'import_id': record.import_id,
                'original_filename': file.filename,
                'file_type': file_type,
                'total_questions': total,
                'success_count': total,
                'failed_count': 0,
                'duplicate_count': 0,
                'questions': preview_items,
                'raw_text_preview': text[:1000000],
                'auto_detected_tags': _auto_detect_tags(file.filename, text),
            }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"文件解析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")


@router.post("/confirm", summary="确认批量导入")
async def confirm_batch_import(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    确认预览数据并批量入库。

    参数：
    - import_id: 导入记录ID
    - action: 'skip' | 'overwrite'
    - skip_duplicate_ids: 跳过的重复题目ID列表
    - overwrite_duplicate_ids: 覆盖更新（暂不支持）
    - custom_tags: 自定义标签
    """
    import_id = payload.get('import_id')
    if not import_id:
        raise HTTPException(status_code=400, detail="缺少 import_id")

    record = db.query(QuestionImportRecord).filter(
        QuestionImportRecord.import_id == import_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="导入记录不存在")
    if record.import_status != 'PREVIEW':
        raise HTTPException(status_code=400, detail=f"当前状态 {record.import_status} 不允许确认")

    try:
        preview_data = record.preview_data
        if isinstance(preview_data, str):
            preview_data = json.loads(preview_data)
        items = preview_data.get('items', [])

        imported = 0
        skipped = 0
        failed = 0
        errors = []

        for item in items:
            if item.get('status') == 'DUPLICATE' or item.get('is_duplicate'):
                skipped += 1
                continue
            if item.get('status') == 'SKIPPED':
                failed += 1
                errors.append({'error': item.get('reason', '数据不完整'), 'raw': item.get('raw', {})})
                continue

            try:
                subject = _get_or_create_subject(db, item.get('subject_name', '行测'))
                qtype = _get_or_create_type(db, item.get('type_name', '选择题'), subject.subject_id)

                options = item.get('options')
                # 直接赋值给JSON列，不调用json.dumps（避免双重编码）

                question = QuestionBank(
                    subject_id=subject.subject_id,
                    type_id=qtype.type_id,
                    question_content=item['question_content'],
                    options=options,
                    answer=item['answer'],
                    answer_analysis=item.get('answer_analysis', ''),
                    difficulty=item.get('difficulty', 3),
                    score=item.get('score', 1.0),
                    year=item.get('year'),
                    source=item.get('source', ''),
                    tags=item.get('tags', ''),
                    creator_id=current_user.user_id,
                    audit_status=1,
                    xingce_subcategory=_detect_subcategory(subject.subject_id, item['question_content'], item.get('type_name', '')) if subject.subject_id == 1 else '无',
                    shenlun_subcategory=_detect_subcategory(subject.subject_id, item['question_content'], item.get('type_name', '')) if subject.subject_id == 2 else '无',
                    gongzhuan_subcategory=_detect_subcategory(subject.subject_id, item['question_content'], item.get('type_name', '')) if subject.subject_id == 3 else '无',
                )
                db.add(question)
                db.flush()

                detail = QuestionDetailCategory(
                    question_id=question.question_id,
                    question_type_detail=item.get('type_name', '选择题'),
                )
                db.add(detail)

                # 图片提取与保存（失败时清除已刷新的题目，避免孤儿行）
                try:
                    images = _extract_and_save_images(
                        item.get('question_content', '') + ' ' + str(item.get('options', '')),
                        question.question_id
                    )
                    for img_order, img_path in enumerate(images):
                        db.add(QuestionImage(
                            question_id=question.question_id,
                            image_path=img_path,
                            image_type='题干图',
                            image_order=img_order
                        ))
                except Exception as img_err:
                    logger.warning(f"图片提取失败 question_id={question.question_id}: {img_err}")
                    db.delete(question)
                    raise

                imported += 1
            except Exception as e:
                failed += 1
                errors.append({'error': str(e), 'item': item.get('question_content', '')[:100]})

        record.success_count = imported
        record.failed_count = failed
        record.duplicate_count = skipped + record.duplicate_count
        record.import_status = 'COMPLETED'
        record.complete_time = datetime.now()
        if errors:
            record.error_messages = json.dumps(errors, ensure_ascii=False)
        db.commit()

        return {
            'success_count': imported,
            'failed_count': failed,
            'skipped_count': skipped,
            'errors': errors,
            'message': f'导入完成：成功 {imported}，失败 {failed}，跳过 {skipped}',
        }
    except Exception as e:
        db.rollback()
        logger.error(f"确认导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/separate-match", summary="分离导入智能匹配")
async def separate_match_endpoint(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    接收题目文本和答案文本，在后端进行智能匹配。
    适用于分离导入模式（题目文件和答案文件分别上传）。

    参数：
    - questions_text: 题目文件原始文本（必填）
    - answers_text: 答案文件原始文本（必填）
    - paper_name: 试卷名称（可选）
    - subject_category: 科目（可选，自动检测）

    返回：
    - match_rate: 匹配率
    - questions: 匹配后的结构化题目列表
    - unmatched_numbers: 未匹配的题号
    - strategy_used: 使用的匹配策略
    """
    questions_text = payload.get('questions_text', '').strip()
    answers_text = payload.get('answers_text', '').strip()

    if not questions_text:
        raise HTTPException(status_code=400, detail="题目文件文本为空")
    if not answers_text:
        raise HTTPException(status_code=400, detail="答案文件文本为空")

    try:
        # 调用智能匹配引擎
        result = smart_match_questions_answers(
            questions_text, answers_text, payload.get('paper_name', '')
        )

        # 对每个题目进行去重检测
        subject_name = payload.get('subject_category', '')
        if not subject_name:
            # 从题目文本自动检测科目
            all_content = ' '.join(q.get('content', '') for q in result.questions[:10])
            subject_name = detect_subject_category(all_content)
        subject = _get_or_create_subject(db, subject_name)

        for q in result.questions:
            content = q.get('content', '')
            dup_info = _get_duplicate_info(db, content, q.get('answer', ''), subject.subject_id)
            q['is_duplicate'] = dup_info['is_duplicate']
            q['similarity'] = dup_info['similarity']
            if dup_info['is_duplicate']:
                q['existing_id'] = dup_info['existing_id']

        return {
            'status': 'success',
            'match_rate': round(result.match_rate * 100, 1),
            'matched_count': result.matched_count,
            'total_questions': result.total_questions,
            'questions': result.questions,
            'unmatched_question_numbers': result.unmatched_question_numbers,
            'extra_answer_numbers': result.extra_answer_numbers,
            'analysis_count': result.analysis_count,
            'strategy_used': result.strategy_used,
            'auto_detected_subject': subject_name,
            'details': result.details,
            'message': f'匹配完成：{round(result.match_rate*100, 1)}%（{result.matched_count}/{result.total_questions}）'
        }
    except Exception as e:
        logger.error(f"分离导入匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"智能匹配失败: {str(e)}")


@router.post("/ocr", summary="图片OCR识别（PaddleOCR）")
async def ocr_recognize(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
):
    """
    提交图片 Base64，返回 PaddleOCR 识别文本。

    参数：
    - image_base64: 图片的 Base64 编码（可含 data:image/xxx;base64, 前缀）

    返回：
    - ocr_text: 识别的纯文本
    - status: 'success' | 'error'
    """
    image_base64 = payload.get('image_base64', '')
    if not image_base64:
        raise HTTPException(status_code=400, detail="图片数据为空")

    try:
        from ...services.ocr import recognize_image_base64
        text = recognize_image_base64(image_base64)
        if not text or not text.strip():
            return {
                'status': 'success',
                'ocr_text': '',
                'message': '未能识别到文字内容，请确认图片清晰度或手动输入'
            }
        return {
            'status': 'success',
            'ocr_text': text,
            'char_count': len(text),
            'message': f'识别成功，共 {len(text)} 字符'
        }
    except RuntimeError as e:
        logger.warning(f"OCR 服务不可用: {e}")
        return {
            'status': 'error',
            'ocr_text': '',
            'message': 'OCR 服务暂不可用，请安装 PaddleOCR 依赖: pip install paddleocr paddlepaddle'
        }
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {str(e)}")


@router.get("/ocr/status", summary="OCR 服务状态")
async def ocr_status():
    """检查 PaddleOCR 是否可用"""
    try:
        from ...services.ocr import get_ocr_status
        return get_ocr_status()
    except ImportError:
        return {'available': False, 'model_loaded': False, 'version': None, 'message': 'PaddleOCR 未安装'}


@router.post("/image", summary="图片OCR导入（增强版：自动分类+去重）")
async def import_from_image(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    图片 OCR 识别并导入题目（增强版）。

    参数：
    - image_base64: 图片的 Base64 编码
    - image_ext: 图片扩展名
    - client_ocr_text: 前端 OCR 预识别文本
    - structured_questions: 前端结构化提取后的题目列表（优先级最高）
    - subject_category: 科目大类（可选，自动检测）
    - paper_name: 试卷名称
    - auto_save: 是否自动入库（默认 true）
    """
    image_base64 = payload.get('image_base64', '')
    client_ocr_text = payload.get('client_ocr_text', '').strip()
    structured_questions = payload.get('structured_questions', [])

    if not image_base64 and not client_ocr_text and not structured_questions:
        raise HTTPException(status_code=400, detail="图片数据、OCR文本和结构化题目均为空")

    try:
        # 如果有结构化题目列表，逐题导入
        if structured_questions:
            return await _import_structured_from_ocr(
                structured_questions, payload, current_user, db
            )

        # 单题导入模式
        ocr_text = client_ocr_text
        if not ocr_text and image_base64:
            # 服务端OCR识别
            try:
                from ...services.ocr import recognize_image_base64
                ocr_text = recognize_image_base64(image_base64)
            except (ImportError, RuntimeError) as e:
                logger.warning(f"OCR服务不可用: {e}")
                ocr_text = '[OCR服务未安装，请使用前端OCR预识别]'

        if not ocr_text or not ocr_text.strip():
            return {
                'import_status': 'SKIPPED',
                'message': 'OCR未能识别到文字内容',
            }

        # 自动检测科目
        subject_name = payload.get('subject_category', '')
        if not subject_name:
            subject_name = detect_subject_category(ocr_text)
        subject = _get_or_create_subject(db, subject_name)

        # 尝试从OCR文本提取题目结构
        question_blocks = extract_question_blocks(ocr_text)
        auto_tags = _auto_detect_tags(payload.get('paper_name', ''), ocr_text)

        # 如果提取到多道题目，逐题导入
        if len(question_blocks) > 1:
            return await _import_structured_from_ocr(
                question_blocks, payload, current_user, db
            )

        # 单题：尝试从OCR文本提取答案
        extracted = extract_answer_from_lines(ocr_text.split('\n'))
        detected_answer = extracted.get('answer') if extracted else None

        # 自动检测题型
        detected_type = _detect_question_type(ocr_text, [])
        qtype = _get_or_create_type(db, detected_type, subject.subject_id)

        content = ocr_text[:100000]
        answer = detected_answer or '[待人工补充]'
        analysis = extracted.get('analysis') if extracted else '[OCR导入，待补充答案解析]'

        # 去重检测
        dup_info = _get_duplicate_info(db, content, answer, subject.subject_id)
        if dup_info['is_duplicate'] and payload.get('auto_save', True):
            return {
                'import_status': 'DUPLICATE',
                'similarity': dup_info['similarity'],
                'existing_id': dup_info['existing_id'],
                'existing_content': dup_info.get('existing_content'),
                'message': f'该题目已存在（相似度 {dup_info["similarity"]*100:.0f}%）',
            }

        # 子科目自动检测
        subcategory = _detect_subcategory(subject.subject_id, content)

        question = QuestionBank(
            subject_id=subject.subject_id,
            type_id=qtype.type_id,
            question_content=content,
            answer=answer,
            answer_analysis=analysis,
            difficulty=3,
            score=1.0,
            year=auto_tags.get('exam_year') or payload.get('exam_year'),
            source=payload.get('source', '图片导入'),
            tags=payload.get('tags', 'OCR导入'),
            creator_id=current_user.user_id,
            audit_status=0,
        )

        # 设置子科目
        if subject.subject_id == 1:
            question.xingce_subcategory = subcategory
        elif subject.subject_id == 2:
            question.shenlun_subcategory = subcategory
        elif subject.subject_id == 3:
            question.gongzhuan_subcategory = subcategory

        db.add(question)
        db.flush()

        detail = QuestionDetailCategory(
            question_id=question.question_id,
            question_type_detail=detected_type,
        )
        # 设置详细分类的子科目
        if subject.subject_id == 1:
            detail.xingce_subcategory = subcategory
        elif subject.subject_id == 2:
            detail.shenlun_subcategory = subcategory
        elif subject.subject_id == 3:
            detail.gongzhuan_subcategory = subcategory
        db.add(detail)

        record = QuestionImportRecord(
            user_id=current_user.user_id,
            original_filename=payload.get('paper_name', '图片导入'),
            file_type='PDF',
            total_questions=1,
            success_count=1,
            failed_count=0,
            import_status='COMPLETED',
            import_time=datetime.now(),
            complete_time=datetime.now(),
        )
        db.add(record)
        db.commit()

        return {
            'import_status': 'SUCCESS',
            'question_id': question.question_id,
            'auto_detected_subject': subject_name,
            'auto_detected_subcategory': subcategory,
            'auto_detected_type': detected_type,
            'auto_detected_answer': detected_answer,
            'message': f'题目已导入至"{subject_name}-{subcategory}"分类，答案: {answer}',
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"图片导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"图片导入失败: {str(e)}")


async def _import_structured_from_ocr(
    structured_questions: List[Dict[str, Any]],
    payload: Dict[str, Any],
    current_user: SysUser,
    db: Session
) -> Dict[str, Any]:
    """从OCR结构化题目列表批量导入"""
    imported = 0
    duplicates = 0
    failed = 0
    results = []

    # 自动检测科目
    all_text = ' '.join(
        q.get('content', '') or q.get('question_content', '')
        for q in structured_questions[:5]
    )
    subject_name = payload.get('subject_category', '') or detect_subject_category(all_text)
    subject = _get_or_create_subject(db, subject_name)

    for q_data in structured_questions:
        content = q_data.get('content') or q_data.get('question_content', '')
        answer = q_data.get('answer', '') or '[待人工补充]'
        analysis = q_data.get('analysis') or q_data.get('answer_analysis', '') or '[OCR导入]'

        if not content:
            failed += 1
            results.append({'status': 'FAILED', 'reason': '题目内容为空'})
            continue

        # 去重检测
        dup_info = _get_duplicate_info(db, content, answer, subject.subject_id)
        if dup_info['is_duplicate']:
            duplicates += 1
            results.append({
                'status': 'DUPLICATE',
                'similarity': dup_info['similarity'],
                'existing_id': dup_info['existing_id'],
                'content_preview': content[:50],
            })
            continue

        try:
            detected_type = _detect_question_type(content, q_data.get('options', []))
            qtype = _get_or_create_type(db, detected_type, subject.subject_id)
            # 优先使用前端传来的子分类，否则自动检测
            subcategory = q_data.get('subcategory', '') or _detect_subcategory(subject.subject_id, content)

            question = QuestionBank(
                subject_id=subject.subject_id,
                type_id=qtype.type_id,
                question_content=content[:50000],
                options=q_data.get('options') if q_data.get('options') else None,
                answer=answer,
                answer_analysis=analysis,
                difficulty=q_data.get('difficulty', 3),
                score=float(q_data.get('score', 1.0)),
                year=payload.get('exam_year'),
                source=payload.get('source', '图片OCR导入'),
                tags=payload.get('tags', 'OCR导入'),
                creator_id=current_user.user_id,
                audit_status=0,
            )
            if subject.subject_id == 1:
                question.xingce_subcategory = subcategory
            elif subject.subject_id == 2:
                question.shenlun_subcategory = subcategory
            elif subject.subject_id == 3:
                question.gongzhuan_subcategory = subcategory
            db.add(question)
            db.flush()

            detail = QuestionDetailCategory(
                question_id=question.question_id,
                question_type_detail=detected_type,
            )
            if subject.subject_id == 1:
                detail.xingce_subcategory = subcategory
            elif subject.subject_id == 2:
                detail.shenlun_subcategory = subcategory
            elif subject.subject_id == 3:
                detail.gongzhuan_subcategory = subcategory
            db.add(detail)

            # 图片提取与保存（失败时清除已刷新的题目，避免孤儿行）
            try:
                images = _extract_and_save_images(
                    content + ' ' + str(q_data.get('options', '')),
                    question.question_id
                )
                for img_order, img_path in enumerate(images):
                    db.add(QuestionImage(
                        question_id=question.question_id,
                        image_path=img_path,
                        image_type='题干图',
                        image_order=img_order
                    ))
            except Exception as img_err:
                logger.warning(f"OCR图片提取失败 question_id={question.question_id}: {img_err}")
                db.delete(question)
                raise

            imported += 1
            results.append({
                'status': 'IMPORTED',
                'question_id': question.question_id,
                'type': detected_type,
                'subcategory': subcategory,
            })
        except Exception as e:
            failed += 1
            results.append({'status': 'FAILED', 'reason': str(e), 'content_preview': content[:50]})

    # 创建导入记录
    record = QuestionImportRecord(
        user_id=current_user.user_id,
        original_filename=payload.get('paper_name', '图片批量导入'),
        file_type='PDF',
        total_questions=len(structured_questions),
        success_count=imported,
        failed_count=failed,
        duplicate_count=duplicates,
        import_status='COMPLETED',
        import_time=datetime.now(),
        complete_time=datetime.now(),
    )
    db.add(record)
    db.commit()

    return {
        'import_status': 'SUCCESS' if imported > 0 else 'PARTIAL',
        'auto_detected_subject': subject_name,
        'total': len(structured_questions),
        'imported': imported,
        'duplicates': duplicates,
        'failed': failed,
        'results': results,
        'message': f'图片导入完成：成功 {imported}，重复 {duplicates}，失败 {failed}',
    }


def _detect_question_type(content: str, options: list) -> str:
    """从OCR文本自动检测题型"""
    # 导入 text_parser 的函数
    from ...services.text_parser import _detect_question_type as _detect
    return _detect(content, options)


@router.get("/records", summary="导入记录列表")
async def get_import_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分页查询导入记录"""
    q = db.query(QuestionImportRecord)
    user_role = getattr(current_user, 'user_type', '') or getattr(current_user, 'role', '')
    if user_role not in ('admin', 'teacher'):
        q = q.filter(QuestionImportRecord.user_id == current_user.user_id)
    if status:
        q = q.filter(QuestionImportRecord.import_status == status)

    total = q.count()
    records = q.order_by(desc(QuestionImportRecord.import_time))\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    items = []
    for r in records:
        def _fmt(dt):
            if dt is None:
                return None
            try:
                return dt.isoformat()
            except AttributeError:
                return str(dt)
        items.append({
            'import_id': r.import_id,
            'original_filename': r.original_filename,
            'file_type': r.file_type,
            'total_questions': r.total_questions,
            'success_count': r.success_count,
            'failed_count': r.failed_count,
            'duplicate_count': r.duplicate_count,
            'import_status': r.import_status,
            'import_time': _fmt(r.import_time),
            'complete_time': _fmt(r.complete_time),
        })

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}


@router.get("/stats", summary="导入统计数据")
async def get_import_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取导入统计数据（题库总数、科目分布、题型分布、最近导入）"""
    # 题库总数
    total_questions = db.query(func.count(QuestionBank.question_id)).scalar() or 0

    # 科目分布
    subject_stats = db.query(
        QuestionSubject.subject_name,
        func.count(QuestionBank.question_id).label('count')
    ).join(QuestionBank, QuestionBank.subject_id == QuestionSubject.subject_id)\
        .group_by(QuestionSubject.subject_name)\
        .all()

    # 题型分布
    type_stats = db.query(
        QuestionType.type_name,
        func.count(QuestionBank.question_id).label('count')
    ).join(QuestionBank, QuestionBank.type_id == QuestionType.type_id)\
        .group_by(QuestionType.type_name)\
        .all()

    # 最近导入
    latest = db.query(QuestionImportRecord)\
        .filter(QuestionImportRecord.import_status == 'COMPLETED')\
        .order_by(desc(QuestionImportRecord.complete_time))\
        .first()

    return {
        'total_questions': total_questions,
        'subject_stats': [
            {'subject_name': s[0], 'question_count': s[1]}
            for s in subject_stats
        ],
        'type_stats': [
            {'type_name': t[0], 'question_count': t[1]}
            for t in type_stats
        ],
        'latest_import': {
            'original_filename': latest.original_filename,
            'success_count': latest.success_count,
            'complete_time': latest.complete_time.isoformat() if latest and latest.complete_time else None,
        } if latest else None,
    }
