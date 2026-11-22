"""
学习计划智能推荐 - 路由

提供：
- POST /api/plan/generate    学生提交信息，LLM 生成计划，批量写 StudyGoal
- GET  /api/plan/current     当前激活计划
- GET  /api/plan/{id}/tasks  某计划下所有任务
- POST /api/plan/task/{goal_id}/toggle  勾选/取消完成
- DELETE /api/plan/{id}      删除整个计划
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    PlanAdjustment,
    PracticeRecord,
    QuestionSubject,
    StudyGoal,
    SysUser,
    UserNotify,
    UserProfile,
    WrongQuestionPersonal,
)
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
        "", max_length=300, description="调整要求（如：多留时间给公专）；撤销时可为空"
    )
    undo: bool = Field(False, description="true=撤销最近一次已应用的调整（同一端点，不新增路由）")


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
    if not getattr(req, "undo", False) and (not instruction or not instruction.strip()):
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

    # 4. 撤销通道（不新增端点：同一 POST，body 里 undo=true）
    if getattr(req, "undo", False):
        return _undo_last_adjustment(db, current_user.user_id, plan_id, meta)

    # 5. 拼 prompt → LLM：要求输出"受限变更指令"，而不是只给一句话
    plan_rows = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.plan_id == plan_id,
            StudyGoal.status == 1,
        )
        .order_by(StudyGoal.sort_order.asc())
        .all()
    )
    tasks_brief = [
        {"goal_id": t.goal_id, "title": t.title, "date": t.task_date, "minutes": t.expected_minutes}
        for t in plan_rows[:30]
    ]
    adjust_input = (
        f"现有备考计划摘要：{meta.get('summary', '')}\n"
        f"阶段规划：{json.dumps(meta.get('phases', []), ensure_ascii=False)[:300]}\n"
        f"现有任务（最多30条）：{json.dumps(tasks_brief, ensure_ascii=False)[:1200]}\n"
        f"今日任务（{len(today_rows)}项，已完成{done}项）：{'；'.join(today_titles)}\n"
        f"{profile_line}\n"
        f"用户要求调整：{instruction}\n"
        "请只输出 JSON：{\"summary\": \"调整后方案摘要（100字内）\", \"ops\": [ ... ]}，ops 最多 8 条，"
        "每条只能是下列之一：\n"
        '{"op":"add","title":"任务标题","date":"YYYY-MM-DD","minutes":40}\n'
        '{"op":"move","goal_id":123,"to":"YYYY-MM-DD"}\n'
        '{"op":"modify","goal_id":124,"minutes":45}\n'
        '{"op":"remove","goal_id":125}\n'
        "约束：date/to 必须是今天起 30 天内；改期只动未完成任务；不得编造 goal_id；"
        "若用户要求不明确，只给 summary、ops 给空数组。"
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
    ops = plan.get("ops", [])
    if not isinstance(ops, list):
        ops = []
    ops = ops[:8]

    # 6. 事务应用：变更 + 快照（供撤销）+ 排课重算
    applied, snapshot, rejected = _apply_adjust_ops(
        db, current_user.user_id, plan_id, plan_rows, ops
    )
    meta["summary"] = new_summary or meta.get("summary", "")
    meta["adjust_times"] = int(meta.get("adjust_times", 0)) + 1
    meta["last_adjust_at"] = datetime.now().isoformat(timespec="seconds")
    db.query(StudyGoal).filter(StudyGoal.plan_id == plan_id, StudyGoal.status == 1).update(
        {StudyGoal.plan_meta: json.dumps(meta, ensure_ascii=False)}
    )
    record = PlanAdjustment(
        user_id=current_user.user_id,
        plan_id=plan_id,
        reason=instruction.strip()[:300],
        adjustment=json.dumps(
            {"summary": new_summary, "ops": ops, "applied": applied, "snapshot": snapshot},
            ensure_ascii=False,
        ),
        apply_flag=1,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 变更后重算排课（任务/日期变了）
    schedule_recomputed = False
    try:
        refreshed = (
            db.query(StudyGoal)
            .filter(
                StudyGoal.user_id == current_user.user_id,
                StudyGoal.plan_id == plan_id,
                StudyGoal.status == 1,
            )
            .order_by(StudyGoal.sort_order.asc())
            .all()
        )
        if refreshed:
            _ensure_schedule(db, current_user.user_id, plan_id, refreshed, meta)
            schedule_recomputed = True
    except Exception as exc:  # noqa: BLE001 - 排课失败不影响调整结果
        logger.warning("调整后重算排课失败: %s", exc)

    return {
        "adjust_id": record.adjust_id,
        "summary": new_summary,
        "applied": applied,
        "rejected": rejected,
        "applied_count": len(applied),
        "schedule_recomputed": schedule_recomputed,
        "message": f"已应用 {len(applied)} 项调整" if applied else "AI 只给了建议，未改动任务",
        "undoable": bool(applied),
    }


# ---------- P2：调整指令的校验、应用与撤销 ----------
_VALID_OPS = {"add", "move", "modify", "remove"}


def _recent_adjustments(db: Session, user_id: int, plan_id: int, limit: int = 3) -> list:
    """最近几条调整记录（供前端展示"本次调整了什么"，退出重进也能看到）。"""
    rows = (
        db.query(PlanAdjustment)
        .filter(PlanAdjustment.user_id == user_id, PlanAdjustment.plan_id == plan_id)
        .order_by(PlanAdjustment.adjust_id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        try:
            payload = json.loads(r.adjustment or "{}")
        except ValueError:
            payload = {}
        applied = payload.get("applied") or payload.get("reverted") or []
        out.append(
            {
                "adjust_id": r.adjust_id,
                "reason": r.reason,
                "applied": bool(r.apply_flag == 1),
                "summary": payload.get("summary", ""),
                "changes": applied[:8],
                "change_count": len(applied),
                "undo_of": payload.get("undo_of"),
                "created_at": r.create_time.isoformat() if getattr(r, "create_time", None) else None,
            }
        )
    return out


def _parse_day(value) -> str | None:
    try:
        day = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    today = datetime.now().date()
    if day < today or (day - today).days > 30:
        return None
    return day.strftime("%Y-%m-%d")


def _apply_adjust_ops(db: Session, user_id: int, plan_id: int, tasks, ops) -> tuple:
    """按受限指令修改 study_goal；返回 (applied, snapshot, rejected)。"""
    by_id = {t.goal_id: t for t in tasks}
    applied, snapshot, rejected = [], [], []
    next_sort = (max((t.sort_order or 0) for t in tasks) + 1) if tasks else 0
    meta_template = tasks[0].plan_meta if tasks else None

    for raw_op in ops:
        if not isinstance(raw_op, dict):
            rejected.append({"op": str(raw_op)[:40], "why": "不是对象"})
            continue
        op = str(raw_op.get("op") or "").strip().lower()
        if op not in _VALID_OPS:
            rejected.append({"op": op or "?", "why": "未知指令"})
            continue

        if op == "add":
            title = str(raw_op.get("title") or "").strip()[:200]
            day = _parse_day(raw_op.get("date"))
            minutes = int(raw_op.get("minutes") or 30)
            if not title or not day:
                rejected.append({"op": "add", "why": "标题或日期不合法"})
                continue
            minutes = max(10, min(120, minutes))
            goal = StudyGoal(
                user_id=user_id,
                title=title,
                target_count=0,
                plan_id=plan_id,
                sort_order=next_sort,
                task_date=day,
                expected_minutes=minutes,
                is_completed=0,
                status=1,
                plan_meta=meta_template,
            )
            db.add(goal)
            db.flush()
            next_sort += 1
            snapshot.append({"op": "add", "goal_id": goal.goal_id})
            applied.append({"op": "add", "goal_id": goal.goal_id, "title": title, "date": day, "minutes": minutes})
            continue

        goal_id = raw_op.get("goal_id")
        goal = by_id.get(goal_id) if isinstance(goal_id, int) else None
        if goal is None:
            rejected.append({"op": op, "why": f"任务不存在或不属于本计划: {goal_id}"})
            continue

        if op == "move":
            day = _parse_day(raw_op.get("to"))
            if not day:
                rejected.append({"op": "move", "goal_id": goal_id, "why": "目标日期不合法"})
                continue
            if goal.is_completed == 1:
                rejected.append({"op": "move", "goal_id": goal_id, "why": "已完成任务不改期"})
                continue
            snapshot.append({"op": "move", "goal_id": goal.goal_id, "from": goal.task_date})
            applied.append({"op": "move", "goal_id": goal.goal_id, "title": goal.title, "from": goal.task_date, "to": day})
            goal.task_date = day
        elif op == "modify":
            minutes = int(raw_op.get("minutes") or 0)
            if minutes <= 0:
                rejected.append({"op": "modify", "goal_id": goal_id, "why": "时长不合法"})
                continue
            old = int(goal.expected_minutes or 0)
            minutes = max(10, min(120, minutes))
            snapshot.append({"op": "modify", "goal_id": goal.goal_id, "minutes_from": old})
            applied.append({"op": "modify", "goal_id": goal.goal_id, "title": goal.title, "minutes_from": old, "minutes_to": minutes})
            goal.expected_minutes = minutes
        elif op == "remove":
            snapshot.append({"op": "remove", "goal_id": goal.goal_id, "status": goal.status})
            applied.append({"op": "remove", "goal_id": goal.goal_id, "title": goal.title})
            goal.status = 0

    db.flush()
    return applied, snapshot, rejected


def _undo_last_adjustment(db: Session, user_id: int, plan_id: int, meta: dict) -> dict:
    """撤销最近一次已应用的调整（同端点 body undo=true，不新增路由）。"""
    record = (
        db.query(PlanAdjustment)
        .filter(
            PlanAdjustment.user_id == user_id,
            PlanAdjustment.plan_id == plan_id,
            PlanAdjustment.apply_flag == 1,
        )
        .order_by(PlanAdjustment.adjust_id.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="没有可撤销的调整记录")
    try:
        payload = json.loads(record.adjustment or "{}")
    except ValueError:
        payload = {}
    snapshot = payload.get("snapshot") or []

    reverted = []
    for item in snapshot:
        op = item.get("op")
        goal = (
            db.query(StudyGoal)
            .filter(StudyGoal.goal_id == item.get("goal_id"), StudyGoal.user_id == user_id)
            .first()
        )
        if goal is None:
            continue
        if op == "add":
            goal.status = 0
        elif op == "move" and item.get("from"):
            goal.task_date = item["from"]
        elif op == "modify" and item.get("minutes_from"):
            goal.expected_minutes = int(item["minutes_from"])
        elif op == "remove":
            goal.status = 1
        reverted.append({"op": op, "goal_id": goal.goal_id, "title": goal.title})

    record.apply_flag = 0
    undo_record = PlanAdjustment(
        user_id=user_id,
        plan_id=plan_id,
        reason=f"撤销调整 #{record.adjust_id}"[:300],
        adjustment=json.dumps({"undo_of": record.adjust_id, "reverted": reverted}, ensure_ascii=False),
        apply_flag=1,
    )
    db.add(undo_record)
    db.commit()
    db.refresh(undo_record)

    try:
        refreshed = (
            db.query(StudyGoal)
            .filter(
                StudyGoal.user_id == user_id,
                StudyGoal.plan_id == plan_id,
                StudyGoal.status == 1,
            )
            .order_by(StudyGoal.sort_order.asc())
            .all()
        )
        if refreshed:
            _ensure_schedule(db, user_id, plan_id, refreshed, meta)
    except Exception as exc:  # noqa: BLE001
        logger.warning("撤销后重算排课失败: %s", exc)

    return {
        "adjust_id": undo_record.adjust_id,
        "undo_of": record.adjust_id,
        "reverted": reverted,
        "reverted_count": len(reverted),
        "message": f"已撤销上一次调整（{len(reverted)} 项）",
        "undoable": False,
    }


# ==================== 智能排课（P1：按人按天生成、可动态重算） ====================
# 设计要点：
#   - 排课存 plan_meta["schedule"]（JSON，零迁移），带 date + sig，任务或日期一变就重算；
#   - 规则优先（不依赖 LLM）：任务科目/预计分钟 + 画像每日时长 + 待复习错题数；
#   - 输出三段：上午（资料/数量等重计算）/ 下午（判断/言语）/ 晚上（申论/公专 + 错题复习）；
#   - 每项带 goal_id（可勾选同步）或 wrong 复习标记，前端据此渲染并回写。
SCHEDULE_VERSION = 1

_SCHEDULE_PERIODS = (
    {"key": "morning", "label": "上午 9:00-12:00", "cap": 180, "subjects": ("行测",)},
    {"key": "afternoon", "label": "下午 14:00-17:00", "cap": 180, "subjects": ("行测", "公专")},
    {"key": "evening", "label": "晚上 19:00-21:30", "cap": 150, "subjects": ("申论", "公专")},
)

_SUBJECT_KEYWORDS = (
    ("行测", ("行测", "言语", "资料", "判断", "数量", "常识", "推理", "分析")),
    ("申论", ("申论", "范文", "归纳", "大作文", "作文", "概括")),
    ("公专", ("公专", "公安", "法律", "执法", "警务", "专业科目")),
)


def _subject_of(title: str) -> str:
    for name, keys in _SUBJECT_KEYWORDS:
        if any(k in (title or "") for k in keys):
            return name
    return "综合"


def _load_plan_meta(tasks) -> dict:
    for t in tasks:
        if isinstance(t.plan_meta, str) and t.plan_meta:
            try:
                data = json.loads(t.plan_meta)
                if isinstance(data, dict):
                    return data
            except (ValueError, TypeError):
                continue
    return {}


def _save_plan_meta(db: Session, plan_id: int, user_id: int, meta: dict) -> None:
    db.query(StudyGoal).filter(
        StudyGoal.plan_id == plan_id,
        StudyGoal.user_id == user_id,
        StudyGoal.status == 1,
    ).update({StudyGoal.plan_meta: json.dumps(meta, ensure_ascii=False)})


def _schedule_sig(tasks, date_str: str, daily_hours: float) -> str:
    raw = "|".join(
        [date_str, str(daily_hours)]
        + [f"{t.goal_id}:{t.title}:{t.task_date}:{t.is_completed}" for t in tasks]
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _due_review_count(db: Session, user_id: int) -> int:
    """待复习错题数（只读错题域；口径与 /growth/review/summary 一致：未排程也算今天到期）。"""
    from sqlalchemy import func as _func

    return (
        db.query(_func.count(WrongQuestionPersonal.wrong_id))
        .filter(
            WrongQuestionPersonal.user_id == user_id,
            WrongQuestionPersonal.status == 1,
            WrongQuestionPersonal.collection_type == "WRONG",
            or_(
                WrongQuestionPersonal.next_review_at.is_(None),
                WrongQuestionPersonal.next_review_at <= datetime.now(),
            ),
        )
        .scalar()
        or 0
    )


def _build_schedule(db: Session, user_id: int, tasks, date_str: str | None = None) -> dict:
    """生成某日排课（纯规则，幂等）。返回 {date, slots, planned_minutes, budget_minutes, ...}。"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    daily_hours = float(getattr(profile, "daily_hours", 0) or 0) or 3.0
    budget = int(round(daily_hours * 60 * 0.9))

    today_tasks = [t for t in tasks if (t.task_date or "") == date_str]
    slots = []
    remaining_budget = budget
    used: dict[str, int] = {p["key"]: 0 for p in _SCHEDULE_PERIODS}

    def _pick_period(subject: str) -> dict:
        # 先找"科目匹配且还有余量"的时段；都满则取余量最大的
        for p in _SCHEDULE_PERIODS:
            if subject in p["subjects"] and used[p["key"]] < p["cap"]:
                return p
        return min(_SCHEDULE_PERIODS, key=lambda p: used[p["key"]] / max(p["cap"], 1))

    for t in today_tasks:
        subject = _subject_of(t.title)
        period = _pick_period(subject)
        minutes = int(getattr(t, "expected_minutes", 0) or 0) or 30
        minutes = max(10, min(60, minutes))
        if remaining_budget <= 0:
            break
        avail = period["cap"] - used[period["key"]]
        if avail <= 0:
            period = max(_SCHEDULE_PERIODS, key=lambda p: p["cap"] - used[p["key"]])
            avail = max(0, period["cap"] - used[period["key"]])
        if avail <= 0:
            break
        minutes = max(10, min(minutes, remaining_budget, avail))
        used[period["key"]] += minutes
        remaining_budget -= minutes
        slots.append(
            {
                "period": period["key"],
                "period_label": period["label"],
                "kind": "task",
                "goal_id": t.goal_id,
                "subject": subject,
                "title": t.title,
                "minutes": minutes,
                "done": int(t.is_completed or 0) == 1,
            }
        )

    # 错题复习项（若今日有到期错题）：晚上时段，最多 30 分钟
    due = _due_review_count(db, user_id) if today_tasks else 0
    if due > 0 and remaining_budget > 0:
        minutes = min(30, due * 5, remaining_budget)
        slots.append(
            {
                "period": "evening",
                "period_label": "晚上 19:00-21:30",
                "kind": "review",
                "goal_id": None,
                "subject": "错题复习",
                "title": f"复习今日到期错题 {due} 道",
                "minutes": minutes,
                "done": False,
            }
        )
        remaining_budget -= minutes

    planned = sum(s["minutes"] for s in slots)
    grouped = []
    for p in _SCHEDULE_PERIODS:
        items = [s for s in slots if s["period"] == p["key"]]
        if not items:
            continue
        grouped.append(
            {
                "period": p["key"],
                "label": p["label"],
                "planned_minutes": sum(i["minutes"] for i in items),
                "items": items,
            }
        )

    return {
        "date": date_str,
        "version": SCHEDULE_VERSION,
        "sig": _schedule_sig(tasks, date_str, daily_hours),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "budget_minutes": budget,
        "planned_minutes": planned,
        "daily_hours": daily_hours,
        "slots": grouped,
        "hint": "" if today_tasks else "今天没有排任务，先去生成或调整计划",
    }


