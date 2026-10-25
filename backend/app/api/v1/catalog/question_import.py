"""
题目导入API - 支持单题导入、批量文件导入、图片OCR导入、分离导入智能匹配
"""
import asyncio
import base64
import hashlib
import io
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from ....core.database import get_db
from ....core.config import settings
from ....core.security import get_current_user
from ....models.models import (
    QuestionBank, QuestionSubject, QuestionType, KnowledgePoint,
    QuestionDetailCategory, QuestionImage, QuestionImportRecord, SysUser,
    ExamPaper, PaperQuestionRelation, ExamPaperTag, QuestionKnowledge,
    QuestionGroup,
)
from ....schemas.schemas import SuccessResponse, ParseRequest, ParseResult, ParsedQuestion, ImageRef
from ....services.question_classifier import (
    QuestionClassifier, detect_subcategory_enhanced, UNCLASSIFIED,
)
from ....services import text_cache  # 文档提取文本缓存（P0 提速，260s→0.02s）
from ....services.question_ingest.excel_reader import (  # J-3：列名容错 + 表头探测 + GBK 嗅探
    get_field_value as _xlsx_field,          # 别名容忍的取值（同一列名多种写法）
    parse_excel_buffer as _parse_excel_buffer,   # 多 sheet + 表头行探测
    parse_csv_buffer as _parse_csv_buffer,       # utf-8-sig/gbk/gb18030/latin-1 嗅探
)
from ....services.question_ingest.docx_reader import (  # I-3：畸形 docx 三级容错（pure move 自本文件）
    _rels_base_dir,                     # _rels 目录推导（关系目标解析基准）
    _sanitize_docx_rels,                # 畸形 docx：清洗悬空 relationship 后重打包
    _extract_text_from_docx_raw_xml,    # 畸形 docx：纯 XML 兜底取文本
    _open_docx_resilient,               # 畸形 docx：弹性打开（直接→清洗→None）
    _extract_text_from_docx,            # docx 文本 + 图片占位符提取
)
from ....services.question_ingest.tags import (  # I-4：标签检测 + 自动建卷（pure move 自本文件）
    _auto_detect_tags,               # 文件/全文启发式提取 年份/考试类型/科目/完整卷/试卷名
    _detect_complete_paper,          # 完整试卷判定（连续题号 + 答案区）
    _extract_paper_name,             # 试卷名提取（书名号/模式/首行兜底）
    _get_or_create_import_paper,     # 按标签自动建/复用 ExamPaper（<5 题跳过）
    SUBJECT_NAME_MAP,                # 科目名称 → subject_id（随重度使用方搬迁，re-export 保持调用点零改动）
)
from ....services.question_ingest.images import (  # I-5：题目图提取/落盘 + [IMAGE:x_y] 占位符协议（pure move 自本文件）
    _extract_and_save_images,         # <img>/base64/[IMAGE:x_y] -> static/questions/{qid}/；SSRF + 路径穿越 + 大小防护
)
from ....services.question_ingest.pdf_reader import (  # I-6：PDF 提取全套（pure move 自本文件）
    _pdf_image_to_png,                # PDF 内嵌图片原始像素 -> PNG 字节（色彩空间/位深/尺寸/解压炸弹四道过滤）
    _extract_text_from_pdf,           # pdfplumber 主干（[IMAGE:x_y] 占位符 + 原位表格行）-> MinerU -> PaddleOCR 三级回退
    _extract_text_from_scanned_pdf,   # 扫描件 OCR（PaddleOCR 独立子进程隔离，防 3.13 进程内崩溃）
    _extract_images_from_pdf_page,    # 遍历页面 XObject 提取图片字节（PyPDF2 low-level API）
    _decode_pdf_image,                # PDF 图片 XObject -> PNG（DCTDecode 直通 / 原始像素由 PIL 编码）
    _pdf_has_images_only,             # 快速检测纯扫描件（有 XObject 且文本层 < 20 字符）
)
from ....services.question_ingest import pdf_reader as _pdf_reader  # I-6：_last_extract_engine 随平移迁至 pdf_reader（引擎标记读取点）
from ....services.mineru_service import (  # 扫描件三级回退链第一级（规格§5.2）
    extract_text_sync as mineru_extract_text_sync,
    is_enabled as mineru_is_enabled,
    health_check as mineru_health_cached,
)
from ....services.text_parser import (
    normalize_text_for_comparison,
    compute_text_similarity,
    fuzzy_detect_duplicate,
    smart_match_questions_answers,
    detect_subject_category,
    extract_question_blocks,
    extract_answer_from_lines,
    DEDUP_SIMILARITY_THRESHOLD,
    ContentCleaner,
    normalize_type_name,
    canonical_answer,
    _essay_norm_fp,
    _extract_options,
    _detect_question_type,
    detect_answer_conflicts,
    clean_question_text,
)

router = APIRouter(prefix="/api/questions/import", tags=["题目导入"])
logger = logging.getLogger(__name__)

# ============ 常量 ============
ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.docx', '.pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB — per-image size limit
MAX_BATCH_QUESTIONS = 500  # 单次批量最大题目数

# 题型名称标准化映射 — 统一从 text_parser 导入
# (删除本地 TYPE_MAP，使用 normalize_type_name 代替 _normalize_type_name)

# ============ 工具函数 ============

# ============ 难度唯一收口（P0-5） ============
# 背景：前端下拉用中文（简单/较易/中等/较难/困难），数据库列是 INTEGER。
#       历史代码存在两处解析：_normalize_question 内的 `int(diff_raw)`（有 try 兜底）
#       与 _upsert_question_core 内的 `int(question_data.get('difficulty', 3))`（**无任何保护**），
#       后者在用户于导入预览页编辑难度为"中等"后触发
#       `ValueError: invalid literal for int() with base 10: '中等'`，
#       导致整批导入在该题失败、试卷缺失题目。
# 原则：导入是批量作业，单题字段异常不得中断整批 —— 该函数**永不抛异常**。
_DIFFICULTY_NAME_MAP = {
    '简单': 1, '容易': 1, '入门': 1,
    '较易': 2, '一般': 2, '容易题': 2,
    '中等': 3, '普通': 3, '适中': 3,
    '较难': 4, '偏难': 4,
    '困难': 5, '难': 5, '较难题': 5,
}

# 题型守卫：主观题（无标准答案选项）在教师端不参与客观题难度筛选时的默认值
DEFAULT_DIFFICULTY = 3

# P3b：题型判定置信度低于此阈值即标记 need_review，交教师人工复核。
# 0.95 = 硬规则命中（选项/答案形态决定）；0.85/0.90 = 关键词命中；
# 0.70 = 缺答案时的关键词降级；0.40 = 纯兜底。
# 取 0.60：把「缺答案降级」与「纯兜底」纳入复核，关键词命中与硬规则不放进复核。
NEED_REVIEW_CONFIDENCE = 0.60


def coerce_difficulty(raw: Any, default: int = DEFAULT_DIFFICULTY) -> int:
    """把任意形态的难度值归一化为 1..5 的 int。**永不抛异常。**

    接受：None / '' / 3 / '3' / 3.0 / '中等' / '较难' / '难度4' / True 等。

    设计要点：
    - 唯一收口：所有 difficulty 入库点必须走本函数，禁止再散落 int() 强转
    - 名称→数字映射集中在 _DIFFICULTY_NAME_MAP，前端文案调整只改一处
    - 数字优先于名称："难度4" 抽出 4；纯名称走映射表；都无法识别落 default
    """
    if raw is None:
        return default
    # bool 是 int 的子类，但 True/False 显然是脏数据，按 default 处理
    if isinstance(raw, bool):
        return default
    if isinstance(raw, int):
        return max(1, min(5, raw))
    if isinstance(raw, float):
        try:
            return max(1, min(5, int(round(raw))))
        except (ValueError, OverflowError):
            return default
    # 容器类型（dict/list/tuple/set）走 str() 会捞出无关数字，纯属脏数据 → default
    if isinstance(raw, (dict, list, tuple, set)):
        return default
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            return default
    s = str(raw).strip()
    if not s:
        return default
    if s in _DIFFICULTY_NAME_MAP:
        return _DIFFICULTY_NAME_MAP[s]
    # 先尝试直接整数，再从混合串里抽数字（"难度4" / "第3题" / "3-中等"）
    try:
        return max(1, min(5, int(s)))
    except ValueError:
        pass
    m = re.search(r'\d+', s)
    if m:
        return max(1, min(5, int(m.group())))
    return default


def coerce_score(raw: Any, default: float = 1.0) -> float:
    """分值收口：接受 1 / '1' / 1.5 / None，恒返回 >0 的 float。**永不抛异常。**

    与 coerce_difficulty 同理：导入是批量作业，脏字段不得中断整批。
    """
    if raw is None or raw == '':
        return default
    try:
        v = float(raw)
    except (TypeError, ValueError):
        m = re.search(r'\d+(?:\.\d+)?', str(raw))
        if not m:
            return default
        try:
            v = float(m.group())
        except ValueError:
            return default
    return v if v > 0 else default


def dump_json_once(value: Any) -> Optional[str]:
    """把对象序列化为**单层** JSON 字符串（P0-6：修 preview_data 双重编码）。

    历史事故：preview_data 列存的是 `json.dumps(json.dumps(obj))` 的结果
    （数据库里长成 `"{\\"items\\": ...` 这种带转义引号的外层字符串），
    前端回读时只能拿到字符串而非对象，编辑结果无法落库。

    实现：循环剥离 JSON 字符串外层，直到不再能解析出字符串为止（上限 5 层，
    防构造性嵌套导致死循环），再统一序列化一次。
    对已正确的单层 JSON 输入是幂等的（不改变结果）。
    """
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode('utf-8')
        except UnicodeDecodeError:
            return None
    # 循环解包：处理历史双重/多重编码
    for _ in range(5):
        if not isinstance(value, str):
            break
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            break  # 不是 JSON 字符串，原样保留
        if isinstance(decoded, str):
            value = decoded   # 又剥掉一层，继续
            continue
        value = decoded       # 剥到真实对象了，停止
        break
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=False)


def load_json_lenient(raw: Any) -> Any:
    """P0-6 读取端：兼容单层与历史多重编码的 JSON 字段。

    `question_import_record.preview_data` / `error_messages` 历史上存在双重编码，
    前端回读时需要能取到真实对象而不是字符串。读取失败一律返回 None，不抛异常。
    """
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode('utf-8')
        except UnicodeDecodeError:
            return None
    if not isinstance(raw, str):
        return raw
    for _ in range(5):
        s = raw.strip()
        if not s:
            return None
        try:
            raw = json.loads(s)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(raw, str):
            return raw
    return None


# 各科目合法子科目名（与 question_classifier.SUB_CATEGORY_IDS 保持一致，用于校验显式子科目）
VALID_SUBCATEGORY_NAMES = {
    1: ["政治理论", "常识判断", "言语理解与表达", "数量关系", "判断推理", "资料分析", "知觉速度与准确性", "科学推理"],
    2: ["归纳概括", "综合分析", "提出对策", "应用文写作", "议论文写作"],
    3: ["职业素养", "基础知识", "基本警务能力"],
}


def _detect_subcategory(subject_id: int, content: str, type_name: str = '') -> str:
    """
    根据题目内容和科目自动推断子科目分类（增强版）。
    使用 QuestionClassifier 加权关键词+正则引擎。
    返回子科目名称，若无法判断则返回 '无'。
    """
    return detect_subcategory_enhanced(subject_id, content, type_name)


def _resolve_subcategory(subject_id: int, content: str, type_name: str = '', explicit: str = '') -> str:
    """解析子科目：显式子科目（来自 Excel/JSON 的「子科目」列/键）优先，否则自动推断。"""
    if explicit:
        name = str(explicit).strip()
        if name in VALID_SUBCATEGORY_NAMES.get(subject_id, []):
            return name
    return _detect_subcategory(subject_id, content, type_name)


def _subcategory_tuple(subject_id: int, content: str, type_name: str = '', explicit: str = '') -> tuple:
    """返回 (xingce, shenlun, gongzhuan) 三元组，非当前科目的恒为 '无'。"""
    sc = _resolve_subcategory(subject_id, content, type_name, explicit)
    return (
        sc if subject_id == 1 else '无',
        sc if subject_id == 2 else '无',
        sc if subject_id == 3 else '无',
    )


# ============ W2-1：科目/子科目建议（导入端点返回「建议 + 置信度」） ============
# 计划 v3 6.2/6.3：自动识别只做「预填建议」，教师手选永远压过自动识别。
# 用户已确认阈值：自动建议置信度 < 0.5 → 标 need_review 待人工复核。
SUBJECT_SUGGESTION_THRESHOLD = 0.5


def _build_subject_suggestion(text: str, manual: str = '') -> Dict[str, Any]:
    """构建科目建议 ``{name, confidence, matched_keywords}``（W2-1）。

    - ``manual`` 非空（教师手选/显式传参）→ **跳过自动识别**，置信度 1.0；
    - 否则走 ``detect_subject_category()``（W1-1：DB 驱动 + 置信度修正）；
    - 全 0 分（无关键词命中）→ ``name=''``、``confidence=0.0``，由调用方标
      ``need_review``。
    """
    if manual:
        return {'name': str(manual).strip(), 'confidence': 1.0, 'matched_keywords': []}
    det = detect_subject_category(text)
    return {
        'name': det.subject_name,
        'confidence': round(float(det.confidence), 2),
        'matched_keywords': list(det.matched_keywords or []),
    }


def _build_subcategory_suggestion(subject_id: Optional[int], content: str,
                                  manual: str = '') -> Dict[str, Any]:
    """构建子科目建议 ``{name, confidence}``（W2-1）。

    - ``manual`` 非空（前端显式子科目）→ 置信度 1.0；
    - 否则走三级分类引擎 ``classify()``（W1-2 单一引擎，真实 DB ID）；
    - 无法分类 → ``name=''``、``confidence=0.0``。
    """
    if manual:
        return {'name': str(manual).strip(), 'confidence': 1.0}
    if not subject_id:
        return {'name': '', 'confidence': 0.0}
    result = QuestionClassifier().classify(content, subject_id)
    name = result.sub_category_name
    if not name or name == UNCLASSIFIED:
        return {'name': '', 'confidence': 0.0}
    confidence = result.confidence
    if confidence <= 0.0:
        # classify() 成功分支的 confidence 承载考点置信度：子科目已命中但
        # 考点未命中时为 0.0。给保守基线 0.5（恰好不触发 need_review，
        # 又不虚高），定位是「建议预填 + 教师复核」。
        confidence = 0.5
    return {'name': name, 'confidence': round(float(confidence), 2)}


# I-7：考点关联 + 科目/题型取建（pure move 自本文件，原 :302/:336/:374）
# 本模块无 question_ingest 内部反向依赖，故可在文件头导入区直接引用。
from ....services.question_ingest.links import (
    _link_knowledge_points,               # 分类引擎 → QuestionKnowledge 关联（幂等、异常不阻断）
    _get_or_create_subject,               # 科目取建（强制走 SUBJECT_NAME_MAP 预定义 subject_id）
    _get_or_create_type,                  # 题型取建（type_code 带 subject_id 前缀，跨科目唯一）
)


# _normalize_type_name 已删除，统一使用 text_parser.normalize_type_name


