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
from ....models.models import StudyGoal, SysUser, UserProfile
from ....services import llm_client
from ....services import plan_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plan", tags=["学习计划"])

VALID_SUBJECTS = {"行测", "申论", "公专"}
# 前端展示名 → 后端规范名的别名映射（前端用"公安专业科目"，后端统一存"公专"）
SUBJECT_ALIASES = {"公安专业科目": "公专", "公安专业知识": "公专"}
VALID_LEVELS = {"零基础", "入门", "有基础", "冲刺"}
MAX_TASKS = 200


class GenerateRequest(BaseModel):
    exam_date: str            # YYYY-MM-DD
    weak_subjects: List[str]  # ["行测","申论","公专"]
    daily_hours: float = Field(ge=1, le=8, description="每天可学时长 1-8 小时")
    level: str                # 零基础/有基础/冲刺

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
    profile_row = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.user_id)
        .first()
    )
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
    plan_meta = json.dumps({
        "summary": summary,
        "phases": phases,
        "tips": tips,
    }, ensure_ascii=False)
    created = []
    for i, t in enumerate(tasks):
        task_name = str(t.get("task", "未命名任务"))[:100]
        task_time = str(t.get("time", ""))[:20]
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
            }
            for g in created
        ],
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
    days_left = max((tasks[0].deadline - datetime.now()).days, 0) if tasks and tasks[0].deadline else 0

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