def _ensure_schedule(
    db: Session, user_id: int, plan_id: int, tasks, meta: dict, date_str: str | None = None
) -> dict:
    """确保当天排课存在且与最新任务一致；不一致才重算并落库（幂等）。"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    daily_hours = float(getattr(profile, "daily_hours", 0) or 0) or 3.0
    sig = _schedule_sig(tasks, date_str, daily_hours)
    current = meta.get("schedule") if isinstance(meta.get("schedule"), dict) else None
    if current and current.get("date") == date_str and current.get("sig") == sig:
        return current
    schedule = _build_schedule(db, user_id, tasks, date_str)
    meta["schedule"] = schedule
    _save_plan_meta(db, plan_id, user_id, meta)
    db.commit()
    return schedule


# ---- 能力画像（P1：与"我的"页雷达同一份数据，供学习计划页展示） ----
_LEVEL_SCORES = {
    "零基础": 15,
    "入门": 30,
    "了解一点": 35,
    "有基础": 60,
    "比较稳": 80,
    "冲刺": 90,
    "冲刺提分": 90,
}


def _build_capability(db: Session, user_id: int, profile, done: int, total: int) -> dict:
    """六维能力 + 分科正确率明细（breakdown），数据都来自本域或只读接入。"""
    level = getattr(profile, "self_level", None) if profile else None
    daily_hours = float(getattr(profile, "daily_hours", 0) or 0) if profile else 0.0
    target_score = getattr(profile, "target_score", None) if profile else None
    exam_date = getattr(profile, "exam_date", None) if profile else None
    target_post = getattr(profile, "target_post", None) if profile else None
    target_region = getattr(profile, "target_region", None) if profile else None
    weaknesses = _json_list(getattr(profile, "subject_weaknesses", None) if profile else None)
    intro = str(getattr(profile, "self_intro", "") or "") if profile else ""

    goal_score = (
        (40 if target_score else 0)
        + (40 if exam_date else 0)
        + (20 if (target_post or target_region) else 0)
    )
    plan_percent = round(done / total * 100) if total else 0
    dims = [
        {
            "key": "level",
            "label": "基础水平",
            "value": _LEVEL_SCORES.get(str(level or ""), 30),
            "available": bool(level),
            "source": "画像·当前水平",
        },
        {
            "key": "hours",
            "label": "时间投入",
            "value": min(100, round(daily_hours / 10 * 100)),
            "available": daily_hours > 0,
            "source": "画像·每日时长",
        },
        {
            "key": "goal",
            "label": "目标清晰",
            "value": goal_score,
            "available": goal_score > 0,
            "source": "画像·目标分数/日期/岗位",
        },
        {
            "key": "weak",
            "label": "弱项认知",
            "value": min(100, len(weaknesses) * 25),
            "available": bool(weaknesses),
            "source": "画像·薄弱科目",
        },
        {
            "key": "intro",
            "label": "自我表达",
            "value": min(100, round(len(intro) / 120 * 100)),
            "available": bool(intro),
            "source": "画像·自我描述",
        },
        {
            "key": "plan",
            "label": "计划执行",
            "value": plan_percent,
            "available": total > 0,
            "source": "计划完成率",
        },
    ]
    avg = round(sum(d["value"] for d in dims) / len(dims))
    return {
        "dims": dims,
        "avg": avg,
        "plan_percent": plan_percent,
        "breakdown": _subject_accuracy(db, user_id),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            data = json.loads(value)
            return data if isinstance(data, list) else []
        except ValueError:
            return []
    return []


def _subject_accuracy(db: Session, user_id: int) -> list:
    """近 30 天各科正确率（只读 practice_record，用于"哪科在进步/退步"）。"""
    from sqlalchemy import func as _func

    since = datetime.now() - timedelta(days=30)
    rows = (
        db.query(
            PracticeRecord.subject_id,
            _func.count(PracticeRecord.record_id),
            _func.sum(PracticeRecord.is_correct),
        )
        .filter(PracticeRecord.user_id == user_id, PracticeRecord.practice_time >= since)
        .group_by(PracticeRecord.subject_id)
        .all()
    )
    names = {
        sid: name
        for sid, name in db.query(QuestionSubject.subject_id, QuestionSubject.subject_name).all()
    }
    out = []
    for sid, attempts, correct in rows:
        if not attempts:
            continue
        out.append(
            {
                "subject_id": sid,
                "subject": names.get(sid) or f"科目{sid}",
                "attempts": int(attempts),
                "accuracy": round((int(correct or 0) / int(attempts)) * 100),
            }
        )
    out.sort(key=lambda x: x["accuracy"])
    return out


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
    total = len(tasks)
    percent = round(done / total * 100) if total else 0

    # P1：按人按天排课（任务/日期/画像变化即重算）+ 六维能力（与"我的"雷达同源）
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    schedule = _ensure_schedule(db, current_user.user_id, row.plan_id, tasks, meta)
    capability = _build_capability(db, current_user.user_id, profile, done, total)

    # 动态调整建议：根据完成率自动给出建议
    adjustment_suggestion = None
    if total > 0:
        if percent >= 100:
            adjustment_suggestion = {
                "type": "increase",
                "message": "🎉 今日任务全部完成！要不要明天多加一点挑战？",
            }
        elif percent <= 30:
            adjustment_suggestion = {
                "type": "decrease",
                "message": "💪 今天任务有点难完成？要不要明天少安排一点？",
            }

    return {
        "has_plan": True,
        "plan_id": row.plan_id,
        "exam_date": exam_date,
        "days_left": days_left,
        "schedule": schedule,
        "capability": capability,
        "recent_adjustments": _recent_adjustments(db, current_user.user_id, row.plan_id),
        "adjustment_suggestion": adjustment_suggestion,
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

    # 2026-11-15：勾选完成即自动发币（与 badge_task 对齐）。
    # 幂等靠 coin_claimed：取消勾选再勾选不会重复发，也不会因为玩家反复 toggle 刷币。
    auto_coins = 0
    if goal.is_completed == 1:
        from ....services.goal_task_reward import auto_claim_goal_task

        auto_coins = auto_claim_goal_task(db, current_user, goal)
    db.commit()

    if auto_coins > 0:
        # 里程碑记忆（长期陪伴）：与手动领取保持同一口径
        try:
            _write_milestone(current_user.user_id, goal.plan_id, db)
            db.commit()
        except Exception as e:
            logger.warning("里程碑写入失败: %s", e)

    # P1：任务勾选后重算当日排课（完成状态直接反映到排课项）
    schedule_recomputed = False
    if goal.plan_id is not None:
        try:
            plan_tasks_rows = (
                db.query(StudyGoal)
                .filter(
                    StudyGoal.user_id == current_user.user_id,
                    StudyGoal.plan_id == goal.plan_id,
                    StudyGoal.status == 1,
                )
                .order_by(StudyGoal.sort_order.asc())
                .all()
            )
            if plan_tasks_rows:
                meta = _load_plan_meta(plan_tasks_rows)
                _ensure_schedule(db, current_user.user_id, goal.plan_id, plan_tasks_rows, meta)
                schedule_recomputed = True
        except Exception as exc:  # noqa: BLE001 - 排课失败不影响任务勾选
            logger.warning("重算排课失败: %s", exc)

    return {
        "goal_id": goal.goal_id,
        "is_completed": goal.is_completed,
        "coin_claimed": goal.coin_claimed,
        "auto_claimed_coins": auto_coins,
        "balance": current_user.total_coins,
        "schedule_recomputed": schedule_recomputed,
    }


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
    # P1：今日排课（与 /plan/current 同源；首页/移动端可直接复用 slots）
    schedule = None
    plan_id = next((t.plan_id for t in tasks if t.plan_id), None)
    if plan_id is not None:
        plan_rows = (
            db.query(StudyGoal)
            .filter(
                StudyGoal.user_id == current_user.user_id,
                StudyGoal.plan_id == plan_id,
                StudyGoal.status == 1,
            )
            .order_by(StudyGoal.sort_order.asc())
            .all()
        )
        try:
            meta = _load_plan_meta(plan_rows)
            schedule = _ensure_schedule(db, current_user.user_id, plan_id, plan_rows, meta)
        except Exception as exc:  # noqa: BLE001
            logger.warning("今日排课生成失败: %s", exc)
    return {
        "date": today,
        "total": total,
        "done": done,
        "claimed": claimed,
        "total_coins": total_coins,
        "schedule": schedule,
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
