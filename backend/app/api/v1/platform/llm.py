"""
联考小智（⑱）- 大模型对话路由

提供：
- POST /api/llm/chat                 发消息，返回回复（多轮上下文）
- GET  /api/llm/sessions             我的会话列表
- POST /api/llm/sessions             新建会话
- GET  /api/llm/sessions/{id}/messages 某会话历史
- DELETE /api/llm/sessions/{id}     删除会话（软删）
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.config import settings
from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import ChatSession, ChatMessage, SysUser
from ....services import llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["联考小智"])

MAX_MESSAGE_LEN = 2000
Scene = Literal["psychological", "qa", "advice"]


# ==================== 请求模型 ====================

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LEN, description="消息内容")
    session_id: Optional[int] = None
    scene: Scene = "qa"  # psychological / qa / advice


class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    scene: Scene = "qa"


# ==================== 工具函数 ====================

def _get_user_session(session_id: int, user_id: int, db: Session) -> ChatSession:
    """取当前用户的会话，不存在或不属于当前用户则 404"""
    s = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == user_id,
        ChatSession.status == 1,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    return s


def _load_history(session_id: int, db: Session) -> List[Dict[str, str]]:
    """加载最近 N 条消息作为上下文（user/assistant 交替）"""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.create_time.desc())
        .limit(settings.LLM_MAX_HISTORY)
        .all()
    )
    rows = list(reversed(rows))  # 正序
    return [{"role": r.role, "content": r.content} for r in rows]


# ==================== 路由 ====================

@router.post("/chat", summary="发送消息")
async def chat(
    req: ChatRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送一条消息，返回大模型回复。带 session_id 则多轮，不带则自动新建会话。"""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # 1. 取或建会话
    is_new_session = False
    if req.session_id:
        session = _get_user_session(req.session_id, current_user.user_id, db)
    else:
        is_new_session = True
        session = ChatSession(
            user_id=current_user.user_id,
            title=req.message.strip()[:20],
            scene=req.scene,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # 2. 写用户消息
    user_msg = ChatMessage(
        session_id=session.session_id,
        role="user",
        content=req.message.strip(),
    )
    db.add(user_msg)
    db.commit()

    # 3. 加载历史（含刚写入的用户消息）
    history = _load_history(session.session_id, db)

    # 4. 多 Agent 路由 + 档案上下文装配（模块7 v2；心理场景直接走心理 Agent）
    from ....services.agent_router import route_agent, agent_system_prompt, assemble_context, extract_memories

    agent_id, agent_name, route_score = route_agent(req.message)
    if req.scene == "psychological" or agent_id == "psychology":
        agent_id = "psychology"
        agent_name = "心理辅导"
    extra_parts = []
    agent_prompt = agent_system_prompt(agent_id)
    if agent_prompt:
        extra_parts.append(agent_prompt)
    try:
        ctx = assemble_context(current_user.user_id, db)
        if ctx:
            extra_parts.append(ctx)
        extract_memories(current_user.user_id, db)  # 画像 → 长期记忆（幂等）
    except Exception as e:
        logger.warning("档案上下文装配失败: %s", e)
    extra_system = "\n\n".join(extra_parts)

    # 5. 调大模型
    try:
        reply = await llm_client.chat(messages=history, scene=req.scene, extra_system=extra_system)
    except llm_client.LLMClientError as e:
        logger.warning("联考小智调用失败: %s", e.message)
        # 回滚已持久化的用户消息，避免留下"无回复的悬空消息"
        db.delete(user_msg)
        if is_new_session:
            db.delete(session)
        db.commit()
        raise HTTPException(status_code=503, detail=e.message)

    # 5. 写 AI 回复
    ai_msg = ChatMessage(
        session_id=session.session_id,
        role="assistant",
        content=reply,
    )
    db.add(ai_msg)

    # 6. 更新会话时间
    session.update_time = datetime.now()
    db.commit()

    return {
        "reply": reply,
        "session_id": session.session_id,
        "scene": session.scene,
        "agent": agent_id,
        "agent_name": agent_name,
    }


@router.get("/sessions", summary="我的会话列表")
async def list_sessions(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """会话列表，按更新时间倒序；limit 上限 100，默认 50（分页）"""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    base = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.user_id,
        ChatSession.status == 1,
    )
    total = base.count()
    rows = (
        base.order_by(ChatSession.update_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "session_id": s.session_id,
                "title": s.title,
                "scene": s.scene,
                "create_time": s.create_time.isoformat() if s.create_time else None,
                "update_time": s.update_time.isoformat() if s.update_time else None,
            }
            for s in rows
        ],
    }


@router.post("/sessions", summary="新建会话")
async def create_session(
    req: CreateSessionRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = ChatSession(
        user_id=current_user.user_id,
        title=req.title or "新会话",
        scene=req.scene,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "session_id": session.session_id,
        "title": session.title,
        "scene": session.scene,
    }


@router.get("/sessions/{session_id}/messages", summary="会话历史消息")
async def session_messages(
    session_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_session(session_id, current_user.user_id, db)
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.create_time.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "items": [
            {
                "message_id": m.message_id,
                "role": m.role,
                "content": m.content,
                "create_time": m.create_time.isoformat() if m.create_time else None,
            }
            for m in rows
        ],
    }


@router.delete("/sessions/{session_id}", summary="删除会话（软删）")
async def delete_session(
    session_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_user_session(session_id, current_user.user_id, db)
    session.status = 0
    session.update_time = datetime.now()
    db.commit()
    return {"message": "会话已删除"}


@router.get("/context/assemble", summary="档案上下文预览（带着档案来对话）")
async def assemble_context_api(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回装配好的档案上下文块 + 长期记忆清单（前端可展示'我的档案'）"""
    from ....services.agent_router import assemble_context, extract_memories
    from ....models.models import UserMemory

    ctx = ""
    try:
        ctx = assemble_context(current_user.user_id, db)
        extract_memories(current_user.user_id, db)
    except Exception as e:
        logger.warning("档案上下文装配失败: %s", e)

    memories = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == current_user.user_id)
        .order_by(UserMemory.create_time.desc())
        .all()
    )
    return {
        "has_profile": bool(ctx),
        "context": ctx,
        "memories": [
            {
                "memory_id": m.memory_id,
                "memory_type": m.memory_type,
                "content": m.content,
                "source": m.source,
                "update_time": m.update_time.isoformat() if m.update_time else None,
            }
            for m in memories
        ],
    }
