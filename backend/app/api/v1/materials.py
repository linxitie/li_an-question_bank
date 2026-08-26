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


# ============================ 管理端（role=admin）============================

import json as _json  # noqa: E402
import os as _os  # noqa: E402
import uuid as _uuid  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from fastapi import File, UploadFile  # noqa: E402

from ...models.models import MaterialImportRecord, SysOperationLog  # noqa: E402
from ...services.material_sanitizer import sanitize_html  # noqa: E402

UPLOAD_IMG_DIR = _Path("uploads/materials/images")
UPLOAD_TMP_DIR = _Path("uploads/materials/tmp")

MAGIC_BYTES = {
    ".png": b"\x89PNG",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".webp": b"RIFF",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
    ".pdf": b"%PDF",
}


def _require_admin(user: SysUser):
    """SysUser 的角色字段是 user_type（student/teacher/admin），非 role。"""
    if user is None or getattr(user, "user_type", "") != "admin":
        raise HTTPException(403, "需要管理员权限")


def _audit(db: Session, user: SysUser, action: str, target: str, detail: str = ""):
    """写审计日志。字段名对照 models.SysOperationLog 真实定义（models.py:793）。"""
    try:
        db.add(SysOperationLog(
            user_id=user.user_id,
            user_name=getattr(user, "username", None) or getattr(user, "real_name", ""),
            operation_type=action,
            module_name="materials",
            operation_desc=detail or target,
            request_method="",
            request_url=f"/api/materials/{target}",
            ip_address="",
        ))
    except Exception as e:  # 审计失败不阻断业务
        logger.warning("[materials] audit log failed: %s", e)


def _safe_image_upload(file: UploadFile) -> str:
    ext = _os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "仅支持 png/jpg/webp 图片")
    content = file.file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 5MB")
    magic = MAGIC_BYTES.get(".jpg" if ext == ".jpeg" else ext)
    if magic and not content.startswith(magic):
        raise HTTPException(400, "文件实际格式与扩展名不符")
    UPLOAD_IMG_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{_uuid.uuid4().hex}{ext}"
    (UPLOAD_IMG_DIR / name).write_bytes(content)
    return f"/uploads/materials/images/{name}"


@router.post("/admin/upload/image", summary="上传封面/文章插图(管理员)")
async def upload_image(file: UploadFile = File(...),
                       current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_admin(current_user)
    url = _safe_image_upload(file)
    _audit(db, current_user, "upload_image", url)
    db.commit()
    return {"url": url}


def _validate_material_body(body: dict, partial: bool = False) -> dict:
    keys = ("subject", "type", "category", "title", "summary", "content",
            "card_front", "card_back", "cover_image", "video_id",
            "duration", "read_time", "difficulty", "badge", "sort_order")
    data = {k: body.get(k) for k in keys}
    if not partial:
        if data["subject"] not in SUBJECTS:
            raise HTTPException(400, "无效科目")
        if data["type"] not in TYPES:
            raise HTTPException(400, "无效类型")
        if not (data["title"] or "").strip():
            raise HTTPException(400, "标题必填")
        if data["type"] == "card" and not (data["card_front"] or "").strip():
            raise HTTPException(400, "卡片正面内容必填")
        if data["content"]:
            data["content"] = sanitize_html(data["content"])
    elif data.get("content"):
        data["content"] = sanitize_html(data["content"])
    return {k: v for k, v in data.items() if v is not None}


@router.get("/admin/list", summary="管理列表(含下架)")
async def admin_list(subject: Optional[str] = Query(None),
                     type: Optional[str] = Query(None),
                     status: Optional[int] = Query(None),
                     page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=100),
                     current_user: SysUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _require_admin(current_user)
    q = db.query(StudyMaterial)
    if subject:
        q = q.filter(StudyMaterial.subject == subject)
    if type:
        q = q.filter(StudyMaterial.type == type)
    if status is not None:
        q = q.filter(StudyMaterial.status == status)
    total = q.count()
    rows = (q.order_by(StudyMaterial.material_id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    items = []
    for m in rows:
        item = _item_brief(m)
        item.update({"status": m.status, "study_count": m.study_count or 0,
                     "creator_id": m.creator_id})
        items.append(item)
    return {"total": total, "items": items}


@router.post("/admin", summary="创建资料(管理员)")
async def admin_create(body: dict,
                       current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_admin(current_user)
    data = _validate_material_body(body)
    m = StudyMaterial(**data, creator_id=current_user.user_id)
    db.add(m)
    db.commit()
    db.refresh(m)
    _audit(db, current_user, "create", f"material:{m.material_id}", m.title)
    db.commit()
    return {"id": m.material_id}


@router.put("/admin/{material_id}", summary="更新资料(管理员)")
async def admin_update(material_id: int, body: dict,
                       current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    data = _validate_material_body(body, partial=True)
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    _audit(db, current_user, "update", f"material:{material_id}")
    db.commit()
    return {"ok": True}


@router.put("/admin/{material_id}/status", summary="上架/下架(管理员)")
async def admin_set_status(material_id: int, body: dict,
                           current_user: SysUser = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    _require_admin(current_user)
    st = body.get("status")
    if st not in (0, 1):
        raise HTTPException(400, "status 只能为 0 或 1")
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    m.status = st
    db.commit()
    _audit(db, current_user, "status", f"material:{material_id}", f"status={st}")
    db.commit()
    return {"ok": True}


@router.delete("/admin/{material_id}", summary="删除资料(管理员)")
async def admin_delete(material_id: int,
                       current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    title = m.title
    db.query(UserMaterialProgress).filter(
        UserMaterialProgress.material_id == material_id).delete()
    db.delete(m)
    db.commit()
    _audit(db, current_user, "delete", f"material:{material_id}", title)
    db.commit()
    return {"ok": True}