def _normalize_question(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将原始行数据标准化为题目标准格式（J-3：列名容错 + 丢行可追溯）

    ★ 关键约束：返回值**必须保持 16 个键**且丢行时返回 None。
      历史实现返回 year/tags/paper_name/exam_province/exam_type/subcategory，
      若改用 excel_reader.normalize_question（仅 9 键、无题型判定、无答案归一化）
      会造成静默字段丢失 —— 那是回归而非优化。
      本函数只把「列名取值」换成容错查找，其余逻辑（题型判定 / canonical_answer /
      coerce_difficulty / 选项解析）全部保留。
    """
    content = _xlsx_field(row, 'question_content')
    answer = _xlsx_field(row, 'answer')
    if not content or not answer:
        # 保留 None 契约：调用方据此记 failed_count 并给出可见原因
        return None

    subject_name = _xlsx_field(row, 'subject_name') or '行测'
    raw_type = _xlsx_field(row, 'type_name')

    options = []
    for key in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
        opt_val = ''
        # 选项列容错：`选项A` / 裸 `A` 两种写法都认
        for hdr, val in row.items():
            from ....services.question_ingest.excel_reader import normalize_header as _nh
            if _nh(hdr) in (_nh(f'选项{key}'), _nh(key)):
                opt_val = str(val).strip() if val is not None else ''
                break
        if opt_val:
            options.append({'key': key, 'value': opt_val})

    if not options:
        opt_str = _xlsx_field(row, 'options')
        if opt_str:
            try:
                parsed = json.loads(opt_str)
                if isinstance(parsed, list):
                    options = parsed
            except (json.JSONDecodeError, TypeError):
                pass

    # 题型：通用'选择题'或缺失 → 用关键词工程细分单选/多选（避免'选择题'被归一化为单选）
    if not raw_type or raw_type in ('选择题',):
        # ★ 返回的是 (type_name, confidence) 元组，必须解包
        type_name, _conf0 = _detect_question_type(content, options, answer)
    else:
        type_name = raw_type

    # 客观选择题答案归一化（A、B → AB；对/错 → A/B），论述/写作保留原文
    if type_name in ('单选题', '多选题', '判断题', '选择题'):
        norm = canonical_answer(answer)
        if norm:
            answer = norm

    # 难度：走唯一收口 coerce_difficulty（不再用会抛 ValueError 的裸 int()）
    difficulty = coerce_difficulty(_xlsx_field(row, 'difficulty'))

    try:
        score = float(_xlsx_field(row, 'score') or 1.0)
    except ValueError:
        score = 1.0

    try:
        year = int(_xlsx_field(row, 'year') or 0) or None
    except ValueError:
        year = None

    return {
        'subject_name': subject_name,
        'type_name': type_name,
        'question_content': content,
        'options': options if options else None,
        'answer': answer,
        'answer_analysis': _xlsx_field(row, 'answer_analysis'),
        'difficulty': difficulty,
        'score': score,
        'year': year,
        'source': _xlsx_field(row, 'source'),
        'tags': _xlsx_field(row, 'tags'),
        'knowledge_point': _xlsx_field(row, 'knowledge_point'),
        'paper_name': _xlsx_field(row, 'paper_name'),
        'exam_province': _xlsx_field(row, 'exam_province'),
        'exam_type': _xlsx_field(row, 'exam_type'),
        'subcategory': _xlsx_field(row, 'subcategory'),
    }


# ============ API 端点 ============

def _normalize_requirements(raw: Any) -> str:
    """把解析器给的「题目要求」统一成 TEXT 落库。

    解析器实测会产出两种形态，必须都支持：
      · list —— 带编号分点的要求，如 ['（1）紧扣资料，内容全面；', '（2）不超过500 字']
      · str  —— 纯文本要求，如 '全面、准确、有条理。不超过250 字。'
    另有 None / 空数组 / 非预期结构。

    统一按换行拼接：既保住分点结构（可检索、可比对），又不丢原始分点符号。
    空值一律返回空串 —— 缺要求就留空，绝不伪造。
    """
    if raw is None:
        return ''
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, (list, tuple)):
        parts = []
        for item in raw:
            if item is None:
                continue
            text = item if isinstance(item, str) else str(item)
            text = text.strip()
            if text:
                parts.append(text)
        return '\n'.join(parts)
    # 非预期结构：尽力转字符串，但不猜测语义
    return str(raw).strip()


def _persist_group_images(group) -> None:
    """题组图片落盘 + 回写 shared_content / shared_content_images（J-1-1）。

    必须在 db.add() + db.flush() 之后调用 —— 图片要落到 {group.id}/ 子目录下。

    为什么每个建组点都要调：
      真实数据里 21 个题组全是 material/scenario，由
      _detect_and_link_composite_groups 两层兜底创建；申论
      _get_or_create_shenlun_material_group 目前一条都没建。
      只接申论那条 = 接了个死路径，裂图照旧。

    失败绝不阻塞建组：题组本身有价值，不能因为一张图回滚整批导入。
    """
    try:
        from ....services.question_ingest.images import save_images_for_group
        raw = group.shared_content or ''
        if '[IMAGE:' not in raw:
            return
        new_text, urls = save_images_for_group(raw, group.id)
        if new_text != raw:
            group.shared_content = new_text
        if urls:
            import json as _json
            group.shared_content_images = _json.dumps(urls, ensure_ascii=False)
        logger.debug("[group-images] 题组#%s 图片回写 %d 张", group.id, len(urls))
    except Exception as e:
        logger.warning("[group-images] 题组#%s 图片落盘失败，不影响建组: %s",
                       getattr(group, 'id', '?'), e)


def _digest_for_group_dedup(text: str) -> str:
    """题组幂等键用的规范化指纹 —— **对图片状态不敏感**。

    为什么必须剥离图片标记（J-1-1 引入的坑）：
      建组时 shared_content 里的 [IMAGE:x] 会被换成 <img src=...>，
      若指纹算在替换之前、而库里存的是替换之后的文本，则下次导入同一份材料
      时「读库重算指纹」与「本次算指纹」必然对不上 —— 同一份材料会重复建组。
      故两侧统一先剥离 [IMAGE:...] 与 <img ...> 再取 SHA1。
    """
    normalized = re.sub(r'\[IMAGE:[^\]]+\]', '', text or '')
    normalized = re.sub(r'<img[^>]*>', '', normalized)
    normalized = re.sub(r'\s+', '', normalized)
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:16]


def _get_or_create_shenlun_material_group(db: Session, material: str,
                                         subject_name: str,
                                         source_tag: str) -> Optional[int]:
    """申论「给定材料」落 question_groups，返回 group_id（无材料则 None）。

    为什么必须去重复用而不是每题建组：
      申论一份卷的「给定资料1..N」是**所有小题共享**的上下文。若逐题建组，
      同一份材料会被复制 N 份，题库检索时材料无法跨题复用，且体积翻倍。
      故用材料内容指纹（SHA1 前 16 位）做幂等键：同一份材料只建一行，
      各小题通过 question_bank.group_id 指向它。

    指纹只取归一化文本（去空白），避免 PDF 换行差异导致同一材料被当成多份。
    """
    text = (material or '').strip()
    if not text:
        return None
    digest = _digest_for_group_dedup(text)

    # 同批导入里重复查库代价高，先在本次请求内缓存
    cache_key = 'shenlun_group_' + digest
    cached = _SHENLUN_GROUP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # 跨批复用：库内已存在同指纹材料则直接挂上去
    # ★ J-1-3 修复：用 SHA1 全文指纹替代 LIKE '%前60字%'，消除误合并
    existing = None
    for g in db.query(QuestionGroup).filter(QuestionGroup.group_type == 'shenlun_material').all():
        g_digest = _digest_for_group_dedup(str(g.shared_content or ''))
        if g_digest == digest:
            existing = g
            break
    if existing is not None:
        _shenlun_cache_put(cache_key, existing.id)
        return existing.id

    group = _upsert_question_group(
        db,
        group_type='shenlun_material',
        shared_content=text,
        subject=subject_name or '申论',
        source=source_tag or '',
        title=(subject_name + ' 给定材料')[:200],   # 申论组标题是「科目名 + 给定材料」，非 shared_content 前 200 字
    )
    _shenlun_cache_put(cache_key, group.id)
    return group.id


def _get_or_create_group_by_material(db: Session, material: str,
                                     group_type: str, subject_name: str,
                                     source_tag: str) -> Optional[int]:
    """按材料内容指纹建组，返回 group_id。`_get_or_create_shenlun_material_group`
    的行测/公专对应物：那份把 group_type 写死为 `shenlun_material`、标题写死为
    「科目名 给定材料」，而行测资料分析的组类型来自
    `XINGCE_SECTION_GROUP_TYPE`（data_analysis/passage/scenario/material），故需参数化。

    去重口径与上者完全一致（SHA1 前 16 位归一化指纹），保证 N 道小题共享同一份
    材料时只建一行 `question_groups`，不产生 N 份副本。
    """
    text = (material or '').strip()
    if not text:
        return None
    digest = _digest_for_group_dedup(text)

    cache_key = f'material_group_{group_type}_' + digest
    cached = _SHENLUN_GROUP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    for g in db.query(QuestionGroup).filter(QuestionGroup.group_type == group_type).all():
        if _digest_for_group_dedup(str(g.shared_content or '')) == digest:
            _shenlun_cache_put(cache_key, g.id)
            return g.id

    group = _upsert_question_group(
        db,
        group_type=group_type,
        shared_content=text,
        subject=subject_name or '',
        source=source_tag or '',
    )
    _shenlun_cache_put(cache_key, group.id)
    return group.id


# 同一批导入内多题共享同一份材料，避免重复 flush
# ★ J-1-4 修复：限制缓存大小，防止无界增长
_SHENLUN_GROUP_CACHE: Dict[str, int] = {}
_SHENLUN_GROUP_CACHE_MAX = 256

def _shenlun_cache_put(key: str, value: int):
    if len(_SHENLUN_GROUP_CACHE) >= _SHENLUN_GROUP_CACHE_MAX:
        # 淘汰最旧的一半
        keys = list(_SHENLUN_GROUP_CACHE.keys())
        for k in keys[:len(keys)//2]:
            del _SHENLUN_GROUP_CACHE[k]
    _SHENLUN_GROUP_CACHE[key] = value


# I-7：单题/行测落库 + 去重检测（pure move 自本文件，原 :446/:479/:722/:3410）
# ★ 导入位置约束（**非逻辑变更**）：`upsert.py` 反向依赖本文件的
#   `coerce_difficulty` / `NEED_REVIEW_CONFIDENCE` / `_subcategory_tuple` /
#   `_normalize_requirements` / `_get_or_create_shenlun_material_group`，
#   故本 import 必须置于上述符号定义之后，**不能**提到文件头 —— 否则
#   `question_ingest` 包初始化时 upsert 会撞上「半初始化的 question_import」而 ImportError。
from ....services.question_ingest.upsert import (
    _detect_duplicate,                    # 精确 + 模糊（>= DEDUP_SIMILARITY_THRESHOLD）去重
    _get_duplicate_info,                  # 去重详情（前端展示用）
    _upsert_question_core,                # 公专/申论单题入库核心（供 /single 与 /batch-parsed 复用）
    _upsert_xingce_question,              # 行测单题入库（全程不 commit，事务边界归调用方）
)

# I-8：题组建组单一入口（原 :513 / :641 / :698 三处 QuestionGroup(...) 收敛）
# ★ 同款导入位置约束（**非逻辑变更**）：`groups.py` 反向依赖本文件的
#   `_persist_group_images`（题组图片落盘 + 回写），故本 import 必须置于其定义之后 ——
#   提到文件头会让 question_ingest 在 question_import 半初始化时 ImportError。
from ....services.question_ingest.groups import (
    _upsert_question_group,               # 唯一建组入口（add → flush → 图片落盘，参数化 group_type）
)


# ============ 测试模板数据防御（问题1-R3 防呆闸门） ============
# 历史事故：backend/tests/test_batch_parsed_import.py 曾直连真实库，断言失败后
# 清理不执行，UTB 模板垃圾题（"UTB{8位hex}"标记 + "人民警察基本素养测试要点N"）
# 污染生产库。此闸门在入库前拦截同类数据；真实公安题目不含这些标记（920题实测）。
_TEST_UTB_RE = re.compile(r'UTB[a-f0-9]{8,}', re.IGNORECASE)
_TEST_KEYWORD = '测试要点'


def _is_test_garbage(q: Dict[str, Any]) -> bool:
    """检测题目数据是否为自动化测试模板泄漏（UTB 标记 / 测试要点模板）"""
    blob_parts = [str(q.get('question_content') or ''),
                  str(q.get('answer_analysis') or '')]
    for o in (q.get('options') or []):
        if isinstance(o, dict):
            blob_parts.append(str(o.get('value') or ''))
        else:
            blob_parts.append(str(o))
    blob = ' '.join(blob_parts)
    return bool(_TEST_UTB_RE.search(blob) or _TEST_KEYWORD in blob)


# ============ B2 复合题（题组）规则引擎识别（方案 v1.0 层1 规则集） ============
# 题组仅为展示聚合视图（v1.1 §7.5）：小题仍以扁平题目参与组卷/答题/计分。
# 规则集已抽至 services/composite_matcher.py：题号范围/材料/情境/文章四类标识，
# 避免识别逻辑散落在 API 层（单一事实来源）。


def _extract_first_qnum(content: str):
    """提取题干中第一个题号（复用 text_parser 统一题号提取器，禁止另写解析）"""
    try:
        from ....services.text_parser import extract_question_numbers
        nums = extract_question_numbers(content or '')
        return nums[0].number if nums else None
    except Exception:
        return None


def _link_shenlun_material_groups(db: Session, items: List[Dict[str, Any]],
                                  id_map: Dict[int, int], subject_name: str,
                                  source_tag: str) -> int:
    """C 修复：申论「给定资料N」材料组建组并回填 group_id。

    _detect_and_link_composite_groups 只认公专/行测材料头（「回答第X-Y题」），
    申论材料（「给定资料1..N」）经 material_text 字段传来但无人建组，
    导致教师端/学生端/管理员端的题组材料弹窗拿不到材料（图 5 缺失）。

    复用 confirm 路径的 _get_or_create_shenlun_material_group（内容指纹幂等），
    同一份材料只建一行，各小题 group_id 指向它。
    返回挂载的小题数；任何异常由调用方兜底（不影响导入）。
    """
    from ....models.models import QuestionBank as _QB

    # P3-14 灰度开关：关闭时保留旧的解析/建组行为（不建组、不挂 group_id）。
    if not settings.MATERIAL_OWNERSHIP_V2:
        return 0

    linked = 0
    # D 修复：文档级材料。申论整卷「给定资料1..N」只挂在第一题（解析器省内存设计），
    # 同卷小题 material_text 为空——必须继承文档级材料建组，否则其他子题成为
    # 「无头苍蝇」（教师端无材料可看）。
    doc_mat = ''
    for it in items or []:
        _m = (it.get('material_text') or '').strip()
        if _m and not doc_mat:
            doc_mat = _m
    for idx, item in enumerate(items or []):
        mat = (item.get('material_text') or '').strip()
        if not mat and doc_mat and (
                item.get('format') == 'essay' or item.get('subject_category') == '申论'):
            mat = doc_mat
        if len(mat) < 20:
            continue
        gid = _get_or_create_shenlun_material_group(db, mat, subject_name, source_tag)
        if gid is None:
            continue
        qid = id_map.get(idx)
        if qid is None:
            continue
        q = db.query(_QB).filter(_QB.question_id == qid).first()
        # W1 修复：不可改回 `is None`——group_id 列默认值是 0（models.py:214），
        # 全库 IS NULL 计数为 0，该判断会静默失效，使下方文档级材料继承永不生效。
        if q is not None and not q.group_id:
            q.group_id = gid
            linked += 1
    return linked


def _detect_and_link_composite_groups(db, ok_items, qid_by_index, subject_name, source_tag=''):
    """批内复合题识别：返回 (groups_created, members_linked)。

    算法（批内作用域，调用方统一 commit 保证事务安全）：
    1. 为每个成功入库题提取题号（question_number）
    2. 用 composite_matcher 规则集识别题组头（题号范围/材料/情境/文章标识）
    3. 建 question_groups 行（shared_content=头题题干），头题与推断的小题
       全部挂 group_id / question_level=2 / sort_order / question_number
    """
    from ....services.composite_matcher import match_group_head, infer_member_qnums, semantic_grouping

    # P3-14 灰度开关：关闭时保留旧的解析/建组行为（不建组、不挂 group_id）。
    if not settings.MATERIAL_OWNERSHIP_V2:
        return 0, 0
    if not settings.COMPOSITE_QUESTION_ENABLED:
        return 0, 0
    if not ok_items:
        return 0, 0

    # 预提取题号
    numbered = []  # (idx, qid, qnum)
    for i, q in enumerate(ok_items):
        qid = qid_by_index.get(i)
        if not qid:
            continue
        qn = _extract_first_qnum(q.get('question_content') or '')
        numbered.append((i, qid, qn))
    qnum_map = {qid: (qn if qn is not None else 9999) for _, qid, qn in numbered}

    def _group_shared_content(q: Dict[str, Any]) -> str:
        """题组材料优先取解析器切出的 material_text / shared_content。

        旧实现固定取头题 `question_content`：材料正文已经被 text_parser 剥离到
        `material_text`，再用题干当组材料，会让「材料+题干」在详情里重复显示，
        而真正的材料在多题共享时又会串到别的组（P3-9）。
        """
        return (q.get('material_text') or q.get('shared_content')
                or q.get('question_content') or '')

    groups_created, members_linked = 0, 0
    # ★ P3-9：claimed 必须拆成两个集合。旧实现把「批内下标 i」与「题目ID jid」
    #   塞进同一个 set —— 两者值域重叠（内存库 qid 从 1 递增，正是下标值域），
    #   于是 `if i in claimed` 会把「下标恰好等于前一组某成员 qid」的合法组头
    #   当成已认领而跳过，第二组凭空消失；`jid not in claimed` 又漏掉用下标
    #   记录的认领，可能让同一题被挂进两个组。故：
    #   · claimed_indices 只存批内下标；claimed_ids 只存 question_id。
    claimed_indices = set()
    claimed_ids = set()
    for i, q in enumerate(ok_items):
        if i in claimed_indices:
            continue
        head_hit = match_group_head(q.get('question_content') or '')
        if not head_hit:
            continue
        group_type, qnum_range = head_hit
        head_qid = qid_by_index.get(i)
        if not head_qid:
            continue
        # 组头本身已被前一组认领 → 它是子题，不能再开新组，否则会把它从
        # 前一组抢走，破坏「一个子题只属于一个组」。
        if head_qid in claimed_ids:
            continue
        head_qn = qnum_map.get(head_qid)
        head_qn = None if head_qn == 9999 else head_qn

        # 候选小题：批内其他未挂组的题号（按 qid 判重，不能用下标）
        candidate_qnums = [qn for j, jid, qn in numbered
                           if j != i and jid not in claimed_ids and qn is not None]
        member_qnums = infer_member_qnums(head_qn, candidate_qnums, qnum_range)
        if not member_qnums:
            # 无小题可挂 → 不建组（避免空题组）
            continue

        # 题号 → qid 映射（用于把 member_qnums 转为 qid）
        qn_to_qid = {qn: jid for j, jid, qn in numbered if qn is not None}
        member_ids = [head_qid]
        for mqn in member_qnums:
            jid = qn_to_qid.get(mqn)
            if jid and jid not in claimed_ids and jid not in member_ids:
                member_ids.append(jid)

        # W3：member_qnums 非空 ≠ 能挂上题——对应 qid 可能已被前面的组 claimed 掉，
        # 结果只剩头题（实测公专 21 个组每组恰好 1 题）。这种组不携带任何信息：
        # 其 shared_content 本就取自头题题干（:784），单成员时材料与题干重复，
        # 不建组不会丢内容，而建组会让详情弹窗把同一段文字显示两遍。
        # 跳过时也不写 claimed，这些题仍可被下面的层2 语义兜底接管。
        if len(member_ids) < 2:
            logger.info("[composite] 跳过单题组：头题 qid=%s 推断题号 %s 无可挂成员",
                        head_qid, member_qnums[:10])
            continue

        claimed_indices.add(i)
        claimed_ids.add(head_qid)
        for jid in member_ids[1:]:
            claimed_ids.add(jid)

        group = _upsert_question_group(
            db,
            group_type=group_type,
            shared_content=_group_shared_content(q),
            subject=subject_name or '公专',
            source=source_tag or q.get('paper_name', ''),
        )
        groups_created += 1

        # 写入组字段（按题号升序排列）
        for sort_idx, mid in enumerate(sorted(member_ids, key=lambda mid_: qnum_map.get(mid_, 9999))):
            db.query(QuestionBank).filter(
                QuestionBank.question_id == mid).update({
                    'group_id': group.id,
                    'question_level': 2,
                    'sort_order': sort_idx + 1,
                }, synchronize_session=False)
            members_linked += 1
        logger.info(f"[composite] 题组#{group.id} 创建：{len(member_ids)} 题挂组 "
                    f"(type={group_type}, 题号 {member_qnums[:10]})")

    # ===== 层2 语义增强兜底：对层1 未命中的题目做分组（无显式标识的复合题）=====
    unclaimed = [(i, q) for i, q in enumerate(ok_items) if i not in claimed_indices]
    if unclaimed:
        unclaimed_questions = [q for _, q in unclaimed]
        suggestions = semantic_grouping(unclaimed_questions)
        for sug in suggestions:
            head_local = sug.get('head_index')
            member_locals = sug.get('member_indices') or []
            if head_local is None or not member_locals:
                continue
            # 映射回 ok_items 原始索引
            head_idx = unclaimed[head_local][0]
            head_qid = qid_by_index.get(head_idx)
            if not head_qid:
                continue
            member_qids = []
            for ml in member_locals:
                if 0 <= ml < len(unclaimed):
                    mqid = qid_by_index.get(unclaimed[ml][0])
                    if mqid:
                        member_qids.append(mqid)
            if not member_qids:
                continue

            group = _upsert_question_group(
                db,
                group_type=sug.get('group_type') or 'material',
                shared_content=_group_shared_content(ok_items[head_idx]),
                subject=subject_name or '公专',
                source=source_tag or ok_items[head_idx].get('paper_name', ''),
            )
            groups_created += 1

            member_ids = [head_qid] + member_qids
            for sort_idx, mid in enumerate(sorted(member_ids, key=lambda mid_: qnum_map.get(mid_, 9999))):
                db.query(QuestionBank).filter(
                    QuestionBank.question_id == mid).update({
                        'group_id': group.id,
                        'question_level': 2,
                        'sort_order': sort_idx + 1,
                    }, synchronize_session=False)
                members_linked += 1
            logger.info(f"[composite] 语义增强题组#{group.id} 创建：{len(member_ids)} 题挂组 "
                        f"(type={sug.get('group_type')}, conf={sug.get('confidence')})")

    return groups_created, members_linked


def _build_preview_groups(preview_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把预览题目按「给定材料」聚合成题组，供前端渲染复合题总题干。

    背景（用户实测缺陷 D1）
    ----------------------
    申论是**复合题结构**：一份「给定资料1..N」被多道小题共享。
    旧预览把每道小题渲染成独立卡片，用户只能看到孤立的小题，
    完全看不到总题干，无从判断小题在问什么（用户原话：
    「缺失总题干信息，针对复合题目请设计好怎么在导入匹配后总体预览的题目排版」）。

    分组规则
    --------
    · 有``material_text`` 的题按材料内容归为同一组（一份材料只存一次）
    · 无材料的单选题**各自成组**，``material_length=0``，
      前端据此不渲染材料头，行为与旧版完全一致（零回归）
    · 组内题目保持原有题号顺序

    返回结构::

        [{'group_key','material_text','material_titles','material_length',
          'question_count','questions':[...]}, ...]
    """
    groups: List[Dict[str, Any]] = []
    by_key: Dict[str, Dict[str, Any]] = {}
    # ★ 先扫一遍取「文档级材料」。
    #   解析器为省内存**只把 material_text 挂在第一题上**（实测安徽A卷：
    #   Q1 带 7402 字材料，Q2/Q3/Q4 全空）。若按逐题是否有材料分组，
    #   4 道共享同一份给定资料的小题会被拆成 4 组（实测 groups=4，qcount 均为1），
    #   总题干就又看不见了 —— 用户缺陷 D1 直接复发。
    #   同一份 PDF 里的申论小题共享同一份「给定资料1..N」，故文档级材料即全卷通用。
    doc_mat = ''
    doc_titles: List[str] = []
    for it in preview_items or []:
        m = (it.get('material_text') or '').strip()
        if m and not doc_mat:
            doc_mat = m
            doc_titles = it.get('material_titles') or []
    doc_key = ''
    if doc_mat:
        doc_key = 'm_' + hashlib.sha1(
            re.sub(r'\s+', '', doc_mat).encode('utf-8')).hexdigest()[:16]

    for item in preview_items or []:
        mat = (item.get('material_text') or '').strip()
        is_essay = (item.get('format') == 'essay')
        if not mat and doc_mat and is_essay:
            # 同卷申论小题继承文档级材料（Q2..QN）
            mat = doc_mat
            if not item.get('material_titles') and doc_titles:
                item['material_titles'] = list(doc_titles)
        if mat:
            # 归一化后取指纹，避免同一份材料因换行差异被拆成多组
            key = 'm_' + hashlib.sha1(
                re.sub(r'\s+', '', mat).encode('utf-8')).hexdigest()[:16]
        else:
            # 无材料：按题号独立成组，绝不把不相干的题凑成一组
            key = 'q_%s' % (item.get('question_number')
                            or item.get('sort_order') or len(groups))
        grp = by_key.get(key)
        if grp is None:
            grp = {
                'group_key': key,
                'material_text': mat,
                'material_titles': item.get('material_titles') or [],
                'material_length': len(mat),
                'question_count': 0,
                'questions': [],
            }
            by_key[key] = grp
            groups.append(grp)
        grp['questions'].append(item)
        grp['question_count'] += 1
        # 同组内后续题若未带材料信息，以首题为准补齐
        if not grp['material_text'] and mat:
            grp['material_text'] = mat
            grp['material_length'] = len(mat)
        if not grp['material_titles'] and item.get('material_titles'):
            grp['material_titles'] = item['material_titles']
    return groups


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
    - question_type_detail: 题型（选择题/单选题/多选题/论述题/写作题等）
    - options: 选项列表 [{"key":"A","value":"..."}]
    - difficulty: 难度 1-5
    - score: 分值

    实现：核心入库逻辑已抽取为 _upsert_question_core（与 /batch-parsed 共享），
    本端点仅负责单题导入记录与事务提交。
    """
    try:
        result = _upsert_question_core(db, current_user, question_data)
        if result.get('import_status') == 'DUPLICATE':
            # 与原行为一致：重复题不做任何写库
            return result
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

        # 单题录入完成后同样广播同步事件（与批量导入一致），通知三端刷新。
        # 只含统计信息，不含题目正文；广播失败不阻断返回。
        try:
            from ....services.scheduler import _broadcast_sync
            _broadcast_sync(
                "题目更新",
                {
                    "scope": "question_bank",
                    "action": "import_single",
                    "count": 1,
                    "subject_id": question_data.get('subject_id') or None,
                },
            )
        except Exception as e:
            logger.warning(f"[import] 广播单题导入完成事件失败(非阻断): {e}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"单题导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/batch-parsed", summary="批量导入已解析题目（单请求·双轨入库：题库+试卷）")
async def batch_import_parsed(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量入库前端已解析/已匹配的题目 —— 对应《双轨入库》流程图。

    解决两个问题：
      1. 前端逐题循环 POST /single（97题→97请求）触发限流429；
         本端点单次请求承载全部题目，服务端单事务处理。
      2. 分离导入路径此前从不创建试卷；本端点按"检测层"判定试卷文档后，
         自动创建/复用 ExamPaper(DRAFT) 并批量建立 PaperQuestionRelation，
         使导入成果同步出现在"试卷管理"。

    请求体:
    {
      "paper_name": "2016江西招警考试《人民警察基础知识》真题",
      "subject_category": "公专",
      "import_mode": "separate",           # combined | separate
      "match_rate": 100.0,                  # 可选，用于摘要展示
      "questions": [ { ...与 /single 字段一致... }, ... ]
    }

    返回（对应"导入结果展示"原型）:
    {total, success_count, duplicate_count, need_confirm_count, failed_items[],
     new_question_ids[], reused_question_ids[], paper_id?, paper_name?, match_rate, message}
    """
    paper_name = (payload.get('paper_name') or '').strip()
    mode = (payload.get('import_mode') or payload.get('mode') or 'combined').strip()
    try:
        match_rate = float(payload.get('match_rate') or 0)
    except (TypeError, ValueError):
        match_rate = 0.0
    items = payload.get('questions') or []
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="questions 不能为空")
    if len(items) > 500:
        raise HTTPException(status_code=400, detail="单次最多导入500题，请分批操作")

    # ★ RC-5 修复：blocked 闸门 —— 任一题 blocked=true 则整批拒绝，零写入
    _BLOCK_LABEL = {
        'missing_score': '缺少分值信息',
        'answer_block_count_mismatch': '答案段数与题目数不匹配',
        'answer_missing_for_question': '答案卷缺少该题号',
        'stem_fingerprint_mismatch': '题干与答案卷不匹配（可能传错文件）',
        'score_mismatch': '题目与答案分值不一致',
    }
    for _q in items:
        if _q.get('blocked'):
            _reasons = _q.get('block_reasons') or []
            _cn = [_BLOCK_LABEL.get(r, r) for r in _reasons]
            raise HTTPException(
                status_code=409,
                detail=f"存在阻断问题，无法入库：{'；'.join(_cn)}。已阻断 {sum(1 for x in items if x.get('blocked'))} 题，请核对原卷后重新导入。"
            )

    ok_ids: List[int] = []
    reused_ids: List[int] = []
    ok_items: List[Dict[str, Any]] = []  # 成功入库的原payload（用于缺答案/解析提示）
    failed_items: List[Dict[str, Any]] = []
    need_confirm = 0
    need_confirm_items: List[Dict[str, Any]] = []  # P0-3: 结构化异常题清单（含题号/类型/原因，供前端定位）
    backfill_count = 0  # A2: 重复题回填缺失字段的题数
    default_subject = (payload.get('subject_category') or '').strip()

    # ===== A1 元数据自动注入（根因修复）=====
    # 此前 _auto_detect_tags 只在建卷判断处调用，提取的年份/省份/考试类型
    # 从未写入题目行，导致 source/year 为空（192题无法追溯来源的根因）。
    # 现提前计算并注入每题 payload（payload 自带值优先，setdefault 语义）。
    _joined_head = ' '.join((q.get('question_content') or '')[:150] for q in items[:20])
    auto_tags = _auto_detect_tags(paper_name or _joined_head[:60], _joined_head)

    # ===== 静默错答预检（答案字段 vs 解析正文声明） =====
    # 字段完整率对"错答案"完全免疫：有答案就能通过完整率，哪怕答案是从干扰项
    # 或下一题取错的。整批一次性检测，按题号建索引，供下方循环 O(1) 查询。
    # 不自动改写答案（源数据可能自相矛盾），只标记出来交人工复核。
    _conflict_by_qn: Dict[Any, Dict[str, Any]] = {}
    try:
        for _c in detect_answer_conflicts(items):
            _conflict_by_qn[_c.get('question_number')] = _c
        if _conflict_by_qn:
            logger.warning(
                f"[batch-parsed] 预检到 {len(_conflict_by_qn)} 处答案与解析声明不一致，"
                f"题号: {list(_conflict_by_qn)[:20]}"
            )
    except Exception as e:  # noqa: BLE001 — 预检绝不能阻断导入
        logger.warning(f"答案一致性预检异常（已忽略）: {e}")
    _inject_source = ''.join(
        p for p in (auto_tags.get('exam_province', ''), auto_tags.get('exam_type', '')) if p
    )
    _inject_year = auto_tags.get('exam_year')

    for idx, q in enumerate(items):
        if not isinstance(q, dict):
            failed_items.append({'index': idx, 'question_number': str(idx + 1), 'reason': '题目数据格式异常'})
            continue
        q.setdefault('paper_name', paper_name or '批量解析导入')
        q.setdefault('subject_category', default_subject or '公专')
        q.setdefault('import_mode', mode)
        if _inject_source:
            q.setdefault('source', _inject_source)
        if _inject_year:
            q.setdefault('year', _inject_year)
        # P0-3: 提取题号用于异常题定位（题干无题号时回退为序号 idx+1）
        _qn = _extract_first_qnum(q.get('question_content') or '')
        _qn_label = str(_qn) if _qn is not None else str(idx + 1)
        # 测试模板防御（问题1-R3）：命中即拒收，不入库
        if _is_test_garbage(q):
            failed_items.append({
                'index': idx,
                'question_number': _qn_label,
                'reason': 'test_pattern_detected: 检测到测试模板数据(UTB标记/测试要点模板)，拒绝入库',
            })
            continue
        
        # ===== 新增：重新验证题目类型 =====
        content = q.get('question_content', '')
        options_raw = q.get('options', [])
        answer = q.get('answer', '')
        
        # 提取选项文本
        option_texts = []
        for opt in options_raw:
            if isinstance(opt, dict):
                option_texts.append(opt.get('value', ''))
            else:
                option_texts.append(str(opt))
        
        # 调用后端识别逻辑
        from ....services.text_parser import _detect_question_type
        detected_type, confidence = _detect_question_type(content, option_texts, answer)
        
        # 如果前端传递的类型与后端识别不一致，使用后端识别结果
        frontend_type = q.get('question_type_detail', '')
        if frontend_type != detected_type:
            direction = f"{frontend_type}→{detected_type}"
            logger.warning(f"[batch-parsed] 题目{idx}类型修正: {direction} "
                          f"(置信度: {confidence:.2f}, 答案: '{answer[:20]}')")
            q['question_type_detail'] = detected_type
        
        try:
            r = _upsert_question_core(db, current_user, q)
            qid = r['question_id']
            if r['import_status'] == 'DUPLICATE':
                reused_ids.append(qid)
                if r.get('backfilled_fields'):
                    backfill_count += 1
            else:
                ok_ids.append(qid)
                ok_items.append(q)
            ans = (q.get('answer') or '').strip()
            conf = q.get('confidence')
            _confirm_reason = None
            # 静默错答：答案字段与解析正文声明矛盾（字段完整率无法发现此类问题）
            # 预检按题号索引；题号缺失时退化为逐题检测，避免 None 键互相覆盖导致漏检
            _cf = _conflict_by_qn.get(q.get('question_number')) if q.get('question_number') is not None else None
            if _cf is None:
                try:
                    _hit = detect_answer_conflicts([q])
                    _cf = _hit[0] if _hit else None
                except Exception:  # noqa: BLE001
                    _cf = None
            if _cf is not None:
                _confirm_reason = '答案与解析不一致'
            elif not ans or ans == '待补充':
                _confirm_reason = '缺答案'
            elif isinstance(conf, (int, float)) and conf < 0.5:
                _confirm_reason = '低置信度'
            if _confirm_reason:
                need_confirm += 1
                _item = {
                    'index': idx,
                    'question_number': _qn_label,
                    'reason': _confirm_reason,
                }
                if _cf is not None:
                    _item['answer'] = _cf.get('answer')
                    _item['declared_in_analysis'] = _cf.get('declared_in_analysis')
                need_confirm_items.append(_item)
        except HTTPException as he:
            failed_items.append({'index': idx, 'question_number': _qn_label, 'reason': str(he.detail)})
        except Exception as e:  # noqa: BLE001 — 单题失败不阻断整批
            failed_items.append({'index': idx, 'question_number': _qn_label, 'reason': str(e)[:200]})

    # ===== 检测层 → 双轨入库层 =====
    # auto_tags 已在循环前计算并注入题目行（A1），此处直接复用
    joined_head = _joined_head
    is_paper_doc = (
        bool(auto_tags.get('is_complete_paper'))
        or bool(auto_tags.get('exam_year') and auto_tags.get('exam_type'))
        # 分离导入(题库文档+答案文档)本身即"成卷意图"：≥5题且给出匹配率时按试卷处理
        or (mode == 'separate' and (len(ok_ids) + len(reused_ids)) >= 5 and match_rate > 0)
    )

    paper_id: Optional[int] = None
    linked = 0
    if is_paper_doc and (ok_ids or reused_ids):
        try:
            paper = _get_or_create_import_paper(
                db, current_user, auto_tags,
                paper_name or (auto_tags.get('paper_name') or '导入试卷'),
                question_count=len(ok_ids) + len(reused_ids))
            if paper is None:
                # 题目数量少于阈值，不创建试卷
                logger.info(f"[batch-parsed] 题目数量({len(ok_ids) + len(reused_ids)})少于阈值，跳过试卷创建")
            else:
                existing_rel_qids = {
                    r.question_id for r in db.query(PaperQuestionRelation).filter(
                        PaperQuestionRelation.paper_id == paper.paper_id).all()}
                # W1：同一份文档内若出现重复题目，第 1 次入库进 ok_ids，第 2 次会被
                #   去重命中刚建的题而进 reused_ids —— 两者指向同一 question_id。
                #   existing_rel_qids 只挡库内已有的，挡不住**批内**重复，于是
                #   flush 时撞 UNIQUE(paper_id, question_id)，整卷 500 回滚
                #   （实测卷#53「关联1题成功」后失败，关联行数=0）。
                #   保序去重，不改变任何有效题目的顺序与内容。
                _seen_qids: set = set()
                all_ids = []
                for _qid in ok_ids + reused_ids:
                    if _qid in _seen_qids:
                        logger.info('[batch-parsed] 试卷%s 跳过批内重复题 qid=%s',
                                    paper.paper_id, _qid)
                        continue
                    _seen_qids.add(_qid)
                    all_ids.append(_qid)
                order_base = paper.question_count or 0
                for pos, qid in enumerate(all_ids, start=order_base + 1):
                    if qid in existing_rel_qids:
                        continue
                    item_score = items[min(pos - order_base - 1, len(items) - 1)].get('score')
                    db.add(PaperQuestionRelation(
                        paper_id=paper.paper_id,
                        question_id=qid,
                    question_order=pos,
                    question_score=float(item_score) if item_score else 5.0,
                ))
                linked += 1
            if linked:
                paper.question_count = (paper.question_count or 0) + linked
            paper_id = paper.paper_id
            logger.info(f"[batch-parsed] 试卷#{paper_id} 关联{linked}题 "
                        f"(累计{paper.question_count})")
        except Exception as pe:  # noqa: BLE001 — 建卷失败不阻断题库入库
            logger.warning(f"[batch-parsed] 双轨建卷失败(不阻断): {pe}")

    total = len(items)
    summary_record = QuestionImportRecord(
        user_id=current_user.user_id,
        original_filename=paper_name or '批量解析导入',
        file_type='JSON',
        total_questions=total,
        success_count=len(ok_ids),
        failed_count=len(failed_items),
        duplicate_count=len(reused_ids),
        import_status=('COMPLETED' if not failed_items
                       else ('PARTIAL' if ok_ids or reused_ids else 'FAILED')),
        import_time=datetime.now(),
        complete_time=datetime.now(),
        # 模型无独立match_rate列 → 存入preview_data便于追溯
        preview_data={
            'source': 'batch-parsed',
            'import_mode': mode,
            'match_rate': round(match_rate, 1),
            'need_confirm_count': need_confirm,
            'paper_id': paper_id,
        },
        paper_id=paper_id,
    )
    db.add(summary_record)
    try:
        db.commit()
    except Exception as ce:  # noqa: BLE001
        db.rollback()
        logger.error(f"[batch-parsed] 提交失败: {ce}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量入库失败: {str(ce)}")

    # ===== B2 复合题识别（独立事务：主数据已提交，识别失败仅丢分组不伤导入）=====
    groups_created, members_linked = 0, 0
    try:
        groups_created, members_linked = _detect_and_link_composite_groups(
            db, ok_items, dict(enumerate(ok_ids)),
            default_subject or '公专', _inject_source)
        if groups_created:
            db.commit()
    except Exception as ge:  # noqa: BLE001 — 分组失败不影响导入结果
        db.rollback()
        logger.warning(f"[composite] 题组识别失败（导入数据不受影响）: {ge}")

    # ===== C 修复：申论材料组建（「给定资料N」材料组；复合题识别只认公专/行测材料头）=====
    _shenlun_linked = 0
    try:
        _shenlun_linked = _link_shenlun_material_groups(
            db, ok_items, dict(enumerate(ok_ids)),
            default_subject or '公专', _inject_source)
        if _shenlun_linked:
            db.commit()
    except Exception as se:  # noqa: BLE001 — 材料组建失败不影响导入结果
        db.rollback()
        logger.warning(f"[shenlun-group] 申论材料组建失败（导入数据不受影响）: {se}")

    msg = f"导入完成：新增 {len(ok_ids)} 题，复用 {len(reused_ids)} 题，失败 {len(failed_items)} 题"
    if backfill_count:
        msg += f"，回填缺失字段 {backfill_count} 题"
    if groups_created:
        msg += f"；识别复合题组 {groups_created} 组（{members_linked} 题挂组）"
    if _shenlun_linked:
        msg += f"；申论材料组挂载 {_shenlun_linked} 题"
    if paper_id:
        msg += f"；试卷 #{paper_id} 已保存到试卷管理（关联 {len(ok_ids)+len(reused_ids)} 题）"
    # 问题3-R2：分离导入明示缺答案/解析的题号（按提交顺序），避免静默缺失
    if mode == 'separate' and ok_items:
        missing = [
            str(i + 1) for i, q in enumerate(ok_items)
            if not (q.get('answer') or '').strip()
            or not (q.get('answer_analysis') or '').strip()
        ]
        if missing:
            head = '、'.join(missing[:20])
            more = f" 等共{len(missing)}题" if len(missing) > 20 else ''
            msg += f"；以下{len(missing)}题缺答案/解析待补：第{head}题{more}"

    return {
        'import_status': 'SUCCESS' if not failed_items else 'PARTIAL',
        'total': total,
        'success_count': len(ok_ids),
        'duplicate_count': len(reused_ids),
        'failed_items': failed_items,
        'new_question_ids': ok_ids,
        'reused_question_ids': reused_ids,
        'need_confirm_count': need_confirm,
        'need_confirm_items': need_confirm_items,
        'match_rate': match_rate,
        'paper_id': paper_id,
        'paper_name': paper_name or None,
        'message': msg,
    }


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


