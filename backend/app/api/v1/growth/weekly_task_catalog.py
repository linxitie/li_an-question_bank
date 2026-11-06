"""周任务设计分配 · 学生端/运营端只读接口。

数据源：weekly_task_* 四张表（由 scripts/import_weekly_task_pack.py 导入）。
可见性（2026-11-06 用户决策）：学生端**现在可见**——当天不在任何周计划区间时，
返回最近一个即将开始的周计划并标记 is_preview=true，避免"任务看不到"。
可开始条件：供给=可试点；待补题一律不可开始（点不开题）。
"""
from __future__ import annotations

import json
from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser
from ....models.weekly_task import (
    WeeklyTaskInstance,
    WeeklyTaskPlan,
)

router = APIRouter(prefix="/api/v1/weekly-tasks", tags=["周任务设计"])

_START_SUBJECT = {"行测": "xc", "申论": "sl", "公专": "ga"}


def _task_payload(row: WeeklyTaskInstance) -> dict:
    startable = (row.supply or "") == "可试点"
    return {
        "instance_id": row.instance_id,
        "week_no": row.week_no,
        "task_date": row.task_date,
        "weekday": row.weekday,
        "title": row.title,
        "subject": row.subject,
        "domain": row.domain,
        "form": row.form,
        "difficulty": row.difficulty,
        "qty": row.qty,
        "unit": row.unit,
        "minutes": row.minutes,
        "coins": row.coins,
        "supply": row.supply,
        "status": row.status,
        "startable": startable,
        "blocked_reason": None if startable else "待补题",
        "start_subject": _START_SUBJECT.get(row.subject or "", "xc"),
        "theme_id": row.theme_id,
        "template_id": row.template_id,
        "anchors": json.loads(row.anchors) if row.anchors else [],
    }


def _pick_plan(db: Session, today: str) -> tuple[Optional[WeeklyTaskPlan], bool]:
    current = (
        db.query(WeeklyTaskPlan)
        .filter(WeeklyTaskPlan.start_date <= today, WeeklyTaskPlan.end_date >= today)
        .order_by(WeeklyTaskPlan.week_no.asc())
        .first()
    )
    if current:
        return current, False
    upcoming = (
        db.query(WeeklyTaskPlan)
        .filter(WeeklyTaskPlan.start_date > today)
        .order_by(WeeklyTaskPlan.start_date.asc())
        .first()
    )
    return upcoming, True


@router.get("/overview", summary="我的周任务（金币购 · 任务 Tab）")
async def overview(
    date: Optional[str] = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date or date_cls.today().strftime("%Y-%m-%d")
    plan, is_preview = _pick_plan(db, today)

    pilots = (
        db.query(WeeklyTaskInstance)
        .filter(WeeklyTaskInstance.supply == "可试点")
        .order_by(WeeklyTaskInstance.task_date.asc())
        .limit(12)
        .all()
    )
    later = (
        db.query(WeeklyTaskPlan)
        .filter(WeeklyTaskPlan.plan_id != (plan.plan_id if plan else ""))
        .order_by(WeeklyTaskPlan.week_no.asc())
        .all()
    )

    if not plan:
        return {
            "today": today,
            "is_preview": False,
            "plan": None,
            "days": [],
            "pilot_tasks": [_task_payload(row) for row in pilots],
            "later_weeks": [],
            "summary": {"tasks": 0, "minutes": 0, "coins": 0, "pilot": len(pilots)},
        }

    instances = (
        db.query(WeeklyTaskInstance)
        .filter(WeeklyTaskInstance.plan_id == plan.plan_id)
        .order_by(WeeklyTaskInstance.task_date.asc(), WeeklyTaskInstance.instance_id.asc())
        .all()
    )
    days: list[dict] = []
    by_date: dict[str, list[dict]] = {}
    weekday_by_date: dict[str, str] = {}
    for row in instances:
        by_date.setdefault(row.task_date, []).append(_task_payload(row))
        weekday_by_date.setdefault(row.task_date, row.weekday or "")
    for task_date in sorted(by_date):
        days.append({
            "date": task_date,
            "weekday": weekday_by_date.get(task_date, ""),
            "tasks": by_date[task_date],
        })

    return {
        "today": today,
        "is_preview": is_preview,
        "plan": {
            "plan_id": plan.plan_id,
            "week_no": plan.week_no,
            "week_key": plan.week_key,
            "title": plan.title,
            "stage": plan.stage,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "status": plan.status,
            "task_count": plan.task_count,
            "minutes": plan.minutes,
            "coins": plan.coins,
        },
        "days": days,
        "pilot_tasks": [_task_payload(row) for row in pilots],
        "later_weeks": [
            {
                "week_no": p.week_no,
                "title": p.title,
                "start_date": p.start_date,
                "status": p.status,
                "task_count": p.task_count,
            }
            for p in later
        ],
        "summary": {
            "tasks": len(instances),
            "minutes": sum(r.minutes or 0 for r in instances),
            "coins": sum(r.coins or 0 for r in instances),
            "pilot": sum(1 for r in instances if r.supply == "可试点"),
        },
    }


@router.get("/plans", summary="周计划列表（教研/管理员）")
async def list_plans(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (current_user.user_type or "").lower() not in ("admin", "teacher"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="仅教研/管理员可查看周计划列表")
    rows = db.query(WeeklyTaskPlan).order_by(WeeklyTaskPlan.week_no.asc()).all()
    return {
        "items": [
            {
                "plan_id": r.plan_id,
                "week_no": r.week_no,
                "title": r.title,
                "stage": r.stage,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "status": r.status,
                "task_count": r.task_count,
                "minutes": r.minutes,
                "coins": r.coins,
            }
            for r in rows
        ]
    }
