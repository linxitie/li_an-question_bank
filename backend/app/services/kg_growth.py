"""自生长知识图谱（2026-11-05 M3）。

核心闭环（对应设计文档 §4）：
1. 采集行为（答题对错/错题/笔记编辑）→ 更新用户级节点掌握度与生长热度；
2. 边演化：同一时间窗内先后命中的两个知识点之间新增/加权边；
3. 采样：按 `heat` 与"边权重变化率"构造 softmax 非均匀分布，抽节点生成个性化周任务；
4. 奖励：`contribution = heat × (1 - mastery)`，生长快但掌握度低的节点奖励加成。

为什么用户级而不是复用静态 kg_edge：
静态图谱是"教材的结构"，这里是"这个人的图谱"。同一知识点，A 已掌握、B 刚踩坑，
两者的任务价值完全不同。
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import (
    KgUserEdge,
    KgUserEvent,
    KgUserNodeState,
    KnowledgePoint,
    Task,
)

logger = logging.getLogger(__name__)

# 事件权重：错题 > 编辑笔记 > 答对（设计文档 §4.1 权 2）
EVENT_WEIGHTS = {
    "answer_wrong": 1.0,
    "note_edit": 0.8,
    "answer_correct": 0.3,
}
# 掌握度 EMA 系数与新事件增量
MASTERY_ALPHA = 0.25
HEAT_ON_EVENT = 0.6
HEAT_DECAY_PER_DAY = 0.92
EDGE_DECAY_PER_DAY = 0.98
# 采样温度与系数
DEFAULT_TEMPERATURE = 0.8
DEFAULT_ALPHA_HEAT = 1.0
DEFAULT_BETA_GROWTH = 1.2
# 个性化任务的奖励加成上限（设计文档 §4.1 权 4）
MAX_REWARD_BONUS = 0.30


def _point_id_by_name(db: Session, name: str) -> Optional[int]:
    """把答题记录里的知识点文本映射到 knowledge_point（设计文档 A6：需数据清洗）。"""
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    row = db.query(KnowledgePoint).filter(KnowledgePoint.point_name == name).first()
    if row:
        return row.point_id
    # 容错：包含匹配（如"行政法-行政处罚" → "行政处罚"）
    row = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.point_name.contains(name))
        .first()
    )
    return row.point_id if row else None


def record_event(
    db: Session,
    user_id: int,
    point_id: int,
    event_type: str,
    *,
    ref_id: Optional[int] = None,
) -> KgUserNodeState:
    """记录一次行为事件并更新节点状态（掌握度/热度）。"""
    if event_type not in EVENT_WEIGHTS:
        raise ValueError(f"未知事件类型: {event_type}")

    weight = EVENT_WEIGHTS[event_type]
    now = datetime.now()

    node = db.query(KgUserNodeState).filter(
        KgUserNodeState.user_id == user_id,
        KgUserNodeState.point_id == point_id,
    ).first()
    if not node:
        node = KgUserNodeState(user_id=user_id, point_id=point_id, mastery=0.0, heat=0.0)
        db.add(node)
        db.flush()

    # 掌握度用 EMA：答对拉高、答错拉低
    target = 1.0 if event_type == "answer_correct" else 0.0
    if event_type == "note_edit":
        target = node.mastery  # 编辑笔记不直接改掌握度，只加热度
    node.mastery = round((1 - MASTERY_ALPHA) * (node.mastery or 0.0) + MASTERY_ALPHA * target, 4)

    # 热度：每次事件加热，长期不练自然冷却（decay 由定时任务处理）
    node.heat = round((node.heat or 0.0) + HEAT_ON_EVENT * weight, 4)
    if event_type.startswith("answer_"):
        node.attempt_count = (node.attempt_count or 0) + 1
        if event_type == "answer_correct":
            node.correct_count = (node.correct_count or 0) + 1
    node.last_event_at = now

    db.add(
        KgUserEvent(
            user_id=user_id,
            point_id=point_id,
            event_type=event_type,
            weight=weight,
            ref_id=ref_id,
        )
    )

    # 边演化：与最近 30 分钟内该用户触达的其它节点建立/加权 co_occur 边
    window_start = now - timedelta(minutes=30)
    recent = (
        db.query(KgUserEvent.point_id)
        .filter(
            KgUserEvent.user_id == user_id,
            KgUserEvent.created_at >= window_start,
            KgUserEvent.point_id != point_id,
        )
        .distinct()
        .all()
    )
    for (other,) in recent:
        _upsert_edge(db, user_id, point_id, other, weight)
        _upsert_edge(db, user_id, other, point_id, weight)

    db.flush()
    return node


def _upsert_edge(db: Session, user_id: int, src: int, dst: int, delta: float) -> KgUserEdge:
    edge = db.query(KgUserEdge).filter(
        KgUserEdge.user_id == user_id,
        KgUserEdge.src_point == src,
        KgUserEdge.dst_point == dst,
        KgUserEdge.rel_type == "co_occur",
    ).first()
    if not edge:
        edge = KgUserEdge(
            user_id=user_id, src_point=src, dst_point=dst, rel_type="co_occur",
            weight=1.0 + delta, heat=delta,
        )
        db.add(edge)
    else:
        edge.weight = round((edge.weight or 1.0) * 0.9 + delta, 4)
        edge.heat = round((edge.heat or 0.0) + delta, 4)
    db.flush()
    return edge


def record_answer(
    db: Session,
    user_id: int,
    knowledge_point_name: Optional[str],
    is_correct: bool,
    *,
    ref_id: Optional[int] = None,
) -> Optional[KgUserNodeState]:
    """答题入口：知识点文本 → point_id → 事件。映射不到就跳过（不阻塞答题）。"""
    point_id = _point_id_by_name(db, knowledge_point_name or "")
    if not point_id:
        return None
    return record_event(
        db,
        user_id,
        point_id,
        "answer_correct" if is_correct else "answer_wrong",
        ref_id=ref_id,
    )


def decay(db: Session, user_id: Optional[int] = None) -> dict:
    """每日衰减：热度与边权重随时间回落（由调度调用）。"""
    q = db.query(KgUserNodeState)
    if user_id:
        q = q.filter(KgUserNodeState.user_id == user_id)
    nodes = q.all()
    for node in nodes:
        node.heat = round((node.heat or 0.0) * HEAT_DECAY_PER_DAY, 4)

    eq = db.query(KgUserEdge)
    if user_id:
        eq = eq.filter(KgUserEdge.user_id == user_id)
    edges = eq.all()
    for edge in edges:
        edge.weight = round(max(0.1, (edge.weight or 1.0) * EDGE_DECAY_PER_DAY), 4)
        edge.heat = round((edge.heat or 0.0) * EDGE_DECAY_PER_DAY, 4)

    db.commit()
    return {"nodes": len(nodes), "edges": len(edges)}


def growth_rate(db: Session, user_id: int, point_id: int, days: int = 7) -> float:
    """近 N 天的"生长速度"：该节点事件权重之和 / N（越新越重要）。"""
    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(KgUserEvent.point_id, KgUserEvent.weight)
        .filter(
            KgUserEvent.user_id == user_id,
            KgUserEvent.point_id == point_id,
            KgUserEvent.created_at >= since,
        )
        .all()
    )
    return round(sum(w for _, w in rows) / max(1, days), 4) if rows else 0.0


def node_score(db: Session, node: KgUserNodeState, days: int = 7) -> float:
    """采样打分：生长热度 + 边权重变化率（越"正在生长"分越高）。"""
    rate = growth_rate(db, node.user_id, node.point_id, days)
    return DEFAULT_ALPHA_HEAT * (node.heat or 0.0) + DEFAULT_BETA_GROWTH * rate


def contribution(node: KgUserNodeState) -> float:
    """生长贡献度 = 热度 × (1 - 掌握度)：长得快、还没掌握 → 贡献大。"""
    return round((node.heat or 0.0) * (1.0 - min(1.0, node.mastery or 0.0)), 4)


def sample_nodes(
    db: Session,
    user_id: int,
    n: int = 2,
    *,
    temperature: Optional[float] = None,
    exclude_mastered: float = 0.85,
    use_habits: bool = True,
) -> list[dict]:
    """按 softmax((α·heat + β·growth)/T) 抽样，返回概率最高的 n 个节点。

    与均匀随机的区别：这里抽的是"正在快速生长但还没掌握"的节点（设计文档 §4.1 权 3）。

    M3.5：温度 T 不再写死，而是由做题习惯画像调制——
    习惯稳定 → T 低（聚焦已知薄弱点）；习惯波动大 → T 高（多探索）；
    同时命中偏好学科的节点获得轻微加分。
    """
    from . import kg_habits

    profile = kg_habits.build_habit_profile(db, user_id) if use_habits else None
    if temperature is None:
        temperature = profile["temperature"] if profile else DEFAULT_TEMPERATURE

    nodes = db.query(KgUserNodeState).filter(KgUserNodeState.user_id == user_id).all()
    candidates = [x for x in nodes if (x.mastery or 0.0) < exclude_mastered and (x.heat or 0.0) > 0]
    if not candidates:
        return []

    point_rows = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.point_id.in_([x.point_id for x in candidates]))
        .all()
    )
    points = {p.point_id: p for p in point_rows}

    scores = []
    for node in candidates:
        base = node_score(db, node)
        if profile:
            point = points.get(node.point_id)
            if point is not None:
                base += kg_habits.prefer_subject_boost(
                    db, user_id, profile, point.subject_id or 0
                )
        scores.append(base)

    peak = max(scores)
    exp = [math.exp((s - peak) / max(0.05, temperature)) for s in scores]  # 数值稳定
    total = sum(exp) or 1.0
    probs = [e / total for e in exp]

    ranked = sorted(
        zip(candidates, probs, scores),
        key=lambda item: item[1],
        reverse=True,
    )[:n]

    return [
        {
            "point_id": node.point_id,
            "point_name": points[node.point_id].point_name if node.point_id in points else f"知识点#{node.point_id}",
            "mastery": round(node.mastery or 0.0, 4),
            "heat": round(node.heat or 0.0, 4),
            "score": round(score, 4),
            "probability": round(prob, 4),
            "contribution": contribution(node),
        }
        for node, prob, score in ranked
    ]


def reward_bonus(node: KgUserNodeState) -> float:
    """个性化任务奖励加成：贡献度越高加成越大，封顶 30%。"""
    return round(min(MAX_REWARD_BONUS, contribution(node)), 4)


def ensure_personalized_tasks(db: Session, user_id: int, week: Optional[str] = None, n: int = 2) -> list:
    """为本人生成本周的个性化周任务（幂等：按 week+user+point 唯一 code 复用）。

    生成的任务 `personalized_for=user_id`、`metric=kg_node_questions`、`metric_param=point_id`，
    只在本人 overview 中出现，不影响全站任务池。
    """
    from .weekly_tasks import week_key

    week = week or week_key()
    sampled = sample_nodes(db, user_id, n=n)
    created = []
    for item in sampled:
        point_id = item["point_id"]
        code = f"kg_{week}_{user_id}_{point_id}"
        task = db.query(Task).filter(Task.task_code == code).first()
        node = db.query(KgUserNodeState).filter(
            KgUserNodeState.user_id == user_id,
            KgUserNodeState.point_id == point_id,
        ).first()
        bonus = reward_bonus(node) if node else 0.0
        base = int(round(150 * (1 + bonus)))  # 基础 150 币，叠加贡献度加成
        if not task:
            task = Task(
                task_code=code,
                t_type="weekly",
                title=f"本周在「{item['point_name']}」完成 30 道题",
                description=f"系统按你的薄弱点生成（贡献度 {item['contribution']}）",
                metric="kg_node_questions",
                mode="calc",
                threshold=30,
                reward_coins=base,
                reward_growth=0,
                difficulty_factor=1.2,
                scarcity_factor=1.0,
                category="A",
                pin_eligible=0,
                metric_param=point_id,
                personalized_for=user_id,
                sort_order=500 + len(created),
                enabled=1,
            )
            db.add(task)
        created.append(task)
    db.commit()
    return created