def _process_import_async(import_id: int, buf: bytes, filename: str, ext: str, file_type: str) -> None:
    """后台执行导入解析：提取文本 → 结构化 → 构建预览 → 落库为 PREVIEW。

    异步化的动因（实测）：扫描件 PDF 走 MinerU OCR 需 260~320s，
    而前端/代理层任何一环的超时都远小于此 → 长文档导入必然失败。
    改为「立即返回 import_id + 后台执行 + 前端轮询」后，
    单次 HTTP 请求只需毫秒级，代理层默认 60s 超时不再是瓶颈。

    设计要点：
      1. **自带独立 DB 会话** —— 请求会话在响应返回时即关闭，后台任务不能复用。
      2. 成功与失败都**落库**：PREVIEW / FAILED(带 error_messages)，
         前端据此轮询，不会出现"永远 PARSING"的无反馈状态。
      3. 完整响应体存入 preview_data['_response']，使状态端点能**原样返回**，
         前端拿到后的消费逻辑与原同步接口完全一致（零改动）。
      4. 同步函数 —— Starlette 会自动丢到线程池执行，不阻塞事件循环。
    """
    from ....core.database import SessionLocal

    db = SessionLocal()
    try:
        record = db.query(QuestionImportRecord).filter(
            QuestionImportRecord.import_id == import_id
        ).first()
        if record is None:
            logger.error(f"[import-async] 记录不存在 import_id={import_id}")
            return

        # ---------- 进度上报（2026-09-29 新增）----------
        # 写入 record.progress_percent / record.current_phase，
        # 由 GET /records/{id}/status 原样返回给前端轮询。
        # 写进度本身绝不能影响解析：任何异常都吞掉并回滚。
        def _set_progress(percent: int, phase: str) -> None:
            """写入真实进度，单调守卫：绝不让进度值倒退。

            进度条回跳比不动更糟（用户会以为解析出错），因此这里显式夹住下界。
            前端 GET /records/{id}/status 原样返回这两个字段。
            写进度本身绝不能影响解析：任何异常都吞掉并回滚。
            """
            try:
                target = max(0, min(100, int(percent)))
                current = record.progress_percent or 0
                if target < current:
                    target = current
                record.progress_percent = target
                record.current_phase = phase
                db.commit()
            except Exception as e:  # noqa: BLE001
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass
                logger.debug(f"[import-async] 进度写入失败(忽略) {phase}: {e}")

        # ---------- 1) 提取文本 / 原始行 ----------
        _set_progress(5, 'READING')
        _progress_img_counter = {'n': 0}   # 跨页累计已发现图片数，驱动 45→60 段
        raw_questions = []
        text = ''
        if ext in ('.xlsx', '.xls'):
            raw_questions = _parse_excel_buffer(buf, filename)
        elif ext == '.csv':
            raw_questions = _parse_csv_buffer(buf)
        elif ext == '.docx':
            _set_progress(10, 'EXTRACTING')
            text = _extract_text_from_docx(buf)
            _set_progress(45, 'IMAGES')
            raw_questions = [{'type': 'docx_text', 'content': text}]
        elif ext == '.pdf':
            _set_progress(10, 'EXTRACTING')

            def _on_page(page_no: int, total_pages: int, images_on_page: int) -> None:
                """逐页真实进度，**每页只写一个单调递增的值**（10→60）。

                为什么不再分别上报「文本百分比」和「图片计数」两个指标：
                二者独立推进会互相回跳（实测出现 12→45→14→45→16→47 的锯齿），
                进度条倒退会让用户误以为解析出错。页循环内文本与图片是同一次
                推进完成的，因此按页序折算单一完成度才是真实度量。

                长文档（扫描件 OCR 可达 260s+）时前端能看到进度平滑爬升，
                而不是卡在某个数字后突然跳到 100。
                """
                ratio = (page_no / total_pages) if total_pages else 1.0
                imgs = _progress_img_counter['n'] + images_on_page
                _progress_img_counter['n'] = imgs
                logger.debug(
                    f"[import-async] 页 {page_no}/{total_pages} 完成，"
                    f"累计图片 {imgs} 张")
                _set_progress(10 + int(ratio * 50), 'EXTRACTING')

            text = _extract_text_from_pdf(buf, progress_cb=_on_page)   # 含 md5 提取缓存
            _set_progress(60, 'IMAGES')
            raw_questions = [{'type': 'pdf_text', 'content': text}]

        # ---------- 2) 构建预览 ----------
        if ext in ('.xlsx', '.xls', '.csv'):
            preview_items = []
            success_count = duplicate_count = failed_count = 0
            for row in raw_questions[:MAX_BATCH_QUESTIONS]:
                normalized = _normalize_question(row)
                if not normalized:
                    failed_count += 1
                    preview_items.append({
                        'status': 'SKIPPED', 'reason': '缺少题目内容或答案', 'raw': row,
                    })
                    continue
                existing = _detect_duplicate(db, normalized['question_content'], normalized['answer'])
                if existing:
                    dup_info = _get_duplicate_info(db, normalized['question_content'], normalized['answer'])
                    duplicate_count += 1
                    preview_items.append({
                        **normalized, 'status': 'DUPLICATE', 'is_duplicate': True,
                        'existing_id': existing.question_id, 'similarity': dup_info['similarity'],
                    })
                else:
                    success_count += 1
                    preview_items.append({**normalized, 'status': 'NEW', 'is_duplicate': False})

            total = len(raw_questions[:MAX_BATCH_QUESTIONS])
            auto_tags = _auto_detect_tags(filename, str(preview_items[:5]) if preview_items else '')
            # W2-1：科目/子科目建议（追加字段，不改既有字段）
            _upload_sug_text = ' '.join(
                (it.get('question_content') or '') for it in preview_items[:10])
            subject_suggestion = _build_subject_suggestion(_upload_sug_text)
            _upload_sub_id = SUBJECT_NAME_MAP.get(subject_suggestion.get('name') or '')
            subcategory_suggestion = _build_subcategory_suggestion(
                _upload_sub_id, _upload_sug_text) if _upload_sub_id else {
                    'name': '', 'confidence': 0.0}
            response_payload = {
                'import_id': import_id, 'original_filename': filename, 'file_type': file_type,
                'total_questions': total, 'success_count': success_count,
                'failed_count': failed_count, 'duplicate_count': duplicate_count,
                'questions': preview_items, 'auto_detected_tags': auto_tags,
                'subject_suggestion': subject_suggestion,
                'subcategory_suggestion': subcategory_suggestion,
            }
            stored = {'items': preview_items, 'auto_detected_tags': auto_tags,
                      '_response': response_payload}
            record.total_questions = total
            record.success_count = success_count
            record.failed_count = failed_count
            record.duplicate_count = duplicate_count
        else:
            from ....services.text_parser import (
                extract_question_blocks,
                looks_like_answer_document,
                extract_answer_entries,
            )
            _set_progress(60, 'SPLITTING')
            # ★ 答案卷不能套用题干切块器（2026-10-25 事故）：
            #   实测「题本 125 块 / 答案解析 95 块」，前端据此显示"答案对不上"；
            #   按题号锚点解析答案卷恰好 125 条，与题本同口径。
            is_answer_doc = looks_like_answer_document(text, filename)
            parsed_blocks = [] if is_answer_doc else extract_question_blocks(text)
            _set_progress(75, 'MATCHING')
            auto_tags = _auto_detect_tags(filename, text)
            detected_subject = auto_tags.get('subject_category', '行测')

            preview_items = []
            for idx, block in enumerate(parsed_blocks):
                if block.get('content'):
                    qtype = block.get('question_type', '选择题')
                    _fmt = block.get('format')
                    # ★ 申论题：科目必须显式定为「申论」。
                    #   _auto_detect_tags 的启发式对「给定资料」长文本常误判成行测/公专，
                    #   科目错了 → requirements 语义全错、题型表挂到错误 subject 下。
                    _subj = detected_subject
                    if _fmt == 'essay':
                        _subj = '申论'
                    preview_items.append({
                        'question_content': block['content'],
                        'options': block.get('options', []),
                        'answer': block.get('answer', ''),
                        # ★键名对齐：/confirm 读的是 answer_analysis，
                        #   这里原来只写 'analysis'，导致申论解析整段丢失。
                        'analysis': block.get('analysis', ''),
                        'answer_analysis': block.get('analysis', ''),
                        'question_type_detail': qtype, 'type_name': qtype,
                        'subject_name': _subj, 'status': 'NEW',
                        'is_duplicate': False,
                        'difficulty': 3,
                        # ★ 分值不能硬编码 1：申论每题 15/20/25/40 分，
                        #   硬编码会把全部申论题记成 1 分，题库排序与统计全错。
                        'score': block.get('score') or 1,
                        # 串题检测结果透传给前端，供预览卡片高亮「疑似串题」
                        'suspicious': bool(block.get('suspicious')),
                        'suspicious_reason': block.get('suspicious_reason', ''),
                        # ★ 以下为申论必需字段，缺一个前端就渲染不出/入库丢数据
                        'format': _fmt,
                        'requirements': block.get('requirements', []),
                        'blocked': bool(block.get('blocked')),
                        'block_reasons': block.get('block_reasons', []),
                        'material_text': block.get('material_text', ''),
                        'material_titles': block.get('material_titles', []),
                        'question_number': block.get('question_number'),
                        'question_level': block.get('question_level'),
                        'sort_order': block.get('sort_order'),
                    })
                # 逐题推进 75→90：大文档（数百题）时进度同样是平滑的
                if parsed_blocks and (idx % 20 == 0 or idx == len(parsed_blocks) - 1):
                    _set_progress(75 + int((idx + 1) / max(len(parsed_blocks), 1) * 15), 'MATCHING')
            _set_progress(90, 'BUILDING')

            # 答案卷：预览条目 = 题号/答案/解析，不计入"题目"，但题号集合与题本可比对。
            if is_answer_doc:
                answer_entries = extract_answer_entries(text)
                preview_items = [{
                    # 答案卷条目没有题干；用「第N题」占位，避免预览出现空白卡片，
                    # 但 is_answer_doc 会阻断 /confirm 把它当题目入库。
                    'question_content': '第%d题' % e['number'],
                    'role_label': '答案',
                    'options': [],
                    'answer': e['answer'],
                    'analysis': e['analysis'],
                    'answer_analysis': e['analysis'],
                    'question_number': e['number'],
                    'question_type_detail': '答案',
                    'type_name': '答案',
                    'subject_name': '答案',
                    'status': 'ANSWER_ONLY',
                    'is_answer_doc': True,
                    'is_duplicate': False,
                    'difficulty': 3,
                    'score': 0,
                } for e in answer_entries]
                logger.info(
                    f"[import-async] 识别为答案卷 {filename}："
                    f"{len(preview_items)} 条答案锚点")

            total = len(preview_items)
            is_scanned = (ext == '.pdf' and len(preview_items) == 0 and _pdf_has_images_only(buf))
            # W2-1：科目/子科目建议（追加字段，不改既有字段）
            subject_suggestion = _build_subject_suggestion(text)
            _upload_sub_id = SUBJECT_NAME_MAP.get(subject_suggestion.get('name') or '')
            subcategory_suggestion = _build_subcategory_suggestion(
                _upload_sub_id, text) if _upload_sub_id else {
                    'name': '', 'confidence': 0.0}
            response_payload = {
                'import_id': import_id, 'original_filename': filename, 'file_type': file_type,
                # file_role 让前端/教师一眼区分「题目卷 / 答案卷」，答案卷不再按题目数展示
                'file_role': 'answer' if is_answer_doc else 'question',
                'total_questions': total, 'success_count': total, 'failed_count': 0,
                'duplicate_count': 0, 'questions': preview_items,
                # ★ groups：按「给定材料」聚合的复合题组，供前端渲染总题干。
                #   保留顶层 questions 不变，旧前端逻辑零回归。
                'groups': _build_preview_groups(preview_items),
                'raw_text_preview': text[:1000000] if text else '',
                'auto_detected_tags': auto_tags, 'scanned_pdf': is_scanned,
                'subject_suggestion': subject_suggestion,
                'subcategory_suggestion': subcategory_suggestion,
                'engine': _pdf_reader._last_extract_engine,  # ★ 本次实际使用的识别引擎（I-6 起状态随平移迁至 pdf_reader）
                'ocr_hint': ('该PDF为扫描件（无文本层），请使用"图片导入"标签页上传，'
                             '或先通过OCR工具转换为文本格式') if is_scanned else None,
                # F-6：OCR 失败的具体原因（供前端可操作提示，替代笼统的"解析失败"）
                'ocr_failure_reason': _pdf_reader._last_ocr_failure or None,
            }
            stored = {'items': preview_items, 'raw_text': text[:1000000],
                      'auto_detected_tags': auto_tags,
                      'groups': _build_preview_groups(preview_items),
                      '_response': response_payload}
            record.total_questions = total
            record.success_count = total
            record.failed_count = 0
            record.duplicate_count = 0

        # ---------- 3) 落库为 PREVIEW ----------
        record.import_status = 'PREVIEW'
        # 用 dump_json_once 保证单层编码（历史代码在别处曾造成双重编码）
        record.preview_data = dump_json_once(stored)
        # 进度收尾：与 PREVIEW 状态同一次提交落库，前端轮询到 100 即停止
        record.progress_percent = 100
        record.current_phase = 'DONE'
        db.commit()
        logger.info(f"[import-async] import_id={import_id} 解析完成 → PREVIEW（{total} 题）")

    except Exception as e:  # noqa: BLE001 — 后台任务必须把失败写回库，否则前端永远轮询中
        logger.error(f"[import-async] import_id={import_id} 解析失败: {e}", exc_info=True)
        try:
            db.rollback()
            record = db.query(QuestionImportRecord).filter(
                QuestionImportRecord.import_id == import_id
            ).first()
            if record is not None:
                record.import_status = 'FAILED'
                record.error_messages = [{'stage': 'parse', 'error': str(e)[:500]}]
                record.complete_time = datetime.now()
                db.commit()
        except Exception:  # noqa: BLE001 — 连失败状态都写不回时只能放弃，绝不抛出
            logger.error(f"[import-async] import_id={import_id} 写入 FAILED 状态亦失败", exc_info=True)
    finally:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass


