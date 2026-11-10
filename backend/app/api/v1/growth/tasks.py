"""
任务中心 API：总览 / 随机任务刷新 / 领取奖励

- 任务进度 calc 模式实时重算（查 practice_record / daily_checkin），不落库进度
- 每日任务 t_type=daily（周期键=当天日期）；周常任务 t_type=weekly（周期键=ISO 周）
- 随机任务 t_type=random：每日从池随机抽 N 个，可免费刷新 1 次（刷新配额用内部任务计数）
- 签到复用 stats.auto_checkin（自动签到），此处只展示状态
- 幂等：领取用 claimed 标志位 + uk_user_task_period 唯一约束
"""
import logging
import random
from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    SysUser, Task, UserTaskProgress, CoinRecord, DailyCheckin, PracticeRecord,
)
from ....services.growth_service import add_growth
from ....services.coin_ledger import grant as grant_coins
from ....services import weekly_tasks as weekly

router = APIRouter(prefix="/api/tasks", tags=["任务中心"])
logger = logging.getLogger(__name__)

RANDOM_TASK_COUNT = 3  # 每日随机任务数量
REFRESH_QUOTA_CODE = "random_refresh_quota"  # 刷新配额内部任务代码


# ------------------------- 周期键 -------------------------

def _today_key() -> str:
    return date.today().strftime("%Y%m%d")


def _week_key() -> str:
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _period_key_for(task: Task) -> str:
    if task.t_type == "weekly":
        return _week_key()
    return _today_key()  # daily / random


# ------------------------- 进度计算（calc） -------------------------

def _calc_metric(user_id: int, metric: str, db: Session, param: Optional[int] = None) -> float:
    # M2：周任务指标统一由 weekly_tasks 计算（按 ISO 周范围，数据源 exam 域）
    if metric.startswith("week_"):
        return weekly.compute_metric(metric, user_id, db)
    # M3：个性化任务按知识点统计本周答题数
    if metric == "kg_node_questions":
        return weekly.compute_metric(metric, user_id, db, param=param)

    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = datetime.now() - timedelta(days=7)

    if metric == "today_questions":
        return db.query(PracticeRecord).filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_time >= today_start,
        ).count()

    if metric == "week_questions":
        return db.query(PracticeRecord).filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_time >= week_start,
        ).count()

    if metric == "total_questions":
        return db.query(PracticeRecord).filter(
            PracticeRecord.user_id == user_id,
        ).count()

    if metric in ("today_accuracy", "week_accuracy"):
        q = db.query(PracticeRecord).filter(PracticeRecord.user_id == user_id)
        if metric == "today_accuracy":
            q = q.filter(PracticeRecord.practice_time >= today_start)
        else:
            q = q.filter(PracticeRecord.practice_time >= week_start)
        rows = q.all()
        total = len(rows)
        if total == 0:
            return 0.0
        correct = sum(1 for r in rows if r.is_correct == 1)
        return round(correct / total * 100, 1)

    if metric == "streak_days":
        user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
        return user.continuous_checkin_days if user else 0

    return 0


def _task_view(task: Task, user_id: int, db: Session, pinned_slot: int = 0) -> dict:
    """任务展示结构（含实时进度、状态机与生效奖励）"""
    period_key = _period_key_for(task)
    prog = db.query(UserTaskProgress).filter(
        UserTaskProgress.user_id == user_id,
        UserTaskProgress.task_id == task.task_id,
        UserTaskProgress.period_key == period_key,
    ).first()

    current = _calc_metric(user_id, task.metric, db, task.metric_param)
    completed = current >= task.threshold
    claimed = bool(prog and prog.claimed == 1)
    expired = bool(prog and prog.expired == 1)

    # M2：周任务的生效奖励 = 基础值 × 难度 × 稀缺（置顶套 1.30/1.45/1.50）
    is_weekly = task.t_type == "weekly"
    scarcity = weekly.PINNED_SCARCITY.get(pinned_slot) if pinned_slot else None
    reward = weekly.effective_reward(task, scarcity) if is_weekly else (task.reward_coins or 0)

    if expired:
        status = "expired"
    elif claimed:
        status = "claimed"
    elif completed:
        status = "pending"  # 待判定
    elif current > 0:
        status = "in_progress"
    else:
        status = "not_started"

    return {
        "task_id": task.task_id,
        "task_code": task.task_code,
        "title": task.title,
        "description": task.description,
        "metric": task.metric,
        "threshold": task.threshold,
        "reward_coins": reward,
        "reward_base": task.reward_coins,
        "current": current,
        "completed": completed,
        "claimed": claimed,
        "status": status,
        # M2 周任务字段
        "category": getattr(task, "category", None) or "A",
        "pinned": bool(pinned_slot),
        "pinned_slot": pinned_slot,
        "difficulty_factor": float(task.difficulty_factor or 1.0),
        "scarcity_factor": float(scarcity if scarcity is not None else (task.scarcity_factor or 1.0)),
        "coupon_code": getattr(task, "coupon_code", None),
    }


