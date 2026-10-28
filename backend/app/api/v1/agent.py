# -*- coding: utf-8 -*-
"""
模块7 v2 - 工作模式：任务清单 + 结构化执行
点选任务 → 收集参数 → 对应 Agent + 档案上下文 → LLM 生成结构化结果
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import SysUser, StudyGoal
from ...services import llm_client
from ...services.agent_router import agent_system_prompt, assemble_context, extract_memories, retrieve_knowledge, build_trajectory, AGENT_META

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["联考小智-工作模式"])

# ==================== 工作模式任务清单 ====================
AGENT_TASKS: List[Dict] = [
    {
        "task_id": "xingce_diagnose",
        "title": "行测错题诊断",
        "agent": "xingce",
        "desc": "基于你的错题本与薄弱点，诊断行测短板并给出提升方案",
        "fields": [
            {"key": "weak_type", "label": "薄弱题型（选填）", "type": "text", "required": False, "placeholder": "如：资料分析、图形推理"},
        ],
    },
    {
        "task_id": "interview_sim",
        "title": "模拟一场面试",
        "agent": "interview",
        "desc": "出一道结构化面试题 + 示范答题框架 + 一个追问",
        "fields": [
            {"key": "qtype", "label": "题目类型", "type": "select", "required": True,
             "options": ["综合分析", "应急处突", "组织管理", "人际沟通"]},
        ],
    },
    {
        "task_id": "shenlun_week",
        "title": "生成一周申论计划",
        "agent": "shenlun",
        "desc": "按周生成申论学习计划，含每日任务，可一键写入今日任务",
        "fields": [
            {"key": "focus", "label": "本周重点（选填）", "type": "text", "required": False, "placeholder": "如：归纳概括专项"},
        ],
    },
    {
        "task_id": "gongzhuan_fatiao",
        "title": "公专法条梳理",
        "agent": "gongzhuan",
        "desc": "梳理指定法规的高频考点、情景题要点与记忆口诀",
        "fields": [
            {"key": "law", "label": "法规", "type": "select", "required": True,
             "options": ["治安管理处罚法", "人民警察法", "刑法", "公安机关办理刑事案件程序规定"]},
        ],
    },
    {
        "task_id": "choose_post_advice",
        "title": "选岗建议",
        "agent": "choose_post",
        "desc": "结合你的画像档案，给出岗位筛选思路与竞争分析建议",
        "fields": [
            {"key": "region", "label": "意向地区（选填）", "type": "text", "required": False, "placeholder": "如：山东、北京"},
        ],
    },
]


class AgentRunRequest(BaseModel):
    task_id: str
    params: Optional[Dict[str, str]] = Field(default_factory=dict)


class ImportTodayRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    content: Optional[str] = Field(None, max_length=500)
    coin_reward: int = Field(10, ge=0, le=100)


@router.post("/import-today", summary="工作台结果一键写入今日任务（模块4联动）")
async def import_to_today(
    req: ImportTodayRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """把工作台生成的结果写入学习计划今日任务：完成可领金币，进入模块4每日闭环"""
    today = date.today().isoformat()
    # 当日任务排序：取当日最大 sort_order + 1
    max_sort = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == current_user.user_id,
            StudyGoal.task_date == today,
            StudyGoal.status == 1,
        )
        .order_by(StudyGoal.sort_order.desc())
        .first()
    )
    sort_order = (max_sort.sort_order + 1) if max_sort and max_sort.sort_order else 0

    goal = StudyGoal(
        user_id=current_user.user_id,
        title=req.title.strip(),
        description=(req.content or "").strip(),
        goal_type="DAILY",
        target_count=1,
        current_count=0,
        subject_mode=0,
        is_completed=0,
        status=1,
        task_date=today,
        coin_reward=req.coin_reward,
        coin_claimed=0,
        sort_order=sort_order,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return {
        "goal_id": goal.goal_id,
        "task_date": today,
        "title": goal.title,
        "coin_reward": goal.coin_reward,
        "message": f"已写入今日任务，完成可领取 {goal.coin_reward} 金币",
    }


@router.get("/memories", summary="长期记忆列表（记忆管理）")
async def agent_memories(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ...models.models import UserMemory
    items = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == current_user.user_id)
        .order_by(UserMemory.create_time.desc())
        .limit(100)
        .all()
    )
    return {
        "memories": [
            {
                "memory_id": m.memory_id,
                "memory_type": m.memory_type,
                "content": m.content,
                "source": m.source,
                "create_time": m.create_time.isoformat() if m.create_time else None,
            }
            for m in items
        ]
    }


@router.delete("/memory/{memory_id}", summary="删除一条长期记忆")
async def agent_memory_delete(
    memory_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ...models.models import UserMemory
    row = (
        db.query(UserMemory)
        .filter(UserMemory.memory_id == memory_id, UserMemory.user_id == current_user.user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="记忆不存在")
    db.delete(row)
    db.commit()
    return {"message": "已删除该记忆"}


@router.get("/trajectory", summary="备考轨迹（长期陪伴：进度/打卡/里程碑）")
async def agent_trajectory(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        text = build_trajectory(current_user.user_id, db)
    except Exception as e:
        logger.warning("轨迹读取失败: %s", e)
        text = ""
    return {"trajectory": text, "has_trajectory": bool(text)}


@router.get("/tasks", summary="工作模式任务清单")
async def list_agent_tasks():
    return {"tasks": AGENT_TASKS}


@router.post("/run", summary="执行工作模式任务")
async def run_agent_task(
    req: AgentRunRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = next((t for t in AGENT_TASKS if t["task_id"] == req.task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    agent_id = task["agent"]
    agent_prompt = agent_system_prompt(agent_id)

    # 档案上下文（只取摘要）
    extra = agent_prompt
    try:
        ctx = assemble_context(current_user.user_id, db)
        extract_memories(current_user.user_id, db)
        if ctx:
            extra = agent_prompt + "\n\n" + ctx
    except Exception as e:
        logger.warning("档案装配失败: %s", e)

    # 拼任务 prompt：任务要求 + 用户参数
    param_lines = []
    for f in task["fields"]:
        val = req.params.get(f["key"], "")
        if val:
            param_lines.append(f"{f['label']}：{val}")
    params_text = "；".join(param_lines) if param_lines else "无额外参数"
    user_prompt = (
        f"【工作模式任务】{task['title']}\n"
        f"任务要求：{task['desc']}\n"
        f"用户提供的参数：{params_text}\n"
        "请按任务要求给出结构化、可落地的结果；需要分点时分点；涉及法条注明'以现行有效法条为准'。"
    )

    # 知识库参考（Phase3 自生长知识库）
    try:
        kb = retrieve_knowledge(current_user.user_id, db, user_prompt)
        if kb:
            extra = extra + "\n\n" + kb
    except Exception as e:
        logger.warning("知识库检索失败: %s", e)

    try:
        reply = await llm_client.chat(
            messages=[{"role": "user", "content": user_prompt}],
            scene="qa",
            extra_system=extra,
        )
    except llm_client.LLMClientError as e:
        raise HTTPException(status_code=503, detail=e.message)

    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "agent": agent_id,
        "agent_name": AGENT_META.get(agent_id, {}).get("name", "联考小智"),
        "reply": reply,
    }
