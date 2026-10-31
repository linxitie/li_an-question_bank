"""
学习计划智能推荐 - 路由

提供：
- POST /api/plan/generate    学生提交信息，LLM 生成计划，批量写 StudyGoal
- GET  /api/plan/current     当前激活计划
- GET  /api/plan/{id}/tasks  某计划下所有任务
- POST /api/plan/task/{goal_id}/toggle  勾选/取消完成
- DELETE /api/plan/{id}      删除整个计划
"""

import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import PlanAdjustment, StudyGoal, SysUser, UserNotify, UserProfile
from ....services import llm_client, plan_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plan", tags=["学习计划"])

VALID_SUBJECTS = {"行测", "申论", "公专"}
# 前端展示名 → 后端规范名的别名映射（前端用"公安专业科目"，后端统一存"公专"）
SUBJECT_ALIASES = {"公安专业科目": "公专", "公安专业知识": "公专"}
VALID_LEVELS = {"零基础", "入门", "有基础", "冲刺"}
MAX_TASKS = 200


class AdjustRequest(BaseModel):
    instruction: str = Field(
        ..., min_length=1, max_length=300, description="调整要求（如：多留时间给公专）"
    )


class GenerateRequest(BaseModel):
    exam_date: str  # YYYY-MM-DD
    weak_subjects: List[str]  # ["行测","申论","公专"]
    daily_hours: float = Field(ge=1, le=8, description="每天可学时长 1-8 小时")
    level: str  # 零基础/有基础/冲刺

    @field_validator("weak_subjects")
    @classmethod
    def _check_subjects(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list) or not v:
            raise ValueError("请至少选择一个薄弱科目")
        if len(v) > len(VALID_SUBJECTS):
            raise ValueError(f"薄弱科目最多选择 {len(VALID_SUBJECTS)} 个")
        cleaned: List[str] = []
        for s in v:
            s = SUBJECT_ALIASES.get(s, s)  # 归一化前端展示名（如"公安专业科目"→"公专"）
            if not isinstance(s, str) or s not in VALID_SUBJECTS:
                raise ValueError(f"科目必须是 {'/'.join(sorted(VALID_SUBJECTS))} 之一")
            if s not in cleaned:
                cleaned.append(s)
        return cleaned

    @field_validator("level")
    @classmethod
    def _check_level(cls, v: str) -> str:
        if v not in VALID_LEVELS:
            raise ValueError(f"当前水平必须是 {'/'.join(VALID_LEVELS)} 之一")
        return v


