# -*- coding: utf-8 -*-
"""徽章服务：档位判定、累计积分、形状映射。

档位阈值（用户批复）：<200 黑铁 ｜ 200–399 青铜 ｜ 400–599 白银 ｜ 600–799 黄金 ｜ ≥800 钻石
钻石不封顶：≥800 后积分继续累积，仅用于星级/排名等展示。
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import CoinRecord

# (下界, code, 中文名)
TIERS: List[tuple] = [
    (0, "iron", "黑铁"),
    (200, "bronze", "青铜"),
    (400, "silver", "白银"),
    (600, "gold", "黄金"),
    (800, "diamond", "钻石"),
]

# 成就类别 → 徽章形状（成就统一盾牌；称号用缎带；科目/稀有预留给后续阶段）
CATEGORY_SHAPE: Dict[str, str] = {
    "数量": "shield",
    "坚持": "shield",
    "正确率": "shield",
    "综合": "shield",
    "社交": "ribbon",
    "错题": "shield",
    "成长": "ribbon",
}


def tier_of(score: int) -> Dict[str, Any]:
    """按累计积分返回档位。score 为负按 0 处理。"""
    s = max(0, int(score or 0))
    idx = 0
    for i, (low, _code, _label) in enumerate(TIERS):
        if s >= low:
            idx = i
    low, code, label = TIERS[idx]
    nxt = TIERS[idx + 1] if idx + 1 < len(TIERS) else None
    return {
        "index": idx,
        "code": code,
        "label": label,
        "threshold": low,
        "next_label": nxt[2] if nxt else None,
        "next_threshold": nxt[0] if nxt else None,
        "maxed": nxt is None,
    }


def progress_to_next(score: int) -> Dict[str, Any]:
    """当前档位 → 下一档的进度（钻石档返回 maxed=True，积分继续累积）。"""
    s = max(0, int(score or 0))
    info = tier_of(s)
    if info["maxed"]:
        return {"percent": 100.0, "need": 0, "maxed": True, "score": s}
    span = info["next_threshold"] - info["threshold"]
    done = s - info["threshold"]
    pct = round(min(100.0, max(0.0, done / span * 100)), 1) if span else 100.0
    return {
        "percent": pct,
        "need": max(0, info["next_threshold"] - s),
        "maxed": False,
        "score": s,
        "span": span,
        "done": done,
    }


def total_score(db: Session, user_id: int) -> int:
    """累计积分 = 正向流水之和（不扣减消费）。"""
    got = (db.query(func.coalesce(func.sum(CoinRecord.coin_change), 0))
           .filter(CoinRecord.user_id == user_id,
                   CoinRecord.coin_change > 0)
           .scalar() or 0)
    return int(got)


def shape_of(category: Optional[str]) -> str:
    return CATEGORY_SHAPE.get((category or "").strip(), "shield")


def tier_label_by_index(idx: Optional[int]) -> Optional[str]:
    """把快照档位索引转成中文；非法/未记录返回 None。"""
    if idx is None:
        return None
    try:
        i = int(idx)
    except (TypeError, ValueError):
        return None
    if 0 <= i < len(TIERS):
        return TIERS[i][2]
    return None