# ------------------------- 随机任务分配 -------------------------

def _ensure_random_tasks(user_id: int, db: Session):
    """确保当天已分配随机任务，返回已分配的 UserTaskProgress 列表"""
    today = _today_key()
    pool = db.query(Task).filter(Task.t_type == "random", Task.enabled == 1).all()
    if not pool:
        return []

    assigned = db.query(UserTaskProgress).filter(
        UserTaskProgress.user_id == user_id,
        UserTaskProgress.period_key == today,
        UserTaskProgress.task_id.in_([t.task_id for t in pool]),
    ).all()
    if assigned:
        return assigned

    chosen = random.sample(pool, min(RANDOM_TASK_COUNT, len(pool)))
    records = []
    for t in chosen:
        rec = UserTaskProgress(
            user_id=user_id, task_id=t.task_id, period_key=today,
            current=0, completed=0, claimed=0,
        )
        db.add(rec)
        records.append(rec)
    db.commit()
    return records


def _get_refresh_quota_task(db: Session) -> Task:
    """刷新配额内部任务（懒创建，用于计数当日刷新次数）"""
    t = db.query(Task).filter(Task.task_code == REFRESH_QUOTA_CODE).first()
    if not t:
        t = Task(
            task_code=REFRESH_QUOTA_CODE, t_type="random", title="随机任务刷新配额",
            description="内部任务，不对用户展示", metric="", mode="event",
            threshold=1, reward_coins=0, reward_growth=0, sort_order=999, enabled=0,
        )
        db.add(t)
        db.commit()
        db.refresh(t)
    return t


# ------------------------- 接口 -------------------------

@router.get("/overview", summary="任务中心总览")
async def overview(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """聚合返回签到状态 + 每日任务 + 随机任务 + 周常任务"""
    today = date.today().strftime("%Y-%m-%d")

    # 签到状态
    checkin = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id,
        DailyCheckin.checkin_date == today,
    ).first()

    # 每日任务
    daily_tasks = db.query(Task).filter(Task.t_type == "daily", Task.enabled == 1)\
        .order_by(Task.sort_order.asc()).all()

    # 随机任务（懒分配）
    _ensure_random_tasks(current_user.user_id, db)
    random_records = db.query(UserTaskProgress).filter(
        UserTaskProgress.user_id == current_user.user_id,
        UserTaskProgress.period_key == _today_key(),
    ).all()
    random_task_ids = [r.task_id for r in random_records]
    random_tasks = db.query(Task).filter(
        Task.task_id.in_(random_task_ids),
        Task.t_type == "random",
    ).all() if random_task_ids else []

    # 周常任务（M2：按置顶槽位排序，置顶任务套稀缺系数；M3：附带本人个性化任务）
    weekly.ensure_week_pool(db)
    slots = weekly.pinned_slots(db)
    weekly_tasks = db.query(Task).filter(
        Task.t_type == "weekly",
        Task.enabled == 1,
        (Task.personalized_for.is_(None)) | (Task.personalized_for == current_user.user_id),
    ).order_by(Task.sort_order.asc()).all()
    weekly_views = [_task_view(t, current_user.user_id, db, slots.get(t.task_id, 0)) for t in weekly_tasks]
    # 置顶在前，其余按原排序
    weekly_views.sort(key=lambda v: (0 if v["pinned"] else 1, v["pinned_slot"] or 99, v["task_id"]))

    return {
        "checkin": {
            "checked_in": bool(checkin),
            "continuous_days": checkin.continuous_days if checkin else 0,
            "today_reward": checkin.coin_reward if checkin else 0,
        },
        "daily": [_task_view(t, current_user.user_id, db) for t in daily_tasks],
        "random": [_task_view(t, current_user.user_id, db) for t in random_tasks],
        "weekly": weekly_views,
        "weekly_meta": {
            "week_key": weekly.week_key(),
            "pinned_count": len([s for s in slots.values() if s]),
            "claimed_total": weekly.weekly_claimed_total(current_user.user_id, db),
            "reward_cap": weekly.WEEKLY_REWARD_CAP,
        },
    }