@router.post("/generate", summary="AI 生成学习计划")
async def generate_plan(
    req: GenerateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. 组装用户输入
    try:
        exam_dt = datetime.strptime(req.exam_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="考试日期格式应为 YYYY-MM-DD")

    days_left = (exam_dt - datetime.now()).days
    if days_left <= 0:
        raise HTTPException(status_code=400, detail="考试日期必须晚于今天")

    user_input = (
        f"考试日期：{req.exam_date}（还剩 {days_left} 天）\n"
        f"薄弱科目：{'、'.join(req.weak_subjects)}\n"
        f"每天可学时长：{req.daily_hours} 小时\n"
        f"当前水平：{req.level}\n"
        "请生成复习计划。"
    )

    # 2. PlanAgent 画像推理增强：有画像则注入推理结论，无画像走原有表单参数
    profile_row = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if profile_row:
        profile_data = plan_agent.profile_from_row(profile_row)
        if profile_data:
            reasoning = plan_agent.reason(profile_data, days_left)
            user_input += "\n" + plan_agent.build_prompt_extra(reasoning)
            logger.info(
                "PlanAgent 推理注入: user=%s total_hours=%s weights=%s",
                current_user.user_id,
                reasoning["total_hours"],
                reasoning["subject_weights"],
            )

    # 2. 调 LLM
    try:
        raw = await llm_client.chat_plan(user_input)
    except llm_client.LLMClientError as e:
        raise HTTPException(status_code=503, detail=e.message)

    # 3. 解析 JSON（容错：去掉 ```json 包裹）
    plan_text = raw.strip()
    if plan_text.startswith("```"):
        plan_text = plan_text.strip("`")
        if plan_text.startswith("json"):
            plan_text = plan_text[4:]
    try:
        plan = json.loads(plan_text)
    except json.JSONDecodeError:
        logger.warning("LLM 返回非 JSON: %s", raw[:300])
        raise HTTPException(status_code=502, detail="AI 生成失败，请重试")

    # 4. 严格类型校验（LLM 输出是外部输入，必须先校验再落库）
    if not isinstance(plan, dict):
        raise HTTPException(status_code=502, detail="AI 返回格式异常，请重试")
    tasks = plan.get("daily_tasks", [])
    if not isinstance(tasks, list) or not tasks:
        raise HTTPException(status_code=502, detail="AI 未返回有效任务，请重试")
    if len(tasks) > MAX_TASKS:
        tasks = tasks[:MAX_TASKS]
    for t in tasks:
        if not isinstance(t, dict):
            raise HTTPException(status_code=502, detail="AI 返回任务格式异常，请重试")
    phases = plan.get("phases", [])
    if not isinstance(phases, list):
        phases = []
    summary = plan.get("summary", "")
    if not isinstance(summary, str):
        summary = ""
    tips = plan.get("tips", "")
    if not isinstance(tips, str):
        tips = ""

    # 5+6+7. 同一事务：软删旧计划 → 生成 plan_id → 批量写新任务 → 统一提交
    db.query(StudyGoal).filter(
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.plan_id.isnot(None),
        StudyGoal.status == 1,
    ).update({StudyGoal.status: 0})

    # plan_id：秒级时间戳，冲突则顺延
    plan_id = int(datetime.now().timestamp())
    while db.query(StudyGoal.goal_id).filter(StudyGoal.plan_id == plan_id).first():
        plan_id += 1

    # 元数据统一存 plan_meta；description 存任务原文（不再重复存 summary）
    plan_meta = json.dumps(
        {
            "summary": summary,
            "phases": phases,
            "tips": tips,
        },
        ensure_ascii=False,
    )

    # 每日任务闭环：金币按规则分配（10 基础 + 弱项科目 +5）；任务按顺序每 4 个滚动到后续日期
    _weak_set = set(req.weak_subjects)
    _TASKS_PER_DAY = 4
    from datetime import timedelta

    created = []
    for i, t in enumerate(tasks):
        task_name = str(t.get("task", "未命名任务"))[:100]
        task_time = str(t.get("time", ""))[:20]
        task_subject = str(t.get("subject", ""))[:20]
        task_date = (datetime.now() + timedelta(days=i // _TASKS_PER_DAY)).strftime("%Y-%m-%d")
        coin = 10 + (5 if task_subject in _weak_set else 0)
        goal = StudyGoal(
            user_id=current_user.user_id,
            title=f"[{task_time}] {task_name}" if task_time else task_name,
            description=str(t.get("task", ""))[:500],
            goal_type="CUSTOM",
            target_count=1,
            current_count=0,
            deadline=exam_dt,
            priority=2,
            is_completed=0,
            plan_id=plan_id,
            sort_order=i,
            plan_meta=plan_meta,
            task_date=task_date,
            coin_reward=coin,
            coin_claimed=0,
        )
        db.add(goal)
        created.append(goal)
    db.commit()

    return {
        "plan_id": plan_id,
        "days_left": days_left,
        "exam_date": req.exam_date,
        "task_count": len(created),
        "summary": summary,
        "phases": phases,
        "tips": tips,
        "progress": {"done": 0, "total": len(created), "percent": 0},
        "tasks": [
            {
                "goal_id": g.goal_id,
                "title": g.title,
                "is_completed": g.is_completed,
                "sort_order": g.sort_order,
                "task_date": g.task_date,
                "coin_reward": g.coin_reward,
            }
            for g in created
        ],
    }


@router.post("/adjust", summary="AI 调整计划（可干预）")
async def adjust_plan(
    req: AdjustRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """读取当前计划+今日任务+画像 → LLM 生成调整建议 → 落 PlanAdjustment + 更新 plan_meta.summary"""
    instruction = req.instruction
    if not instruction or not instruction.strip():
        raise HTTPException(status_code=400, detail="请说明你想怎么调整")

    # 1. 取当前计划（最新 plan_id）
    row = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.plan_id.isnot(None),
            StudyGoal.status == 1,
        )
        .order_by(StudyGoal.plan_id.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="还没有学习计划，请先生成")

    plan_id = row.plan_id
    try:
        meta = json.loads(row.plan_meta or "{}")
    except (ValueError, TypeError):
        meta = {}

    # 2. 今日任务 + 完成情况
    today = datetime.now().strftime("%Y-%m-%d")
    today_rows = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.task_date == today,
            StudyGoal.status == 1,
        )
        .all()
    )
    done = sum(1 for t in today_rows if t.is_completed == 1)
    today_titles = [t.title for t in today_rows[:10]]

    # 3. 画像摘要
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    profile_line = ""
    if profile:
        profile_line = (
            f"画像：目标分数{profile.target_score}、薄弱科目{profile.subject_weaknesses or '无'}、"
            f"每日{profile.daily_hours}小时"
        )

    # 4. 拼 prompt → LLM
    adjust_input = (
        f"现有备考计划摘要：{meta.get('summary', '')}\n"
        f"阶段规划：{json.dumps(meta.get('phases', []), ensure_ascii=False)[:300]}\n"
        f"今日任务（{len(today_rows)}项，已完成{done}项）：{'；'.join(today_titles)}\n"
        f"{profile_line}\n"
        f"用户要求调整：{instruction}\n"
        '请给出调整后的计划。只输出 JSON：{"summary": "调整后的计划摘要（100字内）", '
        '"adjustments": ["具体调整点1", "调整点2", ...]}。调整要具体可落地。'
    )
    try:
        raw = await llm_client.chat_plan(adjust_input)
    except llm_client.LLMClientError as e:
        raise HTTPException(status_code=503, detail=e.message)

    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("调整 LLM 返回非 JSON: %s", raw[:300])
        raise HTTPException(status_code=502, detail="AI 调整失败，请重试")
    if not isinstance(plan, dict):
        raise HTTPException(status_code=502, detail="AI 返回格式异常，请重试")
    new_summary = str(plan.get("summary", ""))[:200]
    adjustments = plan.get("adjustments", [])
    if not isinstance(adjustments, list):
        adjustments = []
    adjustments = [str(a)[:200] for a in adjustments[:10]]

    # 5. 落 PlanAdjustment + 应用到计划（更新 summary）
    record = PlanAdjustment(
        user_id=current_user.user_id,
        plan_id=plan_id,
        reason=instruction.strip()[:300],
        adjustment=json.dumps(
            {"summary": new_summary, "adjustments": adjustments}, ensure_ascii=False
        ),
        apply_flag=1,
    )
    db.add(record)
    if new_summary:
        meta["summary"] = new_summary
        meta["adjust_times"] = int(meta.get("adjust_times", 0)) + 1
        db.query(StudyGoal).filter(StudyGoal.plan_id == plan_id, StudyGoal.status == 1).update(
            {StudyGoal.plan_meta: json.dumps(meta, ensure_ascii=False)}
        )
    db.commit()
    db.refresh(record)

    return {
        "adjust_id": record.adjust_id,
        "summary": new_summary,
        "adjustments": adjustments,
        "message": "已按你的要求调整计划并应用" if new_summary else "调整建议已生成",
    }


@router.get("/current", summary="当前激活计划")
async def current_plan(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.plan_id.isnot(None),
            StudyGoal.status == 1,
        )
        .order_by(StudyGoal.plan_id.desc())
        .first()
    )
    if not row:
        return {"has_plan": False}

    tasks = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.plan_id == row.plan_id,
            StudyGoal.status == 1,
        )
        .order_by(StudyGoal.sort_order.asc())
        .all()
    )

    # 解析 plan_meta（存了 summary/phases/tips）
    meta = {}
    if tasks:
        try:
            meta = json.loads(tasks[0].plan_meta or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}

    exam_date = None
    if tasks and tasks[0].deadline:
        exam_date = tasks[0].deadline.strftime("%Y-%m-%d")
    days_left = (
        max((tasks[0].deadline - datetime.now()).days, 0) if tasks and tasks[0].deadline else 0
    )

    done = sum(1 for t in tasks if t.is_completed == 1)
    return {
        "has_plan": True,
        "plan_id": row.plan_id,
        "exam_date": exam_date,
        "days_left": days_left,
        "summary": meta.get("summary", ""),
        "phases": meta.get("phases", []),
        "tips": meta.get("tips", ""),
        "progress": {
            "done": done,
            "total": len(tasks),
            "percent": round(done / len(tasks) * 100) if tasks else 0,
        },
        "tasks": [
            {
                "goal_id": t.goal_id,
                "title": t.title,
                "is_completed": t.is_completed,
                "sort_order": t.sort_order,
            }
            for t in tasks
        ],
    }


