# -*- coding: utf-8 -*-
"""答案文本 → 逐题答案（P4，2026-11-09）。

**为什么单独一个纯函数模块**：答案错一位，学生看到的解析就对不上，而且错得"很像对的"。
所以规则必须可单测、可回放；写库、对齐题型、冲突判定都在 `service.py`。

四层取答案（优先级从高到低，实测依据见
`docs/plans/答案上传_PDF与Excel多通道_方案_v1.md` §2）：

  L0 题号后独立字母   `1、A 本题考查…` / `1、A` / `1.A。`            2024 国考 99/100
  L1 显式标记         `【答案】A` / `正确答案为A` / `参考答案：A`      2019 北京 100、2016 江西 97
  L2 句尾结论         `故本题选A` / `答案选A`                        （兜底）
  L3 解析推断         `A项正确` 且不是 `A项错误`                     **只给建议，不自动填**
                                                                    （实测该层在 2024 卷会错 16 题）

两个实测坑（已各自有回归用例）：

  ① **幻影题号**：解析正文里的编号列表（`2.重点环节。1 控制场所…`、`3、创造警民协作新形式；4、…`）
     会被误当题号。同一题号出现多次时**保留第一次** —— 真实题号行总在解析之前。
  ② **列举被吞**：`87、A、B、C 项：正确…D 项：正确` 会被 L0 读成 `A`（真实答案是 ABCD）。
     L0 只认"独立成词"的字母（`^A$` / `^A[。.、,]` / `^A(本题|答案|故|解析)`），
     剩下的交给题型交叉校验在 service 里抓出来。
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

#: 题号行：`1、` / `1.` / `1．`
QNO_RE = re.compile(r"^\s*(\d{1,3})\s*[、.．]")
#: 2026-11-12（P1）：OCR 会把答案字母识别成小写（实测 `c项错误`），
#: 所以所有"答案字母"相关正则统一 re.IGNORECASE，取到的字母再由
#: `normalize_letters` 统一大写 —— 否则 `C项正确 + c项错误` 会被算成"建议 C"。
CI = re.IGNORECASE
#: L0：题号后独立成词的字母（不能是 `A项…` 这种解析正文）
L0_PATTERNS = (
    re.compile(r"^([A-D]{1,4})$", CI),
    re.compile(r"^([A-D]{1,4})[。.、,，；;：:]", CI),
    re.compile(r"^([A-D]{1,4})(?:本题|答案|故|解析)", CI),
)
#: 列举式解析：`A、B、C 项：正确` / `A、B项` —— 这不是答案，是逐项评议
ENUM_HEAD_RE = re.compile(r"^[A-D][、.．,，]\s*[A-D]", CI)
#: L1：显式答案标记
L1_RE = re.compile(r"(?:【\s*答案\s*】|正确答案|参考答案|答案)\s*[:：是为]?\s*([A-D]{1,4})", CI)
#: L2：句尾结论
L2_RE = re.compile(r"(?:故\s*)?(?:正确)?答案(?:应)?(?:为|是|选)\s*[:：]?\s*([A-D]{1,4})", CI)
L2B_RE = re.compile(r"故\s*(?:本题)?\s*选\s*[:：]?\s*([A-D]{1,4})", CI)
#: L3：解析推断（允许 `项：正确` 这种带全角冒号的写法，实测 2017 江苏就是这种）
#: 支持"成串"写法：`A、B、C 项：正确` → ABC（单个 `D 项正确` 也吃得住）
L3_OK_RE = re.compile(r"((?:[A-D]\s*[、,，]\s*)*[A-D])\s*项?\s*[:：]?\s*正确", CI)
L3_NO_RE = re.compile(r"([A-D]{1,4})\s*项?\s*[:：]?\s*错误", CI)
#: 纯文本 `1 A` / `1、AB` / `1.AB`（Excel/粘贴通道）
PLAIN_RE = re.compile(r"^\s*(\d{1,3})\s*[、.．,，]?\s*([A-D]{1,4})\s*$", CI)

CJK = "\u4e00-\u9fff"
#: 答案字母合法集合（题库只有四选一）
VALID_LETTERS = set("ABCD")


def clean_cn(text: str) -> str:
    """删掉 PDF 换行造成的汉字间空格（与 `paper_ingest.splitter.clean_cn` 同口径）。"""
    if not text:
        return ""
    s = re.sub(rf"(?<=[{CJK}，。；：、（）“”《》！？])\s+(?=[{CJK}，。；：、（）“”《！？])", "", text)
    s = re.sub(r"(?<=[0-9])\s+(?=[年月日时分秒题页条款项分])", "", s)
    s = re.sub(r"(?<=[年月日])\s+(?=[0-9])", "", s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def normalize_letters(raw: Optional[str]) -> str:
    """答案字母归一：去空白/标点、大写、去重、按 A–D 排序；非法返回空串。"""
    if not raw:
        return ""
    letters = [c for c in str(raw).upper() if c in VALID_LETTERS]
    return "".join(sorted(set(letters)))


def split_blocks(lines: List[str]) -> Dict[int, tuple]:
    """按题号切块，返回 `{题号: (整块文本, 题号行剩余部分)}`。

    **同一题号只保留第一次**（幻影题号，见模块文档①）。
    """
    raw = [(i, int(m.group(1))) for i, ln in enumerate(lines) for m in [QNO_RE.match(ln)] if m]
    seen = set()
    starts = []
    for i, no in raw:
        if no in seen:
            continue
        seen.add(no)
        starts.append((i, no))
    blocks: Dict[int, tuple] = {}
    for k, (i, no) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        body = [lines[j] for j in range(i, end)]
        head = re.sub(r"\s+", "", QNO_RE.sub("", body[0]))
        text = clean_cn(" ".join((x or "").strip() for x in body if (x or "").strip()))
        blocks[no] = (text, head)
    return blocks


def extract_one(text: str, head: str = "") -> dict:
    """单题：返回 `{answer, tier, suggestion, evidence}`。

    `answer` 为空 = 没有可信答案（可能只有 `suggestion`，也可能要人工补）。
    """
    flat = re.sub(r"\s+", "", text or "")
    head_raw = re.sub(r"\s+", "", head or "")
    # 列举式开头（`A、B、C 项：正确…`）不是答案 —— 实测 2017 江苏 #87 就是这样把 ABCD 读成 A 的
    enumeration = bool(ENUM_HEAD_RE.match(head_raw))
    if not enumeration:
        for rx in L0_PATTERNS:
            m = rx.match(head_raw)
            if m:
                letters = normalize_letters(m.group(1))
                if letters:
                    return {"answer": letters, "tier": "L0", "suggestion": "",
                            "evidence": f"题号后直给 {m.group(1)}"}
    m = L1_RE.search(flat)
    if m:
        letters = normalize_letters(m.group(1))
        if letters:
            return {"answer": letters, "tier": "L1", "suggestion": "",
                    "evidence": m.group(0)[:24]}
    m = L2_RE.search(flat) or L2B_RE.search(flat)
    if m:
        letters = normalize_letters(m.group(1))
        if letters:
            return {"answer": letters, "tier": "L2", "suggestion": "",
                    "evidence": m.group(0)[:24]}
    # L3 只给"建议"，绝不当作答案（实测会错）
    cand = set()
    for m in L3_OK_RE.finditer(flat):
        cand.update(normalize_letters(m.group(1)))
    wrong = set()
    for grp in L3_NO_RE.findall(flat):
        # 归一后再比：OCR 会输出 `c项错误`，直接拿原串会把大写 C 漏掉
        wrong.update(normalize_letters(grp))
    cand = {c for c in cand if c not in wrong}
    suggestion = "".join(sorted(cand)) if 0 < len(cand) <= 4 else ""
    return {"answer": "", "tier": "L3" if suggestion else "L4",
            "suggestion": suggestion,
            "evidence": ("推断：" + "/".join(sorted(cand)) + "项正确") if suggestion else ""}


def plain_pairs(text: str) -> Dict[int, str]:
    """纯文本/Excel 通道：`1 A` / `1、AB` 一行一题 → {题号: 答案}。"""
    out: Dict[int, str] = {}
    for line in (text or "").splitlines():
        m = PLAIN_RE.match(line)
        if not m:
            continue
        no = int(m.group(1))
        letters = normalize_letters(m.group(2))
        if letters:
            out[no] = letters
    return out


def parse_text(text: str) -> List[dict]:
    """答案解析（PDF/docx 的文本流）→ 逐题草稿。

    返回项：`{no, answer, tier, suggestion, analysis, flags}`。
    `analysis` = 整块文本（含"本题考查…"），去掉题号与开头的答案字母，供入库到 `answer_analysis`。
    """
    lines = (text or "").splitlines()
    items: List[dict] = []
    for no, (block, head) in sorted(split_blocks(lines).items()):
        info = extract_one(block, head)
        analysis = block
        # 去掉题号行开头那个"答案字母"（`1、A 本题考查…` → `本题考查…`）
        analysis = re.sub(r"^\s*(?:第\s*)?\d{1,3}\s*[、.．]\s*", "", analysis)
        if re.match(r"^[A-D]{1,4}(?![A-Za-z\u4e00-\u9fff])", analysis, CI):
            analysis = analysis[len(re.match(r"^[A-D]{1,4}", analysis, CI).group(0)):].strip()
        flags: List[str] = []
        if not info["answer"] and info["suggestion"]:
            flags.append("仅推断建议")
        if not info["answer"] and not info["suggestion"]:
            flags.append("未识别答案")
        items.append({
            "no": no,
            "answer": info["answer"],
            "tier": info["tier"],
            "suggestion": info["suggestion"],
            "evidence": info["evidence"],
            "analysis": analysis[:4000],
            "flags": flags,
        })
    return items


def parse_plain(text: str) -> List[dict]:
    """纯文本/Excel 通道 → 逐题草稿（没有解析正文）。"""
    out = []
    for no, letters in sorted(plain_pairs(text).items()):
        out.append({"no": no, "answer": letters, "tier": "P", "suggestion": "",
                    "evidence": "一行一题", "analysis": "", "flags": []})
    return out
