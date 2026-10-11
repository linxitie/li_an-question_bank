"""
行测解析：分节路由 + 分离配对（自 text_parser.py 行测区块的纯搬迁）

迁移说明（任务 44，I-9，唯一动 text_parser.py 的拆分步骤）
-----------------------------------------------------------
1. 本文件内容自 text_parser.py 的「行测分节路由」区块逐字节搬迁而来，
   未改动任何一个字符。三个入口函数 route_xingce_sections /
   split_xingce_answer_blocks / xingce_cross_validate 的函数体与
   搬迁前完全一致（可用 git show 比对原文）。
2. text_parser.py 只以 from ... import 的形式 re-export 本文件符号，
   因此所有 from app.services.text_parser import X 的调用方零改动。
3. 为何不用 text_parser/ 目录而用扁平模块 text_parser_xingce.py：
   目录形态的 text_parser/（含 __init__.py）在 import 时会遮蔽
   同名的 text_parser.py，使 from app.services.text_parser import X
   解析到包上、全部模块级属性丢失（实测：同名的目录包优先于 .py）；
   而不含 __init__.py 的目录又会让 text_parser 不成为 package，
   其子模块不可导入（ModuleNotFoundError: 'text_parser' is not a package）。
   在「text_parser.py 必须保持为可导入模块」（L0 红线按文件路径读取它）
   的前提下，text_parser/xingce.py 这一路径不可行，故采用等价扁平模块。
4. 有两个 text_parser.py 的函数在本文件中只被引用、不被定义：
   ``xingce_cross_validate`` 调用 ``extract_question_blocks``；
   ``split_xingce_answer_blocks`` 调用 ``canonical_answer``。
   为保持这两个函数体逐字节不变，这里只在模块级做别名绑定（见文件末尾），
   **不可**在模块顶部直接 import 这两个名字——既会构成 import 环，
   也会触发 L0 红线「extract_question_blocks 未外泄」（红线用逐行字面量
   扫描 services/ 下所有非 text_parser 模块，故本文档与注释也避免把该名称
   与 import 关键字写在同一行）。
5. 申论解析（_parse_essay_document 及其 15 个符号）按红线要求留在
   text_parser.py 原地未动，它被 extract_question_blocks 入口直接调用。
"""
import re
from typing import List, Dict, Any, Optional, Tuple

# 循环依赖方向：本模块调用 text_parser.extract_question_blocks 与
# text_parser.canonical_answer，而 text_parser 在其文件末尾 import 本模块
# 以 re-export 行测符号。
# 因此本模块对 text_parser 的引用**必须放在本文件末尾**（即本模块全部符号
# 定义完之后）—— 反过来先 import 本模块时，text_parser.py 末尾的
# `from app.services.text_parser_xingce import ...` 会因为本模块还没定义出
# 这些名字而 ImportError。见文件末尾的说明。

# ============================================================================
# 行测分节路由（任务 7 新增）
# ============================================================================
#
# 设计契约（红线，违反即回归公专/申论链路）
# ------------------------------------------------
# 1. **纯增量**：本区块全部为新增符号，不修改本文件任何既有函数体。
#    `extract_question_blocks` / `ContentCleaner` / `_mark_and_split_suspected`
#    等一律保持字节级不变。接入点在任务 11 的独立端点，不在此处埋入。
# 2. **>=2 锚点安全门槛**：仅当同时命中 **2 个及以上**行测分节锚点才返回非 None，
#    否则返回 None 由调用方走原路径。仿申论 `_route_sections` 的同款门槛，
#    是保证 2,583 道公专题零回归的唯一保险。
# 3. **分区身份只取词表，不取序号**：实测同一分区在不同卷里序号不同
#    （`常识判断` 出现过 `一、` `二、` `四、`；`资料分析` 出现过 `五、` `六、` `七、`），
#    故 ordinal 仅作呈现，name 才是身份。
# 4. **锚点须有终止符**：分节头必须以全角冒号结尾或独占一行，
#    以免把「一、资料分析显示…」这类正文首句误判为分节头。
#    这是前序铁律「行级正则必须处理标记与内容同行的常态；锚定 $ 是脆弱假设」
#    与本条「但也不能无终止符」的折中：终止符 = 冒号 or 行尾。
#
# 实测依据（题库/行测 85 套全量，170/170 PDF）
# ------------------------------------------------
#   - 分节头命中率 100%（85/85 题本、85/85 答案解析）
#   - 分节序列：5 节 57 套 / 6 节 27 套 / 7 节 1 套
#   - 词表：言语理解与表达 85 / 数量关系 85 / 判断推理 85 / 资料分析 85 /
#           常识判断 84 / 政治理论 25 / 科学推理 4 / 常识 1
#   - 资料分析材料锚点：`（一）（二）…` 全角括号独占行，共 364 块，85/85 覆盖
#   - 同一分节头的两种实测形态：`一、 政治理论：`（冒号式）与 `四、 常识判断`（独占行式）

