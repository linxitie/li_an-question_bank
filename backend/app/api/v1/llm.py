"""
支持大模型引入、
支持智能批改，解析生成，提升建议，问题解决等功能
"""
from typing import List, Optional, Dict
import logging
from datetime import datetime

from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.models import QuestionBank,SysUser
from ...schemas.schemas import (
    SmartGradingRequest, SmartGradingResponse,
    GenerateAnalysisRequest, GenerateAnalysisResponse,
    DailyGoldenSentenceResponse, RecruitmentInfoResponse,
    RecruitmentInfoItem, SuccessResponse
)

from ...core.security import get_current_user



router = APIRouter(prefix="/api/llm",tags = ["大模型服务"])
logger = logging.getLogger(__name__)


@router.post("/chat")
async def llm_chat(
    message: Dict[str, str],
    current_user: SysUser = Depends(get_current_user)
):
    user_message = message.get("message", "")
    
    try:
        response = requests.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "police-exam",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是公安联考学习助手'联考小智'，专门帮助考生备考公安联考。请用友好、专业的语言回答问题。"
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return {"reply": result.get("content", "抱歉，我无法回答这个问题。")}
        else:
            return {"reply": "抱歉，暂时无法回答，请稍后重试。"}
    
    except Exception:
        return {"reply": "抱歉，服务暂时不可用，请稍后重试。"}