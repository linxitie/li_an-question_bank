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

from ...core.database import get_db
from ...core.config import settings
from ...core.security import get_current_user
from ...models.models import (
    QuestionBank, QuestionSubject, QuestionType, KnowledgePoint,
    QuestionDetailCategory, QuestionImage, QuestionImportRecord, SysUser,
    ExamPaper, PaperQuestionRelation, ExamPaperTag, QuestionKnowledge,
    QuestionGroup,
)
from ...schemas.schemas import SuccessResponse, ParseRequest, ParseResult, ParsedQuestion, ImageRef
from ...services.question_classifier import QuestionClassifier, detect_subcategory_enhanced
from ...services import text_cache  # 文档提取文本缓存（P0 提速，260s→0.02s）
from ...services.mineru_service import (  # 扫描件三级回退链第一级（规格§5.2）
    extract_text_sync as mineru_extract_text_sync,
    is_enabled as mineru_is_enabled,
    health_check as mineru_health_cached,
)
from ...services.text_parser import (
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

# 科目名称 → subject_id 缓存
SUBJECT_NAME_MAP = {
    '行测': 1, '申论': 2, '公专': 3, '公安专业知识': 3,
    '其他': 4, '综合': 4,
}

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


def _link_knowledge_points(db: Session, questions) -> int:
    """对导入的题目运行分类引擎并建立考点关联（幂等、异常不阻断导入）。

    仅 db.add 关联，不 commit，由调用方在合适时机提交。
    返回成功建立考点关联的题目数。
    """
    if not questions:
        return 0
    linked = 0
    classifier = QuestionClassifier()
    for q in questions:
        try:
            result = classifier.classify_with_db(
                q.question_content or "", q.subject_id, db
            )
            if result.knowledge_point_id:
                existing = db.query(QuestionKnowledge).filter(
                    QuestionKnowledge.question_id == q.question_id,
                    QuestionKnowledge.knowledge_point_id == result.knowledge_point_id
                ).first()
                if not existing:
                    db.add(QuestionKnowledge(
                        question_id=q.question_id,
                        knowledge_point_id=result.knowledge_point_id
                    ))
                    linked += 1
        except Exception as e:
            logger.warning(f"考点关联失败 question_id={getattr(q, 'question_id', None)}: {e}")
    return linked


# _normalize_type_name 已删除，统一使用 text_parser.normalize_type_name


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
    try:
        db.add(subject)
        db.flush()
    except Exception:
        db.rollback()
        subject = db.query(QuestionSubject).filter(
            QuestionSubject.subject_name == name
        ).first()
    return subject


def _get_or_create_type(db: Session, type_name: str, subject_id: int) -> QuestionType:
    """
    获取或创建题型（处理并发重复插入与跨科目 type_code 冲突）。

    根因修复：原 type_code=f"auto_{type_name}" 在跨科目（如行测与公专都有"单选题"）时
    违反 type_code 的 UNIQUE 约束 → commit 失败 → rollback → 再查询 (type_name, subject_id)
    仍返回 None → qtype.type_id 抛 AttributeError。
    修复：type_code 改为带 subject_id 前缀，确保跨科目唯一；并加 fallback 防止返回 None。
    """
    # 规范化 type_name（防止脏数据）
    if not type_name:
        type_name = '选择题'

    # 1. 主查询：(type_name, subject_id)
    qtype = db.query(QuestionType).filter(
        and_(
            QuestionType.type_name == type_name,
            QuestionType.subject_id == subject_id
        )
    ).first()
    if qtype:
        return qtype

    # 2. 兼容旧数据：按 type_code 查询（旧格式 "auto_{type_name}"，可能跨科目存在）
    legacy_code = f"auto_{type_name}"
    qtype = db.query(QuestionType).filter(
        QuestionType.type_code == legacy_code
    ).first()
    if qtype:
        # 旧记录存在但 subject_id 不匹配 → 复用其 type_id 关联到当前科目
        # 为避免破坏其他科目已有引用，这里改为：在该 type_id 下创建一条科目映射
        # 实际上更安全的做法是新建一条带新 type_code 的记录
        pass  # 落到下面的创建逻辑

    # 3. 创建新记录：type_code 带 subject_id 前缀确保跨科目唯一
    new_type_code = f"auto_{subject_id}_{type_name}"
    qtype = QuestionType(
        type_name=type_name,
        type_code=new_type_code,
        subject_id=subject_id,
        is_objective=1 if type_name in ('选择题', '单选题', '多选题') else 0
    )
    try:
        db.add(qtype)
        db.commit()
        db.refresh(qtype)
        return qtype
    except Exception as e:
        db.rollback()
        logger.warning(f"_get_or_create_type 创建失败(type_name={type_name}, subject_id={subject_id}): {e}")
        # 4. 并发场景：重新查询
        qtype = db.query(QuestionType).filter(
            and_(
                QuestionType.type_name == type_name,
                QuestionType.subject_id == subject_id
            )
        ).first()
        if qtype:
            return qtype
        # 5. 终极兜底：按新 type_code 再查一次
        qtype = db.query(QuestionType).filter(
            QuestionType.type_code == new_type_code
        ).first()
        if qtype:
            return qtype
        # 6. 仍失败：抛出明确异常，避免返回 None 导致上层 qtype.type_id 报错
        raise HTTPException(
            status_code=500,
            detail=f"题型创建失败: type_name={type_name}, subject_id={subject_id}, code={new_type_code}"
        )


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
    raw_type = (row.get('题型') or row.get('题目类型') or row.get('type') or '').strip()

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
    diff_raw = row.get('难度') or row.get('difficulty')
    difficulty = coerce_difficulty(diff_raw)

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
        'subcategory': row.get('子科目') or row.get('细分') or row.get('小类') or row.get('subcategory') or '',
    }


def _rels_base_dir(rels_name: str) -> str:
    """`<dir>/_rels/<name>.rels` → `<dir>/`（关系目标相对于其宿主 part 所在目录）。"""
    d = os.path.dirname(rels_name)          # e.g. word/_rels
    if os.path.basename(d) == '_rels':
        d = os.path.dirname(d)             # e.g. word
    return d


