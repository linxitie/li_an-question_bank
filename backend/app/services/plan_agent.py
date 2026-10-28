"""
模块4 v2 - PlanAgent 规划智能体（推理服务）

职责：基于用户画像做多维度认知推理，输出：
- 可用学时预算（剩余天数 × 每日时长）
- 科目权重建议（弱项加权 / 强项减权）
- 学习节奏建议（水平自评映射）
- 注入生成 prompt 的增强文本

与 LLM 生成的关系：PlanAgent 做"确定性推理"（规则可复算），
LLM 负责把推理结果转化为具体可执行的阶段/任务（保持生成质量与可审计性）。
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 水平 → 节奏建议
LEVEL_PACE = {
    "零基础": "先打基础：前段以教材/知识点系统梳理为主，中段进入分题型练习，冲刺段模考。",
    "入门": "系统强化：教材快速过一遍后立即进入分题型刷题，及时归因错题，冲刺段全真模考。",
    "有基础": "强化+模考：直接分题型限时训练，每周 1-2 次套卷模考，重点补薄弱环节。",
    "冲刺阶段": "模考为主：全真套卷高频模考，错题重刷与考点复盘优先，减少新知识摄入。",
}

# 科目基础权重（公安联考三科基准）
BASE_WEIGHTS = {"行测": 0.4, "公专": 0.35, "申论": 0.25}


def _load_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def compute_weights(weaknesses: List[str], strengths: List[str]) -> Dict[str, float]:
    """科目权重：弱项 +0.08，强项 -0.05，其余维持基准；保证和=1"""
    weights = dict(BASE_WEIGHTS)
    for s in weaknesses:
        if s in weights:
            weights[s] = min(weights[s] + 0.08, 0.6)
    for s in strengths:
        if s in weights:
            weights[s] = max(weights[s] - 0.05, 0.15)
    total = sum(weights.values())
    return {k: round(v / total, 3) for k, v in weights.items()}


def reason(profile: dict, days_left: int) -> dict:
    """核心推理：输入画像 dict（数据库行转 dict）+ 剩余天数，输出推理结论"""
    daily_hours = profile.get("daily_hours") or 4.0
    weaknesses = profile.get("subject_weaknesses") or []
    strengths = profile.get("subject_strengths") or []
    level = profile.get("self_level") or "有基础"
    target_score = profile.get("target_score") or ""

    total_hours = int(days_left * daily_hours)
    weights = compute_weights(weaknesses, strengths)
    pace = LEVEL_PACE.get(level, LEVEL_PACE["有基础"])

    # 可审计的推理说明
    reasoning = {
        "total_hours": total_hours,
        "daily_hours": daily_hours,
        "days_left": days_left,
        "level": level,
        "subject_weights": weights,
        "weaknesses": weaknesses,
        "strengths": strengths,
        "pace_advice": pace,
        "target_score": target_score,
    }
    return reasoning


def build_prompt_extra(reasoning: dict) -> str:
    """把推理结论格式化为注入生成 prompt 的增强文本"""
    w = reasoning["subject_weights"]
    weights_txt = "、".join(f"{k} {int(v * 100)}%" for k, v in w.items())
    lines = [
        "【画像推理补充（PlanAgent 计算，请严格参考）】",
        f"可用总学时约 {reasoning['total_hours']} 小时（剩余 {reasoning['days_left']} 天 × 每天 {reasoning['daily_hours']} 小时）",
        f"建议科目学时占比：{weights_txt}",
        f"节奏建议：{reasoning['pace_advice']}",
    ]
    if reasoning.get("weaknesses"):
        lines.append(f"薄弱科目：{'、'.join(reasoning['weaknesses'])}——安排更多针对性任务")
    if reasoning.get("target_score"):
        lines.append(f"目标分数：{reasoning['target_score']}——阶段任务量应匹配目标梯度")
    return "\n".join(lines)


def profile_from_row(row) -> Optional[dict]:
    """把 UserProfile ORM 行转为推理输入 dict（无行返回 None）"""
    if not row:
        return None
    return {
        "grade": row.grade,
        "target_score": row.target_score,
        "self_level": row.self_level,
        "daily_hours": row.daily_hours,
        "subject_strengths": _load_list(row.subject_strengths),
        "subject_weaknesses": _load_list(row.subject_weaknesses),
        "exam_date": row.exam_date,
        "target_region": row.target_region,
        "target_post": row.target_post,
    }