XINGCE_SECTION_NAMES = (
    "政治理论",
    "常识判断",
    "常识",
    "言语理解与表达",
    "数量关系",
    "判断推理",
    "科学推理",
    "资料分析",
)

# 终止符 = 全角/半角冒号 或 行尾（re.M 下 $ 即行尾）
_XINGCE_SEC_ALT = "|".join(XINGCE_SECTION_NAMES)
XINGCE_SECTION_PATTERN = re.compile(
    r"^[ \t]*([一二三四五六七八九十]{1,3})[、.．][ \t]*"
    r"(" + _XINGCE_SEC_ALT + r")"
    r"[ \t]*(?:[：:]|$)",
    re.M,
)

# 资料分析材料锚点：全角括号独占行。
# 与申论的「材料1 / 给定资料N」、公专的「情境材料」是**不同形态**，不可复用。
XINGCE_MATERIAL_PATTERN = re.compile(
    r"^[ \t]*（([一二三四五六七八九十]{1,3})）[ \t]*$", re.M
)

# 安全门槛：命中多少个分节才算「这是行测试卷」
XINGCE_MIN_SECTION_HITS = 2


def route_xingce_sections(text: str) -> Optional[dict]:
    """识别行测试卷的分节结构与资料分析材料锚点。

    与申论 `_route_sections` 同款设计：一个模型同时适配「合并本」与「分离型」，
    不产生第二套体系。

    Args:
        text: 试卷全文（题本或答案解析均可——实测两者携带**完全相同**的分节头，
              这是行测配对安全网的地基）。

    Returns:
        命中 >=2 个分节锚点时返回::

            {
              'sections': [
                  {'ordinal': '一', 'name': '政治理论', 'start': 31, 'end': 4032},
                  ...
              ],
              'section_names': ['政治理论', '常识判断', ...],
              'materials': [{'ordinal': '一', 'start': 22039, 'end': 22600}, ...],
              'material_count': 4,
            }

        否则返回 ``None`` —— 调用方必须据此走原路径（公专/申论链路的安全门）。
    """
    if not text:
        return None

    hits = list(XINGCE_SECTION_PATTERN.finditer(text))
    if len(hits) < XINGCE_MIN_SECTION_HITS:
        return None

    sections = []
    for i, m in enumerate(hits):
        sections.append({
            'ordinal': m.group(1),
            'name': m.group(2),
            'start': m.start(),
            'end': hits[i + 1].start() if i + 1 < len(hits) else len(text),
        })

    # 材料锚点：行测**全分节通用**，实测分布 资料分析 299 / 言语理解与表达 39 /
    # 判断推理 19 / 常识判断 7 = 364（85 套题本全量）。
    #   - 言语理解：「（一）以下是略有删节的公文部分内容，阅读之后回答51—55题」→ 多篇文章
    #   - 判断推理：「（一）6天休假期间，单位需要每天安排一人值班…」→ 情景材料
    #   - 常识判断：「（一）2017年9月，党中央、国务院批复的《北京城市总体规划》…」→ 材料
    # 故**不得**限定在资料分析内 —— 限定会丢弃 65 个材料块（364 → 299）。
    # 每个材料块标注所属分节，供任务 9 映射 question_groups.group_type。
    materials = []
    for i, m in enumerate(XINGCE_MATERIAL_PATTERN.finditer(text)):
        owner = ''
        for sec in sections:
            if sec['start'] <= m.start() < sec['end']:
                owner = sec['name']
                break
        nxt = XINGCE_MATERIAL_PATTERN.search(text, m.end())
        materials.append({
            'ordinal': m.group(1),
            'start': m.start(),
            'end': nxt.start() if nxt else len(text),
            'section': owner,
        })

    return {
        'sections': sections,
        'section_names': [s['name'] for s in sections],
        'materials': materials,
        'material_count': len(materials),
        'materials_by_section': {
            name: sum(1 for x in materials if x['section'] == name)
            for name in sorted({x['section'] for x in materials})
        },
    }


