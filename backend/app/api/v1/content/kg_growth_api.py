"""自生长知识图谱 API（2026-11-05 M3）。

- GET  /api/knowledge/kg/nodes/mine     我的节点状态（掌握度/热度/贡献度）
- GET  /api/knowledge/kg/edges/mine     我的边（权重/热度）
- GET  /api/knowledge/kg/sample         本周个性化任务候选（非均匀采样结果）
- POST /api/knowledge/kg/generate       生成本周个性化任务（幂等）
- POST /api/knowledge/kg/decay          热度衰减（调度用）
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_admin, get_current_user
from ....models.models import KgUserEdge, KgUserNodeState, KnowledgePoint, SysUser
from ....services import kg_growth

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
    temperature: float = Query(kg_growth.DEFAULT_TEMPERATURE, gt=0.05, le=5),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = kg_growth.sample_nodes(db, current_user.user_id, n=n, temperature=temperature)
    return {
        "user_id": current_user.user_id,
        "count": len(items),
        "temperature": temperature,
        "items": items,
    }


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
