"""标签检测与自动建卷 — 试卷元数据启发式 + ExamPaper 落库。

I-4：pure move 自 backend/app/api/v1/question_import.py（任务 39），
四个函数体一字未改（唯一例外：`_get_or_create_import_paper` 内
`from .paper_generation import generate_paper_code` 的相对导入基准
随模块位置适配为 `...api.v1.paper_generation` —— import 位置调整，
非逻辑变更）；`SUBJECT_NAME_MAP` 常量随其重度使用方一并搬迁，
question_import.py 改为导入并 re-export，外部调用方
（tests/test_gongzhuan_regression.py、scripts/probe_xingce_corpus.py 等）零改动。
"""
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 科目名称 → subject_id 缓存
SUBJECT_NAME_MAP = {
    '行测': 1, '申论': 2, '公专': 3, '公安专业知识': 3,
    '其他': 4, '综合': 4,
}


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
    from ...api.v1.paper_generation import generate_paper_code

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
