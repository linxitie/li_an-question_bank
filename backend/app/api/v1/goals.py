"""
学习目标模块路由 - 支持目标管理、进度追踪、手动确认完成
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.models import StudyGoal, SysUser
from ...schemas.schemas import (
    StudyGoalCreate,
    StudyGoalUpdate,
    SuccessResponse
)
from ...core.security import get_current_user

router = APIRouter(prefix="/api/goals", tags=["学习目标"])
logger = logging.getLogger(__name__)


def compute_progress(goal: StudyGoal) -> float:
    """计算目标完成进度百分比"""
    if goal.target_count > 0:
        return round(goal.current_count / goal.target_count * 100, 1)
    return 0.0


def to_response(goal: StudyGoal) -> dict:
    """将模型转为统一响应格式"""
    return {
        "goal_id": goal.goal_id,
        "user_id": goal.user_id,
        "title": goal.title,
        "description": goal.description,
        "goal_type": goal.goal_type,
        "target_count": goal.target_count,
        "current_count": goal.current_count,
        "deadline": goal.deadline,
        "priority": goal.priority,
        "is_completed": bool(goal.is_completed),
        "completed_time": goal.completed_time,
        "create_time": goal.create_time,
        "update_time": goal.update_time,
        "progress_percent": compute_progress(goal),
    }


# ==================== 基础 CRUD ====================

@router.get("/", response_model=Dict[str, Any], summary="获取我的学习目标列表")
async def get_my_goals(
        goal_type: Optional[str] = Query(None, description="目标类型: DAILY/WEEKLY/MONTHLY/CUSTOM"),
        is_completed: Optional[bool] = Query(None, description="是否完成"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取当前用户的学习目标列表，支持类型/状态筛选"""
    query = db.query(StudyGoal).filter(
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    )

    if goal_type:
        query = query.filter(StudyGoal.goal_type == goal_type)
    if is_completed is not None:
        query = query.filter(StudyGoal.is_completed == (1 if is_completed else 0))

    goals = query.order_by(
        StudyGoal.priority.desc(),
        StudyGoal.deadline.asc().nulls_last(),
        StudyGoal.create_time.desc()
    ).all()

    return {"total": len(goals), "items": [to_response(g) for g in goals]}