@router.post("/random/refresh", summary="刷新随机任务（每日免费1次）")
async def refresh_random(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = _today_key()
    quota_task = _get_refresh_quota_task(db)

    # 当日刷新次数
    quota = db.query(UserTaskProgress).filter(
        UserTaskProgress.user_id == current_user.user_id,
        UserTaskProgress.task_id == quota_task.task_id,
        UserTaskProgress.period_key == today,
    ).first()

    if quota and quota.current >= quota_task.threshold:
        raise HTTPException(status_code=400, detail="今日免费刷新次数已用完")

    # 删除当天已分配的随机任务
    pool = db.query(Task).filter(Task.t_type == "random", Task.enabled == 1).all()
    pool_ids = [t.task_id for t in pool]
    if pool_ids:
        db.query(UserTaskProgress).filter(
            UserTaskProgress.user_id == current_user.user_id,
            UserTaskProgress.period_key == today,
            UserTaskProgress.task_id.in_(pool_ids),
        ).delete(synchronize_session=False)

    # 重新随机分配
    if pool:
        chosen = random.sample(pool, min(RANDOM_TASK_COUNT, len(pool)))
        for t in chosen:
            db.add(UserTaskProgress(
                user_id=current_user.user_id, task_id=t.task_id, period_key=today,
                current=0, completed=0, claimed=0,
            ))

    # 刷新配额 +1
    if quota:
        quota.current += 1
    else:
        db.add(UserTaskProgress(
            user_id=current_user.user_id, task_id=quota_task.task_id, period_key=today,
            current=1, completed=0, claimed=0,
        ))

    db.commit()

    # 返回刷新后的随机任务
    random_records = db.query(UserTaskProgress).filter(
        UserTaskProgress.user_id == current_user.user_id,
        UserTaskProgress.period_key == today,
        UserTaskProgress.task_id.in_(pool_ids),
    ).all() if pool_ids else []
    random_tasks = [db.query(Task).filter(Task.task_id == r.task_id).first() for r in random_records]

    return {
        "message": "刷新成功",
        "refresh_remaining": 0,
        "random": [_task_view(t, current_user.user_id, db) for t in random_tasks if t],
    }


@router.post("/{task_id}/claim", summary="领取任务奖励")
async def claim_task(
    task_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.task_id == task_id, Task.enabled == 1).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    period_key = _period_key_for(task)
    prog = db.query(UserTaskProgress).filter(
        UserTaskProgress.user_id == current_user.user_id,
        UserTaskProgress.task_id == task_id,
        UserTaskProgress.period_key == period_key,
    ).first()

    # 实时进度校验（M2：周任务的指标从 exam 域按周聚合；M3：个性化任务按知识点）
    current = _calc_metric(current_user.user_id, task.metric, db, task.metric_param)
    if current < task.threshold:
        raise HTTPException(status_code=400, detail="任务未完成")

    if prog and prog.claimed == 1:
        raise HTTPException(status_code=400, detail="奖励已领取")
    if prog and prog.expired == 1:
        raise HTTPException(status_code=400, detail="任务已失效")

    now = datetime.now()
    if not prog:
        prog = UserTaskProgress(
            user_id=current_user.user_id, task_id=task_id, period_key=period_key,
            current=0, completed=0, claimed=0,
        )
        db.add(prog)

    # 状态机：进行中 → 待判定 → 已发放
    prog.current = int(current)
    prog.pending_verify = 1
    prog.completed = 1
    prog.completed_at = now

    # M2：周任务按「基础值 × 难度 × 稀缺」发放，并受单任务 500 / 每周 900 封顶
    is_weekly = task.t_type == "weekly"
    if is_weekly:
        slot = weekly.pinned_slots(db).get(task.task_id, 0)
        reward = weekly.claimable_amount(task, current_user.user_id, db, weekly.PINNED_SCARCITY.get(slot))
        if reward <= 0:
            db.rollback()
            raise HTTPException(status_code=400, detail="本周金币奖励已达上限（900）")
    else:
        reward = task.reward_coins or 0

    prog.claimed = 1
    prog.claimed_at = now
    prog.pending_verify = 0

    source_type = "RANDOM_TASK" if task.t_type == "random" else "TASK"

    # 发币（2026-11-04 M1：统一走金币台账，确保生成批次以支持 12 个月到期清零）
    if reward > 0:
        grant_coins(
            db,
            current_user,
            reward,
            source_type=source_type,
            related_id=task_id,
            description=f"完成任务：{task.title}",
        )

    # M2：C 类场景任务完成时额外发券（把学习行为与兑换闭环）
    granted_coupon = None
    coupon_code = getattr(task, "coupon_code", None)
    if is_weekly and coupon_code:
        from ....api.v1.reward.coupons import grant_coupon

        grant = grant_coupon(db, current_user, coupon_code, source="TASK")
        if grant is not None:
            granted_coupon = coupon_code

    if task.reward_growth and task.reward_growth > 0:
        add_growth(db, current_user, task.reward_growth)

    db.commit()

    logger.info(
        "用户 %s 领取任务 %s，奖励 %s 金币（周任务=%s）",
        current_user.user_id,
        task.title,
        reward,
        is_weekly,
    )
    return {
        "message": "领取成功",
        "reward_coins": reward,
        "reward_base": task.reward_coins,
        "coupon_code": granted_coupon,
        "balance": current_user.total_coins,
    }
