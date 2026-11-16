# 方案版本快照与双栏 diff（模块4 · 7-4）
#
# - POST /api/v1/growth/plan-snapshot/capture  把当前方案存成一版快照
# - GET  /api/v1/growth/plan-snapshot/list     历史版本列表
# - GET  /api/v1/growth/plan-snapshot/diff     两版之间新增/删除/状态变化的任务差异
#
# 新增端点，不改既有契约（R11 只增不改）。
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import StudyGoal, StudyPlanSnapshot, SysUser

router = APIRouter(prefix="/api/v1/growth/plan-snapshot", tags=["方案快照"])
logger = logging.getLogger(__name__)


def _current_plan_goals(db: Session, user_id: int) -> tuple[Optional[int], List[StudyGoal]]:
    row = (
        db.query(StudyGoal.plan_id)
        .filter(StudyGoal.user_id == user_id, StudyGoal.plan_id.isnot(None))
        .order_by(StudyGoal.goal_id.desc())
        .first()
    )
    if not row:
        return None, []
    plan_id = int(row[0])
    goals = (
        db.query(StudyGoal)
        .filter(StudyGoal.user_id == user_id, StudyGoal.plan_id == plan_id)
        .order_by(StudyGoal.sort_order.asc(), StudyGoal.goal_id.asc())
        .all()
    )
    return plan_id, goals


def _serialize(goals: List[StudyGoal]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    tasks = []
    for g in goals:
        if isinstance(g.plan_meta, str) and g.plan_meta and not meta:
            try:
                meta = json.loads(g.plan_meta)
            except ValueError:
                meta = {}
        tasks.append(
            {
                "title": g.title or "",
                "done": int(g.is_completed or 0),
                "subject_mode": int(g.subject_mode or 0),
            }
        )
    return {
        "summary": meta.get("summary", ""),
        "phases": meta.get("phases", []),
        "tasks": tasks,
    }


@router.post("/capture", summary="把当前方案存成一版快照")
async def capture(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan_id, goals = _current_plan_goals(db, current_user.user_id)
    if plan_id is None:
        raise HTTPException(status_code=404, detail="当前没有学习计划，无法生成快照")

    payload = _serialize(goals)
    last = (
        db.query(func.max(StudyPlanSnapshot.version))
        .filter(StudyPlanSnapshot.user_id == current_user.user_id, StudyPlanSnapshot.plan_id == plan_id)
        .scalar()
        or 0
    )
    row = StudyPlanSnapshot(
        user_id=current_user.user_id,
        plan_id=plan_id,
        version=int(last) + 1,
        payload=json.dumps(payload, ensure_ascii=False),
        task_count=len(payload["tasks"]),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"snapshot_id": row.snapshot_id, "version": row.version, "task_count": row.task_count}


@router.get("/list", summary="方案历史版本")
async def list_versions(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(StudyPlanSnapshot)
        .filter(StudyPlanSnapshot.user_id == current_user.user_id)
        .order_by(StudyPlanSnapshot.snapshot_id.desc())
        .limit(20)
        .all()
    )
    return {
        "items": [
            {
                "snapshot_id": r.snapshot_id,
                "plan_id": r.plan_id,
                "version": r.version,
                "task_count": r.task_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get("/diff", summary="两版方案差异")
async def diff(
    from_version: int = Query(..., ge=1),
    to_version: int = Query(..., ge=1),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    def load(version: int) -> Optional[StudyPlanSnapshot]:
        return (
            db.query(StudyPlanSnapshot)
            .filter(
                StudyPlanSnapshot.user_id == current_user.user_id,
                StudyPlanSnapshot.version == version,
            )
            .order_by(StudyPlanSnapshot.snapshot_id.desc())
            .first()
        )

    a, b = load(from_version), load(to_version)
    if not a or not b:
        raise HTTPException(status_code=404, detail="快照不存在")

    def parse(row: StudyPlanSnapshot) -> Dict[str, Any]:
        try:
            return json.loads(row.payload or "{}")
        except ValueError:
            return {}

    pa, pb = parse(a), parse(b)
    ta = {t.get("title", ""): t for t in pa.get("tasks", [])}
    tb = {t.get("title", ""): t for t in pb.get("tasks", [])}

    added = [tb[k] for k in tb if k not in ta]
    removed = [ta[k] for k in ta if k not in tb]
    changed = []
    for k in tb:
        if k in ta and int(ta[k].get("done", 0)) != int(tb[k].get("done", 0)):
            changed.append({"title": k, "from": ta[k].get("done"), "to": tb[k].get("done")})

    return {
        "from": {"version": from_version, "created_at": a.created_at.isoformat() if a.created_at else None},
        "to": {"version": to_version, "created_at": b.created_at.isoformat() if b.created_at else None},
        "summary_changed": pa.get("summary", "") != pb.get("summary", ""),
        "added": added,
        "removed": removed,
        "changed": changed,
        "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
    }