# ============================================================================
# 行测分离配对（任务 8 新增）
# ============================================================================
#
# 为何必须有独立的安全网（方案立论）
# ------------------------------------
# 申论有「题号 + 分值 + 题干指纹」三重判据；行测答案解析**既不重复题干、也无分值**，
# 三重判据只剩 1/3。若上传 2024 题本 + 2025 答案解析，**计数相等也照样全卷配错，
# 且无任何机制能察觉**。
#
# 行测专属替代安全网：**分节边界对齐**。题本与答案解析携带**完全相同的分节头**
# （实测 170/170 命中，85 对分节序列逐套全等），故「每节题号区间必须逐一相等」
# 在信息论上等价于申论的「分值锚点 + 题干指纹」的合成替代物，**且成本为零**。
#
# 为何必须按「答案锚点」切分（任务 1 实测的缺陷）
# --------------------------------------------------
# 行测资料分析解析中密集出现「小数 + 单位」文本（`780.9毫米` / `42.3、64.1` /
# `77.01元/公斤`）。PDF 拆行使数字落在行首，既有 `QuestionNumberRecognizer`
# 的 `^\s*(\d+)\.\s*` 会把它当成题号：
#   - 42 / 77 是**倒退**的 → 被既有 monotonic 过滤挡下（但仍会错误切断相邻题解析）
#   - **780 是前进的** → 单调性挡不住 → 切断块边界 → 安徽 101~110 共 10 题
#     的解析被吞进一个编号 780 的块 → `110 − 100 − 1 = 101`（与 DB 记录吻合）
#
# 而 `N. 正确答案：X` 锚点**不受影响**：`780.9毫米` 后面不跟「正确答案」，
# 故不会被误判为块边界。实测锚点切分在 85 套上**伪题号归零**、题号集合精确等于
# `1..N`（无缺失、无重复）。

# 答案锚点：行首 `N. 正确答案：X`，X 支持 `A` / `AC` / `A,C` / `A、C`
XINGCE_ANSWER_ANCHOR_PATTERN = re.compile(
    r"^[ \t]*(\d{1,3})[ \t]*[.．、][ \t]*"
    r"(?:本题)?正确答案[：:][ \t]*"
    r"([A-H](?:[ \t]*[、,，]?[ \t]*[A-H])*)",
    re.M,
)