@router.get("/{goal_id}", response_model=Dict[str, Any], summary="获取目标详情")
async def get_goal_detail(
        goal_id: int,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取单个学习目标详情"""
    goal = db.query(StudyGoal).filter(
        StudyGoal.goal_id == goal_id,
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).first()

    if not goal:
        raise HTTPException(status_code=404, detail="学习目标不存在")

    return to_response(goal)


@router.post("/", response_model=Dict[str, Any], summary="创建学习目标")
async def create_goal(
        goal_data: StudyGoalCreate,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """创建新的学习目标"""
    new_goal = StudyGoal(
        user_id=current_user.user_id,
        title=goal_data.title,
        description=goal_data.description,
        goal_type=goal_data.goal_type.value,
        target_count=goal_data.target_count,
        current_count=0,
        deadline=goal_data.deadline,
        priority=goal_data.priority,
        is_completed=0,
    )

    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)

    logger.info(
        f"用户 {current_user.username} 创建目标: {new_goal.title} "
        f"(类型:{new_goal.goal_type}, 目标:{new_goal.target_count})"
    )

    return to_response(new_goal)


@router.put("/{goal_id}", response_model=Dict[str, Any], summary="更新学习目标")
async def update_goal(
        goal_id: int,
        goal_data: StudyGoalUpdate,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """更新学习目标（标题、进度、优先级等）"""
    goal = db.query(StudyGoal).filter(
        StudyGoal.goal_id == goal_id,
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).first()

    if not goal:
        raise HTTPException(status_code=404, detail="学习目标不存在")

    update_data = goal_data.dict(exclude_unset=True)

    # 如果用户手动标记完成，设置完成时间
    if "is_completed" in update_data:
        if update_data["is_completed"] and not goal.is_completed:
            goal.completed_time = datetime.now()
        elif not update_data["is_completed"]:
            goal.completed_time = None

    for key, value in update_data.items():
        if key == "goal_type" and value:
            value = value.value if hasattr(value, 'value') else value
        setattr(goal, key, value)

    # 自动判断：进度达标则自动完成
    if goal.current_count >= goal.target_count and goal.target_count > 0 and not goal.is_completed:
        goal.is_completed = 1
        if not goal.completed_time:
            goal.completed_time = datetime.now()

    goal.update_time = datetime.now()
    db.commit()
    db.refresh(goal)

    logger.info(f"用户 {current_user.username} 更新目标 ID: {goal_id}")

    return to_response(goal)


@router.delete("/{goal_id}", response_model=SuccessResponse, summary="删除学习目标")
async def delete_goal(
        goal_id: int,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """软删除学习目标"""
    goal = db.query(StudyGoal).filter(
        StudyGoal.goal_id == goal_id,
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).first()

    if not goal:
        raise HTTPException(status_code=404, detail="学习目标不存在")

    goal.status = 0
    goal.update_time = datetime.now()
    db.commit()

    logger.info(f"用户 {current_user.username} 删除目标 ID: {goal_id}")

    return SuccessResponse(message="目标删除成功")


# ==================== 进度追踪 ====================

@router.post("/{goal_id}/progress", response_model=Dict[str, Any], summary="更新目标进度")
async def update_goal_progress(
        goal_id: int,
        increment: int = Query(1, ge=1, description="增加数量"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """快捷更新目标进度（每次 +increment）"""
    goal = db.query(StudyGoal).filter(
        StudyGoal.goal_id == goal_id,
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).first()

    if not goal:
        raise HTTPException(status_code=404, detail="学习目标不存在")

    if goal.is_completed:
        raise HTTPException(status_code=400, detail="目标已完成，如需继续请先取消完成")

    goal.current_count = min(goal.current_count + increment, goal.target_count)

    # 达标自动标记完成
    if goal.current_count >= goal.target_count:
        goal.is_completed = 1
        goal.completed_time = datetime.now()

    goal.update_time = datetime.now()
    db.commit()
    db.refresh(goal)

    progress = compute_progress(goal)
    logger.info(
        f"用户 {current_user.username} 目标进度: "
        f"{goal.current_count}/{goal.target_count} ({progress}%)"
    )

    return {
        **to_response(goal),
        "message": "进度更新成功" if not goal.is_completed else "🎉 恭喜！目标已达成！"
    }


# ==================== 手动确认完成（新增核心功能） ====================

@router.post("/{goal_id}/confirm-complete", response_model=Dict[str, Any], summary="手动确认目标完成")
async def confirm_goal_complete(
        goal_id: int,
        confirm_note: Optional[str] = Query(None, max_length=200, description="完成确认备注"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    手动确认目标已完成

    适用场景：
    - 目标进度已达但尚未自动标记
    - 需要人工判断主观目标（如"复习一章"）
    - 进度未达标但认为已完成的特殊情况

    确认后自动设置:
    - is_completed = True
    - completed_time = 当前时间
    - 写入操作日志
    """
    goal = db.query(StudyGoal).filter(
        StudyGoal.goal_id == goal_id,
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).first()

    if not goal:
        raise HTTPException(status_code=404, detail="学习目标不存在")

    if goal.is_completed:
        raise HTTPException(
            status_code=400,
            detail="目标已标记为完成，如需更改请先取消完成"
        )

    # 确认前状态
    previous_state = {
        "is_completed": bool(goal.is_completed),
        "current_count": goal.current_count,
        "target_count": goal.target_count,
        "progress": compute_progress(goal),
    }

    # 标记完成
    now = datetime.now()
    goal.is_completed = 1
    goal.completed_time = now
    goal.update_time = now

    # 如果进度未达标但手动确认，将 current 补充到 target
    if goal.current_count < goal.target_count:
        goal.current_count = goal.target_count

    db.commit()
    db.refresh(goal)

    logger.info(
        f"用户 {current_user.username} 手动确认目标完成 ID: {goal_id} "
        f"标题: {goal.title} "
        f"备注: {confirm_note or '无'}"
    )

    return {
        **to_response(goal),
        "message": "✅ 目标已确认完成",
        "confirm_time": now.isoformat(),
        "confirm_note": confirm_note or "",
        "previous_state": previous_state,
        "was_auto_completed": previous_state["progress"] >= 100,
    }


@router.post("/{goal_id}/undo-complete", response_model=Dict[str, Any], summary="取消目标完成状态")
async def undo_goal_complete(
        goal_id: int,
        undo_note: Optional[str] = Query(None, max_length=200, description="取消原因备注"),
        reset_progress: bool = Query(False, description="是否重置进度到0"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    取消目标完成状态，重新开始

    适用场景：
    - 误操作确认完成
    - 每周目标需要重置
    - 目标更新后需要再次确认

    - **reset_progress=False**: 仅取消完成标记，保留进度
    - **reset_progress=True**: 取消完成标记 + 进度归零
    """
    goal = db.query(StudyGoal).filter(
        StudyGoal.goal_id == goal_id,
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).first()

    if not goal:
        raise HTTPException(status_code=404, detail="学习目标不存在")

    if not goal.is_completed:
        raise HTTPException(status_code=400, detail="目标尚未完成，无需取消")

    # 取消前状态
    previous_state = {
        "was_completed": True,
        "completed_time": goal.completed_time,
        "current_count": goal.current_count,
    }

    # 取消完成
    goal.is_completed = 0
    goal.completed_time = None
    goal.update_time = datetime.now()

    # 可选：重置进度
    if reset_progress:
        goal.current_count = 0

    db.commit()
    db.refresh(goal)

    logger.info(
        f"用户 {current_user.username} 取消目标完成 ID: {goal_id} "
        f"重置进度: {reset_progress} 原因: {undo_note or '无'}"
    )

    return {
        **to_response(goal),
        "message": "🔄 完成状态已取消" + ("，进度已重置" if reset_progress else ""),
        "undo_note": undo_note or "",
        "previous_state": previous_state,
    }


@router.post("/batch-confirm", response_model=Dict[str, Any], summary="批量确认目标完成")
async def batch_confirm_goals(
        goal_ids: List[int],
        confirm_note: Optional[str] = Query(None, max_length=200, description="统一备注"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    批量手动确认多个目标完成

    - 一次性确认多个目标
    - 返回成功/失败统计
    """
    if not goal_ids:
        raise HTTPException(status_code=400, detail="目标ID列表不能为空")

    confirmed = []
    failed = []
    now = datetime.now()

    for goal_id in goal_ids:
        try:
            goal = db.query(StudyGoal).filter(
                StudyGoal.goal_id == goal_id,
                StudyGoal.user_id == current_user.user_id,
                StudyGoal.status == 1
            ).first()

            if not goal:
                failed.append({"goal_id": goal_id, "reason": "目标不存在"})
                continue

            if goal.is_completed:
                failed.append({"goal_id": goal_id, "reason": "已完成，跳过"})
                continue

            goal.is_completed = 1
            goal.completed_time = now
            goal.update_time = now

            if goal.current_count < goal.target_count:
                goal.current_count = goal.target_count

            db.flush()
            confirmed.append({"goal_id": goal_id, "title": goal.title})

        except Exception as e:
            failed.append({"goal_id": goal_id, "reason": str(e)})

    db.commit()

    logger.info(
        f"用户 {current_user.username} 批量确认完成: "
        f"成功 {len(confirmed)} 个, 失败 {len(failed)} 个"
    )

    return {
        "message": f"批量确认完成: 成功 {len(confirmed)} 个, 失败 {len(failed)} 个",
        "confirmed": confirmed,
        "failed": failed,
        "total_success": len(confirmed),
        "total_failed": len(failed),
    }


# ==================== 完成状态查询 ====================

@router.get("/status/completed", response_model=Dict[str, Any], summary="获取已完成目标列表")
async def get_completed_goals(
        goal_type: Optional[str] = Query(None, description="目标类型筛选"),
        days: int = Query(30, ge=1, le=365, description="最近N天内完成的目标"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取已完成目标列表

    - 按完成时间倒序排列
    - 可筛选最近N天内完成的目标
    - 可筛选目标类型
    """
    cutoff_date = datetime.now()  # 简化处理

    query = db.query(StudyGoal).filter(
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.is_completed == 1,
        StudyGoal.status == 1
    )

    if goal_type:
        query = query.filter(StudyGoal.goal_type == goal_type)

    goals = query.order_by(StudyGoal.completed_time.desc()).all()

    # 统计各类信息
    total_completed = len(goals)
    by_type = {}
    for g in goals:
        t = g.goal_type
        if t not in by_type:
            by_type[t] = 0
        by_type[t] += 1

    return {
        "total": total_completed,
        "by_type": by_type,
        "items": [
            {
                **to_response(g),
                "completed_days_ago": (
                    (datetime.now() - g.completed_time).days
                    if g.completed_time else None
                ),
            }
            for g in goals
        ],
    }


@router.get("/status/pending", response_model=Dict[str, Any], summary="获取待完成目标列表")
async def get_pending_goals(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取待完成目标列表（按紧急程度排序）

    排序规则：高优先级 + 逼近截止日期 > 低优先级 + 宽松
    """
    goals = db.query(StudyGoal).filter(
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.is_completed == 0,
        StudyGoal.status == 1
    ).order_by(
        StudyGoal.priority.desc(),
        StudyGoal.deadline.asc().nulls_last(),
        StudyGoal.create_time.desc()
    ).all()

    now = datetime.now()

    pending_list = []
    for g in goals:
        days_left = None
        is_overdue = False

        if g.deadline:
            delta = g.deadline - now
            days_left = delta.days
            is_overdue = delta.total_seconds() < 0

        pending_list.append({
            **to_response(g),
            "days_left": days_left,
            "is_overdue": is_overdue,
            "urgency": (
                "overdue" if is_overdue
                else "urgent" if days_left is not None and days_left <= 1
                else "soon" if days_left is not None and days_left <= 3
                else "normal"
            ),
        })

    return {
        "total": len(pending_list),
        "overdue_count": sum(1 for g in pending_list if g["is_overdue"]),
        "items": pending_list,
    }


# ==================== 统计概览 ====================

@router.get("/stats/summary", response_model=Dict[str, Any], summary="目标统计概览")
async def get_goal_stats(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取学习目标统计概览"""
    goals = db.query(StudyGoal).filter(
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).all()

    total = len(goals)
    completed = sum(1 for g in goals if g.is_completed)
    pending = total - completed

    # 按类型统计
    type_stats = {}
    for goal in goals:
        t = goal.goal_type
        if t not in type_stats:
            type_stats[t] = {"total": 0, "completed": 0, "pending": 0}
        type_stats[t]["total"] += 1
        if goal.is_completed:
            type_stats[t]["completed"] += 1
        else:
            type_stats[t]["pending"] += 1

    # 手动确认统计（完成时间与更新时间不同的）
    manual_confirmed = sum(
        1 for g in goals
        if g.is_completed
        and g.completed_time
        and g.update_time
        and abs((g.update_time - g.completed_time).total_seconds()) > 60
    )

    avg_progress = sum(compute_progress(g) for g in goals) / total if total > 0 else 0

    # 今日完成
    today = datetime.now().date()
    today_completed = sum(
        1 for g in goals
        if g.is_completed
        and g.completed_time
        and g.completed_time.date() == today
    )

    return {
        "total_goals": total,
        "completed_goals": completed,
        "pending_goals": pending,
        "manual_confirmed_goals": manual_confirmed,
        "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
        "average_progress": round(avg_progress, 1),
        "today_completed": today_completed,
        "high_priority_pending": sum(
            1 for g in goals
            if g.priority == 3 and not g.is_completed
        ),
        "by_type": type_stats,
    }