@router.post("/upload", summary="批量文件上传（异步解析，立即返回import_id）")
async def upload_file_for_import(
    file: UploadFile = File(...),
    paper_name: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传文件进行题目批量解析（异步）。

    支持格式：.xlsx / .xls / .csv / .docx / .pdf

    **立即返回** {import_id, status:'PARSING'}（HTTP 202），解析在后台执行。
    前端轮询 `GET /records/{import_id}/status` 取结果：
      - ``PARSING`` → 继续轮询
      - ``PREVIEW`` → ``result`` 字段为完整预览数据（与原同步接口响应**同构**，
        前端拿到后的消费逻辑零改动）
      - ``FAILED``  → ``error`` 字段为失败原因

    异步化的动因（实测）：扫描件 PDF 走 MinerU OCR 需 260~320s，而
    前端 fetch 超时与 nginx ``proxy_read_timeout``（默认 60s）都远小于此，
    同步模式下长文档导入必然失败。异步后单次 HTTP 请求仅需毫秒级，
    代理层默认超时不再是瓶颈，也不再需要为长请求放大 nginx 配置。
    """
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}")

    buf = await file.read()
    if len(buf) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件超过 {MAX_FILE_SIZE // 1024 // 1024}MB 限制")

    # ★ RC-6 修复：文件头嗅探，以真实文件类型为准
    from ....services.question_ingest.magic import resolve_type
    file_type, type_conflict = resolve_type(buf, file.filename or '')
    if type_conflict:
        logger.warning(f'[upload] 文件类型冲突: 扩展名={ext}, 文件头={file_type}, 文件={file.filename}')

    # 立即落库并提交 —— 必须先 commit，轮询方才能马上看到这条 PARSING 记录
    record = QuestionImportRecord(
        user_id=current_user.user_id,
        original_filename=file.filename,
        file_type=file_type,
        import_status='PARSING',
        import_time=datetime.now(),
    )
    db.add(record)
    db.commit()
    try:
        db.refresh(record)
    except Exception:  # noqa: BLE001 — 某些驱动 commit 后不回填，自增ID可能已在对象上
        pass
    import_id = record.import_id

    # 后台执行：Starlette 在响应返回后把同步函数丢到线程池，不阻塞事件循环
    if background_tasks is not None:
        background_tasks.add_task(_process_import_async, import_id, buf, file.filename, ext, file_type)
    else:  # 兜底：无 BackgroundTasks 注入时退化为同步，功能不丢
        logger.warning("[upload] 未注入 BackgroundTasks，退化为同步解析")
        _process_import_async(import_id, buf, file.filename, ext, file_type)

    return JSONResponse(
        status_code=202,
        content={
            'import_id': import_id,
            'status': 'PARSING',
            'original_filename': file.filename,
            'file_type': file_type,
            'message': f'文件已接收，正在后台解析，请轮询 /api/questions/import/records/{import_id}/status',
        },
    )


def _sanitize_preview_images(result: dict, import_id: int, db) -> None:
    """预览态返回前，把题目图片字段里的 [IMAGE:xxx] 裸占位符转成 <img>（或剔除）。

    为什么需要（预览态图片实测）
    --------------------------
    preview_data 里的题目图片是**裸 [IMAGE:xxx] 占位符**（0 个 <img>、0 个 data:image），
    而对应图片文件已暂存于扁平目录 app/static/questions/{marker}.png（实测 39/39 命中）。
    若不在此转换，前端 renderQuestionContent 会把占位符整段剔除 → 图片消失或显示为路径文本。
    question_id 传 import_id：resolve_image_marker 先查 {qid}/ 子目录，找不到再回落扁平目录，
    最终命中扁平暂存文件。复用 image_service 的 10 层防线，不新建 sanitize 逻辑。
    """
    from ....services.image_service import sanitize_image_placeholders

    questions = result.get('questions')
    if not isinstance(questions, list):
        return
    for q in questions:
        if not isinstance(q, dict):
            continue
        # 题目对象同时存在 analysis 与 answer_analysis 两个字段（历史兼容），都处理
        for field in ('question_content', 'content', 'answer', 'analysis', 'answer_analysis'):
            v = q.get(field)
            if isinstance(v, str) and '[IMAGE:' in v:
                q[field] = sanitize_image_placeholders(v, import_id, db)
        opts = q.get('options')
        if isinstance(opts, list):
            for o in opts:
                if isinstance(o, dict):
                    v = o.get('value')
                    if isinstance(v, str) and '[IMAGE:' in v:
                        o['value'] = sanitize_image_placeholders(v, import_id, db)


@router.get("/records/{import_id}/status", summary="查询异步导入解析状态")
async def get_import_parse_status(
    import_id: int,
    light: bool = False,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """轮询异步导入的解析状态。

    返回：``{import_id, status, total_questions, success_count, failed_count,
    duplicate_count, error, result}``

    ``status='PREVIEW'`` 时 ``result`` 为完整预览数据（与原同步 /upload 响应同构）。
    ``light=true`` 时跳过 result 的 JSON 反序列化，仅返回元数据（轮询用）。
    """
    record = db.query(QuestionImportRecord).filter(
        QuestionImportRecord.import_id == import_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="导入记录不存在")

    # 权限：非 admin/teacher 只能查询自己的导入记录
    user_role = getattr(current_user, 'user_type', '') or getattr(current_user, 'role', '')
    if user_role not in ('admin', 'teacher') and record.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权查看该导入记录")

    payload = {
        'import_id': record.import_id,
        'status': record.import_status,
        'original_filename': record.original_filename,
        'file_type': record.file_type,
        'total_questions': record.total_questions or 0,
        'success_count': record.success_count or 0,
        'failed_count': record.failed_count or 0,
        'duplicate_count': record.duplicate_count or 0,
        # 2026-09-29 新增：真实解析进度。前端据此渲染进度条，
        # 不再自己用定时器伪造百分比（那会造成「突然就完成」的错觉）。
        # 旧记录这两列为 NULL，回落为 0 / None，前端按未开始处理。
        'progress_percent': record.progress_percent or 0,
        'current_phase': record.current_phase,
    }

    if record.import_status == 'FAILED':
        # load_json_lenient 兼容历史双重编码记录
        errs = load_json_lenient(record.error_messages)
        if errs is None and record.error_messages:
            errs = [{'error': str(record.error_messages)[:500]}]
        msg = ''
        if isinstance(errs, list) and errs:
            first = errs[0]
            msg = first.get('error', '') if isinstance(first, dict) else str(first)
        payload['error'] = msg or '解析失败'
        return payload

    if record.import_status == 'PREVIEW':
        if light:
            # ★ 轻量模式：跳过 JSON 反序列化，仅返回元数据
            payload['has_result'] = True
            return payload
        # ★ P0-6 关键修复：历史记录存在双重编码，单次 json.loads 只能剥一层，
        #   拿到的是字符串而非 dict，导致 `isinstance(data, dict)` 恒假、
        #   预览页拿不到 _response → 用户"编辑后无法导入"。
        data = load_json_lenient(record.preview_data)
        if not isinstance(data, dict):
            data = {}
        if isinstance(data, dict):
            result = data.get('_response')
            if isinstance(result, dict):
                # ★ 预览态图片 sanitize：裸 [IMAGE:xxx] → <img>（或剔除），避免前端显示路径文本
                _sanitize_preview_images(result, import_id, db)
                # F-4：raw_text_preview 出口同步 sanitize —— 前端合并导入会用它做
                # 本地解析，marker 残留会在前端被剥空导致图片消失。
                _raw_preview = result.get('raw_text_preview')
                if isinstance(_raw_preview, str) and '[IMAGE:' in _raw_preview:
                    from ....services.image_service import sanitize_image_placeholders
                    result['raw_text_preview'] = sanitize_image_placeholders(
                        _raw_preview, import_id, db)
                payload['result'] = result
            else:  # 兼容历史记录：没有 _response 时回落到 items/raw_text 拼装
                payload['result'] = {
                    'import_id': record.import_id,
                    'original_filename': record.original_filename,
                    'file_type': record.file_type,
                    'total_questions': record.total_questions or 0,
                    'success_count': record.success_count or 0,
                    'failed_count': record.failed_count or 0,
                    'duplicate_count': record.duplicate_count or 0,
                    'questions': data.get('items', []),
                    'raw_text_preview': data.get('raw_text', ''),
                    'auto_detected_tags': data.get('auto_detected_tags', {}),
                }
        return payload

    # PARSING / CONFIRMED / COMPLETED —— 调用方按需处理
    return payload


@router.post("/records/{import_id}/attach-image", summary="预览态为指定题目添加图片")
async def attach_image_to_preview_question(
    import_id: int,
    file: UploadFile = File(...),
    target: str = Form('content'),
    option_key: Optional[str] = Form(None),
    question_index: int = Form(...),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """在「识别匹配」后的预览态，为某一道题追加图片（题干或某个选项）。

    为什么改 preview_data 而不是 question_bank
    ------------------------------------------
    预览态的题目尚未落库，整份预览数据存在 ``QuestionImportRecord.preview_data``
    里（``items`` 与 ``_response['questions']`` 为 JSON 往返后的两份独立副本，
    必须同步更新，否则状态端点返回的 result 与 items 会不一致）。

    落盘与安全
    ----------
    不自行写文件，而是把上传内容包成 base64 data URI 交给既有的
    ``_extract_and_save_images``，从而完整复用其尺寸上限、无关图过滤、
    压缩与路径安全等防护，避免引入第二套图片写入逻辑。
    """
    record = db.query(QuestionImportRecord).filter(
        QuestionImportRecord.import_id == import_id
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="导入记录不存在")

    # 权限：与状态接口保持一致
    user_role = getattr(current_user, 'user_type', '') or getattr(current_user, 'role', '')
    if user_role not in ('admin', 'teacher') and record.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作该导入记录")

    if record.import_status != 'PREVIEW':
        raise HTTPException(
            status_code=400,
            detail=f"仅预览状态可编辑题目图片，当前状态为 {record.import_status}")

    if target not in ('content', 'option', 'answer', 'analysis'):
        raise HTTPException(status_code=400, detail="target 必须是 content/option/answer/analysis")
    if target == 'option' and not option_key:
        raise HTTPException(status_code=400, detail="target=option 时必须提供 option_key")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(raw) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400, detail=f"图片超过大小限制（{len(raw)} > {MAX_IMAGE_SIZE} 字节）")
    ext = (file.filename or '').rsplit('.', 1)[-1].lower() if file.filename else 'png'
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        raise HTTPException(status_code=400, detail=f"不支持的图片类型：{ext}")

    data_uri = f'data:image/{ext};base64,{base64.b64encode(raw).decode("ascii")}'
    try:
        stored = _extract_and_save_images(f'<img src="{data_uri}">', import_id) or []
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[attach-image] import_id={import_id} 保存失败: {e}")
        raise HTTPException(status_code=500, detail="图片保存失败")
    if not stored:
        raise HTTPException(
            status_code=400, detail="图片未通过安全校验（可能被判定为无关图片或超过限制）")

    img_tag = f'<img src="{stored[0]}" class="q-img" loading="lazy" />'

    data = load_json_lenient(record.preview_data)
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="预览数据损坏，无法编辑")

    result = data.get('_response')
    items = data.get('items')
    if not isinstance(items, list):
        items = result.get('questions') if isinstance(result, dict) else None
    if not isinstance(items, list) or not (0 <= question_index < len(items)):
        raise HTTPException(status_code=400, detail="question_index 超出范围")

    item = items[question_index]
    if not isinstance(item, dict):
        raise HTTPException(status_code=400, detail="题目数据结构异常")

    if target == 'content':
        item['question_content'] = (item.get('question_content') or '') + img_tag
    elif target == 'answer':
        item['answer'] = (item.get('answer') or '') + img_tag
    elif target == 'analysis':
        item['answer_analysis'] = (item.get('answer_analysis') or '') + img_tag
    else:
        opts = item.get('options')
        if isinstance(opts, str):
            try:
                opts = json.loads(opts)
            except Exception:  # noqa: BLE001
                raise HTTPException(status_code=400, detail="选项数据损坏")
        if not isinstance(opts, list):
            raise HTTPException(status_code=400, detail="该题没有可添加图片的选项")
        hit = False
        for o in opts:
            if isinstance(o, dict) and o.get('key') == option_key:
                o['value'] = (o.get('value') or '') + img_tag
                hit = True
                break
        if not hit:
            raise HTTPException(status_code=400, detail=f"未找到选项 {option_key}")
        item['options'] = opts

    # 同步两份副本，保持 items 与 _response['questions'] 一致
    if isinstance(items, list):
        data['items'] = items
    if isinstance(result, dict):
        result['questions'] = items
        data['_response'] = result

    record.preview_data = dump_json_once(data)
    db.commit()
    logger.info(
        f"[attach-image] import_id={import_id} idx={question_index} "
        f"target={target} key={option_key} -> {stored[0]}")

    return {
        'success': True,
        'import_id': import_id,
        'question_index': question_index,
        'target': target,
        'option_key': option_key,
        'url': stored[0],
    }


def _resolve_confirm_subject(item: Dict[str, Any]) -> tuple:
    """W2-1 确认入库的科目解析：手选优先，自动识别仅作建议。

    返回 ``(subject_name, auto_detected, confidence)``：

    1. ``item.subject_name``（教师手选）存在 → **跳过自动识别**，confidence=1.0；
    2. ``format=essay`` → '申论'（解析器确证，压过文本启发式，既有语义保留）；
    3. 否则 ``detect_subject_category()`` 自动识别；全 0 分回退历史默认值
       '行测'，confidence=0.0 → 调用方标 need_review。

    为什么手选优先：
      前端**总是**会传 subject_name（值来自 _auto_detect_tags 的启发式），
      教师在下拉里改过的值必须原样落库，绝不能被自动识别二次覆盖；
      只有未手选时才允许自动识别介入，并凭置信度提示人工复核。
    """
    manual = str((item or {}).get('subject_name') or '').strip()
    if manual:
        return manual, False, 1.0
    if (item or {}).get('format') == 'essay':
        return '申论', False, 1.0
    det = detect_subject_category(
        ' '.join([
            (item or {}).get('question_content') or '',
            str((item or {}).get('options') or ''),
            (item or {}).get('answer') or '',
        ]))
    if det.subject_name:
        return det.subject_name, True, det.confidence
    return '行测', True, 0.0


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
        # payload.questions 是主路径；未回落 preview_data 快照时保持空字典，
        # 否则下方 preview_data.get(...) 会因未绑定变量抛 UnboundLocalError。
        preview_data: Dict[str, Any] = {}
        # ★ P0-6：历史记录 preview_data 为双重编码，单次 json.loads 只剥一层会返回 str，
        #   紧接着 .get() 会抛 AttributeError: 'str' object has no attribute 'get'。
        #   load_json_lenient 会循环剥到真实对象，并对脏数据返回 {}。
        # ★ RC-3 修复：优先使用 payload.questions，preview_data 降级为历史快照
        _payload_questions = payload.get('questions')
        if _payload_questions and isinstance(_payload_questions, list) and len(_payload_questions) > 0:
            items = _payload_questions
        else:
            logger.warning('[confirm] deprecated: 未传 questions，已回落到 preview_data 快照')
            preview_data = load_json_lenient(record.preview_data)
            if not isinstance(preview_data, dict):
                preview_data = {}
            items = preview_data.get('items', []) or []

        imported = 0
        skipped = 0
        failed = 0
        errors = []
        new_questions = []
        confirmed_items = []  # ★ RC-4 修复：初始化 confirmed_items，供试卷关联使用
        group_stats = {'groups': 0, 'members': 0, 'materials': 0}

        for item in items:
            if item.get('status') == 'DUPLICATE' or item.get('is_duplicate'):
                skipped += 1
                continue
            if item.get('status') == 'SKIPPED':
                failed += 1
                errors.append({'error': item.get('reason', '数据不完整'), 'raw': item.get('raw', {})})
                continue
            # 答案卷条目不是题目：必须走「分离导入」与题本匹配后再入库，
            # 否则 /confirm 会把「第N题」当成 125 道新题写进题库（数据污染）。
            if item.get('is_answer_doc') or item.get('status') == 'ANSWER_ONLY':
                failed += 1
                errors.append({
                    'error': '该文件被识别为答案卷，不能作为题目直接入库；请使用「分离导入」与题本匹配',
                    'question_number': item.get('question_number'),
                })
                continue
            # ★ 阻断闸门：解析器判定为 blocked 的题块拒绝入库。
            #   /confirm 是前端的**主入库路径**，若不在这里拦，
            #   requirements/答案错配的数据会绕过 /single 与 /batch-parsed 直接进库，
            #   前端禁用按钮也挡不住直接调 API。用户硬约束：宁可阻断，不许错配入库。
            if item.get('blocked'):
                failed += 1
                _rs = item.get('block_reasons') or []
                errors.append({
                    'error': '解析阻断：%s' % ('、'.join(str(r) for r in _rs) or '未知原因'),
                    'question_content': item.get('question_content', '')[:120],
                    'block_reasons': _rs,
                })
                continue

            try:
                # 清洗题目内容：去除推广/无关字段
                raw_content = item['question_content']
                cleaned_content = ContentCleaner.clean_question_content(raw_content)
                raw_analysis = item.get('answer_analysis', '')
                cleaned_analysis = ContentCleaner.clean_question_content(raw_analysis)

                # W2-1 手选优先：item.subject_name 存在 → 跳过自动识别；
                # 不存在 → 自动识别 + 置信度 < 0.5 标 need_review（见下方）。
                _subject_name, _subject_auto, _subject_conf = _resolve_confirm_subject(item)
                subject = _get_or_create_subject(db, _subject_name)

                options = item.get('options')
                # 直接赋值给JSON列，不调用json.dumps（避免双重编码）

                # 答案保护：question_bank.answer 字段为 NOT NULL，docx 无答案时默认占位
                answer_val = item.get('answer') or '待补充'
                if not str(answer_val).strip():
                    answer_val = '待补充'

                # 题型：通用'选择题'或缺失 → 走 text_parser 规则优先级分类器（P3 单一事实来源）
                # ★ 修复：_detect_question_type 返回 (type_name, confidence) **元组**，
                #   旧代码 `final_type_name = _detect_question_type(...)` 把元组整体
                #   塞进了 final_type_name，随后 _get_or_create_type 用元组去匹配 type_name
                #   必然查不到 → 每导入一题就新建一条垃圾题型行。
                #   这是 question_type 表被撑脏的机制之一。
                raw_type_name = (item.get('type_name') or '').strip()
                _is_essay_item = (item.get('format') == 'essay')
                if _is_essay_item:
                    # 申论豁免选择题置信度校验：_detect_question_type 是选择题分类器，
                    # 拿它给长文本主观题打分必然 <0.60 → 每题都 need_review=1，
                    # 前端弹「低置信度题目(建议人工核对)」逼用户逐题确认。
                    final_type_name = raw_type_name or '简答题'
                    need_review = 0
                else:
                    if not raw_type_name or raw_type_name == '选择题':
                        final_type_name, _tconf = _detect_question_type(
                            cleaned_content, options, answer_val)
                    else:
                        final_type_name = raw_type_name
                        # 用户/前端显式指定题型时，仍按真实内容复核置信度
                        _, _tconf = _detect_question_type(
                            cleaned_content, options, answer_val)
                    # P3b：置信度不足 → 标记待复核，教师在「题目管理 → 待复核」确认
                    need_review = 1 if (_tconf or 0) < NEED_REVIEW_CONFIDENCE else 0
                # W2-1：自动识别的科目置信度 < 0.5 → need_review（手选/申论确证时跳过）。
                if _subject_auto and _subject_conf < SUBJECT_SUGGESTION_THRESHOLD:
                    need_review = 1
                # 客观选择题答案归一化（A、B → AB；对/错 → A/B），论述/写作保留原文
                if final_type_name in ('单选题', '多选题', '判断题', '选择题'):
                    _norm = canonical_answer(answer_val)
                    if _norm:
                        answer_val = _norm

                qtype = _get_or_create_type(db, final_type_name, subject.subject_id)

                _xingce_sc, _shenlun_sc, _gongzhuan_sc = _subcategory_tuple(
                    subject.subject_id, cleaned_content, final_type_name,
                    item.get('subcategory') or item.get('子科目') or ''
                )
                # ★ 材料落库：申论「给定资料」上万字，不能塞进题干。
                #   按内容指纹去重复用同一 question_groups 行，各小题 group_id 指向它。
                #   W2：行测分离导入的题带 material_group（预览阶段已切片好材料正文），
                #   组类型由 XINGCE_SECTION_GROUP_TYPE 决定，故走参数化的建组助手。
                _gid = 0
                _mt = item.get('material_text') or item.get('material') or ''
                _mg = item.get('material_group') or {}
                _mg_type = _mg.get('group_type') if isinstance(_mg, dict) else None
                if _mt and _mg_type:
                    _gid = (_get_or_create_group_by_material(
                        db, _mt, _mg_type, subject.subject_name,
                        item.get('source', '')) or 0)
                elif _mt:
                    _gid = (_get_or_create_shenlun_material_group(
                        db, _mt, subject.subject_name,
                        item.get('source', '')) or 0)
                _qno = item.get('question_number')
                question = QuestionBank(
                    subject_id=subject.subject_id,
                    type_id=qtype.type_id,
                    question_content=cleaned_content,
                    options=options,
                    answer=answer_val,
                    answer_analysis=cleaned_analysis,
                    difficulty=coerce_difficulty(item.get('difficulty')),
                    need_review=need_review,
                    score=coerce_score(item.get('score')),
                    year=item.get('year'),
                    source=item.get('source', ''),
                    tags=item.get('tags', ''),
                    creator_id=current_user.user_id,
                    audit_status=1,
                    xingce_subcategory=_xingce_sc,
                    shenlun_subcategory=_shenlun_sc,
                    gongzhuan_subcategory=_gongzhuan_sc,
                    # ★ 申论四要素：要求/题号/层级/组序，缺任一项题库都无法正确呈现
                    requirements=_normalize_requirements(item.get('requirements')),
                    group_id=_gid,
                    question_number=str(_qno).strip() if _qno not in (None, '') else None,
                    question_level=int(item.get('question_level') or 0) or 1,
                    sort_order=int(item.get('sort_order') or 0),
                )
                db.add(question)
                db.flush()
                new_questions.append(question)
                confirmed_items.append({**item, 'question_id': question.question_id, 'score': item.get('score', 5.0)})

                detail = QuestionDetailCategory(
                    question_id=question.question_id,
                    xingce_subcategory=_xingce_sc,
                    shenlun_subcategory=_shenlun_sc,
                    gongzhuan_subcategory=_gongzhuan_sc,
                    question_type_detail=normalize_type_name(final_type_name),
                )
                db.add(detail)

                # 图片提取与保存（失败时清除已刷新的题目，避免孤儿行）
                try:
                    # ★ 与 /single 保持一致：扫描范围必须含答案与解析。
                    #   实测 254 份申论语料 118 份含真实图片，绝大多数在答案区。
                    #   /confirm 是前端的**主入库路径**，若只扫题干+选项，
                    #   答案区的 [IMAGE:xxx] 占位符不会被发现也不会被替换
                    #   （用户截图残留 [[IMAGE:f4419932_2_0]] 即由此而来）。
                    _confirm_scope = ' '.join([
                        item.get('question_content') or '',
                        str(item.get('options') or ''),
                        item.get('answer') or '',
                        item.get('answer_analysis') or item.get('analysis') or '',
                    ])
                    images = _extract_and_save_images(
                        _confirm_scope,
                        question.question_id,
                        question_obj=question
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
            record.error_messages = dump_json_once(errors)
        _link_knowledge_points(db, new_questions)
        db.commit()

        # ★ P3-11：主入库路径接建组。题目已提交后再挂组，失败只丢组关系不丢题。
        if confirmed_items:
            try:
                id_map = {i: it['question_id'] for i, it in enumerate(confirmed_items)}
                _group_subject = ''
                for it in confirmed_items:
                    _sn = str(it.get('subject_name') or '').strip()
                    if _sn:
                        _group_subject = _sn
                        break
                if not _group_subject and new_questions:
                    _group_subject = (new_questions[0].subject.subject_name or '')
                _group_source = record.original_filename or ''
                _n_groups, _n_members = _detect_and_link_composite_groups(
                    db, confirmed_items, id_map, _group_subject, _group_source)
                _n_materials = _link_shenlun_material_groups(
                    db, confirmed_items, id_map, _group_subject or '申论', _group_source)
                group_stats['groups'] = _n_groups
                group_stats['members'] = _n_members
                group_stats['materials'] = _n_materials
                if _n_groups or _n_members or _n_materials:
                    db.commit()
                    logger.info("[confirm] 建组完成: groups=%d members=%d materials=%d",
                                _n_groups, _n_members, _n_materials)
            except Exception as e:
                db.rollback()
                logger.warning(f"[confirm] 建组失败(非阻断，题目已入库): {e}")

        # N1: 确认导入阶段创建试卷（延迟创建策略）
        if imported > 0 and preview_data.get('auto_detected_tags'):
            try:
                auto_tags = preview_data.get('auto_detected_tags', {})
                # 阈值检查：至少5题才创建试卷
                paper = _get_or_create_import_paper(
                    db, current_user, auto_tags,
                    record.original_filename or '导入试卷',
                    question_count=imported
                )
                if paper:
                    record.paper_id = paper.paper_id
                    logger.info(f"[confirm] 确认导入后创建试卷: paper_id={paper.paper_id}")
                    db.commit()
            except Exception as e:
                logger.warning(f"[confirm] 创建试卷失败(非阻断): {e}")

        # N1: 将导入的题目关联到试卷
        if record.paper_id:
            try:
                paper = db.query(ExamPaper).filter(ExamPaper.paper_id == record.paper_id).first()
                if paper:
                    linked_count = 0
                    for item in confirmed_items:
                        qid = item.get('question_id')
                        if not qid:
                            continue
                        # 检查是否已关联
                        existing_rel = db.query(PaperQuestionRelation).filter(
                            PaperQuestionRelation.paper_id == paper.paper_id,
                            PaperQuestionRelation.question_id == qid
                        ).first()
                        if existing_rel:
                            continue
                        relation = PaperQuestionRelation(
                            paper_id=paper.paper_id,
                            question_id=qid,
                            question_order=paper.question_count + linked_count + 1,
                            question_score=item.get('score', 5.0)
                        )
                        db.add(relation)
                        linked_count += 1
                    paper.question_count = (paper.question_count or 0) + linked_count
                    db.commit()
                    logger.info(f"[import] 题目已关联到试卷: paper_id={paper.paper_id} linked={linked_count}")
            except Exception as e:
                logger.warning(f"[import] 关联题目到试卷失败(非阻断): {e}")

        # 题目导入完成后广播同步事件，通知三端（手机/平板/电脑）刷新题库。
        # 只广播统计信息（数量/科目），不含题目正文，避免信息泄露。
        # 用 try/except 完全隔离：广播失败绝不能影响导入结果返回。
        try:
            from ....services.scheduler import _broadcast_sync
            _broadcast_sync(
                "题目更新",
                {
                    "scope": "question_bank",
                    "action": "import",
                    "count": imported,
                    "subject_id": preview_data.get('auto_detected_subject') or None,
                },
            )
        except Exception as e:
            logger.warning(f"[import] 广播导入完成事件失败(非阻断): {e}")

        message = f'导入完成：成功 {imported}，失败 {failed}，跳过 {skipped}'
        if group_stats['groups'] or group_stats['materials']:
            message += (f'；题组 {group_stats["groups"]}（成员 {group_stats["members"]}），'
                        f'材料组 {group_stats["materials"]}')
        return {
            'success_count': imported,
            'failed_count': failed,
            'skipped_count': skipped,
            'errors': errors,
            'paper_id': record.paper_id,
            'match_rate': preview_data.get('match_rate', 0),
            'group_stats': group_stats,
            'message': message,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"确认导入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


def _separate_match_essay(db: Session, payload: Dict[str, Any],
                          q_blocks: List[Dict[str, Any]],
                          a_blocks: List[Dict[str, Any]],
                          subject_name: str = '') -> Dict[str, Any]:
    """申论分离导入的匹配响应（题号+分值+题干指纹三方交叉校验后）。

    与原 `separate_match_endpoint` 的返回结构保持一致，前端无需分支：
      status / match_rate / matched_count / total_questions / questions /
      unmatched_question_numbers / extra_answer_numbers / strategy_used / details / message
    额外附 `essay_report` 承载三方校验明细，便于前端展示阻断原因。
    """
    merged = _essay_cross_validate(q_blocks, a_blocks)
    qs = merged['questions']
    report = merged['report']

    if not subject_name:
        subject_name = '申论'
    subject = _get_or_create_subject(db, subject_name)

    # 去重检测：与原链路同口径
    for q in qs:
        content = q.get('content') or ''
        dup_info = _get_duplicate_info(db, content, q.get('answer') or '',
                                       subject.subject_id)
        q['is_duplicate'] = dup_info['is_duplicate']
        q['similarity'] = dup_info['similarity']
        if dup_info['is_duplicate']:
            q['existing_id'] = dup_info['existing_id']

    total = report['question_count']
    ok_cnt = total - report['blocked_count']
    rate = (ok_cnt / total * 100) if total else 0.0
    return {
        'status': 'success',
        'match_rate': round(rate, 1),
        'matched_count': ok_cnt,
        'total_questions': total,
        'questions': qs,
        'unmatched_question_numbers': report['only_in_answers'],
        'extra_answer_numbers': report['only_in_answers'],
        'analysis_count': sum(1 for q in qs if (q.get('analysis') or '').strip()),
        'strategy_used': 'essay_triple_cross_validate',
        'auto_detected_subject': subject_name,
        'details': report['details'],
        'essay_report': report,
        'message': ('三方交叉校验完成：%s%%（%d/%d 通过）'
                    % (round(rate, 1), ok_cnt, total)),
    }


def _essay_cross_validate(q_blocks: List[Dict[str, Any]],
                          a_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分离导入的申论三方交叉校验：题号 + 分值 + 题干指纹。

    用户硬约束：「题目数=正确答案段数」**仅是必要条件**，必须逐题校验，
    禁止计数相等但错配。因此这里逐题比对三项，任何一项不一致即置 blocked，
    绝不按序盲配。

    为什么要三方而不是只比题号：
      安徽/国考的答案 PDF **自带完整题干与要求**，因此可以把答案文档里的
      题干指纹与题目文档的题干指纹直接比对。实测两者逐字一致，
      一旦不一致就说明两份文档不是同一套卷（例如上传错了年份或卷别），
      按序配对会把A 卷答案贴到 B 卷题目上 —— 这类错配计数完全正常，
      只靠数量校验抓不住。

    返回: {'questions': [...], 'report': {...}}
    """
    q_by_no = {}
    for b in q_blocks:
        if b.get('format') != 'essay':
            continue
        q_by_no[str(b.get('question_number'))] = b
    a_by_no = {}
    for b in a_blocks:
        if b.get('format') != 'essay':
            continue
        a_by_no[str(b.get('question_number'))] = b

    merged: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []

    for qno, qb in sorted(q_by_no.items(), key=lambda kv: int(kv[0] or 0)):
        out = dict(qb)
        reasons: List[str] = list(qb.get('block_reasons') or [])
        ab = a_by_no.get(qno)

        if ab is None:
            # 题目卷有这道题，答案卷没有 → 绝不能留空后放行，那会让用户拿到无答案题
            reasons.append('answer_missing_for_question')
            out['answer'] = ''
            out['analysis'] = ''
            details.append({'question_number': qno, 'ok': False,
                            'reason': '答案卷缺少该题号'})
        else:
            # ① 题干指纹
            fp_q = _essay_norm_fp(qb.get('content') or '')
            fp_a = _essay_norm_fp(ab.get('content') or '')
            if fp_q and fp_a and fp_q != fp_a:
                reasons.append('stem_fingerprint_mismatch')
            # ② 分值
            sq, sa = qb.get('score'), ab.get('score')
            if sq and sa and abs(float(sq) - float(sa)) > 0.01:
                reasons.append('score_mismatch')
            # ③ 题号本身必须存在且已对齐（走到这里说明 qno 是双方共有的）
            out['answer'] = ab.get('answer') or ''
            out['analysis'] = ab.get('analysis') or ''
            # 答案卷若带更准的要求，以题目卷为准（题目卷是权威来源）
            if not out.get('requirements') and ab.get('requirements'):
                out['requirements'] = ab.get('requirements')
            details.append({
                'question_number': qno,
                'ok': not reasons,
                'stem_match': fp_q == fp_a,
                'score_q': sq, 'score_a': sa,
                'answer_len': len(out['answer'] or ''),
            })

        out['block_reasons'] = reasons
        out['blocked'] = bool(reasons)
        merged.append(out)

    only_q = sorted(set(q_by_no) - set(a_by_no), key=lambda x: int(x or 0))
    only_a = sorted(set(a_by_no) - set(q_by_no), key=lambda x: int(x or 0))

    # 材料传播：解析器只在**第一题**挂 material_text（省内存，避免每题存一份
    # 上万字的同份材料），但落库时每道题都要通过 group_id 指向同一份材料。
    # 故在此把整批共享的材料补齐到每一题，否则 Q2..QN 会group_id=0 且材料丢失。
    # 实测漏掉这一步的后果：材料只进第 1 题，其余 3 题在题库里查不到给定资料。
    _shared_material = ''
    _shared_titles = None
    for b in q_blocks:
        if b.get('material_text'):
            _shared_material = b.get('material_text') or ''
            _shared_titles = b.get('material_titles')
            break
    if _shared_material:
        for m in merged:
            if not m.get('material_text'):
                m['material_text'] = _shared_material
            if not m.get('material_titles') and _shared_titles:
                m['material_titles'] = _shared_titles

    report = {
        'question_count': len(q_by_no),
        'answer_count': len(a_by_no),
        'matched': len(set(q_by_no) & set(a_by_no)),
        'only_in_questions': only_q,
        'only_in_answers': only_a,
        'blocked_count': sum(1 for m in merged if m.get('blocked')),
        'details': details,
    }
    return {'questions': merged, 'report': report}


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

    # ★ 申论专用三方交叉校验（题号 + 分值 + 题干指纹）
    #   仅当**两份文档都判定为申论**才启用；否则一律走原
    #   smart_match_questions_answers，保证公专/行测链路零回归。
    #   申论不能按序硬配：答案段数与题目数相等也可能整卷配错年份/卷别，
    #   而安徽/国考答案卷自带完整题干，指纹一比就能抓出来。
    _q_blocks = extract_question_blocks(questions_text)
    _a_blocks = extract_question_blocks(answers_text)
    _q_is_essay = bool(_q_blocks) and _q_blocks[0].get('format') == 'essay'
    _a_is_essay = bool(_a_blocks) and _a_blocks[0].get('format') == 'essay'
    if _q_is_essay and _a_is_essay:
        return _separate_match_essay(db, payload, _q_blocks, _a_blocks,
                                     subject_name=payload.get('subject_category', ''))

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
            subject_name, subject_confidence = detect_subject_category(all_content)
        # W1-1：detect_subject_category 无关键词命中时返回空名（不再静默回退）。
        # question_subject 已是前端科目下拉的唯一事实来源（/taxonomy），
        # 落一条空名科目会污染字典表；W2-1 将改为「标 need_review + 教师手选」，
        # 在此之前沿用历史默认值兜底。
        if not subject_name:
            subject_name = '行测'
        subject = _get_or_create_subject(db, subject_name)

        for q in result.questions:
            content = q.get('content', '')
            dup_info = _get_duplicate_info(db, content, q.get('answer', ''), subject.subject_id)
            q['is_duplicate'] = dup_info['is_duplicate']
            q['similarity'] = dup_info['similarity']
            if dup_info['is_duplicate']:
                q['existing_id'] = dup_info['existing_id']

        _response_payload = {
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
        # F-1：与 /parse、/status 同口径 —— 返回前 sanitize 裸 [IMAGE:] 占位符
        _sanitize_preview_images(_response_payload, None, db)
        return _response_payload
    except Exception as e:
        logger.error(f"分离导入匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"智能匹配失败: {str(e)}")


# ══════════════════════════════════════════════════════════════════════
# 行测专用分离导入端点（任务 11）
#
# 设计红线：**绝不改动共享 dispatch**。既有 `separate_match_endpoint`
# (:3970-4051) 被公专/申论/行测三科目共用，其分流逻辑在 :4005-4011。
# 改动它 = 给 2,583 道公专题 + 申论链路引入回归风险。本端点是**独立新增**
# 的兄弟路由，前端按科目路由，共享链路保持字节级不变。
#
# 与既有端点的唯一差别是把行测专属的「分节区间安全网」接进来：
#   既有：按序硬配 smart_match_questions_answers（申论另走三方交叉校验）
#   本端：xingce_cross_validate（分节头全等 + 区间一致 + 答案锚点 + 考点覆盖）
#
# 插入位置刻意选在 :4052 之后 —— 若插在既有端点之前，它与共享 dispatch
# 的行号会整体位移，F1 审计断言「dispatch :4005-4011 零改动」将无法用
# 行号定位验证。
# ══════════════════════════════════════════════════════════════════════

# 与 models.py:191-194 的 xingce_subcategory 枚举逐值对齐。
# 分节头命中即落位，未命中一律 '无'（枚举默认值），绝不写入枚举外的值。
_XINGCE_SUB_CATEGORIES = frozenset((
    "政治理论", "常识判断", "言语理解与表达", "数量关系",
    "判断推理", "资料分析", "知觉速度与准确性", "科学推理",
    "常识", "速度与知觉训练", "语言理解与表达", "无",
))

_XINGCE_KAO_MAP = None  # 懒加载缓存：raw token -> 归一名


def _xingce_kao_normalize_map() -> Dict[str, str]:
    """行测考点 token → 归一名（任务 5 清单 / 任务 10 落库）。

    省级私有值必须剥离前缀（``江苏特色-综合资料`` → ``综合资料``），否则
    24 个省会各自产生一套互不相同的知识点。这里直接读任务 5 产出的**数据**
    清单，而不是复制一份前缀正则 —— 正则的单一事实来源在
    ``scripts/build_xingce_kao_points.py``，重复实现必然随省份清单演进而漂移。

    仅做归一，不解析 knowledge_point 主键：ID 解析需要完整 path 上下文，
    属于 confirm 阶段的 `_link_knowledge_points()` 职责。
    """
    global _XINGCE_KAO_MAP
    if _XINGCE_KAO_MAP is None:
        _XINGCE_KAO_MAP = {}
        inv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))),
            'data', 'xingce_kao_points.json')
        try:
            with open(inv_path, encoding='utf-8') as f:
                inv = json.load(f)
            for it in inv.get('items', []):
                _XINGCE_KAO_MAP[it['token']] = it['normalized']
        except (OSError, ValueError, KeyError, TypeError) as e:
            # 清单缺失不应让端点 500：归一降级为原样返回，confirm 阶段仍会拦截
            logger.warning('行测考点清单读取失败，考点归一降级为原样: %s', e)
    return _XINGCE_KAO_MAP


