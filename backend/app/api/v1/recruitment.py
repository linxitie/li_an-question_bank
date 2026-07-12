"""
招考信息 API
GET /api/recruitment — 获取招考信息列表（按分类）
GET /api/recruitment/{id} — 获取招考详情
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_optional_user
from ...models.models import RecruitmentInfo, SysUser

router = APIRouter(prefix="/api/recruitment", tags=["招考信息"])
logger = logging.getLogger(__name__)

CATEGORIES = ["国考省考", "教师招聘", "事业单位", "国企招聘", "医疗卫生", "三支一扶"]

# 状态标签颜色映射（前端胶囊徽标用）
STATUS_COLORS = {
    "正在报名": "#10b981",  # 绿色
    "即将报名": "#1a2a6c",  # 藏蓝色
    "报名结束": "#c41e3a",  # 中国红
}


def _compute_status_label(rec: RecruitmentInfo) -> str:
    """根据报名时间计算前端展示的状态标签文本"""
    # 优先使用爬虫已计算的 tag
    if rec.tag in ("正在报名", "即将报名", "报名结束"):
        return rec.tag
    # 回退：根据 deadline 判断
    if rec.registration_end:
        from datetime import datetime as dt
        import re
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", rec.registration_end)
        if m:
            end_dt = dt(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if end_dt < dt.now():
                return "报名结束"
    if rec.registration_start:
        from datetime import datetime as dt
        import re
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", rec.registration_start)
        if m:
            start_dt = dt(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if start_dt > dt.now():
                return "即将报名"
    # 默认
    return rec.tag or "正在报名"


def _compute_status_color(label: str) -> str:
    """根据状态标签返回对应的颜色值"""
    return STATUS_COLORS.get(label, "#10b981")


@router.get("", summary="获取招考信息列表")
async def get_recruitment(
    category: Optional[str] = Query(None, description="分类名称"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取招考信息，支持按分类筛选。默认返回所有分类各10条（公开访问）"""
    items = {}
    cats_to_query = [category] if category else CATEGORIES

    for cat in cats_to_query:
        records = db.query(RecruitmentInfo).filter(
            RecruitmentInfo.status == 1,
            RecruitmentInfo.category == cat
        ).order_by(RecruitmentInfo.create_time.desc()).limit(limit).all()

        items[cat] = [
            {
                "id": r.recruitment_id,
                "title": r.title,
                "url": r.url or "",
                "category": r.category,
                "organization": r.organization or "",
                "region": r.region or "",
                "registration_start": r.registration_start or "",
                "registration_end": r.registration_end or r.deadline or "",
                "deadline": r.deadline or r.registration_end or "",
                "tag": r.tag or "",
                "tag_color": r.tag_color or "",
                "status_label": _compute_status_label(r),
                "status_color": _compute_status_color(_compute_status_label(r)),
                "content": r.content or "",
                "content_html": r.content_html or r.content or "",
                "images": r.images or [],
                "exam_format": r.exam_format or "",
                "contact_info": r.contact_info or "",
                "requirements": r.requirements or "",
                "view_count": r.view_count or 0,
                "create_time": r.create_time.isoformat() if r.create_time else None
            }
            for r in records
        ]

    return {
        "categories": CATEGORIES,
        "items": items if not category else {category: items.get(category, [])}
    }


@router.get("/categories", summary="获取招考分类列表")
async def get_recruitment_categories(
    current_user: Optional[SysUser] = Depends(get_optional_user)
):
    """获取所有招考信息分类"""
    return {"categories": CATEGORIES}


@router.get("/{recruitment_id}", summary="获取招考详情")
async def get_recruitment_detail(
    recruitment_id: int,
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取单条招考信息详情（含HTML正文、图片、考试方式、联系方式）"""
    rec = db.query(RecruitmentInfo).filter(
        RecruitmentInfo.recruitment_id == recruitment_id,
        RecruitmentInfo.status == 1
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="招考信息不存在")
    rec.view_count = (rec.view_count or 0) + 1
    db.commit()
    return {
        "id": rec.recruitment_id,
        "title": rec.title,
        "organization": rec.organization,
        "category": rec.category,
        "region": rec.region,
        "content": rec.content or "",
        "content_html": rec.content_html or rec.content or "",
        "images": rec.images or [],
        "registration_start": rec.registration_start or "",
        "registration_end": rec.registration_end or "",
        "exam_format": rec.exam_format or "",
        "contact_info": rec.contact_info or "",
        "url": rec.url or "",
        "tag": rec.tag or "",
        "status_label": _compute_status_label(rec),
        "status_color": _compute_status_color(_compute_status_label(rec)),
        "view_count": rec.view_count or 0,
        "create_time": rec.create_time.isoformat() if rec.create_time else None
    }
