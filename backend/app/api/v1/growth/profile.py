"""
模块4 v2 - 用户备考画像（Profile）路由

提供：
- GET  /api/profile/questions  画像问卷模板（引导式/多样式）
- GET  /api/profile            当前用户画像
- POST /api/profile/upsert     保存画像（全量覆盖，前端逐步提交）
"""
import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["备考画像"])


# ==================== 请求模型 ====================

class ProfileUpsertRequest(BaseModel):
    grade: Optional[str] = Field(None, max_length=20)
    target_score: Optional[str] = Field(None, max_length=30)
    self_level: Optional[str] = Field(None, max_length=20)
    daily_hours: Optional[float] = Field(None, ge=1, le=8)
    subject_strengths: Optional[List[str]] = None
    subject_weaknesses: Optional[List[str]] = None
    exam_date: Optional[str] = Field(None, max_length=10)
    target_region: Optional[str] = Field(None, max_length=50)
    target_post: Optional[str] = Field(None, max_length=100)
    profile_status: int = 0


# ==================== 问卷模板 ====================

QUESTION_TEMPLATES = [
    {
        "template_id": "guide-basic",
        "name": "极简卡式向导",
        "style": "card",
        "steps": [
            {
                "step": 1,
                "title": "基本信息",
                "fields": [
                    {"key": "grade", "type": "single", "label": "你现在几年级？",
                     "options": ["大一", "大二", "大三", "大四", "应届/已毕业"]},
                    {"key": "exam_date", "type": "date", "label": "备考截止日期（预计考试时间）"},
                ],
            },
            {
                "step": 2,
                "title": "目标设定",
                "fields": [
                    {"key": "target_score", "type": "text", "label": "目标分数（如：总分220 / 行测70 / 申论65 / 公专85）"},
                    {"key": "daily_hours", "type": "slider", "label": "每天能投入多少小时学习？", "min": 1, "max": 8},
                ],
            },
            {
                "step": 3,
                "title": "水平自评",
                "fields": [
                    {"key": "self_level", "type": "single", "label": "目前整体水平？",
                     "options": ["零基础", "入门", "有基础", "冲刺阶段"]},
                    {"key": "subject_weaknesses", "type": "multi", "label": "最薄弱的科目（可多选）",
                     "options": ["行测", "申论", "公专"]},
                    {"key": "subject_strengths", "type": "multi", "label": "相对有把握的科目（可多选）",
                     "options": ["行测", "申论", "公专"]},
                ],
            },
            {
                "step": 4,
                "title": "岗位意向（选填）",
                "fields": [
                    {"key": "target_region", "type": "text", "label": "意向报考地区（如：山东济南）"},
                    {"key": "target_post", "type": "text", "label": "意向岗位方向（如：基层派出所 / 网安 / 不限）"},
                ],
            },
        ],
    },
    {
        "template_id": "immersive-chat",
        "name": "沉浸问答式",
        "style": "chat",
        "steps": [
            {
                "step": 1,
                "title": "聊聊你的情况",
                "fields": [
                    {"key": "grade", "type": "single", "label": "先说说你现在几年级？",
                     "options": ["大一", "大二", "大三", "大四", "应届/已毕业"]},
                    {"key": "daily_hours", "type": "slider", "label": "每天大概能学多久？", "min": 1, "max": 8},
                ],
            },
            {
                "step": 2,
                "title": "你的目标",
                "fields": [
                    {"key": "target_score", "type": "text", "label": "理想分数是多少？"},
                    {"key": "exam_date", "type": "date", "label": "什么时候考试？"},
                ],
            },
            {
                "step": 3,
                "title": "强弱项盘点",
                "fields": [
                    {"key": "subject_weaknesses", "type": "multi", "label": "哪科让你最头疼？",
                     "options": ["行测", "申论", "公专"]},
                    {"key": "subject_strengths", "type": "multi", "label": "哪科你最有底？",
                     "options": ["行测", "申论", "公专"]},
                    {"key": "self_level", "type": "single", "label": "给自己定个位：",
                     "options": ["零基础", "入门", "有基础", "冲刺阶段"]},
                ],
            },
        ],
    },
    {
        "template_id": "pro-diagnose",
        "name": "专业诊断式",
        "style": "diagnose",
        "steps": [
            {
                "step": 1,
                "title": "基础档案",
                "fields": [
                    {"key": "grade", "type": "single", "label": "年级",
                     "options": ["大一", "大二", "大三", "大四", "应届/已毕业"]},
                    {"key": "target_region", "type": "text", "label": "意向地区（选填）"},
                ],
            },
            {
                "step": 2,
                "title": "量化目标",
                "fields": [
                    {"key": "target_score", "type": "text", "label": "目标总分/单科目标"},
                    {"key": "exam_date", "type": "date", "label": "备考截止"},
                    {"key": "daily_hours", "type": "slider", "label": "每日可用学时", "min": 1, "max": 8},
                ],
            },
            {
                "step": 3,
                "title": "诊断输入",
                "fields": [
                    {"key": "self_level", "type": "single", "label": "水平自评",
                     "options": ["零基础", "入门", "有基础", "冲刺阶段"]},
                    {"key": "subject_weaknesses", "type": "multi", "label": "薄弱科目",
                     "options": ["行测", "申论", "公专"]},
                    {"key": "subject_strengths", "type": "multi", "label": "优势科目",
                     "options": ["行测", "申论", "公专"]},
                    {"key": "target_post", "type": "text", "label": "岗位方向（选填）"},
                ],
            },
        ],
    },
]


@router.get("/questions", summary="画像问卷模板列表")
async def get_question_templates():
    """返回引导式/多样式问卷模板，前端按 template_id 渲染"""
    return {"templates": QUESTION_TEMPLATES}


# ==================== 画像读写 ====================

def _to_dict(p: Optional[UserProfile]) -> dict:
    if not p:
        return {"has_profile": False}
    def _loads(v: Optional[str]) -> list:
        if not v:
            return []
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return []
    return {
        "has_profile": True,
        "profile_id": p.profile_id,
        "grade": p.grade,
        "target_score": p.target_score,
        "self_level": p.self_level,
        "daily_hours": p.daily_hours,
        "subject_strengths": _loads(p.subject_strengths),
        "subject_weaknesses": _loads(p.subject_weaknesses),
        "exam_date": p.exam_date,
        "target_region": p.target_region,
        "target_post": p.target_post,
        "profile_status": p.profile_status,
        "update_time": p.update_time.isoformat() if p.update_time else None,
    }


@router.get("", summary="获取当前用户画像")
async def get_profile(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.user_id)
        .first()
    )
    return _to_dict(row)


@router.post("/upsert", summary="保存/更新画像")
async def upsert_profile(
    req: ProfileUpsertRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.user_id)
        .first()
    )
    if not row:
        row = UserProfile(user_id=current_user.user_id)
        db.add(row)

    row.grade = req.grade
    row.target_score = req.target_score
    row.self_level = req.self_level
    row.daily_hours = req.daily_hours
    row.subject_strengths = json.dumps(req.subject_strengths or [], ensure_ascii=False)
    row.subject_weaknesses = json.dumps(req.subject_weaknesses or [], ensure_ascii=False)
    row.exam_date = req.exam_date
    row.target_region = req.target_region
    row.target_post = req.target_post
    if req.profile_status == 1:
        row.profile_status = 1
    db.commit()
    db.refresh(row)
    return _to_dict(row)
