"""Excel/CSV 解析 — 容错列名字典 + 表头归一 + 表头探测 + GBK 编码嗅探。"""
import csv
import io
import json
import logging
import re

logger = logging.getLogger(__name__)

# ★ J-3-1: 单一事实来源的列名容错字典
# ★ 必须覆盖 question_import._normalize_question 原先读取的**全部**字段，
#   否则接线会丢字段（year/tags/paper_name/... 曾因只保留 9 个键而回归）。
COLUMN_ALIASES = {
    'question_content': ['题目内容', '题干', 'question', '题目', '题目描述', '试题内容', '题干内容', 'content', '题目正文',
                         # 带空格的英文写法：两侧都会被 normalize_header 去掉空白后比对，
                         # 故 'Question Content' → 'questioncontent' 命中 'question content'
                         'question content', 'question text', 'item content'],
    'answer': ['答案', '正确答案', 'answer', '标准答案', '参考答案', '正确选项', '答案选项', 'key'],
    'answer_analysis': ['解析', '答案解析', 'analysis', 'explanation', '解析说明', '答案说明', '详解', '解题思路'],
    'subject_name': ['科目', '科目大类', 'subject', '科目名称', '所属科目', '考试科目'],
    'type_name': ['题型', '题目类型', 'type', '题型名称', '题目分类', '类型'],
    'score': ['分值', 'score', '分数', '题目分值', '满分', '分值(分)'],
    'difficulty': ['难度', 'difficulty', '难度等级', '难易程度'],
    'source': ['来源', 'source', '出处', '题目来源', '考试来源'],
    'knowledge_point': ['知识点', '考点', 'knowledge_point', '知识点名称', '考点名称', '所属知识点'],
    'options': ['选项', 'options', '选项内容', '选项列表'],
    # ↓ 以下为原实现已支持、本次必须保住的字段（接线时不得丢失）
    'year': ['年份', 'year', '考试年份', '出题年份'],
    'tags': ['标签', 'tags', 'tag', '题目标签'],
    'paper_name': ['试卷名称', 'paper_name', '试卷', '试卷名'],
    'exam_province': ['省份', 'exam_province', '省', '考试省份', '地区'],
    'exam_type': ['考试类型', 'exam_type', '类型类型', '考试类别'],
    'subcategory': ['子科目', '细分', '小类', 'subcategory', '细分类型'],
}

# 选项列的别名（A-H）
OPTION_KEYS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']


def normalize_header(h: str) -> str:
    """表头归一：全角→半角、去换行制表、去尾部冒号、去括号备注、大小写不敏感、**移除所有内部空白**。

    ★ 必须移除**内部**空白：真实题库 Excel 里普遍把中文表头排版成
      「题 目 内 容」，英文表头写成「Question Content」。若只做首尾 strip，
      这两种写法都无法与别名匹配 —— 容错字典等于失效。
      移除全部空白后「选项 A」与「选项A」也会统一，不影响选项列解析。
    """
    if not h:
        return ''
    h = str(h)
    h = h.replace('　', ' ')          # 全角空格 → 半角
    h = h.replace('\n', '').replace('\t', ' ').replace('\r', '')
    h = re.sub(r'[：:]\s*$', '', h)          # 去尾部冒号（须在去空白之前）
    h = re.sub(r'[（(].*?[）)]', '', h)      # 去括号备注，如「难度(1-5)」
    h = re.sub(r'\s+', '', h)                # ★ 移除所有内部空白
    return h.lower()


def detect_header_row(rows: list, max_scan: int = 5) -> int:
    """前 max_scan 行逐行打分，命中别名词数最多者即为表头行"""
    best_row = 0
    best_score = 0
    all_aliases = set()
    for aliases in COLUMN_ALIASES.values():
        for a in aliases:
            all_aliases.add(normalize_header(a))

    for i in range(min(max_scan, len(rows))):
        score = 0
        for cell in rows[i]:
            if cell and normalize_header(str(cell)) in all_aliases:
                score += 1
        if score > best_score:
            best_score = score
            best_row = i
    return best_row


