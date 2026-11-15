# 联考小智 · 工作台能力（模块7）
# 提供两件事：
#   1) 真流式对话（SSE token 增量）
#   2) 带工具调用的执行循环（读知识库 / 统计 / 计算），可多步完成复杂问题
# 全部为新增端点，不改既有 /api/llm/* 契约（R11 只增不改）。
from __future__ import annotations

import ast
import json
import logging
import operator
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.models import (
    KnowledgePoint,
    StudyGoal,
    SysUser,
    WrongQuestionPersonal,
)

logger = logging.getLogger(__name__)

XIAOZHI_SYSTEM = (
    "你是联考小智，公安联考备考助手：能调用工具完成多步任务，帮学生查考点、看数据、算分数、排计划。\n"
    "规则：1) 能查就别猜，需要事实时调用工具；2) 工具结果为空就说「库里没有」，不要编造；\n"
    "3) 回答直接、可执行，不写免责声明；4) 涉及代码/命令时给完整可运行版本。"
)

# ---------- 工具定义 ----------
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在知识点库里按名称模糊检索考点，返回考点名与所属科目",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "关键词，如 资料分析 增长率"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "study_stats",
            "description": "查询当前用户的学习数据：错题总数、今日待复习数、方案进度",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "安全四则运算，用于分数换算、时间安排等计算",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "如 (65+58)/2*1.2"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "now",
            "description": "返回当前日期时间（用于算备考剩余天数）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.FloorDiv: operator.floordiv,
}


def _safe_eval(expr: str) -> float:
    """只允许数字与四则运算，杜绝任意代码执行。"""
    node = ast.parse(expr, mode="eval")

    def _walk(n):
        if isinstance(n, ast.Expression):
            return _walk(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](_walk(n.left), _walk(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](_walk(n.operand))
        raise ValueError("表达式只允许数字与 + - * / % ** //")

    return _walk(node)


def run_tool(name: str, args: Dict[str, Any], db: Session, user: SysUser) -> Dict[str, Any]:
    """执行单个工具，返回可 JSON 化的结果。异常不外抛，转成 error 让模型自行处理。"""
    try:
        if name == "search_knowledge":
            q = str(args.get("query") or "").strip()
            if not q:
                return {"error": "query 不能为空"}
            rows = (
                db.query(KnowledgePoint.point_name, KnowledgePoint.subject_id)
                .filter(KnowledgePoint.point_name.like(f"%{q}%"))
                .limit(10)
                .all()
            )
            return {"count": len(rows), "items": [{"name": r[0], "subject_id": r[1]} for r in rows]}

        if name == "study_stats":
            uid = user.user_id
            total_wrong = (
                db.query(func.count(WrongQuestionPersonal.wrong_id))
                .filter(WrongQuestionPersonal.user_id == uid, WrongQuestionPersonal.status == 1)
                .scalar()
                or 0
            )
            due = (
                db.query(func.count(WrongQuestionPersonal.wrong_id))
                .filter(
                    WrongQuestionPersonal.user_id == uid,
                    WrongQuestionPersonal.next_review_at.isnot(None),
                    WrongQuestionPersonal.next_review_at <= datetime.now(),
                )
                .scalar()
                or 0
            )
            done = (
                db.query(func.count(StudyGoal.goal_id))
                .filter(StudyGoal.user_id == uid, StudyGoal.is_completed == 1)
                .scalar()
                or 0
            )
            all_tasks = (
                db.query(func.count(StudyGoal.goal_id)).filter(StudyGoal.user_id == uid).scalar() or 0
            )
            return {
                "wrong_total": total_wrong,
                "due_today": due,
                "tasks_done": done,
                "tasks_total": all_tasks,
            }

        if name == "calc":
            expr = str(args.get("expression") or "").strip()
            return {"expression": expr, "result": _safe_eval(expr)}

        if name == "now":
            return {"now": datetime.now().isoformat(timespec="seconds")}

        return {"error": f"未知工具 {name}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def _endpoint() -> str:
    base = settings.LLM_API_URL.rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def _headers() -> Dict[str, str]:
    key = (settings.LLM_API_KEY or "").strip()
    if not key or key.startswith("<"):
        raise RuntimeError("未配置 LLM_API_KEY")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


# 两个模型档位（ID 由服务商约定，换服务商只改这里）
MODEL_CHAT = "deepseek-chat"          # 标准对话档
MODEL_REASONER = "deepseek-reasoner"  # 深度思考档


async def stream_chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    model: str = "",
) -> AsyncIterator[Dict[str, str]]:
    """真流式：逐块 yield {"kind": "reasoning"|"text", "text": ...}。

    深度思考档会先返回 reasoning_content（思考过程）再返回正式答案，
    这里把两者分开推给前端，前端分别渲染成「深度思考」折叠区与正文。
    """
    use_model = model or settings.LLM_MODEL or MODEL_CHAT
    payload = {
        "model": use_model,
        "messages": [{"role": "system", "content": XIAOZHI_SYSTEM}, *messages],
        "stream": True,
    }
    if use_model != MODEL_REASONER:
        payload["temperature"] = temperature
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        async with client.stream("POST", _endpoint(), headers=_headers(), json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                logger.error("stream 非200 status=%s len=%s", resp.status_code, len(body))
                yield f"[错误] 大模型返回 {resp.status_code}"
                return
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0]["delta"]
                except (KeyError, IndexError, ValueError):
                    continue
                reasoning = delta.get("reasoning_content")
                if reasoning:
                    yield {"kind": "reasoning", "text": reasoning}
                content = delta.get("content")
                if content:
                    yield {"kind": "text", "text": content}


async def run_agent(
    messages: List[Dict[str, str]],
    db: Session,
    user: SysUser,
    max_steps: int = 6,
) -> AsyncIterator[Dict[str, Any]]:
    """Agent 循环：模型决定是否调工具，逐步执行，最后给答案。yield 事件字典。"""
    convo: List[Dict[str, Any]] = [{"role": "system", "content": XIAOZHI_SYSTEM}, *messages]
    headers = _headers()
    model = settings.LLM_MODEL

    for step in range(max_steps):
        payload = {"model": model, "messages": convo, "temperature": 0.6, "tools": TOOLS, "stream": False}
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(_endpoint(), headers=headers, json=payload)
        if resp.status_code != 200:
            yield {"type": "error", "message": f"大模型返回 {resp.status_code}"}
            return
        data = resp.json()
        msg = data["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            content = msg.get("content") or ""
            # 无工具调用：按句子切片模拟打字机，前端进度感更好
            for i in range(0, len(content), 24):
                yield {"type": "token", "text": content[i : i + 24]}
            yield {"type": "done", "steps": step + 1}
            return

        convo.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            yield {"type": "tool_call", "name": name, "args": args}
            result = run_tool(name, args, db, user)
            yield {"type": "tool_result", "name": name, "result": result}
            convo.append({
                "role": "tool",
                "tool_call_id": call.get("id"),
                "content": json.dumps(result, ensure_ascii=False),
            })

    yield {"type": "error", "message": f"超过 {max_steps} 步仍未收敛，已中止"}
