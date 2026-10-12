"""
招考信息 API
GET /api/recruitment — 获取招考信息列表（按分类）
GET /api/recruitment/{id} — 获取招考详情
"""
import logging
import re
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy import or_
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

# 报名状态优先级（用于排序）：即将报名 最优先 > 正在报名 > 报名结束 底部
STATUS_PRIORITY = {
    "即将报名": 0,
    "正在报名": 1,
    "报名结束": 2,
}
# 其他标签（笔试通知/面试/复审/公示 等）归入 3，排在报名结束之后


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


def _sort_key(x: dict):
    """招考条目排序键：真实发布日期倒序 → 状态优先级 → 原次序

    - 有 publish_date 的按日期**倒序**在前（取负数实现倒序）
    - 无 publish_date 的（回填前的历史数据）统一沉底，不污染顶部
    - 状态优先级仅在同一天内生效，不再压倒日期
    """
    pd = (x.get("publish_date") or "").strip()
    if pd:
        digits = re.sub(r"\D", "", pd)[:8]
        return (0, -int(digits) if len(digits) == 8 else 0, x.get("_prio", 3), x.get("_ord", 0))
    return (1, 0, x.get("_prio", 3), x.get("_ord", 0))


@router.get("", summary="获取招考信息列表")
async def get_recruitment(
    category: Optional[str] = Query(None, description="分类名称"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """获取招考信息，支持按分类筛选。默认返回所有分类各10条（公开访问）"""
    items = {}
    cats_to_query = [category] if category else CATEGORIES

    for cat in cats_to_query:
        # 真实发布日期优先。create_time 是爬取插入时间（同批次跨度仅微秒级），
        # 单独用它排序等于"插入顺序的逆序"，会把最旧内容排在最前。
        # 无发布日期的历史数据（回填前）统一沉底，不会污染顶部。
        records = db.query(RecruitmentInfo).filter(
            RecruitmentInfo.status == 1,
            RecruitmentInfo.category == cat
        ).order_by(
            or_(RecruitmentInfo.publish_date.is_(None),
                RecruitmentInfo.publish_date == "").asc(),
            RecruitmentInfo.publish_date.desc(),
            RecruitmentInfo.create_time.desc(),
        ).all()

        cat_items = []
        for r in records:
            label = _compute_status_label(r)
            cat_items.append({
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
                "status_label": label,
                "status_color": _compute_status_color(label),
                "content": r.content or "",
                "content_html": r.content_html or r.content or "",
                "images": r.images or [],
                "exam_format": r.exam_format or "",
                "contact_info": r.contact_info or "",
                "requirements": r.requirements or "",
                "view_count": r.view_count or 0,
                "publish_date": r.publish_date or "",
                "create_time": r.create_time.isoformat() if r.create_time else None,
                # 内部排序键（响应输出前剔除）
                "_prio": STATUS_PRIORITY.get(label, 3),
                "_ord": len(cat_items),
            })

        # 排序主键：真实发布日期倒序 → 状态优先级 → 原始次序。
        # 状态优先级降为次级键：仅在同一天内生效，避免像旧逻辑那样
        # 把整月前的"即将报名"条目顶到最新内容之上。
        cat_items.sort(key=_sort_key)
        for x in cat_items:
            x.pop("_prio", None)
            x.pop("_ord", None)
        items[cat] = cat_items[:limit]

    # ---- meta：让前端能自行判断"数据到底新不新"，而不必猜 ----
    all_dates = [
        d for lst in items.values() for d in
        [r.get("publish_date") or "" for r in lst] if d
    ]
    latest_pd = max(all_dates) if all_dates else ""
    last_updated = max(
        (r.get("create_time") for lst in items.values() for r in lst if r.get("create_time")),
        default=None,
    )

    # 禁缓存：招考信息每日更新，任何层级的缓存都会让用户看到旧内容
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"

    return {
        "categories": CATEGORIES,
        "items": items if not category else {category: items.get(category, [])},
        "meta": {
            "last_updated": last_updated,
            "latest_publish_date": latest_pd,
            "total": sum(len(v) for v in items.values()),
            "source": "rszk.net",
            "sort_by": "publish_date",
        },
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