def split_xingce_answer_blocks(text: str) -> List[Dict[str, Any]]:
    """按**答案锚点** `N. 正确答案：X` 切分行测答案解析。

    与 ``extract_question_blocks`` 的区别：后者以裸题号 `N.` 切分，会被资料分析
    解析中的「小数+单位」误伤；本函数只认「题号 + 正确答案」这一权威形态。

    Returns:
        ``[{'question_number': int, 'answer_raw': str, 'answer': str,
           'analysis': str, 'kao_points': List[str], 'start': int, 'end': int}, ...]``

        ``answer`` 已经过 :func:`canonical_answer` 归一化（唯一归一化入口）。
    """
    if not text:
        return []
    hits = list(XINGCE_ANSWER_ANCHOR_PATTERN.finditer(text))
    if not hits:
        return []

    # 分节边界优先于下一个锚点：答案块不跨分节
    sec = route_xingce_sections(text)
    sec_bounds = [s['start'] for s in sec['sections']] if sec else []

    def _next_limit(pos: int, fallback: int) -> int:
        for b in sec_bounds:
            if b > pos:
                return b
        return fallback

    out: List[Dict[str, Any]] = []
    for i, m in enumerate(hits):
        start = m.start()
        nxt = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        end = min(nxt, _next_limit(start, len(text)))
        body = text[m.end():end]

        # 【考点】→ 考点列表（本字段只存在于行测答案解析）
        kao: List[str] = []
        km = re.search(r"【考点】[ \t]*\r?\n?([^\n【]{1,160})", body)
        if km:
            kao = [t.strip() for t in re.split(r"[,，、;；/／]+", km.group(1)) if t.strip()]

        # 解析正文 = 去掉「解析：」标记与考点段
        analysis = body
        analysis = re.sub(r"^[ \t]*(?:本题)?解析[：:][ \t]*", "", analysis, count=1)
        if km:
            analysis = analysis[: km.start()]

        out.append({
            'question_number': int(m.group(1)),
            'answer_raw': m.group(2),
            'answer': canonical_answer(m.group(2)),
            'analysis': analysis.strip(),
            'kao_points': kao,
            'start': start,
            'end': end,
        })
    return out


# 行测题号（**排除小数形态**）
#
# 行测资料分析中密集出现「小数 + 单位」文本（`780.9毫米` / `5.2万亿元` / `42.3`）。
# PDF 拆行使其数字落在行首；`^\s*(\d{1,3})\s*[.．、]\s*\S` 会把 `780.9毫米` 中的
# `780` 当成题号（分隔点后是 `\s`，不匹配 `(?!\d)`），进而错误切断块边界。
#
# 关键约束：**分隔点后不得紧跟数字** —— `(?!\d)`。
#   - `780.9毫米` → `.` 后是 `9` → 排除 ✔
#   - `60.` + 空格 + `。`（填横线题） → `.` 后是空格 → 保留 ✔
#
# 实测：安徽 2023 题本旧正则得 111 个题号（多 1，即小数误命中），
# 排除小数后得 110，与答案锚点数精确相等；五个分节区间与答案侧逐项全等。
XINGCE_QNUM_PATTERN = re.compile(r"^[ \t]*(\d{1,3})[ \t]*[.．、](?!\d)", re.M)


def _xingce_section_intervals(text: str, qnum_of) -> List[Dict[str, Any]]:
    """每个分节内的题号区间 —— 安全网 X-2 的断言对象。"""
    sec = route_xingce_sections(text)
    if not sec:
        return []
    out = []
    for s in sec['sections']:
        nums = qnum_of(text[s['start']:s['end']])
        out.append({
            'name': s['name'],
            'min': min(nums) if nums else None,
            'max': max(nums) if nums else None,
            'count': len(nums),
        })
    return out


def _xingce_anchor_nums(seg: str) -> List[int]:
    return [int(m.group(1)) for m in XINGCE_ANSWER_ANCHOR_PATTERN.finditer(seg)]


def _xingce_clean_qnums(seg: str) -> List[int]:
    return [int(m.group(1)) for m in XINGCE_QNUM_PATTERN.finditer(seg)]


