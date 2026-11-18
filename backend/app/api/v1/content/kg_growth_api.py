"""自生长知识图谱 API（2026-11-05 M3）。

- GET  /api/knowledge/kg/nodes/mine     我的节点状态（掌握度/热度/贡献度）
- GET  /api/knowledge/kg/edges/mine     我的边（权重/热度）
- GET  /api/knowledge/kg/sample         本周个性化任务候选（非均匀采样结果）
- POST /api/knowledge/kg/generate       生成本周个性化任务（幂等）
- POST /api/knowledge/kg/decay          热度衰减（调度用）
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_admin, get_current_user
from ....models.models import (
    KgEdge,
    KgNodeLayout,
    KgUserEdge,
    KgUserNodeState,
    KnowledgePoint,
    SysUser,
)
from ....services import kg_growth
from ....services import kg_habits

router = APIRouter(prefix="/api/knowledge/kg", tags=["自生长知识图谱"])
logger = logging.getLogger(__name__)


@router.get("/nodes/mine", summary="我的知识节点状态")
async def my_nodes(
    limit: int = Query(50, ge=1, le=200),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(KgUserNodeState)
        .filter(KgUserNodeState.user_id == current_user.user_id)
        .order_by(KgUserNodeState.heat.desc())
        .limit(limit)
        .all()
    )
    names = {
        p.point_id: p.point_name
        for p in db.query(KnowledgePoint)
        .filter(KnowledgePoint.point_id.in_([r.point_id for r in rows]))
        .all()
    }
    return {
        "total": len(rows),
        "items": [
            {
                "point_id": r.point_id,
                "point_name": names.get(r.point_id, f"知识点#{r.point_id}"),
                "mastery": round(r.mastery or 0.0, 4),
                "heat": round(r.heat or 0.0, 4),
                "attempt_count": r.attempt_count,
                "correct_count": r.correct_count,
                "contribution": kg_growth.contribution(r),
                "last_event_at": r.last_event_at.isoformat() if r.last_event_at else None,
            }
            for r in rows
        ],
    }


@router.get("/edges/mine", summary="我的知识边（自生长权重）")
async def my_edges(
    limit: int = Query(50, ge=1, le=200),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(KgUserEdge)
        .filter(KgUserEdge.user_id == current_user.user_id)
        .order_by(KgUserEdge.weight.desc())
        .limit(limit)
        .all()
    )
    ids = {r.src_point for r in rows} | {r.dst_point for r in rows}
    names = {
        p.point_id: p.point_name
        for p in db.query(KnowledgePoint).filter(KnowledgePoint.point_id.in_(ids)).all()
    }
    return {
        "total": len(rows),
        "items": [
            {
                "src_point": r.src_point,
                "src_name": names.get(r.src_point, f"#{r.src_point}"),
                "dst_point": r.dst_point,
                "dst_name": names.get(r.dst_point, f"#{r.dst_point}"),
                "rel_type": r.rel_type,
                "weight": round(r.weight or 0.0, 4),
                "heat": round(r.heat or 0.0, 4),
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.get("/sample", summary="本周个性化任务候选（非均匀采样）")
async def sample(
    n: int = Query(3, ge=1, le=10),
    temperature: Optional[float] = Query(None, gt=0.05, le=5, description="留空则按做题习惯自适应"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = kg_growth.sample_nodes(db, current_user.user_id, n=n, temperature=temperature)
    profile = kg_habits.build_habit_profile(db, current_user.user_id)
    return {
        "user_id": current_user.user_id,
        "count": len(items),
        "temperature": temperature if temperature is not None else profile["temperature"],
        "temperature_source": "manual" if temperature is not None else "habit_profile",
        "items": items,
    }


@router.get("/habits/mine", summary="我的做题习惯画像（近 N 天）")
async def my_habits(
    days: int = Query(30, ge=7, le=180),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return kg_habits.build_habit_profile(db, current_user.user_id, days=days)


@router.post("/generate", summary="生成本周个性化任务（幂等）")
async def generate(
    n: int = Query(2, ge=1, le=5),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = kg_growth.ensure_personalized_tasks(db, current_user.user_id, n=n)
    return {
        "created": len(tasks),
        "items": [
            {
                "task_id": t.task_id,
                "task_code": t.task_code,
                "title": t.title,
                "metric_param": t.metric_param,
                "reward_coins": t.reward_coins,
            }
            for t in tasks
        ],
    }


# ------------------------- 节点坐标持久化（2026-11-15） -------------------------


class KgLayoutNode(BaseModel):
    point_id: int
    x: float
    y: float


class KgLayoutPayload(BaseModel):
    """拖拽后的节点坐标。reset=True 表示「双击复位」，清空该模式的全部坐标。"""

    mode: str = Field("mine", pattern="^(mine|global)$")
    nodes: List[KgLayoutNode] = Field(default_factory=list)
    reset: bool = False


@router.get("/layout", summary="我的图谱节点坐标（mine/global）")
async def get_layout(
    mode: str = Query("mine", pattern="^(mine|global)$"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回该用户在该模式下手动摆放过的节点坐标；没有拖拽过的节点不在返回里。"""
    rows = (
        db.query(KgNodeLayout)
        .filter(KgNodeLayout.user_id == current_user.user_id, KgNodeLayout.mode == mode)
        .all()
    )
    return {
        "mode": mode,
        "total": len(rows),
        "nodes": [
            {"point_id": r.point_id, "x": round(r.x, 3), "y": round(r.y, 3)} for r in rows
        ],
    }


