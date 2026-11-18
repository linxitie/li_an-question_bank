# -*- coding: utf-8 -*-
"""科目自动识别（S2，2026-11-17；口径 Q-57 选 c）

背景：卡片/讲义/文章批量导入时整批只有一个「科目」下拉，xlsx 的「科目」列没被逐行读取，
于是申论内容被落成公专，且导入后不可修改。本模块给一个**纯函数**识别器。

判定口径（c）：
  1) 标题命中即认定该科目（标题是人工摘要，可信度高）；
     若多个科目都在标题命中 → 取标题得分最高；仍并列则 None；
  2) 仅正文命中（标题无特征词）→ 要求最高分 ≥ MIN_BODY_SCORE 且领先次高 ≥ 1；
  3) 都拿不准 → None（调用方标「待确认」，绝不兜底成公专）。
"""
from typing import Optional, Tuple

SUBJECTS = ("shenlun", "xingce", "gongzhuan")

KEYWORDS = {
    "shenlun": (
        "申论", "分论点", "概括", "对策", "公文", "贯彻执行", "综合分析",
        "归纳概括", "提出对策", "申发论述", "倡议书", "讲话稿", "材料作文",
    ),
    "xingce": (
        "行测", "图形推理", "数量关系", "资料分析", "判断推理", "常识判断",
        "言语理解", "定义判断", "类比推理", "逻辑判断", "类比", "百分点",
    ),
    "gongzhuan": (
        "公专", "公安专业", "人民警察", "治安管理处罚", "行政处罚", "行政复议",
        "刑事诉讼法", "警械", "执法", "公安机关", "治安", "刑事强制措施",
    ),
}

TITLE_WEIGHT = 2
BODY_WEIGHT = 1
MIN_BODY_SCORE = 2
MIN_MARGIN = 1


def _hits(text: str, words: Tuple[str, ...]) -> int:
    t = (text or "").lower()
    return sum(1 for w in words if w.lower() in t)


def score_text(title: str, body: str = "") -> dict:
    """返回各科目得分（标题权重 2、正文权重 1），便于测试与调试。"""
    out = {}
    for subject, words in KEYWORDS.items():
        out[subject] = _hits(title, words) * TITLE_WEIGHT + _hits(body, words) * BODY_WEIGHT
    return out


def title_scores(title: str) -> dict:
    """只看标题的得分（判定优先级用）。"""
    return {s: _hits(title, w) for s, w in KEYWORDS.items()}


def detect_subject(title: str, body: str = "") -> Optional[str]:
    """识别科目；不确定返回 None（调用方标「待确认」，不猜、不兜底）。"""
    t_scores = title_scores(title)
    t_rank = sorted(t_scores.items(), key=lambda kv: kv[1], reverse=True)
    if t_rank[0][1] > 0:
        # 标题命中：取标题分最高者；并列则放弃
        if len(t_rank) > 1 and t_rank[0][1] == t_rank[1][1]:
            return None
        return t_rank[0][0]

    scores = score_text(title, body)
    rank = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_name, top_score = rank[0]
    second = rank[1][1] if len(rank) > 1 else 0
    if top_score < MIN_BODY_SCORE:
        return None
    if top_score - second < MIN_MARGIN:
        return None
    return top_name
# 词表扩容（Q-61 c + Q-62：用真实未识别语料的高频词，人工筛后入表）
# 追加在文件末尾，靠模块级 dict 原地扩展生效（保持原有判定逻辑不变）。
KEYWORDS["gongzhuan"] = KEYWORDS["gongzhuan"] + (
    # 公安程序法（卡片里最高频的一类）
    "传唤", "口头传唤", "拘传", "继续盘问", "盘问", "询问查证", "询问",
    "拘留审查", "取保候审", "监视居住", "逮捕", "传讯", "听证",
    "公安机关办理", "办理行政案件", "办理刑事案件", "办案期限",
    # 法律常识/政治理论（题干最高频的一类）
    "公安基础知识", "刑法", "民法", "民法总则", "反恐怖主义法", "宪法",
    "中国特色社会主义", "习近平", "三个代表", "新发展理念", "马克思主义",
    "依法治国", "法治", "党的", "人民军队", "国家治理",
)
KEYWORDS["xingce"] = KEYWORDS["xingce"] + (
    "首数法", "特征数字法", "有效数字", "截位直除", "增长率", "比重",
    "平均数", "语句排序", "语句表达", "逻辑填空", "片段阅读", "排列组合",
)
KEYWORDS["shenlun"] = KEYWORDS["shenlun"] + (
    "应用文", "议论文", "文章写作", "答题要点", "字数要求", "作答要求",
    "材料主旨", "提纲", "调研报告", "工作总结",
)
