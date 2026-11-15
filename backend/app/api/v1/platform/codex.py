# 联考小智 · Codex 模式 API（模块7）
# - POST /api/llm/chat/stream   SSE 真流式对话
# - POST /api/llm/agent/stream  SSE Agent 循环（工具调用可见）
# 两者均为新增端点，不改既有 /api/llm/* 契约。
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser
from ....services import codex_agent

router = APIRouter(prefix="/api/llm", tags=["联考小智-Codex"])
logger = logging.getLogger(__name__)

MAX_HISTORY = 20


class StreamChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: Optional[List[Dict[str, str]]] = Field(default=None, description="[{role, content}]")
    # deepseek-chat（V3 快答） / deepseek-reasoner（R1 深度思考）
    model: Optional[str] = Field(default=None, description="模型档位")


def _build_messages(req_message: str, history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = []
    for h in (history or [])[-MAX_HISTORY:]:
        role = (h or {}).get("role")
        content = (h or {}).get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            msgs.append({"role": role, "content": content.strip()})
    msgs.append({"role": "user", "content": req_message.strip()})
    return msgs


def _sse(payload: Dict[str, Any]) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


@router.post("/chat/stream", summary="流式对话（SSE）")
async def chat_stream(
    payload: StreamChatRequest,
    current_user: SysUser = Depends(get_current_user),
):
    messages = _build_messages(payload.message, payload.history)

    async def gen():
        try:
            async for chunk in codex_agent.stream_chat(messages, model=payload.model or ""):
                kind = chunk.get("kind", "text")
                if kind == "reasoning":
                    yield _sse({"type": "reasoning", "text": chunk.get("text", "")})
                else:
                    yield _sse({"type": "token", "text": chunk.get("text", "")})
            yield _sse({"type": "done"})
        except Exception as e:  # noqa: BLE001
            logger.exception("chat_stream 失败")
            yield _sse({"type": "error", "message": str(e)[:200]})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent/stream", summary="Agent 模式（工具调用 + SSE）")
async def agent_stream(
    payload: StreamChatRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    messages = _build_messages(payload.message, payload.history)

    async def gen():
        try:
            async for event in codex_agent.run_agent(messages, db, current_user):
                yield _sse(event)
        except Exception as e:  # noqa: BLE001
            logger.exception("agent_stream 失败")
            yield _sse({"type": "error", "message": str(e)[:200]})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/agent/tools", summary="可用工具清单（前端展示用）")
async def list_tools(current_user: SysUser = Depends(get_current_user)):
    return {
        "tools": [
            {"name": t["function"]["name"], "description": t["function"]["description"]}
            for t in codex_agent.TOOLS
        ]
    }