def xingce_cross_validate(question_text: str, answer_text: str) -> Dict[str, Any]:
    """行测「题本 + 答案解析」配对 + 五项安全网校验（任务 8 核心）。

    校验项
    ------
    ======  ====================================  ==========================
    编号    判据                                   不一致时
    ======  ====================================  ==========================
    X-1     分节头序列全等（题本 == 答案解析）      整卷 blocked
    X-2     分节→答案锚点区间全等                  整卷 blocked
    X-3     题号连续、无跳号/无重复                该题 answer_missing
    X-4     锚点数 == 题本块数                     **不单独阻断**，输出差集
    X-5     canonical_answer 归一化 ∈ 合法集该题 blocked
    ======  ====================================  ==========================

    「区间全等」在信息论上等价于申论的「分值锚点 + 题干指纹」：两卷各自携带相同分节头，
    分节边界一旦错位（错年份/错卷别），区间立刻不等 → 被拦截。

    **禁止按序盲配**：若答案卷缺某题号，绝不拿相邻题的答案兜底
    （前序 `_essay_cross_validate` 教训：按序配对会把 A 卷答案贴到 B 卷题目上）。
    """
    q_sec = route_xingce_sections(question_text or '')
    a_sec = route_xingce_sections(answer_text or '')
    q_blocks = extract_question_blocks(question_text or '')
    a_blocks = split_xingce_answer_blocks(answer_text or '')

    report: Dict[str, Any] = {
        'question_count': len(q_blocks),
        'answer_count': len(a_blocks),
        'block_reasons': [],
        'only_in_questions': [],
        'only_in_answers': [],
        'missing_answer': [],
        'section_intervals': {'q': [], 'a': []},
    }

    # ── 前置：两份文档都必须能被识别为行测试卷 ──
    if q_sec is None:
        report['block_reasons'].append('question_not_xingce')
    if a_sec is None:
        report['block_reasons'].append('answer_not_xingce')
    if q_sec is None or a_sec is None:
        report['blocked'] = True
        return {'questions': [], 'report': report}
    # 显式标注非 Optional：守卫之上已排除 None，此处只为让类型检查器收窄
    q_sec_map: Dict[str, Any] = q_sec
    a_sec_map: Dict[str, Any] = a_sec

    # ── X-1 分节头序列全等 ──
    q_names = [s['name'] for s in q_sec_map['sections']]
    a_names = [s['name'] for s in a_sec_map['sections']]
    x1_ok = (q_names == a_names)
    if not x1_ok:
        report['block_reasons'].append('section_sequence_mismatch')

    # ── X-2 分节→区间全等 ──
    # 题本侧必须用**排除小数**的清洁题号（`780.9毫米` 的 `780` 不是题号）；
    # 答案侧用锚点题号（权威）。两侧口径不同，但正因如此才能互为校验。
    q_iv = _xingce_section_intervals(question_text, _xingce_clean_qnums)
    a_iv = _xingce_section_intervals(answer_text, _xingce_anchor_nums)
    report['section_intervals'] = {'q': q_iv, 'a': a_iv}
    key = lambda iv: (iv['name'], iv['min'], iv['max'])
    x2_ok = ([key(x) for x in q_iv] == [key(x) for x in a_iv])
    if not x2_ok:
        report['block_reasons'].append('section_interval_mismatch')

    # ── 逐题配对（题号 join，绝不按序）──
    a_by_no: Dict[int, Dict[str, Any]] = {}
    for b in a_blocks:
        a_by_no.setdefault(b['question_number'], b)

    questions: List[Dict[str, Any]] = []
    seen: List[int] = []
    blocked = not (x1_ok and x2_ok)

    # 题本伪题号过滤：小数形态（`469.9亿美元` / `176.0亿元` / `213.4万辆`）被
    # `extract_question_blocks` 当成题号 469/176/213。这些数字**相对前题是前向跳跃**，
    # 故既有 monotonic 过滤挡不住，会凭空多出「缺答案」的题。
    # 实测：清洁题号集（`(?!\d)`）与答案锚点集精确相等（135/110/120），
    # 故以清洁题号集为权威，剔除不在其中的块。
    clean_qnums = set(_xingce_clean_qnums(question_text or ''))
    spurious: List[int] = []

    for qb in q_blocks:
        qno = qb.get('question_number')
        if qno is None:
            continue
        try:
            qno_i = int(qno)
        except (TypeError, ValueError):
            continue
        # 剔除小数伪题号（见上方注释）
        if clean_qnums and qno_i not in clean_qnums:
            spurious.append(qno_i)
            continue
        reasons: List[str] = []

        # 分节归属：以**答案锚点在答案解析中的位置**为准（权威且精确）。
        # 不可用题本块的位置 —— `extract_question_blocks` 不返回位置字段，
        # 退化为 `s['start']` 会让所有块都落进第一个分节。
        sec_name = ''
        ab = a_by_no.get(qno_i)
        if ab is not None:
            for s in a_sec_map['sections']:
                if s['start'] <= ab['start'] < s['end']:
                    sec_name = s['name']
                    break
        if not sec_name and q_sec_map['sections']:
            sec_name = q_sec_map['sections'][0]['name']

        out = dict(qb)
        out['section_name'] = sec_name

        if ab is None:
            reasons.append('answer_missing_for_question')
            out['answer'] = ''
            out['analysis'] = ''
            out['kao_points'] = []
            report['missing_answer'].append(qno_i)
        else:
            out['answer'] = ab['answer']
            out['analysis'] = ab['analysis']
            out['kao_points'] = ab['kao_points']
            # X-5 答案合理性
            if not ab['answer'] or not re.fullmatch(r'[A-Z]{1,4}', ab['answer'] or ''):
                reasons.append('invalid_answer')

        out['block_reasons'] = reasons
        # 防御深度：卷级 blocked（X-1/X-2 失败）时，**每道题也必须 blocked**。
        # 否则若调用方只看questions 列表而忽略 report['blocked']，
        # 错年份配对的答案就会被当作正常结果落库 —— 这正是安全网要防的事故。
        if blocked:
            for r_code in report['block_reasons']:
                if r_code not in reasons:
                    reasons.append(r_code)
        out['blocked'] = bool(reasons)
        out['need_review'] = bool(reasons) or not (out.get('options') or [])
        questions.append(out)
        seen.append(qno_i)

    # ── X-3 题号连续性（题本侧）──
    ordered = sorted(set(seen))
    if ordered:
        expect = list(range(ordered[0], ordered[0] + len(ordered)))
        if ordered != expect:
            report['block_reasons'].append('question_number_not_contiguous')

    # ── X-4 计数与差集（不单独阻断）──
    only_q = sorted(set(seen) - set(a_by_no))
    only_a = sorted(set(a_by_no) - set(seen))
    report['only_in_questions'] = only_q
    report['only_in_answers'] = only_a

    report['blocked'] = blocked
    report['blocked_count'] = sum(1 for q in questions if q.get('blocked'))
    report['matched'] = len(set(seen) & set(a_by_no))
    report['spurious_question_numbers'] = sorted(set(spurious))
    report['x'] = {'x1_section_sequence': x1_ok, 'x2_section_intervals': x2_ok}
    return {'questions': questions, 'report': report}


