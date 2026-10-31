# -*- coding: utf-8 -*-
"""
模块7 v2 - 岗位库：公安联考岗位数据的批量导入与条件筛选。
选岗顾问的数据底座：地区/专业/学历/性别/招录数/竞争比。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import PolicePost, SysUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/post", tags=["岗位库"])

MAX_IMPORT = 500


class PostItem(BaseModel):
    region: str = Field(..., max_length=60, description="招录地区/单位")
    post_type: str = Field(default="执法", max_length=30, description="综合/执法/技术")
    profession: str = Field(default="不限", max_length=120, description="专业要求")
    education: str = Field(default="本科", max_length=30, description="学历要求")
    sex_require: str = Field(default="不限", max_length=20, description="不限/男/女")
    plan_count: int = Field(default=0, ge=0, description="招录人数")
    ratio: str = Field(default="", max_length=30, description="竞争比")
    source: str = Field(default="", max_length=200, description="来源")


class PostImportRequest(BaseModel):
    items: List[PostItem] = Field(..., max_length=MAX_IMPORT)


@router.post("/import", summary="批量导入岗位数据（幂等：region+profession+education 去重）")
async def import_posts(
    req: PostImportRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    imported, skipped = 0, 0
    for item in req.items:
        dup = (
            db.query(PolicePost)
            .filter(
                PolicePost.region == item.region,
                PolicePost.profession == item.profession,
                PolicePost.education == item.education,
            )
            .first()
        )
        if dup:
            skipped += 1
            continue
        db.add(
            PolicePost(
                region=item.region,
                post_type=item.post_type,
                profession=item.profession,
                education=item.education,
                sex_require=item.sex_require,
                plan_count=item.plan_count,
                ratio=item.ratio,
                source=item.source or "用户导入",
            )
        )
        imported += 1
    db.commit()
    total = db.query(PolicePost).filter(PolicePost.status == 1).count()
    return {
        "imported": imported,
        "skipped": skipped,
        "total": total,
        "message": f"导入完成：新增 {imported} 条，跳过重复 {skipped} 条，当前岗位库共 {total} 条",
    }


@router.get("/search", summary="岗位条件筛选")
async def search_posts(
    region: Optional[str] = Query(None, max_length=60),
    post_type: Optional[str] = Query(None, max_length=30),
    profession: Optional[str] = Query(None, max_length=120),
    education: Optional[str] = Query(None, max_length=30),
    sex_require: Optional[str] = Query(None, max_length=20),
    limit: int = Query(20, ge=1, le=50),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(PolicePost).filter(PolicePost.status == 1)
    if region:
        q = q.filter(PolicePost.region.like(f"%{region}%"))
    if post_type:
        q = q.filter(PolicePost.post_type == post_type)
    if profession and profession != "不限":
        q = q.filter(PolicePost.profession.like(f"%{profession}%"))
    if education and education != "不限":
        q = q.filter(PolicePost.education.like(f"%{education}%"))
    if sex_require and sex_require != "不限":
        q = q.filter(PolicePost.sex_require == sex_require)
    items = q.order_by(PolicePost.plan_count.desc()).limit(limit).all()
    return {
        "total": len(items),
        "items": [
            {
                "post_id": p.post_id,
                "region": p.region,
                "post_type": p.post_type,
                "profession": p.profession,
                "education": p.education,
                "sex_require": p.sex_require,
                "plan_count": p.plan_count,
                "ratio": p.ratio,
                "source": p.source,
            }
            for p in items
        ],
    }


@router.get("/stats", summary="岗位库统计")
async def post_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func

    total = db.query(PolicePost).filter(PolicePost.status == 1).count()
    regions = {
        r[0]: r[1]
        for r in (
            db.query(PolicePost.region, func.count(PolicePost.post_id))
            .filter(PolicePost.status == 1)
            .group_by(PolicePost.region)
            .all()
        )
    }
    types = {
        t[0]: t[1]
        for t in (
            db.query(PolicePost.post_type, func.count(PolicePost.post_id))
            .filter(PolicePost.status == 1)
            .group_by(PolicePost.post_type)
            .all()
        )
    }
    return {"total": total, "regions": len(regions), "types": types}