def _sanitize_docx_rels(buf: bytes) -> Optional[bytes]:
    """移除指向不存在 part 的 relationship，返回可被 python-docx 正常打开的新 docx 字节。

    根治的必要性：python-docx 在**打开包**阶段就遍历全部物理 part 并逐个
    `zipf.read(membername)`，只要有任何一个 relationship 指向不存在的成员，
    整个 `Document()` 就抛 KeyError —— 连纯文本都取不出来。
    典型畸形文件（实测 37 份真实题库中命中 1 份）：
        2019年深圳市公安局第四批公开招聘警务辅助人员考试《行政职业能力测验》真题.docx
        word/_rels/document.xml.rels 含 <Relationship ... Target="../NULL"/>，
        解析后为包内成员 "NULL"，而 zip 中并无该条目 →
        KeyError: "There is no item named 'NULL' in the archive"

    仅删除**确实悬空**的内部关系，外部链接(External)与有效关系一律保留，
    因此图片等正常资源仍可被解析（不是降级为"只取文本"）。
    """
    import io as _io
    import re as _re
    import zipfile as _zip
    import xml.etree.ElementTree as _ET

    try:
        src = _zip.ZipFile(_io.BytesIO(buf))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"文件不是有效的 docx（无法作为 zip 打开）：{e}")

    with src:
        names = set(src.namelist())
        rels_files = [n for n in names if n.endswith('.rels')]
        if not rels_files:
            raise HTTPException(status_code=400, detail="docx 缺少关系文件（.rels），文件可能已损坏")

        patched: Dict[str, bytes] = {}
        removed_total = 0
        for rels_name in rels_files:
            base = _rels_base_dir(rels_name)
            try:
                xml_bytes = src.read(rels_name)
                root = _ET.fromstring(xml_bytes)
            except Exception:  # noqa: BLE001 — 单个 rels 坏掉不阻断其它
                continue
            removed = 0
            for rel_el in list(root):
                tgt = rel_el.get('Target')
                mode = (rel_el.get('TargetMode') or '')
                if not tgt or mode.lower() == 'external':
                    continue
                if tgt.startswith(('http://', 'https://', 'mailto:', 'file:', 'ftp://')):
                    continue
                if tgt.startswith('/'):
                    resolved = os.path.normpath(tgt.lstrip('/')).replace('\\', '/')
                else:
                    resolved = os.path.normpath(os.path.join(base, tgt)).replace('\\', '/').lstrip('/')
                if resolved not in names:
                    root.remove(rel_el)
                    removed += 1
            if removed:
                removed_total += removed
                patched[rels_name] = _ET.tostring(root, encoding='UTF-8', xml_declaration=True)

        if not removed_total:
            return None  # 没有悬空关系 → 不是这个问题，交给上层报错

        out = _io.BytesIO()
        with _zip.ZipFile(out, 'w', _zip.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data = patched.get(item.filename) or src.read(item.filename)
                dst.writestr(item, data)
        logger.warning(f"[docx] 清洗掉 {removed_total} 个悬空 relationship 后重试打开")
        return out.getvalue()


def _extract_text_from_docx_raw_xml(buf: bytes) -> str:
    """最后兜底：直接从 zip 里读 word/document.xml 提取纯文本。

    仅在 python-docx 完全无法打开时使用（畸形 docx）。放弃图片与排版，
    但保证「文本不丢」——题目导入的最小可用信息是题干/选项/答案。
    """
    import io as _io
    import re as _re
    import zipfile as _zip

    try:
        with _zip.ZipFile(_io.BytesIO(buf)) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'ignore')
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"无法解析该 Word 文件：文件结构已损坏（既不是有效 docx，也无法读取其 XML 内容）。请用 Word/WPS 打开后另存为 .docx 再上传。原始错误：{e}",
        )
    # 按段落切分，保留题号/选项的换行结构
    xml = _re.sub(r'</w:p>', '\n', xml)
    xml = _re.sub(r'<w:br[^>]*/>', '\n', xml)
    texts = _re.findall(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', xml, _re.S)
    joined = ''.join(texts) if len(texts) <= 1 else '\n'.join(texts)
    if not joined.strip():
        # 回退：粗暴剥标签
        joined = _re.sub(r'<[^>]+>', '', xml)
    return joined


def _open_docx_resilient(buf: bytes, Document):
    """弹性打开 docx：直接开 → 清洗悬空关系后开 → 失败返回 None（交由 XML 兜底）。"""
    import io as _io
    try:
        return Document(_io.BytesIO(buf))
    except HTTPException:
        raise
    except Exception as first_err:  # noqa: BLE001
        logger.warning(f"[docx] 直接打开失败({type(first_err).__name__}: {first_err})，尝试清洗关系后重试")
    try:
        fixed = _sanitize_docx_rels(buf)
        if fixed:
            return Document(_io.BytesIO(fixed))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[docx] 清洗后仍无法打开({type(e).__name__}: {e})，转 XML 兜底")
    return None


def _extract_text_from_docx(buf: bytes) -> str:
    """从docx提取文本+图片占位标记。

    图片定位：通过段落内部 _p 元素的 XPath 精准提取，
    IMAGE 占位符追加到对应段落文本末尾。
    后续 extract_question_blocks 自然按行分离 stem 和 options：
      - 图片在题干段落 → marker 在 stem 中 → 前端题干区展示
      - 图片在选项段落(A.xxx) → marker 在选项值中 → 前端选项区展示
      - 独立图片段落(无文本) → 附加到最近段落，归属当前题号

    容错（2026-09-25 实测修复）：真实题库中存在 python-docx 无法打开的畸形 docx
    （relationship 指向包内不存在的成员），此前直接 500 且整次导入失败。
    现改为三级降级：直接打开 → 清洗悬空 relationship 后打开 → 纯 XML 取文本。
    """
    import io, os, re, uuid
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(status_code=500, detail="服务器缺少 python-docx 库")

    _session_id = uuid.uuid4().hex[:8]  # 每次导入唯一前缀，避免跨文件覆盖
    doc = _open_docx_resilient(buf, Document)
    if doc is None:
        logger.warning("[docx] python-docx 无法打开，转用纯 XML 兜底提取")
        return _extract_text_from_docx_raw_xml(buf)
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
                    img_path = os.path.join(img_dir, f'{_session_id}_{current_qn}_{seq}.png')
                    with open(img_path, 'wb') as f:
                        f.write(image_rel_map[rId])
                    text += f' [IMAGE:{_session_id}_{current_qn}_{seq}]'
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
            img_path = os.path.join(img_dir, f'{_session_id}_{first_qn}_{seq}.png')
            with open(img_path, 'wb') as f:
                f.write(image_rel_map[rId])
            parts[0] += f' [IMAGE:{_session_id}_{first_qn}_{seq}]'
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
                            img_path = os.path.join(img_dir, f'{_session_id}_{current_qn}_{seq}.png')
                            with open(img_path, 'wb') as f:
                                f.write(image_rel_map[rId])
            if row_texts:
                parts.append(' | '.join(row_texts))

    return '\n'.join(parts)


def _norm_for_dedup(s: str) -> str:
    """归一化文本用于重复比对：去除所有空白与表格分隔符。

    pdfplumber 的 ``extract_text()`` 与 ``extract_tables()`` 对同一批内容的
    呈现不同：前者用换行分隔单元格，后者用 ``' | '`` 连接。直接字符串比较
    必然漏判，因此两侧统一去空白与分隔符后再比对，才能稳定识别「已存在」的内容。
    """
    return re.sub(r'[\s|\u3000]+', '', s or '')


# PDF 图片占位符提取所需常量（2026-09-29）
# 行首题号：用于判定图片归属的哪一道题
_PDF_QN_LINE = re.compile(r'^\s*(\d{1,3})\s*[．.、]')
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
# 图片最小边长：过滤碎片。实测目标 PDF 第 11 页含 4 张 14x11 的无效碎片
_PDF_MIN_IMG_DIM = 40


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
        mode, nch = spec
        data = im['stream'].get_data()
        if len(data) != sw * sh * nch:
            logger.debug(f"[pdf-images] 数据长度 {len(data)} != {sw}x{sh}x{nch}，跳过该图")
            return None
        from PIL import Image
        buf = io.BytesIO()
        Image.frombytes(mode, (sw, sh), data).save(buf, format='PNG')
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
                        qn = carry_in_qn or cur_qn
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
                text = '\n'.join(page_lines)   # 含图片占位符的最终页文本
                if text:
                    parts.append(text)
                # 提取表格
                # 2026-09-29 修复（致命缺陷）：当 pdfplumber 因版面把本页判定为表格时，
                # extract_tables() 会把已由 extract_text() 输出的同一批单元格文本
                # **再输出一遍**，导致全文精确翻倍。实测目标 PDF：14,436 → 28,873 字符、
                # 行首题号 70 → 140（每个题号各出现 2 次），进而使 extract_question_numbers
                # 的单调性过滤丢弃重复题号却把重复文本留在题块内 → 重复题 + 串题。
                # 修复：仅在文本层为空（真表格页/扫描页）时全量采纳表格行；
                # 否则只补充「本页文本中确实不存在」的单元格行。
                # 关键约束：不能直接禁用 extract_tables()，否则真正的表格题会丢内容。
                page_norm = _norm_for_dedup(text_raw) if text_raw else None
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            row_texts = [str(c) if c else '' for c in row]
                            row_text = ' | '.join(t for t in row_texts if t)
                            if not row_text:
                                continue
                            if page_norm and _norm_for_dedup(row_text) in page_norm:
                                # 本页文本已包含该单元格内容，跳过以消除重复
                                continue
                            parts.append(row_text)

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
        logger.warning("[mineru] 未返回有效文本，回退PaddleOCR逐页路径")

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
            logger.error(f"[ocr-worker] 子进程异常退出 code={proc.returncode}: "
                         f"{(proc.stderr or '')[-300:]}")
            return ''
        with open(out_json, encoding='utf-8') as f:
            result = json.load(f)
        if not result.get('ok'):
            logger.warning(f"[ocr-worker] 未得到文本: {result.get('error')}")
            return ''
        logger.info(f"[ocr-worker] 完成: 页OK={result.get('pages_ok')} "
                    f"页失败={result.get('pages_fail')} 字符={len(result.get('text',''))}")
        return result.get('text', '')

    except subprocess.TimeoutExpired:
        logger.error(f"[ocr-worker] OCR超时（>{settings.OCR_SUBPROCESS_TIMEOUT}s），"
                     "已终止。建议：该PDF为高清扫描件，请拆分后导入或联系管理员启用MinerU通道")
        return ''
    except Exception as e:
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


def _auto_detect_tags(filename: str, text: str) -> Dict[str, Any]:
    """从文件名和全文文本自动检测标签（增强版：扫描全文+检测完整试卷）"""
    tags = {}
    # 合并搜索范围：文件名 + 全文文本（不再限制前500字符）
    full_search = filename + '\n' + (text or '')
    text_head = text[:3000] if text else ''  # 头部用于快速检测

    # 检测年份
    year_match = re.search(r'(20\d{2})', full_search)
    if year_match:
        tags['exam_year'] = int(year_match.group(1))

    # 检测省份
    provinces = ['北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江',
                 '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东', '河南',
                 '湖北', '湖南', '广东', '广西', '海南', '重庆', '四川', '贵州',
                 '云南', '西藏', '陕西', '甘肃', '青海', '宁夏', '新疆']
    for p in provinces:
        if p in filename or p in text_head:
            tags['exam_province'] = p if p not in ('内蒙古', '黑龙江') else (p + '省' if len(p) == 2 else p)
            break

    # 检测考试类型（扩展到全文）
    exam_types = {
        '国考': '国考', '省考': '省考', '联考': '联考',
        '模拟': '模拟考试', '模拟考': '模拟考试', '招警': '招警考试',
        '统考': '统考', '事业单位': '事业单位考试', '真题': '真题',
        '考试': '考试',  # 兜底：标记为通用考试
    }
    for k, v in exam_types.items():
        if k in filename or k in text_head:
            tags['exam_type'] = v
            break

    # 检测科目（扩展到全文）
    subjects = {
        '行测': '行测', '申论': '申论', '公专': '公专',
        '公安专业': '公专', '公安基础': '公专', '公安知识': '公专',
        '基础知识': '公专', '行政职业能力': '行测', '职业能力': '行测',
    }
    for k, v in subjects.items():
        if k in filename or k in text_head:
            tags['subject_category'] = v
            break

    # 检测是否为完整试卷
    tags['is_complete_paper'] = _detect_complete_paper(text)

    # 尝试从文档标题提取试卷名称
    if not tags.get('paper_name'):
        tags['paper_name'] = _extract_paper_name(filename, text)

    # 检测考试来源标记
    source_markers = {'绝密': '绝密', '启用前': '启用前', '机密': '机密'}
    for k, v in source_markers.items():
        if k in text_head:
            tags['source_marker'] = v
            break

    return tags


def _detect_complete_paper(text: str) -> bool:
    """检测文档是否为完整试卷（连续题号+答案区+科目一致性）"""
    if not text or len(text) < 200:
        return False
    # 检测连续题号（至少5个连续题号）
    numbers = re.findall(r'^(?:\s*(?:\d+)[.、．)）\]】]\s*)', text, re.MULTILINE)
    if len(numbers) < 5:
        # 备选：检测 "第X题" 模式
        numbers = re.findall(r'第\s*\d+\s*题', text)
    if len(numbers) < 5:
        # 备选：简单的数字题号
        numbers = re.findall(r'^\s*(\d{1,3})\s*[.、]', text, re.MULTILINE)
        if len(numbers) < 5:
            return False
        # 检查数字是否连续递增
        try:
            nums = [int(n) for n in numbers[:min(20, len(numbers))]]
            consecutive = sum(1 for i in range(1, len(nums)) if nums[i] == nums[i-1] + 1)
            if consecutive < len(nums) * 0.6:
                return False
        except (ValueError, IndexError):
            return False
    # 检测是否有答案区域（参考答案/答案/正确答案等）
    has_answer_section = bool(re.search(
        r'(参考答案|答案[：:】\]])|正确答案|标准答案',
        text[-2000:] if len(text) > 2000 else text
    ))
    return has_answer_section or len(numbers) >= 10


def _extract_paper_name(filename: str, text: str) -> Optional[str]:
    """从文件名或文档开头提取试卷名称"""
    text_head = text[:800] if text else ''

    # 按优先级尝试多种模式提取标题
    patterns = [
        # 模式1: 带书名号的完整标题 —— 《2025年XX省公务员录用考试行政职业能力测验试卷》
        r'《([^》]{5,60})》',
        # 模式2: XXXX年XX省/市+考试类型+科目/试卷 —— 2025年国考行测真题、2024年公安联考公专试卷
        r'(20\d{2}[年年度][^\n]{2,40}?(?:考试|联考|省考|国考|录用|招录)[^\n]{0,30}?(?:行测|申论|公专|真题|试卷|测验))',
        # 模式3: XX省/市+XXXX年+考试 —— 河南省2025年公务员考试行测
        r'([\u4e00-\u9fa5]{2,6}(?:省|市|自治区)?20\d{2}[年年度][^\n]{2,40}?(?:行测|申论|公专|真题|试卷|测验))',
        # 模式4: 行政职业能力测验 / 申论 / 公安专业科目 —— 直接匹配科目全称做标题
        r'((?:行政职业能力测验|申论|公安专业科目|综合应用能力)[^\n]{0,10}(?:试卷|真题|模拟|练习)?)',
        # 模式5: 第一行非空文本（当作文档标题）—— 去除页眉/水印等短文本
        r'^\s*(.{8,60})\s*$',
    ]

    for i, pattern in enumerate(patterns):
        if i == 4:
            # 模式5只取第一行
            for line in text_head.split('\n'):
                line = line.strip()
                if line and len(line) >= 8 and not re.match(r'^[\d\s\.\-/\\]+$', line):
                    # 过滤掉纯数字行、页码行
                    name = re.sub(r'[\s]+', ' ', line).strip()
                    if len(name) >= 5:
                        return name
            continue
        m = re.search(pattern, text_head)
        if m:
            name = m.group(1).strip() if i == 0 else m.group(0).strip()
            # 清理多余空白和特殊字符
            name = re.sub(r'\s+', ' ', name)
            name = name.strip('— —··、，。')
            if len(name) >= 5:
                return name

    # 兜底：从文件名提取
    if filename:
        name = re.sub(r'\.[^.]+$', '', filename)
        name = re.sub(r'[（(].*?[）)]', '', name)  # 去除括号内容
        name = name.strip()
        if len(name) >= 3:
            return name
    return None


def _get_or_create_import_paper(db, user, auto_tags: Dict[str, Any], filename: str, question_count: int = 0):
    """根据检测到的标签自动创建或查找ExamPaper
    
    新增参数:
        question_count: 导入的题目数量
    
    阈值规则:
        - question_count < 5: 不创建试卷，只入库
        - question_count >= 5: 正常创建试卷
    """
    from ...models.models import ExamPaper, ExamPaperTag
    from .paper_generation import generate_paper_code

    # 阈值检查：少于5题不创建试卷
    MIN_QUESTION_COUNT = 5
    if question_count < MIN_QUESTION_COUNT:
        logger.info(f"[import-paper] 题目数量({question_count})少于阈值({MIN_QUESTION_COUNT})，跳过试卷创建")
        return None

    paper_name = auto_tags.get('paper_name') or filename.rsplit('.', 1)[0] if '.' in filename else filename
    exam_type_tag = auto_tags.get('exam_type', '模拟考试')
    subject_name = auto_tags.get('subject_category', '行测')
    subject_id = SUBJECT_NAME_MAP.get(subject_name, 1)

    # 查重：同名+同创建者 → 复用
    existing = db.query(ExamPaper).filter(
        ExamPaper.paper_name == paper_name,
        ExamPaper.creator_id == user.user_id
    ).first()
    if existing:
        # P2.2 ENDED 复活：同名试卷被删除（ENDED）后重导入同名文档 →
        # 复活为 DRAFT 并重新关联，避免"导入了但试卷管理看不到"
        if existing.paper_type == "ENDED":
            existing.paper_type = "DRAFT"
            logger.info(f"[import-paper] 复活 ENDED 试卷: {existing.paper_id} "
                        f"'{paper_name}' → DRAFT")
        else:
            logger.info(f"[import-paper] 复用已有试卷: {existing.paper_id} '{paper_name}'")
        return existing

    # 新建试卷(DRAFT状态)
    paper = ExamPaper(
        paper_name=paper_name,
        paper_code=generate_paper_code(),
        subject_id=subject_id,
        composition_method="IMPORT",
        creator_id=user.user_id,
        duration=120,
        total_score=100,
        difficulty=3,
        exam_type="SIMULATION",
        paper_type="DRAFT",
        question_count=0,
    )
    db.add(paper)
    db.flush()

    # 创建标签记录
    try:
        tag = ExamPaperTag(
            paper_id=paper.paper_id,
            exam_year=auto_tags.get('exam_year'),
            exam_province=auto_tags.get('exam_province'),
            exam_type=exam_type_tag,
            subject_category=subject_name,
            is_complete=1 if auto_tags.get('is_complete_paper') else 0,
        )
        db.add(tag)
    except Exception as e:
        logger.warning(f"[import-paper] 创建标签失败（表可能不存在）: {e}")

    db.commit()
    db.refresh(paper)
    logger.info(f"[import-paper] 自动创建试卷: {paper.paper_id} '{paper_name}' "
                f"年份={auto_tags.get('exam_year')} 类型={exam_type_tag} 科目={subject_name}")
    return paper


def _extract_and_save_images(content_text, question_id, upload_dir='static/questions', question_obj=None):
    """
    从题目内容中提取base64或URL图片，保存到磁盘，返回路径列表。
    支持格式: <img src="..."> / [IMAGE:x_y] 占位符 / base64 data URI

    安全措施：路径遍历防护、SSRF检测、图片大小限制(MAX_IMAGE_SIZE)。

    路径一致性：upload_dir='static/questions' 与 main.py 中
    `app.mount('/static/questions', StaticFiles(directory=.../static/questions))` 对应，
    返回的 URL `/static/questions/{qid}/{filename}` 可被前端直接访问。

    即时更新（第3层防线）：传入 question_obj 时，会立即把 question_content
    和 options 中的 [IMAGE:xxx] 占位符替换为最终 <img> 标签，写入数据库，
    避免占位符残留导致前端图片不显示。
    """
    images = []

    # 无关图片检测（问题2-R2/P2-1）：委托共享模块 image_filters 的 classify_image
    # 三级判定（block/suspect/keep），与存量清理脚本使用同一判定标准。
    #   block   → 实锤无关图（QR 解码成功 / 黑名单 md5），导入侧直接跳过
    #   suspect → 疑似无关图（推广横幅/疑似二维码/尺寸启发式），放行但记日志待人工复核
    #   keep    → 正常内容图
    # 关键修复：旧逻辑 `hit != 'qr_likely'` 会把 promo_likely/tiny/extreme_ratio/blank
    # 也拦截，误杀正常图表/警务照片等核心内容；现改为仅拦截 block 级。
    def _is_irrelevant_image(img_data: bytes) -> bool:
        """检测图片是否为实锤无关内容（二维码解码成功 / 推广图黑名单）"""
        from ...services.image_filters import classify_image as _check
        decision, reason = _check(img_data)
        if decision == 'block':
            logger.debug(f"[images] 拦截无关图片({reason})")
            return True
        if decision == 'suspect':
            logger.info(f"[images] 疑似无关图片放行待人工复核({reason})")
        return False

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

    # P2-2: 压缩 + 落盘（存储量最小）。压缩后按内容 md5 命名（相同图同名=天然去重）。
    # 返回 (filepath, filename) 或 (None, None)（压缩失败则回退原始字节原样落盘）。
    def _compress_and_store(img_data: bytes, prefix: str, idx: int, fallback_ext: str):
        from ...services.image_service import compress_image
        ext = _safe_ext(fallback_ext)
        if settings.IMAGE_COMPRESSION_ENABLED:
            try:
                img_data, ext = compress_image(
                    img_data,
                    max_side=settings.IMAGE_MAX_SIDE,
                    quality=settings.IMAGE_QUALITY,
                )
            except Exception:
                pass  # 压缩异常则原样落盘，不阻塞导入
        md5 = hashlib.md5(img_data).hexdigest()[:8]
        filename = f'{prefix}{idx}_{md5}.{ext}'
        filepath = os.path.join(img_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(img_data)
        return filepath, filename

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
                # ★ 新增：过滤无关图片（logo/页眉页脚）
                if _is_irrelevant_image(img_data):
                    continue
                # P2-2: 压缩 + 落盘（存储量最小，压缩后 md5 命名）
                filepath, _filename = _compress_and_store(
                    img_data, 'img_', idx, header.split(';')[0].split('/')[-1])
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
                        # ★ 新增：过滤无关图片（logo/页眉页脚）
                        if _is_irrelevant_image(img_data):
                            continue
                        # P2-2: 压缩 + 落盘（存储量最小，压缩后 md5 命名）
                        filepath, _filename = _compress_and_store(
                            img_data, 'img_', idx, src.rsplit('.', 1)[-1] if '.' in src else 'jpg')
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

    # 2. Extract [IMAGE:x_y] or [IMAGE:uuid_x_y] markers (generated by _extract_text_from_docx)
    marker_pattern = re.compile(r'\[IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]')
    markers = marker_pattern.findall(content_text or '')
    for idx, marker_key in enumerate(markers):
        try:
            # 尝试多个可能的源文件路径
            possible_names = [f'{marker_key}.png']
            # 如果 marker_key 是 uuid_x_y 格式，也尝试 x_y 格式
            parts = marker_key.split('_')
            if len(parts) == 3:
                simple_key = f'{parts[1]}_{parts[2]}'
                possible_names.append(f'{simple_key}.png')

            src_file = None
            for candidate_name in possible_names:
                candidate_path = os.path.join(static_img_dir, candidate_name)
                if os.path.exists(candidate_path):
                    src_file = candidate_path
                    break

            if src_file:
                img_data = open(src_file, 'rb').read()
                if not _check_size(img_data, f'docx图片{marker_key}'):
                    continue
                # ★ 新增：过滤无关图片（logo/页眉页脚）
                if _is_irrelevant_image(img_data):
                    continue
                # P2-2: 压缩 + 落盘（存储量最小，压缩后 md5 命名）
                dst_file, dst_name = _compress_and_store(img_data, 'img_docx_', idx, 'png')
                rel_path = f'/static/questions/{question_id}/{dst_name}'
                images.append(rel_path)
                logger.debug(f"[images] 保存docx图片: {rel_path}")

                # 关键：立即更新 question_content 中的占位符为最终 <img> 标签
                if question_obj is not None:
                    question_obj.question_content = (question_obj.question_content or '').replace(
                        f'[IMAGE:{marker_key}]',
                        f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                    )
                    # 同时更新 options 中的占位符
                    if hasattr(question_obj, 'options') and question_obj.options:
                        opts = question_obj.options
                        if isinstance(opts, str):
                            try:
                                import json as _json
                                opts_list = _json.loads(opts)
                                for o in opts_list:
                                    if isinstance(o, dict) and 'value' in o:
                                        o['value'] = o['value'].replace(
                                            f'[IMAGE:{marker_key}]',
                                            f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                                        )
                                question_obj.options = _json.dumps(opts_list, ensure_ascii=False)
                            except Exception:
                                pass
                        elif isinstance(opts, list):
                            for o in opts:
                                if isinstance(o, dict) and 'value' in o:
                                    o['value'] = (o['value'] or '').replace(
                                        f'[IMAGE:{marker_key}]',
                                        f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                                    )

                # ★ 同时回写答案解析：申论答案区大量使用思维导图/答案结构图
                #   （全语料实测 118 份文档有图，绝大多数在答案区）。
                #   旧实现只回写 question_content 与 options，导致答案里的
                #   [IMAGE:xxx] 占位符原样留在库中，前端显示不出图
                #   （用户实测截图里残留 [[IMAGE:f4419932_2_0]]）。
                if question_obj is not None and getattr(question_obj, 'answer_analysis', None):
                    question_obj.answer_analysis = (
                        question_obj.answer_analysis or ''
                    ).replace(
                        f'[IMAGE:{marker_key}]',
                        f'<img src="{rel_path}" class="q-img" loading="lazy" />'
                    )

                # 删除临时扁平文件，避免冗余
                try:
                    os.remove(src_file)
                except Exception:
                    pass
            else:
                logger.debug(f"[images] docx图片未找到: {marker_key}")
                # 文件不存在，移除占位符避免前端显示 broken image
                if question_obj is not None:
                    question_obj.question_content = (question_obj.question_content or '').replace(
                        f'[IMAGE:{marker_key}]', '')
                    # 答案解析里的同一占位符也必须清掉，否则前端照样显示原始文本
                    if getattr(question_obj, 'answer_analysis', None):
                        question_obj.answer_analysis = (
                            question_obj.answer_analysis or ''
                        ).replace(f'[IMAGE:{marker_key}]', '')
        except Exception as e:
            logger.warning(f"[images] docx图片{idx}({marker_key})保存失败: {e}")
            continue

    return images


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
    digest = hashlib.sha1(re.sub(r'\s+', '', text).encode('utf-8')).hexdigest()[:16]

    # 同批导入里重复查库代价高，先在本次请求内缓存
    cache_key = 'shenlun_group_' + digest
    cached = _SHENLUN_GROUP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # 跨批复用：库内已存在同指纹材料则直接挂上去
    existing = db.query(QuestionGroup).filter(
        QuestionGroup.shared_content.like('%' + text[:60] + '%')
    ).first() if text[:60] else None
    if existing is not None and text[:60] in (existing.shared_content or ''):
        _SHENLUN_GROUP_CACHE[cache_key] = existing.id
        return existing.id

    group = QuestionGroup(
        group_type='shenlun_material',
        shared_content=text,
        title=(subject_name + ' 给定材料')[:200],
        subject=subject_name or '申论',
        source=source_tag or '',
    )
    db.add(group)
    db.flush()
    _SHENLUN_GROUP_CACHE[cache_key] = group.id
    return group.id


# 同一批导入内多题共享同一份材料，避免重复 flush
_SHENLUN_GROUP_CACHE: Dict[str, int] = {}


def _upsert_question_core(db: Session, current_user: SysUser,
                          question_data: Dict[str, Any]) -> Dict[str, Any]:
    """单题入库核心逻辑（供 /single 与 /batch-parsed 复用）。

    与原 /single 函数体的差异：
      - 不创建 QuestionImportRecord（由调用方按批次汇总）
      - 不调用 db.commit()（调用方控制事务边界，批处理保证单事务）
    返回: {'import_status': 'SUCCESS'|'DUPLICATE', 'question_id': int, ...}
    """
    content = question_data.get('question_content', '').strip()
    answer = question_data.get('answer', '').strip()
    import_mode = question_data.get('import_mode', 'combined')

    # ★ 阻断闸门：解析器判定为 blocked 的题块一律拒绝入库。
    #   解析器会在下列情况置 blocked：
    #     · missing_score —— 题号行邻近找不到「（N分）」，题号可能误切
    #     · answer_block_count_mismatch —— 答案段数与题目数不等，按序硬配必然错配
    #   用户硬约束：宁可阻断报错交人工，也不允许静默丢题或按序盲配。
    #   必须在最前面拦：一旦入库，错配数据已经污染题库，事后无法区分。
    if question_data.get('blocked'):
        reasons = question_data.get('block_reasons') or ['unknown']
        raise HTTPException(
            status_code=400,
            detail='题目解析存在阻断问题，已拒绝导入（原因：%s）。'
                   '请人工核对原卷后重新导入。' % '、'.join(str(r) for r in reasons))

    if not content:
        raise HTTPException(status_code=400, detail="题目内容不能为空")
    if not answer and import_mode != 'separate':
        raise HTTPException(status_code=400, detail="题目内容和答案不能为空")
    if import_mode == 'separate' and not answer:
        # 分离模式：无答案题目标记为待补充
        answer = '待补充'

    # 统一清洗口径（问题1/T2 配套修复）：去重检测与入库存储必须使用同一
    # 清洗后的内容，否则"原始输入 vs 清洗后存储"指纹不一致会导致重复题
    # 漏检（生产库同题多副本的根因之一）。clean_question_text 移除 UTB ID、
    # "第X题："前缀并合并空白；清洗后为空则回退原文（防御极端输入）。
    content = clean_question_text(content) or content

    # 科目（在去重前获取，用于缩小候选范围）
    subject_name = question_data.get('subject_category', '行测')
    subject = _get_or_create_subject(db, subject_name)

    # 模糊去重检测
    existing = _detect_duplicate(db, content, answer, subject.subject_id)
    if existing:
        # ===== A2 回填式重导入 =====
        # 已存题缺字段而新导入数据有 → 补空不覆盖（绝不破坏已有非空值）。
        # 用户重导入题目/答案文档 = 给存量题补营养，不产生新重复。
        backfilled = []
        new_analysis = (question_data.get('answer_analysis') or '').strip()
        if new_analysis and len(new_analysis) > 10 and \
                not (existing.answer_analysis or '').strip():
            existing.answer_analysis = new_analysis
            backfilled.append('answer_analysis')
        new_ans = answer
        if new_ans and (existing.answer or '').strip() in ('', '待补充'):
            existing.answer = new_ans
            backfilled.append('answer')
        new_source = (question_data.get('source') or '').strip()
        if new_source and not (existing.source or '').strip():
            existing.source = new_source
            backfilled.append('source')
        new_year = question_data.get('exam_year') or question_data.get('year')
        if new_year and not existing.year:
            try:
                existing.year = int(new_year)
                backfilled.append('year')
            except (TypeError, ValueError):
                pass
        # 题干图回填：新导入带 <img>（如看图选择题的图标条）而已存题无
        if '<img' in content and '<img' not in (existing.question_content or ''):
            existing.question_content = content
            backfilled.append('content_images')
        if backfilled:
            logger.info(f"[backfill] 题目{existing.question_id} 回填字段: {backfilled}")
        dup_info = _get_duplicate_info(db, content, answer, subject.subject_id)
        return {
            'import_status': 'DUPLICATE',
            'question_id': existing.question_id,
            'backfilled_fields': backfilled,
            'message': (f'该题目已存在（相似度 {dup_info["similarity"]*100:.0f}%，'
                        f'现有ID: {existing.question_id}）'
                        + (f'，已回填缺失字段: {",".join(backfilled)}' if backfilled else '')),
            'similarity': dup_info['similarity'],
            'existing_content_preview': dup_info.get('existing_content'),
            'error_messages': [{'error': '重复题目', 'existing_id': existing.question_id, 'similarity': dup_info['similarity']}]
        }

    # 题型
    options = question_data.get('options')
    # ★ '选择题' 是历史遗留的"泛型桶"（前端 Excel 默认值），它会让单选/多选无法区分。
    #   这里交给 text_parser 的规则优先级分类器做一次判定（P3 单一事实来源）。
    type_name = question_data.get('question_type_detail') or ''
    if not type_name or type_name == '选择题':
        type_name, _conf = _detect_question_type(content, options or [], answer or '')
    qtype = _get_or_create_type(db, type_name, subject.subject_id)

    # P3b：题型判定置信度不足 → need_review=1，交教师在「题目管理 → 待复核」确认。
    # ★ 申论豁免：_detect_question_type 是选择题分类器，申论是长文本主观题，
    #   拿它打分必然 <0.60 → 每道申论题都被标 need_review=1，
    #   前端弹「低置信度题目(建议人工核对): 第1,2,3,4题」，逼用户逐题人工确认。
    #   申论题型由解析器的体例判定直接给出（简答题/论述题），无需再猜。
    _is_essay = (question_data.get('format') == 'essay')
    if _is_essay:
        type_name = type_name or '简答题'
    need_review = 0
    if _is_essay:
        need_review = 0
    else:
        try:
            _t, _c = _detect_question_type(content, options or [], answer or '')
            if _c < NEED_REVIEW_CONFIDENCE:
                need_review = 1
        except Exception:  # noqa: BLE001 — 判定失败不能阻塞入库
            need_review = 1

    # 创建题目
    # ★ 难度必须走 coerce_difficulty：前端导入预览页用中文下拉（简单/较易/中等/较难/困难），
    #   直接 int() 会抛 `invalid literal for int() with base 10: '中等'` 并让整批导入失败。
    difficulty = coerce_difficulty(question_data.get('difficulty'))
    try:
        score = float(question_data.get('score') or 1.0)
    except (TypeError, ValueError):
        score = 1.0
    if score <= 0:
        score = 1.0

    _xingce_sc, _shenlun_sc, _gongzhuan_sc = _subcategory_tuple(
        subject.subject_id, content, type_name,
        question_data.get('subcategory') or question_data.get('子科目') or ''
    )
    # content 已在函数入口统一清洗（与去重同口径），直接入库
    # 申论「给定材料」落 question_groups 并回填 group_id：同一份材料由所有小题共享，
    # helper 内部按内容指纹去重，保证一份卷只建一行材料。
    _shenlun_gid = 0
    # ★ 键名对齐：解析器实际产出的是 `material_text`（整份给定资料正文）与
    #   `material_titles`（['材料1','材料2',...]），**不是** `material`。
    #   实测误接 `material` 导致 group_id 恒为 0、材料整份丢失。
    #   这里同时兼容 material（Excel/手工导入路径）与 material_text（解析器路径）。
    _material = (question_data.get('material_text')
                 or question_data.get('material') or '')
    if _material:
        _shenlun_gid = (_get_or_create_shenlun_material_group(
            db,
            _material,
            subject_name,
            question_data.get('source', ''),
        ) or 0)
    # 解析器已给出的题号/层级/组序，直接沿用；缺失时给安全默认值
    _group_id = _shenlun_gid or int(question_data.get('group_id') or 0)
    _qno = question_data.get('question_number')
    _qno = str(_qno).strip() if _qno not in (None, '') else None
    _qlevel = int(question_data.get('question_level') or 0) or 1
    _sort = int(question_data.get('sort_order') or 0)
    question = QuestionBank(
        group_id=_group_id,
        parent_id=int(question_data.get('parent_id') or 0),
        question_level=_qlevel,
        sort_order=_sort,
        question_number=_qno,
        subject_id=subject.subject_id,
        type_id=qtype.type_id,
        question_content=content,
        options=options,
        answer=answer,
        answer_analysis=question_data.get('answer_analysis', ''),
        difficulty=difficulty,
        need_review=need_review,
        score=score,
        year=question_data.get('exam_year') or question_data.get('year'),
        source=question_data.get('source', ''),
        tags=question_data.get('tags', ''),
        creator_id=current_user.user_id,
        audit_status=1,  # 自动通过审核
        xingce_subcategory=_xingce_sc,
        shenlun_subcategory=_shenlun_sc,
        gongzhuan_subcategory=_gongzhuan_sc,
        # 申论题目要求落库。解析器可能给 list（带编号分点）或 str（纯文本），
        # 统一按换行拼接成 TEXT 存储，检索与展示都不丢分点结构。
        requirements=_normalize_requirements(question_data.get('requirements')),
    )
    db.add(question)
    db.flush()

    # 图片提取与保存（异常不回滚整题，仅跳过图片）
    try:
        # ★ 扫描范围必须含答案与解析。
        #   实测 254 份申论语料中 118 份含真实图片，且**绝大多数在答案区**
        #   （答案逻辑思维导图 / 答案结构图）。旧实现只扫题干+选项，
        #   导致答案区的 [IMAGE:xxx] 占位符既不会被发现、也不会被替换，
        #   前端只能看到裸占位符 —— 用户实测截图里残留 [[IMAGE:f4419932_2_0]]。
        _img_scope = ' '.join([
            question_data.get('question_content') or '',
            str(question_data.get('options') or ''),
            question_data.get('answer') or '',
            question_data.get('answer_analysis') or question_data.get('analysis') or '',
        ])
        images = _extract_and_save_images(
            _img_scope,
            question.question_id,
            question_obj=question
        )
        for img_order, img_path in enumerate(images):
            db.add(QuestionImage(
                question_id=question.question_id,
                image_path=img_path,
                # 沿用既有'题干图'类型语义不变（公专/行测既有链路依赖它），
                # 答案/解析图片同样归入该类型，避免改枚举破坏既有数据
                image_type='题干图',
                image_order=img_order
            ))
    except Exception as img_err:
        logger.warning(f"图片提取失败 question_id={question.question_id}: {img_err}")

    # 详细分类
    #
    # question_id 上有 UNIQUE 约束(uk_question_category)，此处原本是**盲目 INSERT**。
    # 只要该 question_id 已存在明细行就会撞唯一约束，并因批量入库共用一个事务而
    # **整批回滚、接口 500**。
    # 真实故障：库中曾残留 231 条孤儿明细行（对应题目已被硬删除的脚本清理掉，
    #   详见 clean_questions.py 漏清 question_detail_category），
    #   SQLite 复用主键后新题分配到同 id → IntegrityError，整个导入失败。
    # 因此改为幂等 upsert：存在则更新，不存在才插入 —— 对任何残留行都免疫。
    _existing_detail = db.query(QuestionDetailCategory).filter(
        QuestionDetailCategory.question_id == question.question_id
    ).first()
    if _existing_detail is not None:
        _existing_detail.xingce_subcategory = _xingce_sc
        _existing_detail.shenlun_subcategory = _shenlun_sc
        _existing_detail.gongzhuan_subcategory = _gongzhuan_sc
        _existing_detail.question_type_detail = normalize_type_name(type_name)
        logger.debug(f"[import] 题{question.question_id} 复用已有明细分类行（残留/复用）")
    else:
        detail = QuestionDetailCategory(
            question_id=question.question_id,
            xingce_subcategory=_xingce_sc,
            shenlun_subcategory=_shenlun_sc,
            gongzhuan_subcategory=_gongzhuan_sc,
            question_type_detail=normalize_type_name(type_name),
        )
        db.add(detail)
    _link_knowledge_points(db, [question])

    return {
        'import_status': 'SUCCESS',
        'question_id': question.question_id,
        'message': '题目导入成功',
    }


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
        from ...services.text_parser import extract_question_numbers
        nums = extract_question_numbers(content or '')
        return nums[0].number if nums else None
    except Exception:
        return None


def _detect_and_link_composite_groups(db, ok_items, qid_by_index, subject_name, source_tag=''):
    """批内复合题识别：返回 (groups_created, members_linked)。

    算法（批内作用域，调用方统一 commit 保证事务安全）：
    1. 为每个成功入库题提取题号（question_number）
    2. 用 composite_matcher 规则集识别题组头（题号范围/材料/情境/文章标识）
    3. 建 question_groups 行（shared_content=头题题干），头题与推断的小题
       全部挂 group_id / question_level=2 / sort_order / question_number
    """
    from ...services.composite_matcher import match_group_head, infer_member_qnums, semantic_grouping

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

    groups_created, members_linked = 0, 0
    claimed = set()
    for i, q in enumerate(ok_items):
        if i in claimed:
            continue
        head_hit = match_group_head(q.get('question_content') or '')
        if not head_hit:
            continue
        group_type, qnum_range = head_hit
        head_qid = qid_by_index.get(i)
        if not head_qid:
            continue
        head_qn = qnum_map.get(head_qid)
        head_qn = None if head_qn == 9999 else head_qn

        # 候选小题：批内其他未挂组的题号
        candidate_qnums = [qn for j, jid, qn in numbered
                           if j != i and jid not in claimed and qn is not None]
        member_qnums = infer_member_qnums(head_qn, candidate_qnums, qnum_range)
        if not member_qnums:
            # 无小题可挂 → 不建组（避免空题组）
            continue

        group = QuestionGroup(
            group_type=group_type,
            shared_content=q.get('question_content') or '',
            title=(q.get('question_content') or '')[:200],
            subject=subject_name or '公专',
            source=source_tag or q.get('paper_name', ''),
        )
        db.add(group)
        db.flush()
        groups_created += 1

        # 题号 → qid 映射（用于把 member_qnums 转为 qid）
        qn_to_qid = {qn: jid for j, jid, qn in numbered if qn is not None}
        member_ids = [head_qid]
        claimed.add(i)
        for mqn in member_qnums:
            jid = qn_to_qid.get(mqn)
            if jid and jid not in claimed:
                member_ids.append(jid)
                claimed.add(jid)
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
    unclaimed = [(i, q) for i, q in enumerate(ok_items) if i not in claimed]
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

            group = QuestionGroup(
                group_type=sug.get('group_type') or 'material',
                shared_content=ok_items[head_idx].get('question_content') or '',
                title=(ok_items[head_idx].get('question_content') or '')[:200],
                subject=subject_name or '公专',
                source=source_tag or ok_items[head_idx].get('paper_name', ''),
            )
            db.add(group)
            db.flush()
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
            from ...services.scheduler import _broadcast_sync
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
        from ...services.text_parser import _detect_question_type
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
                all_ids = ok_ids + reused_ids
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

    msg = f"导入完成：新增 {len(ok_ids)} 题，复用 {len(reused_ids)} 题，失败 {len(failed_items)} 题"
    if backfill_count:
        msg += f"，回填缺失字段 {backfill_count} 题"
    if groups_created:
        msg += f"；识别复合题组 {groups_created} 组（{members_linked} 题挂组）"
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
    from ...core.database import SessionLocal

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
            response_payload = {
                'import_id': import_id, 'original_filename': filename, 'file_type': file_type,
                'total_questions': total, 'success_count': success_count,
                'failed_count': failed_count, 'duplicate_count': duplicate_count,
                'questions': preview_items, 'auto_detected_tags': auto_tags,
            }
            stored = {'items': preview_items, 'auto_detected_tags': auto_tags,
                      '_response': response_payload}
            record.total_questions = total
            record.success_count = success_count
            record.failed_count = failed_count
            record.duplicate_count = duplicate_count
        else:
            from ...services.text_parser import extract_question_blocks
            _set_progress(60, 'SPLITTING')
            parsed_blocks = extract_question_blocks(text)
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

            total = len(preview_items)
            is_scanned = (ext == '.pdf' and len(preview_items) == 0 and _pdf_has_images_only(buf))
            response_payload = {
                'import_id': import_id, 'original_filename': filename, 'file_type': file_type,
                'total_questions': total, 'success_count': total, 'failed_count': 0,
                'duplicate_count': 0, 'questions': preview_items,
                # ★ groups：按「给定材料」聚合的复合题组，供前端渲染总题干。
                #   保留顶层 questions 不变，旧前端逻辑零回归。
                'groups': _build_preview_groups(preview_items),
                'raw_text_preview': text[:1000000] if text else '',
                'auto_detected_tags': auto_tags, 'scanned_pdf': is_scanned,
                'ocr_hint': ('该PDF为扫描件（无文本层），请使用"图片导入"标签页上传，'
                             '或先通过OCR工具转换为文本格式') if is_scanned else None,
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

    file_type_map = {'.xlsx': 'EXCEL', '.xls': 'EXCEL', '.csv': 'EXCEL', '.docx': 'WORD', '.pdf': 'PDF'}
    file_type = file_type_map.get(ext, 'EXCEL')

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


@router.get("/records/{import_id}/status", summary="查询异步导入解析状态")
async def get_import_parse_status(
    import_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """轮询异步导入的解析状态。

    返回：``{import_id, status, total_questions, success_count, failed_count,
    duplicate_count, error, result}``

    ``status='PREVIEW'`` 时 ``result`` 为完整预览数据（与原同步 /upload 响应同构）。
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
        # ★ P0-6 关键修复：历史记录存在双重编码，单次 json.loads 只能剥一层，
        #   拿到的是字符串而非 dict，导致 `isinstance(data, dict)` 恒假、
        #   预览页拿不到 _response → 用户"编辑后无法导入"。
        data = load_json_lenient(record.preview_data)
        if not isinstance(data, dict):
            data = {}
        if isinstance(data, dict):
            result = data.get('_response')
            if isinstance(result, dict):
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

    if target not in ('content', 'option'):
        raise HTTPException(status_code=400, detail="target 必须是 content 或 option")
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


def detected_subject_hint(item: Dict[str, Any]) -> str:
    """推断入库科目：优先申论标记，其次前端显式值，最后才回退行测。

    为什么不能沿用旧的 `item.get('subject_name', '行测')` 默认值：
      该默认值只在 key 完全缺失时生效，而前端**总是**会传 subject_name
      （值来自 _auto_detect_tags 的启发式）。申论长文本「给定资料…」很容易被
      启发式判成行测/公专，于是申论题被挂到错误科目下 —— requirements 语义
      全错、题型表也挂错。这是「前端申论导入不稳定」的直接原因之一。

    判定顺序刻意让 format=essay 压过 subject_name：解析器已经确证了这是申论，
    比任何文本启发式都可靠。
    """
    if (item or {}).get('format') == 'essay':
        return '申论'
    name = (item or {}).get('subject_name')
    return name if name else '行测'


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
        # ★ P0-6：历史记录 preview_data 为双重编码，单次 json.loads 只剥一层会返回 str，
        #   紧接着 .get() 会抛 AttributeError: 'str' object has no attribute 'get'。
        #   load_json_lenient 会循环剥到真实对象，并对脏数据返回 {}。
        preview_data = load_json_lenient(record.preview_data)
        if not isinstance(preview_data, dict):
            preview_data = {}
        items = preview_data.get('items', []) or []

        imported = 0
        skipped = 0
        failed = 0
        errors = []
        new_questions = []

        for item in items:
            if item.get('status') == 'DUPLICATE' or item.get('is_duplicate'):
                skipped += 1
                continue
            if item.get('status') == 'SKIPPED':
                failed += 1
                errors.append({'error': item.get('reason', '数据不完整'), 'raw': item.get('raw', {})})
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

                subject = _get_or_create_subject(db, item.get('subject_name') or detected_subject_hint(item))

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
                _gid = 0
                _mt = item.get('material_text') or item.get('material') or ''
                if _mt:
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
            from ...services.scheduler import _broadcast_sync
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

        return {
            'success_count': imported,
            'failed_count': failed,
            'skipped_count': skipped,
            'errors': errors,
            'paper_id': record.paper_id,
            'match_rate': preview_data.get('match_rate', 0),
            'message': f'导入完成：成功 {imported}，失败 {failed}，跳过 {skipped}',
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


@router.get('/mineru-health', summary='MinerU引擎健康巡检')
async def mineru_health():
    """探测独立venv中MinerU是否可用（结果缓存10分钟）。

    供运维巡检与前端诊断使用；不鉴权、仅暴露可用性/版本，不含敏感路径信息。
    """
    return mineru_health_cached()


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
    from ...services.text_parser import (
        extract_question_blocks, smart_match_questions_answers,
        detect_subject_category, ContentCleaner, _extract_options,
        extract_answer_from_lines, _detect_question_type,
    )

    mode = payload.mode or 'combined'
    questions_text = (payload.questions_text or '').strip()
    answers_text = (payload.answers_text or '').strip()
    paper_name = payload.paper_name or ''
    subject_category = payload.subject_category or ''

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
                result = smart_match_questions_answers(
                    questions_text, answers_text, paper_name)
                match_rate = round(result.match_rate * 100, 1)
                matched_count = result.matched_count
                total_questions = result.total_questions
                unmatched_numbers = result.unmatched_question_numbers
                extra_answer_numbers = result.extra_answer_numbers
                analysis_count = result.analysis_count
                strategy_used = result.strategy_used
                essay_prebuilt = None

            if not auto_detected_subject:
                all_content = ' '.join(q.get('content', '') for q in result.questions[:10])
                auto_detected_subject, _ = detect_subject_category(all_content)

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

        else:
            # ===== 合并导入 / OCR模式：提取题目块 =====
            cleaned_text = ContentCleaner.clean_text(questions_text)
            blocks = extract_question_blocks(cleaned_text)

            if not blocks:
                # 回退：尝试用前端兼容的宽松解析（按行切分）
                warnings.append('未检测到标准题号格式，已尝试宽松解析')
                blocks = _fallback_loose_parse(cleaned_text)

            if not auto_detected_subject:
                all_content = ' '.join(b.get('content', '') for b in blocks[:10])
                auto_detected_subject, _ = detect_subject_category(all_content)

            total_questions = len(blocks)
            for block in blocks:
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

            # 统计匹配结果
            matched_count = sum(1 for q in questions if q.answer and q.answer != '待补充')
            analysis_count = sum(1 for q in questions if q.analysis and len(q.analysis) > 10)
            if total_questions > 0:
                match_rate = round(matched_count * 100 / total_questions, 1)
            strategy_used = '合并导入解析'

        # 自动检测标签
        auto_tags = _auto_detect_tags(paper_name, questions_text[:2000])

        # ===== Validator: 数据完整性校验 + 置信度评分 =====
        from ...services.text_parser import AnswerValidator
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

        return ParseResult(
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
    from ...services.text_parser import _extract_options, extract_answer_from_lines, _detect_question_type

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
        from ...services.ocr import recognize_image_enhanced, recognize_image

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

        return response

    except RuntimeError as e:
        logger.warning(f"OCR 服务不可用: {e}")
        return {
            'status': 'error',
            'ocr_text': '',
            'formulas': [],
            'tables': [],
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
            subject_name, _ = detect_subject_category(ocr_text)
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

    # 自动检测科目
    all_text = ' '.join(
        q.get('content', '') or q.get('question_content', '')
        for q in structured_questions[:5]
    )
    subject_name = payload.get('subject_category', '')
    if not subject_name:
        subject_name, _ = detect_subject_category(all_text)
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