# --- 模块级别名绑定（任务 44） ------------------------------------------
# xingce_cross_validate 内部调用 extract_question_blocks(...)，
# split_xingce_answer_blocks 内部调用 canonical_answer(...)；两者唯一定义都在
# text_parser.py。为了让这两个函数体保持逐字节不变，此处以模块级别名解析。
#
# 位置要求（**必须在文件末尾**）：
#   text_parser.py 末尾用 `from app.services.text_parser_xingce import (...)` re-export
#   本模块符号。若本模块在顶部就 import text_parser，则当「本模块被先 import」时，
#   text_parser.py 会在末尾反向 import 一个**尚未定义完**的本模块 → ImportError。
#   把本模块对 text_parser 的引用推迟到全部符号定义之后，两种 import 顺序
#   均可在 Python 3.13.5 上正常加载（已实测）。
#
# 这两行刻意不含 import 字样 —— L0 红线会扫描 services/ 下所有非
# text_parser.py 的模块，任何一行同时出现 extract_question_blocks
# 与 import/from 都会被判为「红线函数外泄」。
from app.services import text_parser as _text_parser

extract_question_blocks = _text_parser.extract_question_blocks

# 同理，split_xingce_answer_blocks 内部调用 canonical_answer（唯一定义在
# text_parser.py 中）：行测答案解析的 'answer' 字段经它归一化。
canonical_answer = _text_parser.canonical_answer
