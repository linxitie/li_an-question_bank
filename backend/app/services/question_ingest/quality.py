# -*- coding: utf-8 -*-
"""题目质量评分与噪声过滤（v8 M4 / P5）。

两件事：
1. score_question() 六维质量分（满分 100），用于导入后「待修正」分流：
   题干完整性 25 / 选项完整性 25 / 答案有效性 20 / 解析 10 / 来源年份 10 / 图片可读性 10。
   低于 60 分入待修正清单——这类题多为「（待补充）」选项、缺解析、缺图。
2. is_noise_line() 过滤页眉页脚类噪声（页码、绝密★启用前、共X页）。
   噪声混进题干会污染检索与 AI 批改，但过滤必须保守：只删「整行就是噪声」的行，
   避免把正常题干里的数字删掉。
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

PASS_SCORE = 60

# 整行噪声：页码、"第3页 共8页"、密封线说明、装订线等
_NOISE_LINE = [
    re.compile(r"^\s*第\s*\d+\s*页\s*(共\s*\d+\s*页)?\s*$"),
    re.compile(r"^\s*共\s*\d+\s*页\s*$"),
    re.compile(r"^\s*[-—–]\s*\d+\s*[-—–]\s*$"),
    re.compile(r"^\s*[（(]?绝密[★☆*]?[）)]?\s*(启用前)?\s*$"),
    re.compile(r"^\s*密\s*封\s*线\s*$"),
    re.compile(r"^\s*装\s*订\s*线\s*$"),
    re.compile(r"^\s*试卷第\s*\d+\s*页.*$"),
]

_PLACEHOLDER = re.compile(r"^\s*[（(]?\s*(待补充|略|无|暂无)\s*[）)]?\s*$")


def is_noise_line(line: str) -> bool:
    """整行是否是排版噪声（页码/密封线/绝密）。"""
    if not line:
        return False
    s = line.strip()
    if not s:
        return True
    return any(p.match(s) for p in _NOISE_LINE)


def strip_noise_lines(text: str) -> str:
    """删除整行噪声，保留其余内容原样（含换行结构）。"""
    if not text:
        return text
    kept = [ln for ln in text.split("\n") if not is_noise_line(ln)]
    return "\n".join(kept).strip()


def _is_placeholder(value: Optional[str]) -> bool:
    return bool(value) and bool(_PLACEHOLDER.match(str(value)))


def score_question(q: Dict) -> Dict:
    """六维质量分。q 需含 question_content / options / answer / answer_analysis 等字段。"""
    flags: List[str] = []
    score = 0

    stem = str(q.get("question_content") or "").strip()
    if len(stem) >= 20:
        score += 25
    elif len(stem) >= 8:
        score += 15
        flags.append("题干偏短")
    elif stem:
        score += 5
        flags.append("题干过短")
    else:
        flags.append("题干为空")

    options = q.get("options") or []
    if isinstance(options, str):
        try:
            import json

            options = json.loads(options)
        except Exception:
            options = []
    opt_values = []
    for o in options if isinstance(options, list) else []:
        if isinstance(o, dict):
            opt_values.append(str(o.get("value") or ""))
        else:
            opt_values.append(str(o))
    filled = [v for v in opt_values if v.strip()]
    if len(filled) >= 4 and not any(_is_placeholder(v) for v in filled):
        score += 25
    elif len(filled) >= 4:
        score += 10
        flags.append("选项含待补充")
    elif filled:
        score += 8
        flags.append("选项不完整")
    else:
        # 主观题（申论）没有选项是正常的，不扣分也不加分
        if str(q.get("type_name") or "").find("主观") >= 0:
            score += 25
        else:
            score += 0

    answer = str(q.get("answer") or "").strip()
    if answer and not _is_placeholder(answer):
        score += 20
    elif answer:
        score += 10
        flags.append("答案为占位符")
    else:
        flags.append("缺答案")

    analysis = str(q.get("answer_analysis") or "").strip()
    if len(analysis) >= 15:
        score += 10
    elif analysis:
        score += 5
        flags.append("解析过短")
    else:
        flags.append("缺解析")

    if q.get("source") or q.get("year"):
        score += 10
    else:
        flags.append("缺来源年份")

    # 图片可读性：题干里引用了图片标记但没有落库图片 → 扣分并标记
    if "[IMAGE:" in stem:
        if q.get("image_count"):
            score += 10
        else:
            flags.append("配图缺失")
    else:
        score += 10

    return {"score": min(score, 100), "flags": flags, "pass": score >= PASS_SCORE}