def _separate_match_xingce(db: Session, payload: Dict[str, Any],
                           questions_text: str, answers_text: str,
                           user_id: int, subject_name: str = '') -> Dict[str, Any]:
    """行测分离导入的匹配响应（分节区间安全网校验后）。

    与 `separate_match_endpoint` 的返回结构保持一致，前端无需分支：
      status / match_rate / matched_count / total_questions / questions /
      unmatched_question_numbers / extra_answer_numbers / analysis_count /
      strategy_used / auto_detected_subject / details / message
    额外附 `xingce_report` 承载分节区间与五项校验明细，便于前端展示阻断原因。
    """
    # 延迟导入：本文件既有惯例（:2281 / :2664 / :3123）。刻意**不**放到文件
    # 顶部——那会使 `separate_match_endpoint` 与共享 dispatch 的行号整体位移，
    # 红线断言「dispatch :4005-4011 零改动」将无法用行号定位验证。
    # 共享 dispatch 链路不引用任何行测符号，公专/申论零影响。
    from ....services.text_parser import (
        route_xingce_sections,
        xingce_cross_validate,
        XINGCE_QNUM_PATTERN,
    )
    from ....services.composite_matcher import match_xingce_material_groups

    # ① 分节路由（题本坐标系）—— 材料块只在题本侧，答案解析不重复材料。
    #    必须与题号位置同坐标系，跨文档混用偏移量会把成员划分彻底搅乱。
    sec_info = route_xingce_sections(questions_text) or {}
    sections = sec_info.get('sections') or []
    materials = sec_info.get('materials') or []

    # ② 配对安全网：内含 extract_question_blocks 双侧切分 + route_xingce_sections
    #    双侧分节 + 答案锚点切分，此处一次调用即完成计划步骤 1-3。
    merged = xingce_cross_validate(questions_text, answers_text)
    qs = merged['questions']
    report = merged['report']

    # ③ 材料 → 小题归组。题号位置取自题本，且用 XINGCE_QNUM_PATTERN（已排除
    #    「780.9毫米」这类小数伪题号），与任务 9 实测口径一致。
    qno_positions = []
    for m in XINGCE_QNUM_PATTERN.finditer(questions_text):
        sec_name = ''
        for s in sections:
            if s['start'] <= m.start() < s['end']:
                sec_name = s['name']
                break
        qno_positions.append((int(m.group(1)), m.start(), sec_name))
    qno_positions.sort(key=lambda t: t[1])
    groups = match_xingce_material_groups(materials, qno_positions, sections)

    qno_to_group = {}
    for g in groups:
        # W2：把材料正文从题本文本切出来挂到组上。此前本函数只回传 start/end
        # 字符区间，落库阶段拿不到 questions_text，材料永远无法入库（行测题组数为 0）。
        g['material_text'] = questions_text[g['start']:g['end'] if g['end'] > 0 else None]
        for qno in g['member_qnums']:
            qno_to_group[qno] = g

    # ④ 分区落位 + 考点归一 + 材料关联
    kao_map = _xingce_kao_normalize_map()
    for q in qs:
        sec_name = q.get('section_name') or ''
        q['xingce_subcategory'] = (sec_name if sec_name in _XINGCE_SUB_CATEGORIES
                                   else '无')
        raw_kao = q.get('kao_points') or []
        q['kao_points_normalized'] = [kao_map.get(k, k) for k in raw_kao]
        g = qno_to_group.get(_as_int(q.get('question_number')))
        q['material_group'] = ({
            'ordinal': g['ordinal'],
            'group_type': g['group_type'],
            'section': g['section'],
            'sort_order': g['member_qnums'].index(
                _as_int(q.get('question_number'))) + 1,
        } if g else None)
        if g:
            # 落库侧 confirm_batch_import 直接读这两个字段建组并回填层级/组序，
            # 不必在前端再解一次 material_group。
            q['material_text'] = g.get('material_text') or ''
            q['question_level'] = 2
            q['sort_order'] = q['material_group']['sort_order']
        # 待复核标记：必须在 material_group 定下来之后才算，否则「材料关联异常」
        # 会把尚未归组的题全部误标。
        reasons = _xingce_review_flags(q)
        q['need_review'] = 1 if reasons else 0
        q['review_reasons'] = reasons

    if not subject_name:
        subject_name = '行测'
    subject = _get_or_create_subject(db, subject_name)

    # ⑤ 去重检测：与既有链路同口径
    dup_cnt = 0
    for q in qs:
        content = q.get('content') or ''
        dup_info = _get_duplicate_info(db, content, q.get('answer') or '',
                                       subject.subject_id)
        q['is_duplicate'] = dup_info['is_duplicate']
        q['similarity'] = dup_info['similarity']
        if dup_info['is_duplicate']:
            q['existing_id'] = dup_info['existing_id']
            dup_cnt += 1

    total = report.get('question_count') or 0
    blocked_count = report.get('blocked_count') or 0
    ok_cnt = total - blocked_count
    rate = (ok_cnt / total * 100) if total else 0.0

    # ⑥ blocked 语义：存在 blocked 题即**不生成可确认入库的预览**
    #    （对齐申论 v4 §T8）。preview_confirmable=False 时前端必须禁用确认入库。
    preview_confirmable = blocked_count == 0

    # ⑦ 状态落库：只 add + flush 取 import_id，**不 commit**。
    #    沿用既有「preview 不落库、confirm 才落库」的两阶段约定。
    record = QuestionImportRecord(
        user_id=user_id,
        original_filename=payload.get('paper_name') or '行测分离导入',
        file_type='PDF',
        total_questions=total,
        success_count=ok_cnt,
        failed_count=blocked_count,
        duplicate_count=dup_cnt,
        import_status='PREVIEW',
        progress_percent=100,
        current_phase='DONE',
        preview_data={
            'strategy': 'xingce_section_cross_validate',
            'match_rate': round(rate, 1),
            'matched': report.get('matched'),
            'blocked_count': blocked_count,
        },
        import_time=datetime.now(),
    )
    db.add(record)
    try:
        db.flush()
        import_id = record.import_id
    except Exception:
        db.rollback()
        import_id = None

    xingce_report = dict(report)
    xingce_report.update({
        'section_names': sec_info.get('section_names') or [],
        'section_intervals_q': (report.get('section_intervals') or {}).get('q', []),
        'material_count': sec_info.get('material_count', 0),
        'materials_by_section': sec_info.get('materials_by_section') or {},
        'material_groups': groups,
        'preview_confirmable': preview_confirmable,
        'import_id': import_id,
        'kao_coverage': report.get('kao_coverage'),
    })

    # 本端点无 db.commit()（get_db 只 yield 后 close），record 不会落库，
    # 故分组元数据只能随 questions 逐题回传，不能挂到 record 上。

    return {
        'status': 'success',
        'match_rate': round(rate, 1),
        'matched_count': ok_cnt,
        'total_questions': total,
        'questions': qs,
        'unmatched_question_numbers': report.get('only_in_answers') or [],
        'extra_answer_numbers': report.get('spurious_question_numbers') or [],
        'analysis_count': sum(1 for q in qs if (q.get('analysis') or '').strip()),
        'strategy_used': 'xingce_section_cross_validate',
        'auto_detected_subject': subject_name,
        'details': report.get('details'),
        'xingce_report': xingce_report,
        'message': ('行测分节区间校验完成：%s%%（%d/%d 通过）%s'
                    % (round(rate, 1), ok_cnt, total,
                       '' if preview_confirmable
                       else '；存在 %d 题被阻断，不可确认入库' % blocked_count)),
    }


