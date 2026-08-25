"""备考资料 API。响应风格与 news.py 一致：裸 JSON。

学生组：GET "" 列表 / GET "/{id}" 详情 / GET "/progress-summary" / POST "/progress"
        POST "/{id}/favorite" / GET "/favorites"
管理组：见同文件下半部（admin/import 组，Task3/T6 追加）。
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user, get_optional_user
from ...models.models import StudyMaterial, UserMaterialProgress, SysUser

router = APIRouter(prefix="/api/materials", tags=["备考资料"])
logger = logging.getLogger(__name__)

SUBJECTS = {"xingce", "shenlun", "gongzhuan"}
TYPES = {"video_intro", "video_advanced", "article", "card"}


def _item_brief(m: StudyMaterial, prog: Optional[UserMaterialProgress] = None) -> dict:
    d = {
        "id": m.material_id, "subject": m.subject, "type": m.type,
        "category": m.category, "title": m.title, "summary": m.summary,
        "badge": m.badge, "cover_image": m.cover_image,
        "duration": m.duration or 0, "read_time": m.read_time or 0,
        "difficulty": m.difficulty or 1, "view_count": m.view_count or 0,
        "card_front": m.card_front, "sort_order": m.sort_order or 0,
    }
    if prog is not None:
        d.update({
            "is_studied": prog.status == 2,
            "progress_percent": round(float(prog.progress_percent or 0), 1),
            "is_favorite": bool(prog.is_favorite),
        })
    return d


@router.get("", summary="资料列表(游客可访问)")
async def list_materials(
    subject: str = Query(..., description="xingce/shenlun/gongzhuan"),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if subject not in SUBJECTS:
        raise HTTPException(400, "无效科目")
    if type and type not in TYPES:
        raise HTTPException(400, "无效类型")
    q = db.query(StudyMaterial).filter(
        StudyMaterial.subject == subject, StudyMaterial.status == 1)
    if type:
        q = q.filter(StudyMaterial.type == type)
    total = q.count()
    rows = (q.order_by(StudyMaterial.sort_order.asc(), StudyMaterial.material_id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    progs = {}
    if current_user and rows:
        ids = [r.material_id for r in rows]
        for p in (db.query(UserMaterialProgress)
                  .filter(UserMaterialProgress.user_id == current_user.user_id,
                          UserMaterialProgress.material_id.in_(ids)).all()):
            progs[p.material_id] = p
    return {"total": total,
            "items": [_item_brief(m, progs.get(m.material_id)) for m in rows]}


@router.get("/progress-summary", summary="科目进度概览(登录)")
async def progress_summary(subject: str = Query(...),
                           current_user: SysUser = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    if subject not in SUBJECTS:
        raise HTTPException(400, "无效科目")
    total = db.query(func.count(StudyMaterial.material_id)).filter(
        StudyMaterial.subject == subject, StudyMaterial.status == 1).scalar() or 0
    studied = (db.query(func.count(UserMaterialProgress.progress_id))
               .join(StudyMaterial,
                     StudyMaterial.material_id == UserMaterialProgress.material_id)
               .filter(UserMaterialProgress.user_id == current_user.user_id,
                       UserMaterialProgress.status == 2,
                       StudyMaterial.subject == subject,
                       StudyMaterial.status == 1).scalar() or 0)
    pct = round(studied * 100.0 / total, 1) if total else 0.0
    return {"studied": studied, "total": total, "percentage": pct}


@router.get("/favorites", summary="我的收藏(登录)")
async def my_favorites(current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    rows = (db.query(StudyMaterial, UserMaterialProgress)
            .join(UserMaterialProgress,
                  UserMaterialProgress.material_id == StudyMaterial.material_id)
            .filter(UserMaterialProgress.user_id == current_user.user_id,
                    UserMaterialProgress.is_favorite.is_(True),
                    StudyMaterial.status == 1)
            .order_by(UserMaterialProgress.update_time.desc()).all())
    items = []
    for m, p in rows:
        item = _item_brief(m)
        item["favorite_time"] = p.update_time.isoformat() if p.update_time else None
        items.append(item)
    return {"total": len(rows), "items": items}


@router.post("/progress", summary="上报学习进度(登录, UPSERT幂等)")
async def report_progress(body: dict,
                          current_user: SysUser = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    mid = body.get("material_id")
    if not mid:
        raise HTTPException(400, "缺少 material_id")
    try:
        pct = max(0.0, min(float(body.get("progress_percent", 0)), 100.0))
    except (TypeError, ValueError):
        raise HTTPException(400, "progress_percent 非法")
    completed = bool(body.get("completed")) or pct >= 95
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == mid, StudyMaterial.status == 1).first()
    if not m:
        raise HTTPException(404, "资料不存在或已下架")

    old = db.query(UserMaterialProgress).filter(
        UserMaterialProgress.user_id == current_user.user_id,
        UserMaterialProgress.material_id == mid).first()
    first_complete = completed and (old is None or old.status != 2)

    stmt = sqlite_insert(UserMaterialProgress).values(
        user_id=current_user.user_id, material_id=mid,
        status=2 if completed else 1, progress_percent=pct,
        completed_at=datetime.now() if completed else None)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "material_id"],
        set_={"progress_percent": stmt.excluded.progress_percent,
              "status": stmt.excluded.status,
              "completed_at": stmt.excluded.completed_at})
    db.execute(stmt)
    if first_complete:
        m.study_count = (m.study_count or 0) + 1
    db.commit()
    return {"ok": True, "completed": completed, "progress_percent": pct}


@router.post("/{material_id}/favorite", summary="收藏切换(登录)")
async def toggle_favorite(material_id: int,
                          current_user: SysUser = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id, StudyMaterial.status == 1).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    prog = db.query(UserMaterialProgress).filter(
        UserMaterialProgress.user_id == current_user.user_id,
        UserMaterialProgress.material_id == material_id).first()
    if prog is None:
        prog = UserMaterialProgress(user_id=current_user.user_id,
                                    material_id=material_id)
        db.add(prog)
        new_val = True
    else:
        new_val = not bool(prog.is_favorite)
    prog.is_favorite = new_val
    db.commit()
    return {"is_favorite": new_val}


@router.get("/{material_id}", summary="资料详情(游客可访问)")
async def material_detail(material_id: int,
                          current_user: Optional[SysUser] = Depends(get_optional_user),
                          db: Session = Depends(get_db)):
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id, StudyMaterial.status == 1).first()
    if not m:
        raise HTTPException(404, "资料不存在或已下架")
    m.view_count = (m.view_count or 0) + 1
    db.commit()
    prog = None
    if current_user:
        prog = db.query(UserMaterialProgress).filter(
            UserMaterialProgress.user_id == current_user.user_id,
            UserMaterialProgress.material_id == material_id).first()
    d = _item_brief(m, prog)
    d.update({"content": m.content or "", "card_back": m.card_back or "",
              "video_url": f"/api/video/{m.video_id}/stream" if m.video_id else ""})
    return d
