"""周任务池管理（2026-11-05 M2，管理员/运营）。

- `GET /api/tasks/weekly/pool`：查看本周池（含置顶槽位）
- `POST /api/tasks/weekly/pool/pin`：设置/取消置顶（槽位 1..3）
- `POST /api/tasks/weekly/recalc`：按指定用户重算进度（换算法/补数据后回放）
- `POST /api/tasks/weekly/expire`：把上周未完成的任务置为已失效（调度每日跑）
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_admin, get_current_user
from ....models.models import SysUser, Task, UserTaskProgress, WeeklyTaskPool
from ....services import weekly_tasks as weekly

router = APIRouter(prefix="/api/tasks/weekly", tags=["周任务"])
logger = logging.getLogger(__name__)


class PinPayload(BaseModel):
    task_id: int
    slot: int = 1  # 0 = 取消置顶
    week_key: Optional[str] = None


def _serialize(task: Task, slot: int) -> dict:
    scarcity = weekly.PINNED_SCARCITY.get(slot)
    return {
        "task_id": task.task_id,
        "task_code": task.task_code,
        "title": task.title,
        "category": task.category,
        "metric": task.metric,
        "threshold": task.threshold,
        "reward_base": task.reward_coins,
        "difficulty_factor": float(task.difficulty_factor or 1.0),
        "scarcity_factor": float(scarcity if scarcity is not None else (task.scarcity_factor or 1.0)),
        "reward": weekly.effective_reward(task, scarcity),
        "pinned_slot": slot,
        "coupon_code": task.coupon_code,
    }


@router.get("/pool", summary="本周周任务池（含置顶槽位）")
async def get_pool(
    week: Optional[str] = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    week = week or weekly.week_key()
    weekly.ensure_week_pool(db, week)
    rows = db.query(WeeklyTaskPool).filter(WeeklyTaskPool.week_key == week).all()
    slots = {r.task_id: r.pinned_slot for r in rows}
    tasks = db.query(Task).filter(Task.t_type == "weekly", Task.enabled == 1).order_by(Task.sort_order.asc()).all()
    items = [_serialize(t, slots.get(t.task_id, 0)) for t in tasks]
    items.sort(key=lambda v: (0 if v["pinned_slot"] else 1, v["pinned_slot"] or 99, v["task_id"]))
    return {"week_key": week, "pinned_count": len([s for s in slots.values() if s]), "items": items}


@router.post("/pool/pin", summary="设置/取消置顶（管理员）")
async def pin_task(
    data: PinPayload,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if data.slot < 0 or data.slot > 3:
        raise HTTPException(status_code=400, detail="置顶槽位只能是 0~3（0=取消）")
    week = data.week_key or weekly.week_key()

    task = db.query(Task).filter(Task.task_id == data.task_id, Task.t_type == "weekly").first()
    if not task:
        raise HTTPException(status_code=404, detail="周任务不存在")

    weekly.ensure_week_pool(db, week)

    if data.slot == 0:
        row = db.query(WeeklyTaskPool).filter(
            WeeklyTaskPool.week_key == week, WeeklyTaskPool.task_id == data.task_id
        ).first()
        if row:
            row.pinned_slot = 0
        db.commit()
        return {"success": True, "task_id": data.task_id, "pinned_slot": 0}

    # 槽位占用则先清空原占用者，保证一个槽位只放一个任务
    occupied = db.query(WeeklyTaskPool).filter(
        WeeklyTaskPool.week_key == week,
        WeeklyTaskPool.pinned_slot == data.slot,
        WeeklyTaskPool.task_id != data.task_id,
    ).all()
    for row in occupied:
        row.pinned_slot = 0

    target = db.query(WeeklyTaskPool).filter(
        WeeklyTaskPool.week_key == week, WeeklyTaskPool.task_id == data.task_id
    ).first()
    if not target:
        target = WeeklyTaskPool(week_key=week, task_id=data.task_id, pinned_slot=data.slot, source="manual")
        db.add(target)
    else:
        target.pinned_slot = data.slot
        target.source = "manual"

    db.commit()
    logger.info("管理员 %s 将任务 %s 置顶到槽位 %s（%s）", current_user.username, data.task_id, data.slot, week)
    return {"success": True, "task_id": data.task_id, "pinned_slot": data.slot, "week_key": week}


@router.post("/recalc", summary="重算某用户的周任务进度（管理员/运营）")
async def recalc(
    user_id: Optional[int] = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """判定重放：按当前算法重新算一遍进度并落库（不改已领取状态）。"""
    target_id = user_id or current_user.user_id
    if user_id and user_id != current_user.user_id and current_user.user_type not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="无权重算他人任务")

    week = weekly.week_key()
    tasks = db.query(Task).filter(Task.t_type == "weekly", Task.enabled == 1).all()
    updated = 0
    for task in tasks:
        current = weekly.compute_metric(task.metric, target_id, db)
        prog = db.query(UserTaskProgress).filter(
            UserTaskProgress.user_id == target_id,
            UserTaskProgress.task_id == task.task_id,
            UserTaskProgress.period_key == week,
        ).first()
        if not prog:
            prog = UserTaskProgress(
                user_id=target_id, task_id=task.task_id, period_key=week,
                current=0, completed=0, claimed=0,
            )
            db.add(prog)
        if prog.claimed == 1:
            continue  # 已发放的不回写，避免把已领的进度改小
        prog.current = int(current)
        prog.completed = 1 if current >= task.threshold else 0
        prog.pending_verify = 1 if prog.completed and not prog.expired else 0
        updated += 1
    db.commit()
    return {"success": True, "week_key": week, "updated": updated}


@router.post("/expire", summary="把过期的未完成任务置为已失效")
async def expire_stale(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """调度用：把非本周、未领取、未完成的任务标记 expired=1。

    只处理周任务；每日/随机任务的过期由各自周期自然失效，不做落库。
    """
    week = weekly.week_key()
    rows = (
        db.query(UserTaskProgress, Task)
        .join(Task, Task.task_id == UserTaskProgress.task_id)
        .filter(
            Task.t_type == "weekly",
            UserTaskProgress.period_key != week,
            UserTaskProgress.claimed == 0,
            UserTaskProgress.expired == 0,
        )
        .all()
    )
    count = 0
    for prog, _task in rows:
        prog.expired = 1
        count += 1
    db.commit()
    return {"success": True, "expired": count, "current_week": week}