@router.post("/task/{goal_id}/toggle", summary="勾选/取消任务完成")
async def toggle_task(
    goal_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    goal = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.goal_id == goal_id,
            StudyGoal.user_id == current_user.user_id,
        )
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="任务不存在")

    goal.is_completed = 0 if goal.is_completed == 1 else 1
    if goal.is_completed == 1:
        goal.completed_time = datetime.now()
        goal.current_count = 1
    else:
        goal.completed_time = None
        goal.current_count = 0
    db.commit()
    return {"goal_id": goal.goal_id, "is_completed": goal.is_completed}


@router.get("/{plan_id}/tasks", summary="某计划下所有任务")
async def plan_tasks(
    plan_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按 docstring 承诺实现：读取指定计划的所有任务（含进度与考试日期）"""
    tasks = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.plan_id == plan_id,
            StudyGoal.status == 1,
        )
        .order_by(StudyGoal.sort_order.asc())
        .all()
    )
    if not tasks:
        raise HTTPException(status_code=404, detail="计划不存在")
    meta = {}
    try:
        meta = json.loads(tasks[0].plan_meta or "{}")
    except (json.JSONDecodeError, TypeError):
        meta = {}
    exam_date = tasks[0].deadline.strftime("%Y-%m-%d") if tasks[0].deadline else None
    done = sum(1 for t in tasks if t.is_completed == 1)
    return {
        "plan_id": plan_id,
        "exam_date": exam_date,
        "summary": meta.get("summary", ""),
        "phases": meta.get("phases", []),
        "tips": meta.get("tips", ""),
        "progress": {
            "done": done,
            "total": len(tasks),
            "percent": round(done / len(tasks) * 100) if tasks else 0,
        },
        "tasks": [
            {
                "goal_id": t.goal_id,
                "title": t.title,
                "is_completed": t.is_completed,
                "sort_order": t.sort_order,
            }
            for t in tasks
        ],
    }


@router.delete("/{plan_id}", summary="删除整个计划")
async def delete_plan(
    plan_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.plan_id == plan_id,
            StudyGoal.status == 1,
        )
        .all()
    )
    if not tasks:
        raise HTTPException(status_code=404, detail="计划不存在")
    for t in tasks:
        t.status = 0
    db.commit()
    return {"deleted": len(tasks)}


# ==================== 模块4 v2 每日任务闭环 ====================


def _task_summary(g: StudyGoal) -> dict:
    return {
        "goal_id": g.goal_id,
        "title": g.title,
        "description": g.description,
        "is_completed": g.is_completed,
        "completed_time": g.completed_time.isoformat() if g.completed_time else None,
        "sort_order": g.sort_order,
        "task_date": g.task_date,
        "coin_reward": g.coin_reward or 0,
        "coin_claimed": g.coin_claimed or 0,
    }


@router.get("/today", summary="今日任务面板（含金币领取状态）")
async def today_tasks(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now().strftime("%Y-%m-%d")
    tasks = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.status == 1,
            StudyGoal.task_date == today,
        )
        .order_by(StudyGoal.sort_order.asc())
        .all()
    )
    total = len(tasks)
    done = sum(1 for t in tasks if t.is_completed == 1)
    claimed = sum(1 for t in tasks if t.coin_claimed == 1)
    total_coins = sum(t.coin_reward or 0 for t in tasks)
    return {
        "date": today,
        "total": total,
        "done": done,
        "claimed": claimed,
        "total_coins": total_coins,
        "tasks": [_task_summary(t) for t in tasks],
    }


@router.post("/task/{goal_id}/claim", summary="完成任务后领取金币（完成才可领）")
async def claim_task_coin(
    goal_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    goal = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.goal_id == goal_id,
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.status == 1,
        )
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="任务不存在")
    if goal.is_completed != 1:
        raise HTTPException(status_code=400, detail="任务尚未完成，完成后才可领取金币")
    if goal.coin_claimed == 1:
        raise HTTPException(status_code=400, detail="金币已领取，请勿重复领取")
    coin = goal.coin_reward or 0
    if coin <= 0:
        raise HTTPException(status_code=400, detail="该任务无金币奖励")

    # 跨域写入走公开契约发币（禁止直接实例化他域表）
    from ..reward.contract import grant_coins

    grant_coins(
        db,
        current_user,
        coin,
        source_type="TASK",
        related_id=goal.goal_id,
        description=f"完成每日任务：{goal.title}",
    )
    goal.coin_claimed = 1
    goal.update_time = datetime.now()
    db.commit()

    # 里程碑记忆（长期陪伴）：计划总完成率跨过 1/3、2/3、100% 时写一条
    try:
        _write_milestone(current_user.user_id, goal.plan_id, db)
    except Exception as e:
        logger.warning("里程碑写入失败: %s", e)

    return {
        "goal_id": goal.goal_id,
        "coin_reward": coin,
        "balance": current_user.total_coins,
        "message": f"领取成功，+{coin} 金币",
    }


def _write_milestone(user_id: int, plan_id, db: Session):
    """完成率首次跨过 1/3/2/3/100% 时写入 UserMemory(milestone)，幂等。"""
    from sqlalchemy import func

    from ....models.models import UserMemory

    if plan_id is None:
        return
    total = (
        db.query(func.count(StudyGoal.goal_id))
        .filter(StudyGoal.user_id == user_id, StudyGoal.plan_id == plan_id, StudyGoal.status == 1)
        .scalar()
    )
    done = (
        db.query(func.count(StudyGoal.goal_id))
        .filter(
            StudyGoal.user_id == user_id,
            StudyGoal.plan_id == plan_id,
            StudyGoal.status == 1,
            StudyGoal.is_completed == 1,
        )
        .scalar()
    )
    if not total:
        return
    pct = round(done / total * 100)
    for threshold, label in ((33, "完成计划 1/3"), (66, "完成计划 2/3"), (100, "完成全部计划")):
        if pct < threshold:
            continue
        content = f"备考里程碑：{label}（{done}/{total}）"
        exists = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.content == content)
            .first()
        )
        if exists:
            continue
        db.add(
            UserMemory(
                user_id=user_id,
                memory_type="milestone",
                content=content,
                source="milestone-auto",
                expire_at=None,
            )
        )
        db.commit()


@router.get("/notifies", summary="站内提醒列表（未完成任务提醒等）")
async def get_notifies(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = (
        db.query(UserNotify)
        .filter(UserNotify.user_id == current_user.user_id)
        .order_by(UserNotify.create_time.desc())
        .limit(20)
        .all()
    )
    return {
        "notifies": [
            {
                "notify_id": n.notify_id,
                "content": n.content,
                "notify_type": n.notify_type,
                "read_flag": n.read_flag,
                "create_time": n.create_time.isoformat() if n.create_time else None,
            }
            for n in items
        ]
    }


@router.post("/notify/{notify_id}/read", summary="标记提醒已读")
async def mark_notify_read(
    notify_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = (
        db.query(UserNotify)
        .filter(
            UserNotify.notify_id == notify_id,
            UserNotify.user_id == current_user.user_id,
        )
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="提醒不存在")
    n.read_flag = 1
    db.commit()
    return {"notify_id": n.notify_id, "read_flag": 1}
