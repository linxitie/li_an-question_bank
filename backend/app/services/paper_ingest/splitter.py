# -*- coding: utf-8 -*-
"""试卷文本 → 题目草稿（P3，2026-11-09）。

**为什么是纯函数**：拆题规则最容易被"换一份卷子"打穿，必须可单测、可回归、可回放。
输入只有一个"带行的文本流"（docx 段落 / pdf 每页文本都归一成行），
输出是题目草稿列表；写库、落图、挂卷都在 `service.py`，本文件不碰数据库。

规则来源：`_run/smoke_2024_gk_parse_v3.py`（2024 国考那套卷实测 100 题/选项齐全/28 图），
把当时的踩坑原样搬过来：

  ① **题型是"段落状态"**：卷面只在少数地方写 `【题型】多选`，或章标题写「一、单项选择题」；
     从该处起，后续题默认这个题型，遇到逐题内联标记 `（多选）` 再覆盖。
  ② **内联标记会被换行切断**（`（多\\n选）`）：判定前先把整块空白去掉再匹配。
  ③ **情境材料**：`根据以下情境材料，回答 91~100 题` → 这一组题共享同一段材料，
     材料文本只挂在组内第一题上（避免 30 题重复 30 份材料）。
  ④ **PDF 换行会把汉字拆开带空格**（`会议指 出`）：`clean_cn()` 只在两个汉字之间删空格，
     英文单词与数字之间的空格保留（否则 `A 选项`、`2023 年` 会被粘错）。
"""
from __future__ import annotations

import re
from statistics import median
from typing import Dict, List, Optional

#: 题号行：`1.` / `1．` / `1、` / `第1题`（行首，最多三位数）
QNO_RE = re.compile(r"^\s*(?:第\s*)?(\d{1,3})\s*(?:题\s*)?[.．、]?\s*")
#: 更严格的一版：必须带分隔符或"第N题"，避免把 "2023 年" 当成题号
QNO_STRICT_RE = re.compile(r"^\s*(?:第\s*(\d{1,3})\s*题|(\d{1,3})\s*[.．、])\s*")
#: 选项行内切分：`A.` / `A、` / `A．`（含全角字母）
OPT_RE = re.compile(r"([A-DＡ-Ｄ])\s*[.．、]\s*")
#: `【题型】单选题`
MARK_RE = re.compile(r"^[\s【\[]*题\s*型[\s】\]]*[:：]?\s*(单选|多选|不定项|判断|复合)")
#: 章标题式题型：`一、单项选择题` / `二、多项选择题`
SECTION_TYPE_RE = re.compile(
    r"^\s*[一二三四五六七八九十]+\s*[、.]\s*(单项选择|多项选择|不定项选择|单选|多选|判断)")
#: 情境材料标题：`根据以下情境材料，回答 91~100 题`
SHARED_RE = re.compile(
    r"(?:根据)?(?:以下|下面|下列)?\s*情境材料\s*[，,：:]?\s*回\s*[答签]\s*"
    r"(\d{1,3})\s*[—~\-－至]+\s*(\d{1,3})\s*题")
#: 内联题型标记：`（多选）`
INLINE_TYPE_RE = re.compile(r"[（(]\s*(单选|多选|不定项|判断)\s*[）)]")
#: 依赖图/表的措辞（用于给草稿打 `依赖图` 标记，提示管理员核对图片是否抽到）
FIGURE_HINT_RE = re.compile(r"如图|下图|上图|见表|下表|如图\d|图\s*\d")

CJK = "\u4e00-\u9fff"
#: 题型归一：卷面写法 → 内部值（与 `question_type` 的中文名对齐）
TYPE_ALIAS = {
    "单项选择": "单选", "多项选择": "多选", "不定项选择": "多选", "不定项": "多选",
    "单选": "单选", "多选": "多选", "判断": "判断",
}
#: 默认分值（卷面没写时）与默认难度（与既有真题一致：难度 3）
DEFAULT_SCORE = 1.0
DEFAULT_DIFFICULTY = 3