def match_column(header: str, field: str) -> bool:
    """判断表头是否匹配某个字段"""
    norm = normalize_header(header)
    for alias in COLUMN_ALIASES.get(field, []):
        if normalize_header(alias) == norm:
            return True
    return False


def get_field_value(row_dict: dict, field: str) -> str:
    """从行字典中按别名查找字段值"""
    for alias in COLUMN_ALIASES.get(field, []):
        for key, val in row_dict.items():
            if normalize_header(key) == normalize_header(alias):
                return str(val).strip() if val is not None else ''
    return ''


def parse_excel_buffer(buf: bytes, filename: str) -> list:
    """使用 openpyxl 解析 Excel 文件，支持表头探测和多 sheet"""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("服务器缺少 openpyxl 库")

    wb = openpyxl.load_workbook(io.BytesIO(buf), read_only=True, data_only=True)
    all_questions = []

    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            continue

        # ★ J-3-3: 表头探测
        header_idx = detect_header_row(rows)
        headers = [str(h).strip() if h else '' for h in rows[header_idx]]

        for row in rows[header_idx + 1:]:
            if all(v is None or str(v).strip() == '' for v in row):
                continue
            row_dict = {}
            for i, h in enumerate(headers):
                val = row[i] if i < len(row) else None
                row_dict[h] = str(val).strip() if val is not None else ''
            all_questions.append(row_dict)

    return all_questions


def parse_csv_buffer(buf: bytes) -> list:
    """解析 CSV 文件，支持 GBK 编码嗅探"""
    # ★ J-3-4: 编码嗅探顺序
    for encoding in ['utf-8-sig', 'gbk', 'gb18030', 'latin-1']:
        try:
            text = buf.decode(encoding)
            reader = csv.DictReader(io.StringIO(text))
            return [dict(row) for row in reader]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise RuntimeError("无法解码 CSV 文件（尝试了 utf-8-sig/gbk/gb18030/latin-1）")


def normalize_question(row: dict) -> dict | None:
    """将原始行数据标准化为题目标准格式。丢行时返回 None 并记录原因。"""
    content = get_field_value(row, 'question_content')
    answer = get_field_value(row, 'answer')

    if not content:
        return {'_drop_reason': '缺题干', '_raw': row}
    if not answer:
        return {'_drop_reason': '缺答案', '_raw': row}

    subject_name = get_field_value(row, 'subject_name') or '行测'
    raw_type = get_field_value(row, 'type_name')
    answer_analysis = get_field_value(row, 'answer_analysis')
    score_str = get_field_value(row, 'score')
    difficulty_str = get_field_value(row, 'difficulty')
    source = get_field_value(row, 'source')
    knowledge_point = get_field_value(row, 'knowledge_point')

    # 选项提取
    options = []
    for key in OPTION_KEYS:
        opt_val = ''
        for k, v in row.items():
            norm_k = normalize_header(k)
            if norm_k in (normalize_header(f'选项{key}'), normalize_header(key)):
                opt_val = str(v).strip() if v else ''
                break
        if opt_val:
            options.append({'key': key, 'value': opt_val})

    if not options:
        opt_str = get_field_value(row, 'options')
        if opt_str:
            try:
                parsed = json.loads(opt_str)
                if isinstance(parsed, list):
                    options = parsed
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        'question_content': content,
        'answer': answer,
        'answer_analysis': answer_analysis,
        'subject_name': subject_name,
        'type_name': raw_type,
        'options': options,
        'score': float(score_str) if score_str else 1.0,
        'difficulty': int(difficulty_str) if difficulty_str and difficulty_str.isdigit() else 3,
        'source': source,
        'knowledge_point': knowledge_point,
    }