def _as_int(v):
    """题号在 block 里可能是 str 或 int（实测首条为 '1'），统一为 int 便于匹配。"""
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@router.post("/separate-match-xingce", summary="行测分离导入智能匹配（专用端点）")
async def separate_match_xingce_endpoint(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    接收行测题目文本与答案解析文本，做分节区间安全网校验后返回匹配结果。

    与 `/separate-match` 的区别：仅在**科目为行测**时走本端点，且配对依据是
    分节头序列与分区题号区间，而非按序硬配。共享 dispatch 未被改动，
    公专与申论仍走原端点。

    参数：
    - questions_text: 题本全文（必填）
    - answers_text: 答案解析全文（必填）
    - paper_name: 试卷名称（可选）
    - subject_category: 科目（可选，缺省「行测」）

    返回：
    - 与 `/separate-match` 完全一致的 12 个字段，外加 `xingce_report`
    - `xingce_report.preview_confirmable=False` 表示存在被阻断题目，
      此时**不得**确认入库
    """
    questions_text = (payload.get('questions_text') or '').strip()
    answers_text = (payload.get('answers_text') or '').strip()

    if not questions_text:
        raise HTTPException(status_code=400, detail="题目文件文本为空")
    if not answers_text:
        raise HTTPException(status_code=400, detail="答案文件文本为空")

    # ★ 任务 21（模块 C-5）：本端点与 `/separate-match` 共用**同一套**校验入口。
    #   行测文档 → `xingce_cross_validate` 五项安全网（自身判据）；
    #   若两份文档实为**申论**（例如用户在行测端点误传申论卷），
    #   改走与 `/separate-match` 完全相同的 `_essay_cross_validate`，
    #   绝不落到行测分节判据上被误判为「非行测试卷」而错配。
    #   `_separate_match_essay` 返回的 12 个公共字段与本端点完全一致，前端无需分支。
    _xq_blocks = extract_question_blocks(questions_text)
    _xa_blocks = extract_question_blocks(answers_text)
    _xq_is_essay = bool(_xq_blocks) and _xq_blocks[0].get('format') == 'essay'
    _xa_is_essay = bool(_xa_blocks) and _xa_blocks[0].get('format') == 'essay'
    if _xq_is_essay and _xa_is_essay:
        _response = _separate_match_essay(
            db, payload, _xq_blocks, _xa_blocks,
            subject_name=payload.get('subject_category', ''))
    else:
        try:
            _response = _separate_match_xingce(
                db, payload, questions_text, answers_text,
                user_id=current_user.user_id,
                subject_name=payload.get('subject_category', ''))
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"行测分离导入匹配失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"行测智能匹配失败: {str(e)}")

    # W2-1：追加「科目建议 + 置信度」（不改既有字段，向后兼容）。
    # 手选（subject_category）存在 → 建议即以手选为准；否则自动识别。
    _x_sug_text = ' '.join(
        (q.get('content') or '') for q in (_response.get('questions') or [])[:10])
    if not _x_sug_text:
        _x_sug_text = questions_text
    subject_suggestion = _build_subject_suggestion(
        _x_sug_text, payload.get('subject_category', ''))
    _x_subject_id = SUBJECT_NAME_MAP.get(subject_suggestion.get('name') or '')
    subcategory_suggestion = _build_subcategory_suggestion(
        _x_subject_id, _x_sug_text) if _x_subject_id else {
            'name': '', 'confidence': 0.0}
    _response['subject_suggestion'] = subject_suggestion
    _response['subcategory_suggestion'] = subcategory_suggestion
    # F-1：与 /parse、/status 同口径 —— 返回前 sanitize 裸 [IMAGE:] 占位符，
    # 否则前端 renderQuestionContent 会把残留 marker 剥空导致图片消失。
    _sanitize_preview_images(_response, None, db)
    return _response


# ══════════════════════════════════════════════════════════════════════
# 行测卷级元数据注入（任务 12）
#
# 核心决策：**省份只能来自文件夹名**。实测 170 份文件名里的省份写法极不可靠
# —— 2025 年安徽/河南/山西/陕西/黑龙江全部缺「省」字，甘肃 3 个年份全省缺「省」，
# 广西写「区考」；而 24 个省级文件夹名干净一致。
# 故本模块把文件夹名作为**显式覆盖**置于 `_auto_detect_tags()` 推断**之前**，
# 且不修改 `_auto_detect_tags()` 一行（公专/申论在用）。
#
# 文件名**只**用于提取年份与卷别，绝不用于省份。
# 全部推导均为实时正则/字符串运算，不硬编码 85 套映射表。
# ══════════════════════════════════════════════════════════════════════

# 卷别实测全集（顺序敏感：长标识在前，避免 '乡镇' 抢先命中 '区级及以上卷'）
_XINGCE_PAPER_VARIANTS = (
    ('副省级', '副省级'),
    ('地市级', '地市级'),
    ('行政执法', '行政执法卷'),
    ('区级及以上', '区级及以上卷'),
    ('乡镇', '乡镇卷'),
    ('县级', '县级卷'),
)
# 江苏 A/B/C 类，形如 （A类）
_XINGCE_ABC_RE = re.compile(r'[（(]\s*([ABC])\s*类\s*[）)]')
# 文件名中的年份
_XINGCE_YEAR_RE = re.compile(r'(20\d{2})')
# 题本角色的全部命名变体：题本 / 题干(国考2025地市级冒充) / 试题(山东) / 题目
_XINGCE_Q_ROLE = ('题本', '题干', '试题', '题目')


def _xingce_folder_province(folder_name: str) -> Optional[str]:
    """从**文件夹名**取省份 —— 行测唯一的可靠省份来源。

    只做 basename 语义上的字符串剥离，不做任何路径拼接。
    国考/全国卷无省份归属，返回 None。
    """
    name = (folder_name or '').strip()
    for suf in ('行测', '申论', '公专'):
        if name.endswith(suf):
            name = name[:-len(suf)]
            break
    name = name.strip()
    if not name or name in ('国考', '国家', '中央', '全国'):
        return None
    return name


def _xingce_doc_role(filename: str) -> str:
    """判定单个 PDF 的角色：'questions' / 'answers' / 'unknown'。

    覆盖 5 类命名异常中的两类：
      - `题干.pdf`（国考 2025 地市级，唯一一处「文件名不含题本」）
      - `试题`（山东 2022-2024 用「试题」而非「题」）
    """
    base = os.path.basename(filename or '')
    if '答案' in base:
        return 'answers'
    for token in _XINGCE_Q_ROLE:
        if token in base:
            return 'questions'
    return 'unknown'


def _xingce_paper_variant(filename: str) -> Optional[str]:
    """从文件名提取卷别。无卷别者返回 None（实测 22 省均无卷别标记）。"""
    base = os.path.basename(filename or '')
    m = _XINGCE_ABC_RE.search(base)
    if m:
        return m.group(1) + '类'
    for key, label in _XINGCE_PAPER_VARIANTS:
        if key in base:
            return label
    return None


def _resolve_xingce_paper_metadata(folder_name: str, filename: str,
                                   text: str = '',
                                   paper_name: str = '') -> Dict[str, Any]:
    """行测卷级元数据：**显式覆盖 > 既有推断**。

    传给 `_auto_detect_tags()` 的一律是 `os.path.basename()`，
    绝不让文件夹路径或用户输入进入任何文件路径拼接。
    """
    base = os.path.basename(filename or '')
    tags = _auto_detect_tags(base, text or '')

    # 年份：文件名优先（实测 170/170 均含 20d{2}），回退既有推断
    ym = _XINGCE_YEAR_RE.search(base)
    if ym:
        tags['exam_year'] = int(ym.group(1))

    # 省份：**只**认文件夹名。既有按文件名/正文推断的结果一律丢弃 ——
    # 计划的硬约束是「禁止用文件名推断省份」，实测文件名省份写法不可靠
    #（2025 安徽/河南/山西/陕西/黑龙江缺「省」，甘肃全年缺「省」，广西写「区考」）。
    prov = _xingce_folder_province(folder_name)
    if prov:
        tags['exam_province'] = prov
    elif (folder_name or '').strip() in ('国考行测', '国考'):
        tags['exam_province'] = '国考'      # 全国卷：显式标注，非省份
    else:
        # 无文件夹名 → 宁缺勿滥，绝不退化为按文件名猜省份
        tags['exam_province'] = None

    # 考试类型：国考卷 vs 省考卷（含广西「区考」归入省考口径）
    tags['exam_type'] = '国考' if (folder_name or '').strip() in ('国考行测', '国考') \
        else '省考'
    tags['subject_category'] = '行测'
    tags['paper_variant'] = _xingce_paper_variant(base)
    tags['doc_role'] = _xingce_doc_role(base)
    if paper_name:
        tags['paper_name'] = paper_name
    return tags


def _upsert_xingce_paper(db: Session, user, meta: Dict[str, Any],
                         paper_name: str, question_count: int,
                         is_complete: Optional[bool] = None):
    """行测试卷 + 标签的**幂等**落库（复用既有查重与 ENDED→DRAFT 复活逻辑）。

    与 `_get_or_create_import_paper()` 的区别：**绝不 commit** —— 既有函数在
    `:1624` 有 `db.commit()`，会破坏「preview 不落库、confirm 才落库」两阶段约定。

    Returns: (paper, created_flag)
    """
    from ....models.models import ExamPaper, ExamPaperTag
    from .paper_generation import generate_paper_code

    if question_count < 5:      # 与既有阈值一致
        return None, False

    # 查重：同名 + 同创建者 → 复用（前序 P2.2 已验证）
    existing = db.query(ExamPaper).filter(
        ExamPaper.paper_name == paper_name,
        ExamPaper.creator_id == user.user_id
    ).first()
    created = False
    if existing:
        if existing.paper_type == 'ENDED':       # P2.2 复活
            existing.paper_type = 'DRAFT'
        paper = existing
    else:
        paper = ExamPaper(
            paper_name=paper_name,
            paper_code=generate_paper_code(),
            subject_id=SUBJECT_NAME_MAP.get('行测', 1),
            composition_method='IMPORT',
            creator_id=user.user_id,
            duration=120,
            total_score=100,
            difficulty=3,
            exam_type='SIMULATION',
            paper_type='DRAFT',
            question_count=0,
        )
        db.add(paper)
        db.flush()
        created = True

    # 标签幂等 upsert：同一 paper 只保留一行，逐字段刷新
    tag = db.query(ExamPaperTag).filter(
        ExamPaperTag.paper_id == paper.paper_id).first()
    if tag is None:
        tag = ExamPaperTag(paper_id=paper.paper_id)
        db.add(tag)
    tag.exam_year = meta.get('exam_year')
    tag.exam_province = meta.get('exam_province')
    tag.exam_type = meta.get('exam_type')
    tag.subject_category = '行测'
    # 修正既有 is_complete=0 的行测失败痕迹（实测 paper_id 14/15）。
    # 调用方可显式覆盖：行测题本+答案解析配对成功即完整卷，而
    # `_detect_complete_paper()` 在文本为空时会返回 False（它要求≥200 字
    # 且能匹配答案区），故需要一个不依赖文本的显式入口。
    if is_complete is None:
        is_complete = bool(meta.get('is_complete_paper'))
    tag.is_complete = 1 if is_complete else 0
    db.flush()
    return paper, created


def _xingce_review_flags(q: Dict[str, Any]) -> List[str]:
    """行测题的待复核原因清单（任一非空即 need_review=1）。

    与 ``blocked`` 是**两套语义，不可混用**：
      - ``blocked`` 阻断「确认导入」，前端按钮置灰；
      - ``need_review`` 只标红提示，**仍然入库**（用户决策 Q2：不达标也入库，
        绝不静默丢弃）。
    本函数绝不产出 blocked 语义，也绝不因为缺答案/缺解析而拦下题目。

    四类情形（对应计划表）：
      1. 选项标记存在但文字全空 → 纯图片选项，需人工补文字
      2. 答案缺失
      3. 解析缺失
      4. 资料分析题未关联到材料块 → 材料传播异常
    另保留原有的「题型存疑」语义（``suspicious``），使既有 7 条 need_review=1
    记录的含义不被本扩展稀释。
    """
    reasons: List[str] = []
    opts = q.get('options')
    # options 实测**恒为 list** of {'key','value'}（行测 130/130），
    # 但既有公专链路产出 dict —— 两种形态都必须兼容，否则
    # `opts.values()` 会在 list 上抛 AttributeError（此缺陷由
    # verify_task13_images.py 在真实 Q126 上捕获）。
    if isinstance(opts, dict):
        keys = list(opts.keys())
        vals = list(opts.values())
    elif isinstance(opts, list):
        pairs = [o for o in opts if isinstance(o, dict)]
        keys = [o.get('key') for o in pairs]
        vals = [o.get('value') for o in pairs]
        if len(pairs) != len(opts):
            reasons.append('选项结构异常')
    else:
        keys, vals = [], []

    if vals and all(not str(v or '').strip() for v in vals):
        reasons.append('选项待补文字')
    # 行测四选项题（单选/多选）的 A/B/C/D 应齐全；实测发现真实错位样本：
    # 国考 2025 地市级 Q126 只解析出 [{'A','B.'},{'C','D.'}] —— 2 个键，
    # 且值是字面标签，说明切分点落在了选项行内部而非题干/选项边界。
    if 0 < len(keys) < 4:
        reasons.append('选项残缺')
    # 值形如 'B.' / 'D.'：选项内容被误当成键值对的内容，指向同一种错位
    if any(re.fullmatch(r'[A-DＡ-Ｄ][.．、]?', str(v or '').strip())
           for v in vals):
        reasons.append('选项值疑似错位')
    if not str(q.get('answer') or '').strip():
        reasons.append('答案缺失')
    if not str(q.get('analysis') or '').strip():
        reasons.append('解析缺失')
    if (q.get('section_name') or '') == '资料分析' and not q.get('material_group'):
        reasons.append('材料关联异常')
    if q.get('suspicious'):
        reasons.append('题型存疑')
    return reasons


@router.get('/mineru-health', summary='MinerU引擎健康巡检')
async def mineru_health():
    """探测独立venv中MinerU是否可用（结果缓存10分钟）。

    供运维巡检与前端诊断使用；不鉴权、仅暴露可用性/版本，不含敏感路径信息。
    """
    return mineru_health_cached()


def _subject_from_paper_name(paper_name: str) -> str:
    """从试卷名称精确提取科目（B 修复：文档名强信号直接归类）。

    仅精确匹配科目词；无信号返回空字符串（调用方走文本检测）。
    """
    name = paper_name or ''
    for kw, subj in (('申论', '申论'), ('行政职业能力', '行测'), ('行测', '行测'),
                     ('公安', '公专'), ('招警', '公专')):
        if kw in name:
            return subj
    return ''


@router.post("/parse", summary="统一文档解析（Pipeline入口）")
async def unified_parse(
    payload: ParseRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    统一文档解析端点 —— 替代前端所有本地解析逻辑。

    支持三种模式：
    - combined: 合并导入（单文档含题+答）→ 提取题目块
    - separate: 分离导入（题目文档+答案文档）→ 智能匹配
    - ocr: 图片OCR文本 → 提取题目结构

    返回 ParseResult，前端仅负责渲染和用户修正。
    """
    from ....services.text_parser import (
        extract_question_blocks, smart_match_questions_answers,
        detect_subject_category, ContentCleaner, _extract_options,
        extract_answer_from_lines, _detect_question_type,
    )
    from ....services.question_ingest.pairing import (
        filename_similarity, diagnose_filename_pair,
    )

    mode = payload.mode or 'combined'
    questions_text = (payload.questions_text or '').strip()
    answers_text = (payload.answers_text or '').strip()
    paper_name = payload.paper_name or ''
    subject_category = payload.subject_category or ''
    questions_filename = (payload.questions_filename or '').strip()
    answers_filename = (payload.answers_filename or '').strip()

    if not questions_text:
        raise HTTPException(status_code=400, detail="题目文本为空")

    warnings = []
    questions = []
    match_rate = 0.0
    matched_count = 0
    total_questions = 0
    analysis_count = 0
    unmatched_numbers = []
    extra_answer_numbers = []
    strategy_used = ''
    auto_detected_subject = subject_category
    # 预初始化：申论路径不经过 smart_match，result 不存在；非 separate 分支也不走它
    result = None
    essay_prebuilt = None
    # C-2：文件名相似度信号（非 separate 分支保持 0.0）
    _filename_sim = 0.0
    # F-8：组聚合轻量字段（供 _build_preview_groups，默认空）
    _group_items = []
    # W2-1：科目建议（追加字段，先初始化为空建议，分支内检测到后再填充）
    subject_suggestion = {'name': '', 'confidence': 0.0, 'matched_keywords': []}

    try:
        if mode == 'separate' and answers_text:
            # ===== 分离导入 =====
            # ★ 申论优先：两份文档都判定为申论时走「题号+分值+题干指纹」三方交叉校验。
            #   smart_match_questions_answers 是选择题匹配器（按选项字母/答案长度比对），
            #   对申论长文本答案必然匹配失败 → match_rate 0%
            #   → 前端弹「匹配率偏低（0%）。请使用手动匹配界面进行人工匹配」，
            #   逼用户逐题手工匹配。申论的正确判据是三方交叉校验，不是选项匹配。
            _sq = extract_question_blocks(questions_text)
            _sa = extract_question_blocks(answers_text)
            _essay_sep = (bool(_sq) and _sq[0].get('format') == 'essay'
                          and bool(_sa) and _sa[0].get('format') == 'essay')
            if _essay_sep:
                merged = _essay_cross_validate(_sq, _sa)
                _qs = merged['questions']
                _rep = merged['report']
                total_questions = _rep['question_count']
                matched_count = total_questions - _rep['blocked_count']
                match_rate = round((matched_count * 100 / total_questions)
                                   if total_questions else 0.0, 1)
                unmatched_numbers = _rep['only_in_answers']
                extra_answer_numbers = _rep['only_in_answers']
                analysis_count = sum(1 for q in _qs if (q.get('analysis') or '').strip())
                strategy_used = 'essay_triple_cross_validate'
                auto_detected_subject = auto_detected_subject or '申论'
                # 申论块已是完整结构，直接复用 combined 分支的统一转换逻辑
                essay_prebuilt = _qs
            else:
                # C-2：文件名配对信号 —— 相似度高时提升位置兜底匹配优先级（B 力度）
                _filename_sim = filename_similarity(
                    questions_filename, answers_filename) if (
                    questions_filename and answers_filename) else 0.0
                result = smart_match_questions_answers(
                    questions_text, answers_text, paper_name, _filename_sim)
                match_rate = round(result.match_rate * 100, 1)
                matched_count = result.matched_count
                total_questions = result.total_questions
                unmatched_numbers = result.unmatched_question_numbers
                extra_answer_numbers = result.extra_answer_numbers
                analysis_count = result.analysis_count
                strategy_used = result.strategy_used
                essay_prebuilt = None
                # C-2：文件名诊断提示（相似度高但匹配失败 / 相似度低）
                _diag = diagnose_filename_pair(
                    questions_filename, answers_filename, result.match_rate * 100)
                if _diag:
                    warnings.append(_diag)

                # C 修复：文档名科目强信号（提示但可覆盖——不强制改归类）
                _name_hint = ''
                for _kw, _subj in (('申论', '申论'), ('行政职业能力', '行测'),
                                   ('行测', '行测'), ('公安', '公专'), ('招警', '公专')):
                    if _kw in (paper_name or ''):
                        _name_hint = _subj
                        break
                if _name_hint and auto_detected_subject and _name_hint != auto_detected_subject:
                    warnings.append(
                        f'文档名含「{_name_hint}」信号，但当前归类为「{auto_detected_subject}」。'
                        f'如分类有误，请在上方手动选择科目后重新匹配。')

            if not auto_detected_subject:
                # B 修复：文档名强信号直接归类（文件名精确含科目词即归类），
                # 无信号才用完整题目文本检测（此前用前10题切碎文本曾误判申论）
                auto_detected_subject = _subject_from_paper_name(paper_name) or ''
                if auto_detected_subject:
                    subject_suggestion = {
                        'name': auto_detected_subject, 'confidence': 1.0,
                        'matched_keywords': ['文档名'],
                    }
                else:
                    all_content = ' '.join(q.get('content', '') for q in result.questions)
                    _subject_det = detect_subject_category(all_content)
                    auto_detected_subject = _subject_det.subject_name
                    subject_suggestion = {
                        'name': _subject_det.subject_name,
                        'confidence': _subject_det.confidence,
                        'matched_keywords': list(_subject_det.matched_keywords or []),
                    }

            # 转换为 ParsedQuestion
            for block in (essay_prebuilt if essay_prebuilt is not None
                          else result.questions):
                q_num = block.get('question_number', 0)
                content = block.get('content', '')
                answer = block.get('answer', '') or '待补充'
                analysis = block.get('analysis', '')
                qtype = block.get('question_type', '单选题')
                options = block.get('options', [])

                # 去重检测
                dup_info = _get_duplicate_info(
                    db, content, answer if answer != '待补充' else '',
                    SUBJECT_NAME_MAP.get(auto_detected_subject)
                )

                # 提取图片引用
                images = _extract_image_refs_from_content(content)

                questions.append(ParsedQuestion(
                    question_number=q_num,
                    question_content=content[:50000],
                    options=options,
                    answer=answer,
                    analysis=analysis[:50000] if analysis else None,
                    images=images,
                    question_type=qtype,
                    subject_category=auto_detected_subject,
                ))

                # F-8：收集组聚合所需的轻量字段（供 _build_preview_groups）
                _group_items.append({
                    'material_text': block.get('material_text', ''),
                    'material_titles': block.get('material_titles', []),
                    'format': block.get('format', ''),
                    'question_number': block.get('question_number'),
                    'sort_order': block.get('sort_order'),
                })

        else:
            # ===== 合并导入 / OCR模式：提取题目块 =====
            cleaned_text = ContentCleaner.clean_text(questions_text)
            blocks = extract_question_blocks(cleaned_text)

            # ★ 任务 21（模块 C-5）：合并导入与分离导入**共用同一套**三方交叉校验。
            #   合订本（题+答在同一文档）的答案区常集中在文末，解析器按序配对
            #   只校验「段数==题数」，一旦相等便整卷放行 —— 正是「计数相等但错配」。
            #   这里把文档切成题目侧/答案侧，喂给与 /separate-match **完全相同**的
            #   `_essay_cross_validate`，逐题比对题号+分值+题干指纹。
            #   非申论文档、或无文末统一答案区（形态②③ 就地配对）→ 返回 None，
            #   完全走既有逻辑，**公专/行测零影响**。
            _essay_import = _essay_cross_validate_import(cleaned_text)
            _essay_merged = _essay_import or {}
            _essay_blocked_by_no = {}
            if _essay_merged.get('report'):
                _rep_combined = _essay_merged['report']
                # 用校验后的块替换解析块：blocked 题的 answer 已被强制清空，
                # 后续按序/就近填充答案的路径一律失效（禁止按序硬配）。
                blocks = _essay_merged['questions'] or blocks
                for _b in blocks:
                    if _b.get('blocked'):
                        _essay_blocked_by_no[str(_b.get('question_number'))] = \
                            list(_b.get('block_reasons') or [])

            if not blocks:
                # 回退：尝试用前端兼容的宽松解析（按行切分）
                warnings.append('未检测到标准题号格式，已尝试宽松解析')
                blocks = _fallback_loose_parse(cleaned_text)

            if not auto_detected_subject:
                # B 修复：文档名强信号直接归类，无信号才用完整题目文本检测
                auto_detected_subject = _subject_from_paper_name(paper_name) or ''
                if auto_detected_subject:
                    subject_suggestion = {
                        'name': auto_detected_subject, 'confidence': 1.0,
                        'matched_keywords': ['文档名'],
                    }
                else:
                    all_content = ' '.join(b.get('content', '') for b in blocks)
                    _subject_det = detect_subject_category(all_content)
                    auto_detected_subject = _subject_det.subject_name
                    subject_suggestion = {
                        'name': _subject_det.subject_name,
                        'confidence': _subject_det.confidence,
                        'matched_keywords': list(_subject_det.matched_keywords or []),
                    }

            total_questions = len(blocks)
            for block in blocks:
                q_num = block.get('question_number', 0)
                content = block.get('content', '')
                answer = block.get('answer', '') or '待补充'
                analysis = block.get('analysis', '')
                qtype = block.get('question_type', '单选题')
                options = block.get('options', [])
                # 三方交叉校验的阻断原因 → 映射为校验异常，让前端读出并阻止入库
                _block_reasons = _essay_blocked_by_no.get(str(q_num)) or []

                # 去重检测
                dup_info = _get_duplicate_info(
                    db, content, answer if answer != '待补充' else '',
                    SUBJECT_NAME_MAP.get(auto_detected_subject)
                )

                # 提取图片引用
                images = _extract_image_refs_from_content(content)

                questions.append(ParsedQuestion(
                    question_number=q_num,
                    question_content=content[:50000],
                    options=options,
                    answer=answer,
                    analysis=analysis[:50000] if analysis else None,
                    images=images,
                    question_type=qtype,
                    subject_category=auto_detected_subject,
                    validation_errors=_block_reasons,
                ))

                # F-8：收集组聚合所需的轻量字段（供 _build_preview_groups）
                _group_items.append({
                    'material_text': block.get('material_text', ''),
                    'material_titles': block.get('material_titles', []),
                    'format': block.get('format', ''),
                    'question_number': block.get('question_number'),
                    'sort_order': block.get('sort_order'),
                })

            # 统计匹配结果
            if _essay_merged.get('report'):
                # 申论合并导入：通过率以「三方交叉校验」为准，blocked 题不计入通过
                _blocked_cnt = _rep_combined['blocked_count']
                matched_count = max(total_questions - _blocked_cnt, 0)
                analysis_count = sum(1 for q in questions
                                     if q.analysis and len(q.analysis) > 10)
                match_rate = round(matched_count * 100 / total_questions, 1) \
                    if total_questions else 0.0
                strategy_used = 'essay_triple_cross_validate'
                if _blocked_cnt:
                    warnings.append(
                        '三方交叉校验阻断 %d/%d 题（含题干与答案卷不匹配），'
                        '请核对是否上传了错误年份/卷别' % (_blocked_cnt, total_questions))
            else:
                matched_count = sum(1 for q in questions if q.answer and q.answer != '待补充')
                analysis_count = sum(1 for q in questions if q.analysis and len(q.analysis) > 10)
                if total_questions > 0:
                    match_rate = round(matched_count * 100 / total_questions, 1)
                strategy_used = '合并导入解析'

        # W2-1：科目建议手选优先 —— payload.subject_category 存在即跳过自动识别；
        # 分支未触发自动识别（如申论 separate 强制 '申论'）时以 auto_detected_subject 为准。
        if subject_category:
            subject_suggestion = _build_subject_suggestion('', subject_category)
        elif not subject_suggestion.get('name') and auto_detected_subject:
            subject_suggestion = {
                'name': auto_detected_subject, 'confidence': 1.0,
                'matched_keywords': []}
        # W2-1：子科目建议（基于建议科目；无科目建议时为空建议）
        _suggested_subject_id = SUBJECT_NAME_MAP.get(subject_suggestion.get('name') or '')
        subcategory_suggestion = (
            _build_subcategory_suggestion(
                _suggested_subject_id,
                ' '.join((q.question_content or '') for q in questions[:10]))
            if _suggested_subject_id else {'name': '', 'confidence': 0.0})

        # 自动检测标签
        auto_tags = _auto_detect_tags(paper_name, questions_text[:2000])

        # ===== Validator: 数据完整性校验 + 置信度评分 =====
        from ....services.text_parser import AnswerValidator
        questions = AnswerValidator.validate(
            [q.model_dump() if hasattr(q, 'model_dump') else (
                q.dict() if hasattr(q, 'dict') else q
            ) for q in questions],
            strategy_used
        )
        # 重新转换为 ParsedQuestion（保留校验结果）
        validated_questions = []
        for q_data in questions:
            validated_questions.append(ParsedQuestion(
                question_number=q_data.get('question_number', 0),
                question_content=q_data.get('question_content', ''),
                options=q_data.get('options', []),
                answer=q_data.get('answer'),
                analysis=q_data.get('analysis'),
                images=q_data.get('images', []),
                question_type=q_data.get('question_type', '单选题'),
                subject_category=q_data.get('subject_category'),
                confidence=q_data.get('confidence', 1.0),
                validation_errors=q_data.get('validation_errors', []),
            ))
        questions = validated_questions

        # 收集校验警告
        low_confidence = [q.question_number for q in questions if q.confidence < 0.5]
        if low_confidence:
            warnings.append(f'低置信度题目(建议人工核对): 第{",".join(map(str, low_confidence[:10]))}题')
        invalid_answers = [q.question_number for q in questions if q.validation_errors]
        if invalid_answers:
            warnings.append(f'校验异常题目: 第{",".join(map(str, invalid_answers[:10]))}题')

        _parse_result = ParseResult(
            status='success' if match_rate >= 80 or mode != 'separate' else 'partial',
            questions=questions,
            match_rate=match_rate,
            matched_count=matched_count,
            total_questions=total_questions,
            unmatched_numbers=unmatched_numbers,
            extra_answer_numbers=extra_answer_numbers,
            analysis_count=analysis_count,
            strategy_used=strategy_used,
            auto_detected_subject=auto_detected_subject,
            auto_detected_tags=auto_tags,
            warnings=warnings,
            raw_text_preview=questions_text[:100000],
        )
        # W2-1：追加「科目建议 + 置信度」字段（不改既有字段，向后兼容）
        _response = (_parse_result.model_dump()
                     if hasattr(_parse_result, 'model_dump')
                     else _parse_result.dict())
        _response['subject_suggestion'] = subject_suggestion
        _response['subcategory_suggestion'] = subcategory_suggestion
        # F-8：返回复合题组结构（与 /upload 预览同构），供前端按组同框渲染
        _response['groups'] = _build_preview_groups(_group_items)
        # C-2：文件名相似度信号（前端可展示配对可信度）
        _response['filename_similarity'] = _filename_sim
        # A-2：与 /status 预览路径一致 —— 返回前 sanitize 裸 [IMAGE:xxx] 占位符，
        # 否则前端 renderQuestionContent 会整段剔除导致图片消失。本端点无 import_id，
        # 传 None：resolve_image_marker 回落扁平暂存目录（复用 /status 的同一 helper）。
        _sanitize_preview_images(_response, None, db)
        return _response

    except Exception as e:
        logger.error(f"统一解析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文档解析失败: {str(e)}")


def _extract_image_refs_from_content(content: str) -> list:
    """从题目内容中提取 [IMAGE:xxx] 占位符，返回 ImageRef 列表"""
    import re as _re
    refs = []
    markers = _re.findall(r'\[IMAGE:([^\]]+)\]', content or '')
    for i, marker in enumerate(markers):
        # 判断位置：在选项标记A.B.C.D.之后的为选项图片
        position = 'stem'
        idx = (content or '').find(f'[IMAGE:{marker}]')
        if idx > 0:
            before = content[:idx]
            # 检查最后一个选项标记
            last_opt = _re.findall(r'([A-D])\s*[.、．)）]', before)
            if last_opt:
                position = f'option_{last_opt[-1]}'
        refs.append({'path': f'[IMAGE:{marker}]', 'position': position, 'order': i})
    return refs


def _fallback_loose_parse(text: str) -> List[Dict[str, Any]]:
    """
    宽松回退解析（当标准题号检测失败时）。
    按空行分段，每段作为一道题。
    """
    from ....services.text_parser import _extract_options, extract_answer_from_lines, _detect_question_type

    # 按双换行分段
    paragraphs = re.split(r'\n\s*\n', text)
    blocks = []
    q_num = 1

    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 10:
            continue

        lines = para.split('\n')
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 简单题号检测
            m = re.match(r'^(?:第\s*)?(\d+)\s*(?:[.、．)）\]】]|\s*题)\s*', stripped)
            if m:
                q_num = int(m.group(1))
                rest = stripped[m.end():].strip()
                if rest:
                    content_lines.append(rest)
            else:
                content_lines.append(stripped)

        if not content_lines:
            continue

        options = _extract_options(content_lines)
        extracted = extract_answer_from_lines(content_lines)
        answer = extracted.get('answer') if extracted else None
        analysis = extracted.get('analysis') if extracted else None
        # ★ 返回的是 (type_name, confidence) 元组，必须解包
        _qtype_name, _conf1 = _detect_question_type(
            '\n'.join(content_lines), options, answer or '')
        qtype = _get_or_create_type(db, _qtype_name, subject.subject_id)

        # 移除选项行
        content = '\n'.join(content_lines)
        for opt in options:
            if isinstance(opt, dict):
                opt_line = f"{opt.get('key', '')}. {opt.get('value', '')}"
                content = content.replace(opt_line, '').strip()

        blocks.append({
            'question_number': q_num,
            'content': content.strip(),
            'options': options,
            'answer': answer,
            'analysis': analysis,
            'question_type': qtype,
        })
        q_num += 1

    return blocks


@router.post("/ocr", summary="图片OCR识别（增强版：文字+公式+表格）")
async def ocr_recognize(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
):
    """
    提交图片 Base64，返回增强版 OCR 识别结果（文字+公式+表格）。

    参数：
    - image_base64: 图片的 Base64 编码（可含 data:image/xxx;base64, 前缀）
    - enhanced: 是否使用增强识别（默认 true，含公式/表格检测）

    返回：
    - ocr_text: 识别的纯文本
    - formulas: 公式列表 [{latex, position, confidence}]
    - tables: 表格列表 [{html, position, rows, cols}]
    - status: 'success' | 'error'
    """
    image_base64 = payload.get('image_base64', '')
    use_enhanced = payload.get('enhanced', True)

    if not image_base64:
        raise HTTPException(status_code=400, detail="图片数据为空")

    # 去除 data URL 前缀
    if ',' in image_base64 and image_base64.startswith('data:'):
        image_base64 = image_base64.split(',', 1)[1]

    image_bytes = base64.b64decode(image_base64)

    try:
        from ....services.ocr import recognize_image_enhanced, recognize_image

        if use_enhanced:
            # 增强版：文字+公式+表格
            result = recognize_image_enhanced(image_bytes)
            response = {
                'status': 'success',
                'ocr_text': result.text,
                'formulas': result.formulas,
                'tables': result.tables,
                'char_count': result.char_count,
                'confidence': result.confidence,
                'message': result.message or f'识别完成，共 {result.char_count} 字符' +
                    (f'，{len(result.formulas)} 个公式' if result.formulas else '') +
                    (f'，{len(result.tables)} 个表格' if result.tables else ''),
            }
        else:
            # 标准版：仅文字
            text = recognize_image(image_bytes)
            response = {
                'status': 'success',
                'ocr_text': text,
                'formulas': [],
                'tables': [],
                'char_count': len(text),
                'confidence': 0.0,
                'message': f'识别成功，共 {len(text)} 字符' if text else '未能识别到文字内容',
            }

        if not response['ocr_text'] and not response['formulas'] and not response['tables']:
            response['message'] = '未能识别到文字内容，请确认图片清晰度或手动输入'

        # W2-1：追加「科目建议 + 置信度」（不改既有字段，向后兼容）
        _ocr_sug_text = response.get('ocr_text') or ''
        subject_suggestion = _build_subject_suggestion(_ocr_sug_text)
        _ocr_sub_id = SUBJECT_NAME_MAP.get(subject_suggestion.get('name') or '')
        subcategory_suggestion = _build_subcategory_suggestion(
            _ocr_sub_id, _ocr_sug_text) if _ocr_sub_id else {
                'name': '', 'confidence': 0.0}
        response['subject_suggestion'] = subject_suggestion
        response['subcategory_suggestion'] = subcategory_suggestion
        return response

    except RuntimeError as e:
        logger.warning(f"OCR 服务不可用: {e}")
        return {
            'status': 'error',
            'ocr_text': '',
            'formulas': [],
            'tables': [],
            'subject_suggestion': {'name': '', 'confidence': 0.0, 'matched_keywords': []},
            'subcategory_suggestion': {'name': '', 'confidence': 0.0},
            'message': 'OCR 服务暂不可用，请安装 PaddleOCR 依赖: pip install paddleocr paddlepaddle'
        }
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {str(e)}")


@router.get("/ocr/status", summary="OCR 服务状态")
async def ocr_status():
    """检查 PaddleOCR 是否可用"""
    try:
        from ....services.ocr import get_ocr_status
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
                from ....services.ocr import recognize_image_base64
                ocr_text = recognize_image_base64(image_base64)
            except (ImportError, RuntimeError) as e:
                logger.warning(f"OCR服务不可用: {e}")
                ocr_text = '[OCR服务未安装，请使用前端OCR预识别]'

        if not ocr_text or not ocr_text.strip():
            return {
                'import_status': 'SKIPPED',
                'subject_suggestion': {'name': '', 'confidence': 0.0, 'matched_keywords': []},
                'subcategory_suggestion': {'name': '', 'confidence': 0.0},
                'message': 'OCR未能识别到文字内容',
            }

        # 自动检测科目（W2-1：手选优先 + 接上置信度，不再丢弃）
        subject_name = payload.get('subject_category', '')
        subject_suggestion = _build_subject_suggestion(ocr_text, subject_name)
        if not subject_name:
            subject_name = subject_suggestion.get('name') or ''
        # 空名兜底：见上文 :2420 附近说明（W1-1，W2-1 前保留历史默认值）
        if not subject_name:
            subject_name = '行测'
        subject = _get_or_create_subject(db, subject_name)
        subcategory_suggestion = _build_subcategory_suggestion(subject.subject_id, ocr_text)

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

        # 自动检测题型（传入从文本提取的选项与答案，避免选择/多选被误判为论述题）
        ocr_options = _extract_options(ocr_text.split('\n'))
        # ★ 返回的是 (type_name, confidence) 元组，必须解包
        detected_type, _conf2 = _detect_question_type(
            ocr_text, ocr_options, detected_answer or '')
        qtype = _get_or_create_type(db, detected_type, subject.subject_id)

        content = ocr_text[:100000]
        answer = detected_answer or '[待人工补充]'
        analysis = extracted.get('analysis') if extracted else '[OCR导入，待补充答案解析]'

        # 清洗题目内容：去除推广/无关字段
        content = ContentCleaner.clean_question_content(content)
        analysis = ContentCleaner.clean_question_content(analysis)

        # 去重检测
        dup_info = _get_duplicate_info(db, content, answer, subject.subject_id)
        if dup_info['is_duplicate'] and payload.get('auto_save', True):
            return {
                'import_status': 'DUPLICATE',
                'similarity': dup_info['similarity'],
                'existing_id': dup_info['existing_id'],
                'existing_content': dup_info.get('existing_content'),
                'subject_suggestion': subject_suggestion,
                'subcategory_suggestion': subcategory_suggestion,
                'message': f'该题目已存在（相似度 {dup_info["similarity"]*100:.0f}%）',
            }

        # 子科目自动检测
        subcategory = _detect_subcategory(subject.subject_id, content)
        clean_content = clean_question_text(content)
        clean_analysis = clean_question_text(analysis)

        question = QuestionBank(
            subject_id=subject.subject_id,
            type_id=qtype.type_id,
            question_content=clean_content,
            answer=answer,
            answer_analysis=clean_analysis,
            difficulty=3,
            score=1.0,
            year=auto_tags.get('exam_year') or payload.get('exam_year'),
            source=payload.get('source', '图片导入'),
            tags=payload.get('tags', 'OCR导入'),
            creator_id=current_user.user_id,
            audit_status=1,  # 教师导入自动审核通过
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
            question_type_detail=normalize_type_name(detected_type),
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
        _link_knowledge_points(db, [question])
        db.commit()

        return {
            'import_status': 'SUCCESS',
            'question_id': question.question_id,
            'auto_detected_subject': subject_name,
            'auto_detected_subcategory': subcategory,
            'auto_detected_type': detected_type,
            'auto_detected_answer': detected_answer,
            'subject_suggestion': subject_suggestion,
            'subcategory_suggestion': subcategory_suggestion,
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
    new_questions = []

    # 自动检测科目（W2-1：手选优先 + 接上置信度，不再丢弃）
    all_text = ' '.join(
        q.get('content', '') or q.get('question_content', '')
        for q in structured_questions[:5]
    )
    subject_name = payload.get('subject_category', '')
    subject_suggestion = _build_subject_suggestion(all_text, subject_name)
    if not subject_name:
        subject_name = subject_suggestion.get('name') or ''
    # 空名兜底：见上文 :2420 附近说明（W1-1，W2-1 前保留历史默认值）
    if not subject_name:
        subject_name = '行测'
    subject = _get_or_create_subject(db, subject_name)
    subcategory_suggestion = _build_subcategory_suggestion(subject.subject_id, all_text)

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
            # ★ 返回的是 (type_name, confidence) 元组，必须解包
            detected_type, _conf3 = _detect_question_type(
                content, q_data.get('options', []), answer or '')
            qtype = _get_or_create_type(db, detected_type, subject.subject_id)
            # 客观选择题：答案归一化（A、B → AB；对/错 → A/B），论述/写作保留原文
            if detected_type in ('单选题', '多选题'):
                _norm = canonical_answer(answer)
                stored_answer = _norm if _norm else answer
            else:
                stored_answer = answer
            # 优先使用前端传来的子分类，否则自动检测
            subcategory = q_data.get('subcategory', '') or _detect_subcategory(subject.subject_id, content)
            clean_content = clean_question_text(content)
            clean_analysis = clean_question_text(analysis)

            question = QuestionBank(
                subject_id=subject.subject_id,
                type_id=qtype.type_id,
                question_content=clean_content[:50000],
                options=q_data.get('options') if q_data.get('options') else None,
                answer=stored_answer,
                answer_analysis=clean_analysis,
                    difficulty=coerce_difficulty(q_data.get('difficulty')),
                    score=coerce_score(q_data.get('score')),

                year=payload.get('exam_year'),
                source=payload.get('source', '图片OCR导入'),
                tags=payload.get('tags', 'OCR导入'),
                creator_id=current_user.user_id,
                audit_status=1,  # 教师导入自动审核通过
            )
            if subject.subject_id == 1:
                question.xingce_subcategory = subcategory
            elif subject.subject_id == 2:
                question.shenlun_subcategory = subcategory
            elif subject.subject_id == 3:
                question.gongzhuan_subcategory = subcategory
            db.add(question)
            db.flush()
            new_questions.append(question)

            detail = QuestionDetailCategory(
                question_id=question.question_id,
                question_type_detail=normalize_type_name(detected_type),
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
                # ★ 第三处入库路径，扫描范围同样补上答案与解析（与前两处一致）
                _ocr_scope = ' '.join([
                    content,
                    str(q_data.get('options') or ''),
                    q_data.get('answer') or '',
                    q_data.get('answer_analysis') or q_data.get('analysis') or '',
                ])
                images = _extract_and_save_images(
                    _ocr_scope,
                    question.question_id,
                    question_obj=question
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
    _link_knowledge_points(db, new_questions)
    db.commit()

    return {
        'import_status': 'SUCCESS' if imported > 0 else 'PARTIAL',
        'auto_detected_subject': subject_name,
        'subject_suggestion': subject_suggestion,
        'subcategory_suggestion': subcategory_suggestion,
        'total': len(structured_questions),
        'imported': imported,
        'duplicates': duplicates,
        'failed': failed,
        'results': results,
        'message': f'图片导入完成：成功 {imported}，重复 {duplicates}，失败 {failed}',
    }


# 注意：此处不再定义同名 _detect_question_type 遮蔽函数。
# 统一使用顶部从 text_parser 导入的 3 参版本 _detect_question_type(content, options, answer)，
# 避免丢弃 answer 参数导致多选被误判为单选，以及 3 参调用触发 TypeError 崩溃。


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


# ══════════════════════════════════════════════════════════════════════
# 任务 21（模块 C-5）：分离与合并路径统一的申论三方校验入口
#
# 背景：`_essay_cross_validate(q_blocks, a_blocks)` 原先是**分离导入专用**，
# 合并导入走 `extract_question_blocks` 后直接入库 —— 而解析器在形态①
# （文末统一答案区）配对时是**按序硬配**（`_parse_essay_document` 的
# `trailing_segments[k] → 第 k 题`）。一旦段数与题数相等（合订本常见），
# 错配会被整卷放行，答案张冠李戴且不可逆。
#
# 本模块把同一套「题号 + 分值 + 题干指纹」校验提升为两条路径共用：
#   分离路径：两份文档 → extract_question_blocks 两次 → _essay_cross_validate
#   合并路径：单份文档 → 按答案区边界切成两半 → 同上
# 判据**只有一份实现**，不做第二份。
#
# 插入位置刻意选在本文件末尾：放在 `separate_match_endpoint` 之前会让
# dispatch 红线的行号定位失效，绝不可行。
# ══════════════════════════════════════════════════════════════════════

# 为什么用延迟导入：本文件顶部 import 块任何增行都会让下方所有函数整体下移，
# 而 gate_l0 的 dispatch 块断言按**固定行号区间**取内容。为守住红线，
# 本模块一律走函数内延迟导入（沿用本文件 :2281/:2664/:3123/:4315 的既有惯例）。


def _essay_split_combined_text(text: str):
    """把**合并**申论文档切成「题目侧 / 答案侧」两段文本。

    判定口径与 `_parse_essay_document` 的形态①完全一致（复用其私有 helper，
    绝不复刻一份正则）：先判体例 → 切题号 → 取最后一个题号行 → 找其后
    第一个答案锚点，再**回退**到该答案块自带的题干行作为分界（合订本的
    答案区第 1 个题块以「带题号的题干行」开头，该行在参考答案锚点之前；
    不回退就会把复述题干整段丢掉，题干指纹无处可比）。

    返回 `(question_text, answer_text)`；**无法判定为申论文档、或不存在
    文末答案区**（形态②③ 就地配对）时返回 `(None, None)`，交由调用方按
    既有逻辑处理 —— 绝不把普通文档硬塞进申论链路。
    """
    # 延迟导入：守住本文件顶部 import 块行号红线（见上文说明）
    from ....services.text_parser import (
        _essay_norm_kangxi,
        _essay_strip_page_marks,
        _detect_essay_numbering,
        _essay_split_questions,
        _essay_is_ans_anchor,
        _essay_looks_like_question_number,
    )
    lines = _essay_strip_page_marks([_essay_norm_kangxi(l) for l in (text or '').split('\n')])
    style = _detect_essay_numbering(lines)
    if style is None:
        return None, None
    numbers = _essay_split_questions(lines, style)
    if not numbers:
        return None, None

    last_q_line = numbers[-1][1]

    # 形态②③（答案紧随每题、就地配对）：在最后一个题号之前就出现答案锚点。
    # 这种情况没有「文末统一答案区」可切，直接退出，走既有解析逻辑。
    def _first_anchor(from_line: int):
        for i in range(from_line, len(lines)):
            if _essay_is_ans_anchor(lines[i].strip()):
                return i
        return None

    tail_anchor = _first_anchor(last_q_line)
    if tail_anchor is None:
        return None, None
    if _first_anchor(0) is not None and _first_anchor(0) < last_q_line:
        return None, None

    # 答案区的第 1 个答案块以「自带题干的题号行」开头，该行在参考答案锚点**之前**。
    # 从这里往回走到最近的同体例题号行作为分界，否则答案侧会从参考答案锚点起头，
    # 复述题干整段丢失 → 题干指纹无处可比（实测安徽合订本即此形态）。
    # 下界严格取 last_q_line+1：绝不允许把题目区最后一道题划进答案侧。
    boundary = tail_anchor
    for i in range(tail_anchor, last_q_line, -1):
        if _essay_looks_like_question_number(lines[i], style):
            boundary = i
            break
    if boundary <= last_q_line:
        return None, None
    return '\n'.join(lines[:boundary]), '\n'.join(lines[boundary:])


def _essay_cross_validate_import(text: str, prefer_subject: str = '') -> Optional[Dict[str, Any]]:
    """任务 21 的统一校验入口：**合并导入**的申论文档共享分离路径的三方校验。

    与分离路径共用同一个 `_essay_cross_validate`（题号 + 分值 + 题干指纹），
    判据只有一份实现：

        combined: `_essay_split_combined_text` 切两半
               → `extract_question_blocks` × 2
               → `_essay_cross_validate(q_blocks, a_blocks)`

    返回结构与 `_essay_cross_validate` 相同：
        {'questions': [...], 'report': {...}}
    每题带 `blocked` / `block_reasons`（含 `stem_fingerprint_mismatch`），
    调用方必须据此阻断入库，**禁止按序硬配**。

    非申论文档 / 无文末答案区 → 返回 None（调用方走既有解析逻辑）。
    """
    # 延迟导入：守住本文件顶部 import 块行号红线（见上文说明）
    from ....services.text_parser import extract_question_blocks
    if not (text or '').strip():
        return None
    q_text, a_text = _essay_split_combined_text(text)
    if q_text is None or a_text is None:
        return None
    q_blocks = extract_question_blocks(q_text)
    a_blocks = extract_question_blocks(a_text)
    if not q_blocks:
        return None
    return _essay_cross_validate(q_blocks, a_blocks)


# ══════════════════════════════════════════════════════════════════════
# W1-5（方案 v3 §6.1）：taxonomy 字典的单一事实来源读出口
#
# 背景：前端科目下拉原本硬编码 4 选项（`question_import.vue:84-89`），
# 与数据库 `question_subject` / `sub_categories` 形成**双事实来源分裂**——
# 后台新增科目前端无感，教师只能选到 4 个中的 1 个。
#
# 本端点是 taxonomy 的**唯一读出口**：前端科目下拉、预览建议、编辑页
# 统一消费它。只读三张既有表（question_subject / sub_categories /
# knowledge_point），**不新增表**；本端点只读不写，建分类仍走各管理端点。
#
# 追加位置刻意选在本文件末尾：放在 `separate_match_endpoint` 之前会让
# dispatch 红线的定位失效，绝不可行。`SubCategory` 走函数内延迟导入，
# 沿用本文件 :2281/:2664/:3123 的既定惯例 —— 顶部 import 块禁止增行。
# ══════════════════════════════════════════════════════════════════════


@router.get("/taxonomy", summary="科目/子科目/考点字典（下拉数据源）")
async def get_taxonomy(
    subject_id: Optional[int] = Query(None, description="可选：只返回该科目的子科目与考点（懒加载）"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """科目 → 子科目 → 考点 三级字典，供前端下拉 / 预览建议 / 编辑页统一消费。

    返回：
        subjects:         全部启用科目（status=1），按 sort_order 排序
        subcategories:    启用子科目（status=1），可按 subject_id 过滤
        knowledge_points: 考点，可按 subject_id 过滤（懒加载场景）

    不传 subject_id 时三个数组全量返回；传了则 subjects 仍是全量
    （下拉要先渲染科目），后两个数组按科目收窄。
    """
    # 延迟导入：守住顶部 import 块行号红线（见上文说明）
    from ....models.models import SubCategory

    subjects = db.query(QuestionSubject)\
        .filter(QuestionSubject.status == 1)\
        .order_by(QuestionSubject.sort_order, QuestionSubject.subject_id)\
        .all()

    sub_query = db.query(SubCategory).filter(SubCategory.status == 1)
    kp_query = db.query(KnowledgePoint)
    if subject_id is not None:
        sub_query = sub_query.filter(SubCategory.subject_id == subject_id)
        kp_query = kp_query.filter(KnowledgePoint.subject_id == subject_id)

    subcategories = sub_query\
        .order_by(SubCategory.subject_id, SubCategory.sort_order, SubCategory.id)\
        .all()
    knowledge_points = kp_query\
        .order_by(KnowledgePoint.subject_id, KnowledgePoint.sub_category_id, KnowledgePoint.point_name)\
        .all()

    return {
        'subjects': [
            {'id': s.subject_id, 'name': s.subject_name, 'code': s.subject_code}
            for s in subjects
        ],
        'subcategories': [
            {'id': s.id, 'subject_id': s.subject_id, 'name': s.name}
            for s in subcategories
        ],
        'knowledge_points': [
            {
                'id': p.point_id,
                'name': p.point_name,
                'subject_id': p.subject_id,
                'sub_category_id': p.sub_category_id,
            }
            for p in knowledge_points
        ],
    }