def clean_cn(text: str) -> str:
    """删掉 PDF 换行造成的"汉字之间空格"，但保留数字/英文两侧的空格。"""
    if not text:
        return ""
    s = re.sub(rf"(?<=[{CJK}，。；：、（）“”《》！？])\s+(?=[{CJK}，。；：、（）“”《》！？])", "", text)
    s = re.sub(r"(?<=[0-9])\s+(?=[年月日时分秒题页条款项分])", "", s)
    # `2023 年 5 月` → 年份说完紧跟月份，中间的空格也一起去掉（中文排版惯例）
    s = re.sub(r"(?<=[年月日])\s+(?=[0-9])", "", s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def _is_structural(line: str) -> bool:
    """是不是"结构性行"（题型标记 / 章标题 / 情境材料标题 / 下一个题号）。

    这些行**不能**被当成上一个选项的续行 —— 否则题型标题会被拼进选项文本里
    （实测：`2、…A．警告 B．拘役 …` 后面的 `二、多项选择题（每题 2 分）`
    会被接到 D 选项尾巴上）。
    """
    text = line or ""
    if MARK_RE.match(text) or SECTION_TYPE_RE.match(text):
        return True
    if SHARED_RE.search(text) or qno_of(text) is not None:
        return True
    # `一、…` / `（一）…` 这种章节序号行也视作结构行
    return bool(re.match(r"^\s*[（(]?\s*[一二三四五六七八九十]+\s*[）)]?\s*[、.]", text))


def _norm_type(raw: Optional[str], default: str = "单选") -> str:
    if not raw:
        return default
    for key, value in TYPE_ALIAS.items():
        if key in raw:
            return value
    return default


def qno_of(line: str) -> Optional[int]:
    """这一行是不是题号起始行？是就返回题号，否则 None。

    为什么要两套正则：`1.` 这种宽松规则会把「2023 年 5 月」当成第 2023 题，
    所以**必须**带分隔符或写成「第 N 题」；`QNO_RE` 只用于从题号行里"切掉"题号前缀。
    """
    m = QNO_STRICT_RE.match(line or "")
    if not m:
        return None
    raw = m.group(1) or m.group(2) or ""
    if not raw.isdigit():
        return None
    no = int(raw)
    return no if 1 <= no <= 999 else None


def _strip_qno(line: str) -> str:
    m = QNO_STRICT_RE.match(line or "")
    return line[m.end():] if m else (line or "")


def split_options(block: List[str]) -> tuple:
    """把一块内容拆成 (题干, {A..D})。

    - 选项可以一行多个（`A.甲 B.乙 C.丙 D.丁`），也可以每行一个；
    - 选项文本跨行时会**续接到当前选项**（PDF 经常把长选项折行）；
    - 第一个选项之前的行都算题干。
    """
    stem: List[str] = []
    options: Dict[str, str] = {"A": "", "B": "", "C": "", "D": ""}
    current: Optional[str] = None
    for raw in block:
        line = (raw or "").strip()
        if not line or MARK_RE.match(line):
            continue
        if _is_structural(line):
            # 结构性行终止"选项续行"状态；否则标题会被吸进上一个选项
            current = None
            continue
        hits = list(OPT_RE.finditer(line))
        if hits:
            head = line[:hits[0].start()].strip()
            if head:
                if current is None:
                    stem.append(head)
                else:
                    options[current] = f"{options[current]} {head}".strip()
            for i, m in enumerate(hits):
                key = m.group(1).translate(str.maketrans("ＡＢＣＤ", "ABCD"))
                if key not in options:       # 只认 A–D，E 及以后当作正文
                    current = None
                    continue
                end = hits[i + 1].start() if i + 1 < len(hits) else len(line)
                options[key] = line[m.end():end].strip()
                current = key
        elif current:
            options[current] = f"{options[current]} {line}".strip()
        else:
            stem.append(line)
    return clean_cn("".join(stem)), {k: clean_cn(v) for k, v in options.items()}


def repair_option_tags(items: List[dict], *, band_px: float = 40.0) -> List[dict]:
    """T3（2026-11-14）：把**丢了 `A-D` 标签**的选项行按缩进带补回标签。

    真机缺陷：第 3 题 C 行 OCR 输出成 `坚持以人民安全为宗旨`（标签被吃掉），
    `split_options` 把它当成 B 的续行 → C 空、B 变长。这里在拆题前修：

    1. 按题号把行分块；取本题**已有标签选项**的 `x` 中位数当缩进带（实测 264.3）；
    2. 块内无标签行若 `x` 落在缩进带 ±`band_px`（C 行 278.4，差 12–14px）→ 判为新选项；
    3. 按 `A→B→C→D` 里**缺的字母顺序**补标签（不猜内容，只补字母）。

    输入输出都是带 `x` 的行字典（`readers._layout_lines` 的产物）；没有坐标时不要调用。
    """
    starts = [i for i, it in enumerate(items) if qno_of(it.get("text") or "")]
    if not starts:
        starts = [0]                                # 一页里没有题号行（题目从上一页续过来）
    elif starts[0] != 0:
        starts.insert(0, 0)                         # 页首那段也要成块，否则开头几行永远修不到

    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(items)
        block = range(start, end)
        tagged = []
        for i in block:
            text = (items[i].get("text") or "").strip()
            m = OPT_RE.match(text)
            if m:
                tagged.append((items[i].get("x") or 0.0,
                               m.group(1).translate(str.maketrans("ＡＢＣＤ", "ABCD"))))
        if not tagged:
            continue
        band = median([x for x, _ in tagged])
        have = {letter for _, letter in tagged}
        missing = [c for c in "ABCD" if c not in have]
        if not missing:
            continue
        for i in block:
            if not missing:
                break
            text = (items[i].get("text") or "").strip()
            if not text or OPT_RE.match(text) or MARK_RE.match(text) or _is_structural(text):
                continue
            x = items[i].get("x")
            if x is None or abs(float(x) - band) > band_px:
                continue                            # 缩进不符：多半是题干续行，别动
            tag = missing.pop(0)
            items[i]["text"] = f"{tag}.{text}"
    return items


def _scan_type_state(lines: List[str]) -> Dict[int, str]:
    """扫一遍题型标记，产出「行号 → 从这行起默认题型」。"""
    marks: Dict[int, str] = {}
    for i, line in enumerate(lines):
        m = MARK_RE.match(line or "")
        if m:
            marks[i] = _norm_type(m.group(1))
            continue
        m = SECTION_TYPE_RE.match(line or "")
        if m:
            marks[i] = _norm_type(m.group(1))
    return marks


def _default_type_for(line_no: int, marks: Dict[int, str]) -> str:
    state = "单选"
    for at in sorted(marks):
        if at < line_no:
            state = marks[at]
        else:
            break
    return state


def split_questions(lines: List[str], *, default_type: str = "单选") -> List[dict]:
    """文本行 → 题目草稿列表。**不做任何 IO**，纯内存。"""
    norm = [(ln or "").replace("\u3000", " ").rstrip() for ln in lines]
    starts = [(i, no) for i, ln in enumerate(norm) for no in [qno_of(ln)] if no]
    if not starts:
        return []
    marks = _scan_type_state(norm)

    # 情境材料：从"回答 X~Y 题"那一行起，到下一个题号行为止的正文
    shared_spans: List[tuple] = []      # (起始行, 题号下限, 上限, 材料文本)
    for i, ln in enumerate(norm):
        m = SHARED_RE.search(ln or "")
        if not m:
            continue
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi < lo:
            lo, hi = hi, lo
        nxt = next((s for s, _ in starts if s > i), len(norm))
        body = " ".join(x.strip() for x in norm[i + 1:nxt]
                        if x.strip() and not qno_of(x))
        shared_spans.append((i, lo, hi, clean_cn(body)))

    items: List[dict] = []
    for idx, (line_no, no) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(norm)
        block = [norm[j] for j in range(line_no, end)]
        # 块里如果出现了下一段情境材料的标题（"根据以下情境材料，回答 4~5 题"），
        # 从那一行起的内容属于**下一组**，不属于本题 —— 截断，否则材料正文会被吸进上一题题干
        for k, ln in enumerate(block):
            if k > 0 and SHARED_RE.search(ln or ""):
                block = block[:k]
                break
        block[0] = _strip_qno(block[0])
        stem, options = split_options(block)

        joined = re.sub(r"\s+", "", " ".join(x.strip() for x in block))
        m = INLINE_TYPE_RE.search(joined)
        qtype = _norm_type(m.group(1)) if m else _default_type_for(line_no, marks)
        if not m and _default_type_for(line_no, marks) == "单选" and default_type != "单选":
            qtype = default_type

        shared, section = "", 0
        for s_idx, (sec_line, lo, hi, body) in enumerate(shared_spans, 1):
            if lo <= no <= hi and sec_line < line_no:
                shared, section = body, s_idx
                break

        flags: List[str] = []
        if not all(options[k] for k in "ABCD"):
            missing = [k for k in "ABCD" if not options[k]]
            flags.append(f"选项不全({'/'.join(missing)})")
        # T3（2026-11-14）：某选项比同题其它选项长 3 倍以上 → 可能把两行/两题粘在一起，
        # 给个标记让人一眼看到（不自动切，切错比不切更难查）
        lens = [len(options[k]) for k in "ABCD" if options[k]]
        if len(lens) >= 3:
            med = median(lens)
            if med and max(lens) > max(3 * med, 120):
                flags.append("选项可能粘连")
        if FIGURE_HINT_RE.search(stem + shared):
            flags.append("依赖图")
        if len(stem) < 4:
            flags.append("题干过短")

        items.append({
            "no": no,
            "type": qtype,
            "stem": stem,
            "options": options,
            "shared": shared,
            "section": section,
            "images": [],
            "flags": flags,
        })
    return items


def draft_warnings(items: List[dict], *, expected: Optional[int] = None) -> List[str]:
    """整卷级告警（给管理员一眼看质量，不要埋在 100 行里）。"""
    out: List[str] = []
    if not items:
        return ["没有拆出题目：请确认文件是「题本」（不是答案/解析），或这份排版需要人工处理"]
    numbers = [it["no"] for it in items]
    if len(numbers) != len(set(numbers)):
        dup = sorted({n for n in numbers if numbers.count(n) > 1})
        out.append(f"题号重复：{dup[:10]}{' 等' if len(dup) > 10 else ''}")
    top = max(numbers)
    missing = sorted(set(range(1, top + 1)) - set(numbers))
    if missing:
        out.append(f"题号缺号 {len(missing)} 个：{missing[:12]}{' 等' if len(missing) > 12 else ''}")
    if expected:
        if len(items) != expected:
            out.append(f"题量 {len(items)} 与预期 {expected} 不一致")
    bad = [it["no"] for it in items if any(f.startswith("选项不全") for f in it["flags"])]
    if bad:
        out.append(f"选项不全 {len(bad)} 题：{bad[:12]}{' 等' if len(bad) > 12 else ''}")
    figures = [it["no"] for it in items if "依赖图" in it["flags"]]
    if figures:
        out.append(f"依赖图/表 {len(figures)} 题（确认前请核对图片是否抽到）：{figures[:12]}")
    sections = {it["section"] for it in items if it["section"]}
    if sections:
        out.append(f"情境材料 {len(sections)} 组（材料挂在组内第一题上）")
    return out