@router.put("/layout", summary="保存图谱节点坐标（拖拽后写回 / 双击复位）")
async def put_layout(
    payload: KgLayoutPayload,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """幂等 upsert：(user_id, mode, point_id) 唯一，重复保存只更新坐标。

    只写用户自己名下，不接受 user_id 参数，避免越权改别人的布局。
    """
    base = db.query(KgNodeLayout).filter(
        KgNodeLayout.user_id == current_user.user_id,
        KgNodeLayout.mode == payload.mode,
    )
    if payload.reset:
        deleted = base.delete(synchronize_session=False)
        db.commit()
        return {"success": True, "mode": payload.mode, "reset": True, "deleted": deleted, "saved": 0}

    if not payload.nodes:
        raise HTTPException(status_code=400, detail="nodes 不能为空；清空布局请传 reset=true")
    if len(payload.nodes) > 3000:
        raise HTTPException(status_code=400, detail="单次最多保存 3000 个节点坐标")

    existing = {row.point_id: row for row in base.all()}
    now = datetime.now()
    for item in payload.nodes:
        row = existing.get(item.point_id)
        if row is not None:
            row.x = float(item.x)
            row.y = float(item.y)
            row.updated_at = now
        else:
            db.add(
                KgNodeLayout(
                    user_id=current_user.user_id,
                    mode=payload.mode,
                    point_id=item.point_id,
                    x=float(item.x),
                    y=float(item.y),
                    updated_at=now,
                )
            )
    db.commit()
    total = (
        db.query(KgNodeLayout)
        .filter(KgNodeLayout.user_id == current_user.user_id, KgNodeLayout.mode == payload.mode)
        .count()
    )
    return {"success": True, "mode": payload.mode, "reset": False, "saved": len(payload.nodes), "total": total}


@router.get("/global", summary="全局知识图谱（全部知识点 + 聚合关系边）")
async def global_graph(
    limit: int = Query(800, ge=50, le=3000),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """全局视图：所有知识点 + 跨用户聚合的关系边（不暴露别人的学习数据）。"""
    points = (
        db.query(KnowledgePoint)
        .filter(or_(KnowledgePoint.status.is_(None), KnowledgePoint.status != 0))
        .limit(limit)
        .all()
    )
    ids = {p.point_id for p in points}
    rows = (
        db.query(
            KgUserEdge.src_point,
            KgUserEdge.dst_point,
            func.max(KgUserEdge.weight),
        )
        .filter(KgUserEdge.src_point.in_(ids), KgUserEdge.dst_point.in_(ids))
        .group_by(KgUserEdge.src_point, KgUserEdge.dst_point)
        .all()
    )
    seen = set()
    edges = []
    for src, dst, weight in rows:
        if src == dst:
            continue
        key = tuple(sorted((src, dst)))
        if key in seen:
            continue
        seen.add(key)
        edges.append({"src_point": src, "dst_point": dst, "weight": float(weight or 1.0), "heat": float(weight or 1.0)})

    # 结构边：知识点父子关系（builtin / contains），保证即便没有用户行为数据，
    # 图谱也能呈现科目 -> 模块 -> 考点 的骨架（模块7 P6）。
    structural = (
        db.query(KgEdge.src_id, KgEdge.dst_id, KgEdge.weight, KgEdge.relation)
        .filter(
            KgEdge.src_type == "knowledge_point",
            KgEdge.dst_type == "knowledge_point",
            KgEdge.relation.in_(("contains", "prerequisite_of", "confusable")),
            KgEdge.src_id.in_(ids),
            KgEdge.dst_id.in_(ids),
        )
        .all()
    )
    for src, dst, weight, relation in structural:
        if src == dst:
            continue
        # 结构边与语义边分开去重：同一对考点可能既有包含又有前置关系
        key = (min(src, dst), max(src, dst), relation)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            {
                "src_point": src,
                "dst_point": dst,
                "weight": float(weight or 1.0),
                "heat": 0.0,
                "rel_type": relation,
            }
        )

    # 用户维度的节点状态（掌握度/热度/答题数）——此前这里是硬编码 0，
    # 导致 3D 图谱永远显示「全部未掌握」，答题数据完全进不了图。
    states = {
        s.point_id: s
        for s in db.query(KgUserNodeState)
        .filter(KgUserNodeState.user_id == current_user.user_id)
        .all()
    }

    degree: dict[int, int] = {}
    for e in edges:
        degree[e["src_point"]] = degree.get(e["src_point"], 0) + 1
        degree[e["dst_point"]] = degree.get(e["dst_point"], 0) + 1

    return {
        "total": len(points),
        "nodes": [
            {
                "point_id": p.point_id,
                "point_name": p.point_name,
                "subject_id": p.subject_id,
                "mastery": round(float(states[p.point_id].mastery or 0.0), 4) if p.point_id in states else 0.0,
                # 热度 = 结构连接度 + 用户行为热度，两者含义不同但都体现在节点大小上
                "heat": round(
                    float(degree.get(p.point_id, 0))
                    + (float(states[p.point_id].heat or 0.0) if p.point_id in states else 0.0),
                    4,
                ),
                "attempt_count": int(states[p.point_id].attempt_count or 0) if p.point_id in states else 0,
                "correct_count": int(states[p.point_id].correct_count or 0) if p.point_id in states else 0,
                "contribution": round(
                    (float(states[p.point_id].heat or 0.0) * (1 - float(states[p.point_id].mastery or 0.0)))
                    if p.point_id in states else 0.0,
                    4,
                ),
            }
            for p in points
        ],
        "edges": edges,
    }


@router.post("/decay", summary="热度衰减（调度/管理）")
async def decay(
    user_id: Optional[int] = None,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user_id and user_id != current_user.user_id and current_user.user_type not in ("admin",):
        raise HTTPException(status_code=403, detail="无权限")
    report = kg_growth.decay(db, user_id)
    return {"success": True, **report}
