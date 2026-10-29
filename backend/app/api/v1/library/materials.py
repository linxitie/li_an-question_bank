"""备考资料 API。响应风格与 news.py 一致：裸 JSON。

学生组：GET "" 列表 / GET "/{id}" 详情 / GET "/progress-summary" / POST "/progress"
        POST "/{id}/favorite" / GET "/favorites"
管理组：见同文件下半部（admin/import 组，Task3/T6 追加）。
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, File, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, get_optional_user
from ....core.trigger_types import TRIGGER_MATERIAL_OPENED
from ....models.models import (StudyMaterial, UserMaterialProgress, SysUser,
                               MaterialShare, MaterialAdoptLog)
from ....services.event_consumer import record_user_action

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
        "card_back": m.card_back,
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




# ==================== 读卡奖励（金币 + 成就接线） ====================
READ_COIN = 2          # 每次首次读完一篇
READ_COIN_DAILY_CAP = 20


def _grant_read_rewards(db: Session, user: SysUser, material: StudyMaterial) -> dict:
    """首次读完一篇：发金币（幂等 + 日封顶）并触发成就判定。

    幂等键：coin_record(user_id, source_type='MATERIAL', related_id=material_id)
    """
    from datetime import date, datetime as _dt

    from ....models.models import CoinRecord
    from ..reward.contract import grant_coins

    already = (db.query(CoinRecord)
               .filter(CoinRecord.user_id == user.user_id,
                       CoinRecord.source_type == "MATERIAL",
                       CoinRecord.related_id == material.material_id)
               .first())
    coins = 0
    if already is None:
        today = _dt.combine(date.today(), _dt.min.time())
        got = (db.query(func.coalesce(func.sum(CoinRecord.coin_change), 0))
               .filter(CoinRecord.user_id == user.user_id,
                       CoinRecord.source_type == "MATERIAL",
                       CoinRecord.transaction_time >= today)
               .scalar() or 0)
        if got < READ_COIN_DAILY_CAP:
            coins = min(READ_COIN, READ_COIN_DAILY_CAP - int(got))
            grant_coins(db, user, coins, source_type="MATERIAL",
                        related_id=material.material_id,
                        description=f"阅读资料：{material.title}")
            db.commit()          # 金币独立提交：不依赖调用方事务

    unlocked = []
    try:
        from ....services.achievement_service import check_and_grant
        for d in check_and_grant(user.user_id, "material", db) or []:
            # check_and_grant 的返回结构随版本而异：兼容 {achievement: obj} 与扁平字典
            ach = d.get("achievement") if isinstance(d, dict) else None
            name = getattr(ach, "name", None) or (d.get("name") if isinstance(d, dict) else "") or ""
            coins = (getattr(ach, "reward_coins", None)
                     or (d.get("coins") if isinstance(d, dict) else 0) or 0)
            unlocked.append({"name": name, "tier": d.get("tier", 1) if isinstance(d, dict) else 1,
                             "coins": coins})
    except Exception as e:  # 成就失败不影响阅读
        logger.warning("[materials] achievement trigger failed: %s", repr(e))

    return {"coins": coins, "achievements": unlocked}


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
        rewards = _grant_read_rewards(db, current_user, m)
    db.commit()
    return {"ok": True, "completed": completed, "progress_percent": pct,
            "rewards": locals().get("rewards", {"coins": 0, "achievements": []})}


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


def _mark_opened(db: Session, user_id: int, material_id: int) -> bool:
    """记录一次资料打开，返回是否为该用户对该资料的首次打开。

    复用 ``user_material_progress`` 的 ``(user_id, material_id)`` 唯一约束做去重：
    没有进度行说明从未打开过，插入一行作为「已打开」标记并发布事件；
    已有进度行（打开 / 学习 / 收藏任一途径建立）则不再重复发布。
    """
    exists = db.query(UserMaterialProgress).filter(
        UserMaterialProgress.user_id == user_id,
        UserMaterialProgress.material_id == material_id).first()
    if exists:
        return False
    db.add(UserMaterialProgress(user_id=user_id, material_id=material_id,
                                status=1, progress_percent=0))
    try:
        db.commit()
    except IntegrityError:
        # 并发下另一个请求先写入：唯一约束兜底，视为非首次
        db.rollback()
        return False
    return True



# ==================== 个人库（B1：三角色建卡，status=2 私有） ====================
def _own_or_admin(user: SysUser) -> bool:
    return (user.user_type or "") == "admin"


@router.post("/my", summary="建卡进我的库(学生/教师/管理员)")
async def my_create(body: dict,
                    current_user: SysUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """建卡：creator_id 由服务端强制写入；默认 status=2（私有）。

    publish=true 时直接公开（status=1）——Q6 已确认学生建卡免审批。
    """
    data = _validate_material_body(body)
    if not data.get("category"):
        auto = _auto_classify(db, data.get("subject"), data.get("title"),
                              data.get("card_front"), data.get("card_back"))
        if auto:
            data["category"] = auto
    m = StudyMaterial(**data, creator_id=current_user.user_id,
                      status=(1 if body.get("publish") else 2))
    db.add(m)
    db.commit()
    db.refresh(m)
    _audit(db, current_user, "my_create", f"material:{m.material_id}", m.title)
    db.commit()
    return {"id": m.material_id, "status": m.status}


@router.get("/my", summary="我的资料库(含草稿/公开/私有)")
async def my_list(subject: str = "", type: str = "", status: int = -1,
                  page: int = 1, page_size: int = 20,
                  current_user: SysUser = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    q = db.query(StudyMaterial).filter(
        StudyMaterial.creator_id == current_user.user_id,
        StudyMaterial.status >= 0,
    )
    if subject:
        q = q.filter(StudyMaterial.subject == subject)
    if type:
        q = q.filter(StudyMaterial.type == type)
    if status in (0, 1, 2):
        q = q.filter(StudyMaterial.status == status)
    total = q.count()
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    rows = (q.order_by(StudyMaterial.material_id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"total": total, "page": page, "page_size": page_size,
            "items": [_item_brief(m) for m in rows]}


@router.put("/my/{material_id}", summary="改我自己的卡")
async def my_update(material_id: int, body: dict,
                    current_user: SysUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    if m.creator_id != current_user.user_id and not _own_or_admin(current_user):
        raise HTTPException(403, "只能修改自己创建的资料")
    data = _validate_material_body(body, partial=True)
    for k, v in data.items():
        setattr(m, k, v)
    if isinstance(body.get("publish"), bool):
        m.status = 1 if body["publish"] else 2
    db.commit()
    _audit(db, current_user, "my_update", f"material:{material_id}", m.title)
    db.commit()
    return {"ok": True, "status": m.status}


@router.delete("/my/{material_id}", summary="删我自己的卡(软删)")
async def my_delete(material_id: int,
                    current_user: SysUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    if m.creator_id != current_user.user_id and not _own_or_admin(current_user):
        raise HTTPException(403, "只能删除自己创建的资料")
    m.status = -1
    db.commit()
    _audit(db, current_user, "my_delete", f"material:{material_id}", m.title)
    db.commit()
    return {"ok": True}


@router.post("/admin/cards/batch-image", summary="批量上传卡片配图(≤9张)")
async def batch_image(files: List[UploadFile] = File(...),
                      current_user: SysUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """一次上传多张配图，供「一卡多图」。任一不合格整批拒绝（原子性）。"""
    _require_admin(current_user)
    if not files:
        raise HTTPException(400, "未选择文件")
    if len(files) > 9:
        raise HTTPException(400, "一次最多 9 张图片")
    images = []
    written = []          # B3：本批已落盘 URL，失败时回收
    try:
        for fh in files:
            url = _safe_image_upload(fh)      # 复用白名单+魔数+uuid 重命名
            images.append({"url": url})
            written.append(url)
    except HTTPException:
        # B3：整批拒绝时回收本批已落盘文件，避免孤儿文件
        for u in written:
            p = UPLOAD_IMG_DIR / _os.path.basename(u)
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        raise                          # 整批拒绝，不落库
    _audit(db, current_user, "batch_image", f"count:{len(images)}", None)
    db.commit()
    return {"images": images, "count": len(images)}




# ==================== 分享与领取（B2：复制语义） ====================
_SHARE_COPY_FIELDS = ("subject", "type", "category", "title", "summary", "content",
                      "card_front", "card_back", "cover_image", "video_id",
                      "duration", "read_time", "difficulty", "badge", "sort_order")


def _get_share(material_id: int, db: Session):
    return db.query(MaterialShare).filter(
        MaterialShare.material_id == material_id).first()


@router.get("/shared", summary="共享区(可领取的卡片)")
async def shared_list(subject: str = "", type: str = "", page: int = 1,
                      page_size: int = 20,
                      current_user: SysUser = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    q = (db.query(MaterialShare, StudyMaterial)
         .join(StudyMaterial, StudyMaterial.material_id == MaterialShare.material_id)
         .filter(MaterialShare.status == 1, StudyMaterial.status >= 0))
    if subject:
        q = q.filter(StudyMaterial.subject == subject)
    if type:
        q = q.filter(StudyMaterial.type == type)
    total = q.count()
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    rows = (q.order_by(MaterialShare.share_id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())

    owners = {r[0]: r[1] for r in db.query(SysUser.user_id, SysUser.username)
              .filter(SysUser.user_id.in_({sh.owner_id for sh, _ in rows})).all()} if rows else {}
    adopted = {r[0] for r in db.query(MaterialAdoptLog.share_id)
               .filter(MaterialAdoptLog.user_id == current_user.user_id,
                       MaterialAdoptLog.share_id.in_({sh.share_id for sh, _ in rows})).all()} if rows else []

    items = []
    for sh, m in rows:
        item = _item_brief(m)
        item.update({
            "share_id": sh.share_id,
            "owner_id": sh.owner_id,
            "owner_name": owners.get(sh.owner_id),
            "adopted_count": sh.adopted_count or 0,
            "is_mine": sh.owner_id == current_user.user_id,
            "is_adopted": sh.share_id in adopted,
        })
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/{material_id}/share", summary="分享卡片到共享区")
async def share_material(material_id: int,
                         current_user: SysUser = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    if m.creator_id != current_user.user_id and not _own_or_admin(current_user):
        raise HTTPException(403, "只能分享自己创建的资料")

    sh = _get_share(material_id, db)
    if sh is None:
        sh = MaterialShare(material_id=material_id,
                           owner_id=current_user.user_id, status=1)
        db.add(sh)
    else:
        sh.status = 1
        sh.owner_id = current_user.user_id
    m.status = 1                     # 分享即公开
    db.commit()
    _audit(db, current_user, "share", f"material:{material_id}", m.title)
    db.commit()
    return {"ok": True, "material_id": material_id, "status": 1}


@router.post("/{material_id}/unshare", summary="撤回分享")
async def unshare_material(material_id: int,
                           current_user: SysUser = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    sh = _get_share(material_id, db)
    if not sh or sh.status != 1:
        raise HTTPException(404, "该卡片未在共享区")
    if sh.owner_id != current_user.user_id and not _own_or_admin(current_user):
        raise HTTPException(403, "只能撤回自己分享的资料")
    sh.status = 0
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id).first()
    if m and m.status == 1:
        m.status = 2                 # 回私有
    db.commit()
    _audit(db, current_user, "unshare", f"material:{material_id}", None)
    db.commit()
    return {"ok": True, "material_id": material_id, "status": 0}


@router.post("/{material_id}/adopt", summary="收进我的库(复制一份)")
async def adopt_material(material_id: int,
                         current_user: SysUser = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    sh = _get_share(material_id, db)
    if not sh or sh.status != 1:
        raise HTTPException(404, "该卡片未分享或已撤回")
    src = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not src:
        raise HTTPException(404, "源卡片不存在或已删除")
    if src.creator_id == current_user.user_id:
        raise HTTPException(400, "不能领取自己分享的卡片")
    dup = db.query(MaterialAdoptLog).filter(
        MaterialAdoptLog.share_id == sh.share_id,
        MaterialAdoptLog.user_id == current_user.user_id).first()
    if dup:
        raise HTTPException(409, "你已经领取过这张卡片")

    from ....services.material_sanitizer import sanitize_html

    data = {f: getattr(src, f) for f in _SHARE_COPY_FIELDS}
    if data.get("content"):
        data["content"] = sanitize_html(data["content"])   # 源卡可能来自低权限用户
    combined = (data.get("card_front") or "") + (data.get("card_back") or "") + (data.get("content") or "")
    new = StudyMaterial(**data,
                        creator_id=current_user.user_id,
                        status=2,
                        source_material_id=material_id,
                        content_hash=(content_cleaner.calculate_content_hash(combined)
                                      if combined else None))
    db.add(new)
    db.flush()
    db.add(MaterialAdoptLog(share_id=sh.share_id,
                            user_id=current_user.user_id,
                            created_id=new.material_id))
    sh.adopted_count = (sh.adopted_count or 0) + 1
    db.commit()
    _audit(db, current_user, "adopt", f"material:{material_id}",
           f"复制为 {new.material_id}")
    db.commit()
    return {"ok": True, "id": new.material_id, "source_material_id": material_id}



@router.get("/{material_id}", summary="资料详情(游客可访问)")
async def material_detail(material_id: int,
                          current_user: Optional[SysUser] = Depends(get_optional_user),
                          db: Session = Depends(get_db)):
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id, StudyMaterial.status == 1).first()
    if not m:
        raise HTTPException(404, "资料不存在或已下架")

    first_open = False
    if current_user:
        try:
            first_open = _mark_opened(db, current_user.user_id, material_id)
        except Exception as e:  # noqa: BLE001 — 打开记录失败不阻断详情返回
            db.rollback()
            logger.warning("[materials] 记录打开失败 material=%s: %s", material_id, e)

    m.view_count = (m.view_count or 0) + 1
    db.commit()

    prog = None
    if current_user:
        prog = db.query(UserMaterialProgress).filter(
            UserMaterialProgress.user_id == current_user.user_id,
            UserMaterialProgress.material_id == material_id).first()

    # E8：同资料二次打开不重复发布（_mark_opened 去重）
    if first_open:
        try:
            await record_user_action(
                db, current_user.user_id, TRIGGER_MATERIAL_OPENED
            )
        except Exception as e:  # noqa: BLE001 — 事件失败不影响详情返回
            logger.warning("[materials] 学习行为事件发布失败 material=%s: %s",
                           material_id, e)

    d = _item_brief(m, prog)
    d.update({"content": m.content or "", "card_back": m.card_back or "",
              "video_url": f"/api/video/{m.video_id}/stream" if m.video_id else ""})
    return d


# ============================ 管理端（role=admin）============================

import json as _json  # noqa: E402
import os as _os  # noqa: E402
import shutil as _shutil  # noqa: E402
import uuid as _uuid  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from fastapi import File, UploadFile  # noqa: E402

from ....models.models import MaterialImportRecord, SysOperationLog  # noqa: E402
from ....services.material_sanitizer import sanitize_html  # noqa: E402
from ....services.material_classifier import classifier  # noqa: E402
from ....services.material_deduplicator import deduplicator  # noqa: E402
from ....services.material_sanitizer import content_cleaner  # noqa: E402
from ....services.material_monitor import import_monitor  # noqa: E402

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


# ==================== 文件校验（Task 12）====================

ALLOWED_UPLOAD_EXT = {".docx", ".xlsx", ".pdf", ".jpg", ".jpeg", ".png", ".mp4", ".zip", ".rar"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB


def _validate_file_upload(file: UploadFile, content: bytes) -> list:
    """校验上传文件，返回错误列表（空=通过）。"""
    errors = []
    if len(content) > MAX_FILE_SIZE:
        errors.append(f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")
    ext = _os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        errors.append(f"不支持的文件格式: {ext}")
    magic = MAGIC_BYTES.get(ext)
    if magic and not content.startswith(magic):
        errors.append("文件实际格式与扩展名不符")
    return errors


def _safe_file_upload(file: UploadFile) -> tuple:
    """安全上传：校验 + 写临时文件，返回 (tmp_path, ext)。"""
    content = file.file.read()
    file.file.seek(0)
    errors = _validate_file_upload(file, content)
    if errors:
        raise HTTPException(400, "; ".join(errors))
    UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    ext = _os.path.splitext(file.filename or "")[1].lower()
    tmp_name = f"{_uuid.uuid4().hex}{ext}"
    tmp_path = UPLOAD_TMP_DIR / tmp_name
    tmp_path.write_bytes(content)
    return str(tmp_path), ext


def _require_admin(user: SysUser):
    """SysUser 的角色字段是 user_type（student/teacher/admin），非 role。"""
    if user is None or getattr(user, "user_type", "") != "admin":
        raise HTTPException(403, "需要管理员权限")


def _audit(db: Session, user: SysUser, action: str, target: str, detail: str = ""):
    """写审计日志。字段名对照 models.SysOperationLog 真实定义（models.py:793）。
    操作类型与模块名统一中文化，保证日志界面无英文。"""
    action_cn = {
        "create": "新建资料",
        "update": "编辑资料",
        "delete": "删除资料",
        "status": "状态变更",
        "upload_image": "上传图片",
        "import_confirm": "导入入库",
        "batch_create": "批量创建",
        "batch_delete": "批量删除",
    }.get(action, action)
    try:
        db.add(SysOperationLog(
            user_id=user.user_id,
            user_name=getattr(user, "username", None) or getattr(user, "real_name", ""),
            operation_type=action_cn,
            module_name="资料管理",
            # 操作描述优先用中文 detail，缺失时回退到中文动作名，
            # 避免泄漏英文 target（URL 路径 / material:123 / created=1 等）
            operation_desc=detail or action_cn,
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
                       purpose: str = Query("inline", description="cover|inline"),
                       current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_admin(current_user)
    url = _safe_image_upload(file)
    _audit(db, current_user, "upload_image", f"{purpose}:{url}")
    db.commit()
    return {"url": url, "purpose": purpose}


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
        _check_card_text(data.get("card_front"), data.get("card_back"))
        if data["content"]:
            data["content"] = sanitize_html(data["content"])
    elif data.get("content"):
        data["content"] = sanitize_html(data["content"])
    return {k: v for k, v in data.items() if v is not None}


# ========== B：卡片文本格式校验 + 关键词自动分类（专利主张 (3) 的落地部件） ==========
CARD_FRONT_MAX = 120
CARD_BACK_MAX = 600
_DANGEROUS_TAGS = ("<script", "<iframe", "<object", "<embed", "<style")


def _check_card_text(front, back) -> None:
    """卡片文本格式校验：长度上限 + 禁止脚本类标签。不合规直接 400。"""
    for label, val, cap in (("卡片正面", front, CARD_FRONT_MAX),
                            ("卡片背面", back, CARD_BACK_MAX)):
        if not val:
            continue
        if len(val) > cap:
            raise HTTPException(400, f"{label}超过 {cap} 字（当前 {len(val)} 字）")
        low = str(val).lower()
        for tag in _DANGEROUS_TAGS:
            if tag in low:
                raise HTTPException(400, f"{label}含不允许的标签（script/iframe/object/embed/style）")


def _auto_classify(db, subject, title, front, back):
    """按 material_classification_rules 的 keyword 规则判定子类；无匹配返回 None。

    规则来自表（可后台维护）；跨科目规则不参与匹配，避免「逻辑填空」这类
    行测词把申论卡误分类。
    """
    from ....models.models import MaterialClassificationRule  # 局部导入

    text = " ".join(x for x in (title, front, back) if x)
    if not text:
        return None
    rules = (db.query(MaterialClassificationRule)
             .filter(MaterialClassificationRule.enabled == 1,
                     MaterialClassificationRule.rule_type == "keyword")
             .order_by(MaterialClassificationRule.priority.desc()).all())
    for r in rules:
        try:
            cfg = r.rule_config or {}
            if isinstance(cfg, str):          # 兼容存字符串的历史数据
                cfg = _json.loads(cfg)
            if not isinstance(cfg, dict):
                continue
        except Exception:
            continue
        if cfg.get("subject") and cfg["subject"] != subject:
            continue
        if any(k and k in text for k in (cfg.get("keywords") or [])):
            return cfg.get("category")
    return None


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
    if not data.get("category"):
        auto = _auto_classify(db, data.get("subject"), data.get("title"),
                              data.get("card_front"), data.get("card_back"))
        if auto:
            data["category"] = auto
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
    _audit(db, current_user, "status", f"material:{material_id}",
           "上架" if st == 1 else "下架")
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


# ============================ 统计概览 & 批量操作（Task3/4）============================

@router.get("/admin/stats", summary="统计概览(管理员)")
async def admin_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回资料总量、按类型/科目/状态的分布统计。"""
    _require_admin(current_user)

    total = db.query(func.count(StudyMaterial.material_id)).scalar() or 0

    type_rows = (
        db.query(StudyMaterial.type, func.count(StudyMaterial.material_id))
        .group_by(StudyMaterial.type)
        .all()
    )
    type_stats = dict(type_rows)

    subject_rows = (
        db.query(StudyMaterial.subject, func.count(StudyMaterial.material_id))
        .group_by(StudyMaterial.subject)
        .all()
    )
    subject_stats = dict(subject_rows)

    status_rows = (
        db.query(StudyMaterial.status, func.count(StudyMaterial.material_id))
        .group_by(StudyMaterial.status)
        .all()
    )
    status_stats = dict(status_rows)

    return {
        "total": total,
        "by_type": {
            "video_intro": type_stats.get("video_intro", 0),
            "video_advanced": type_stats.get("video_advanced", 0),
            "article": type_stats.get("article", 0),
            "card": type_stats.get("card", 0),
        },
        "by_subject": {
            "xingce": subject_stats.get("xingce", 0),
            "shenlun": subject_stats.get("shenlun", 0),
            "gongzhuan": subject_stats.get("gongzhuan", 0),
        },
        "by_status": {
            "published": status_stats.get(1, 0),
            "draft": status_stats.get(0, 0),
        },
    }


@router.post("/admin/batch", summary="批量创建资料(管理员)")
async def admin_batch_create(
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量创建多条资料。body.items 为资料对象数组。"""
    _require_admin(current_user)
    items = body.get("items", [])
    if not items:
        raise HTTPException(400, "items 不能为空")
    limit = 100
    if len(items) > limit:
        raise HTTPException(400, f"单次最多 {limit} 条")

    created_ids = []
    for item in items:
        data = _validate_material_body(item)
        m = StudyMaterial(**data, creator_id=current_user.user_id)
        db.add(m)
        db.flush()
        created_ids.append(m.material_id)

    db.commit()
    _audit(db, current_user, "batch_create", f"created={len(created_ids)}")
    db.commit()
    return {"created": len(created_ids), "material_ids": created_ids}


@router.delete("/admin/batch", summary="批量删除资料(管理员)")
async def admin_batch_delete(
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量删除多条资料。body.ids 为资料 ID 数组。"""
    _require_admin(current_user)
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "ids 不能为空")

    # 先删学习进度
    db.query(UserMaterialProgress).filter(
        UserMaterialProgress.material_id.in_(ids)
    ).delete(synchronize_session=False)

    deleted = db.query(StudyMaterial).filter(
        StudyMaterial.material_id.in_(ids)
    ).delete(synchronize_session=False)

    db.commit()
    _audit(db, current_user, "batch_delete", f"deleted={deleted}")
    db.commit()
    return {"deleted": deleted}


@router.get("/admin/import-records", summary="导入记录列表(管理员)")
async def admin_import_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询导入记录分页列表。"""
    _require_admin(current_user)
    q = db.query(MaterialImportRecord)
    total = q.count()
    rows = (
        q.order_by(MaterialImportRecord.import_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for r in rows:
        items.append({
            "import_id": r.import_id,
            "file_name": r.file_name,
            "file_type": r.file_type,
            "file_size": r.file_size,
            "parse_status": r.parse_status,
            "uploader_id": r.uploader_id,
            "create_time": r.create_time.isoformat() if r.create_time else None,
        })
    return {"total": total, "items": items}


# ============================ 智能导入（内容工厂四步流）============================

from fastapi import BackgroundTasks  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402

ALLOWED_DOC_EXT = {".docx", ".xlsx", ".pdf"}
DOC_SIZE_LIMIT = 20 * 1024 * 1024
XLSX_SIZE_LIMIT = 5 * 1024 * 1024
CARD_ROW_LIMIT = 500


def _save_tmp(file: UploadFile) -> tuple:
    ext = _os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_DOC_EXT:
        raise HTTPException(400, "仅支持 docx/xlsx/pdf")
    content = file.file.read()
    limit = XLSX_SIZE_LIMIT if ext == ".xlsx" else DOC_SIZE_LIMIT
    if len(content) > limit:
        raise HTTPException(400, f"文件超过 {limit // 1024 // 1024}MB 上限")
    magic = MAGIC_BYTES.get(ext)
    if magic and not content.startswith(magic):
        raise HTTPException(400, "文件实际格式与扩展名不符")
    UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_name = f"{_uuid.uuid4().hex}{ext}"
    (UPLOAD_TMP_DIR / tmp_name).write_bytes(content)
    return str(UPLOAD_TMP_DIR / tmp_name), ext


def _load_result(rec: MaterialImportRecord) -> dict:
    try:
        return _json.loads(rec.parse_result or "{}")
    except (TypeError, ValueError):
        return {}


def _migrate_images(import_id: int, result: dict) -> None:
    """把 parse_result.images 的临时图片迁入正式目录并改写 html 引用。"""
    html = result.get("html") or ""
    dest_dir = UPLOAD_IMG_DIR / f"import_{import_id}"
    for img in result.get("images", []):
        src = _Path(img.get("src_path", ""))
        if not src.exists():
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / img.get("name", src.name)
        _shutil.move(str(src), str(dest))
        old_ref = f"/uploads/materials/tmp/{src.name}"
        new_ref = f"/uploads/materials/images/import_{import_id}/{dest.name}"
        html = html.replace(old_ref, new_ref)
    # Word 内嵌图引用同样从 tmp 迁移
    for name in result.get("images", []):
        if isinstance(name, str):
            src = UPLOAD_TMP_DIR / name
            if src.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                _shutil.move(str(src), str(dest_dir / name))
                html = html.replace(f"/uploads/materials/tmp/{name}",
                                    f"/uploads/materials/images/import_{import_id}/{name}")
    result["html"] = sanitize_html(html)


@router.post("/admin/import/upload", summary="上传素材并解析(docx/xlsx/文字pdf同步；扫描pdf异步)")
async def import_upload(background_tasks: BackgroundTasks,
                        file: UploadFile = File(...),
                        current_user: SysUser = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _require_admin(current_user)
    tmp_path, ext = _save_tmp(file)
    rec = MaterialImportRecord(
        file_name=file.filename, file_type=ext.lstrip("."),
        file_size=_os.path.getsize(tmp_path), parse_status="pending",
        uploader_id=current_user.user_id)
    db.add(rec)
    db.commit()
    db.refresh(rec)

    scanned = False
    if ext == ".pdf":
        from ....services.material_parser import detect_scanned
        try:
            scanned = detect_scanned(tmp_path)
        except Exception:
            rec.parse_status = "failed"
            rec.error_message = "PDF 已加密或损坏，请解除密码后重新上传"
            rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
            db.commit()
            raise HTTPException(400, rec.error_message)

    if ext == ".docx":
        try:
            from ....services.material_parser import parse_docx
            out = parse_docx(tmp_path, image_dir=UPLOAD_TMP_DIR)
            out["_tmp"] = tmp_path
            rec.parse_mode = "sync"
            rec.parse_status = "success"
            rec.parse_result = _json.dumps(out, ensure_ascii=False)
        except Exception as e:
            rec.parse_status = "failed"
            rec.error_message = f"Word 文档损坏或格式不受支持: {e}"
            rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
        db.commit()
    elif ext == ".xlsx":
        try:
            from ....services.material_parser import parse_xlsx
            out = parse_xlsx(tmp_path)
            out["_tmp"] = tmp_path
            rec.parse_mode = "sync"
            rec.parse_status = "success"
            rec.parse_result = _json.dumps(out, ensure_ascii=False)
        except Exception as e:
            rec.parse_status = "failed"
            rec.error_message = f"Excel 解析失败（空表或损坏）: {e}"
            rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
        db.commit()
    elif ext == ".pdf":
        if scanned:
            from ....services.mineru_material_service import (
                mineru_available, run_mineru, MineruError)
            if not mineru_available():
                rec.parse_status = "failed"
                rec.error_message = ("该 PDF 为扫描图片版且系统 OCR 组件未就绪，"
                                     "请转存为文字版 Word 后重新上传")
                rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
                db.commit()
                raise HTTPException(400, rec.error_message)
            rec.parse_mode = "async(mineru)"
            rec.parse_status = "processing"
            rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
            db.commit()

            def _ocr_job(import_id: int, path: str, workdir: str):
                """后台线程：跑 OCR 并回写记录（自带独立 DB 会话）。"""
                from ....core.database import SessionLocal
                s = SessionLocal()
                try:
                    r = run_mineru(path, _Path(workdir))
                    row = s.query(MaterialImportRecord).get(import_id)
                    result = _load_result(row)
                    result.update({"chapters": [], "html": r["html"],
                                   "images": r["images"],
                                   "word_count": len(r["html"]),
                                   "_seconds": r["seconds"]})
                    row.parse_status = "success"
                    row.parse_result = _json.dumps(result, ensure_ascii=False)
                    s.commit()
                except Exception as e:
                    row = s.query(MaterialImportRecord).get(import_id)
                    row.parse_status = "failed"
                    row.error_message = f"OCR 失败({type(e).__name__}): 可点击重试或转存 Word"
                    s.commit()
                finally:
                    s.close()

            background_tasks.add_task(run_in_threadpool,
                                      _ocr_job, rec.import_id, tmp_path,
                                      str(UPLOAD_TMP_DIR))
        else:
            try:
                from ....services.material_parser import parse_pdf_text
                out = parse_pdf_text(tmp_path)
                out["_tmp"] = tmp_path
                rec.parse_mode = "sync"
                rec.parse_status = "success"
                rec.parse_result = _json.dumps(out, ensure_ascii=False)
            except Exception as e:
                rec.parse_status = "failed"
                rec.error_message = f"PDF 解析失败: {e}"
                rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
            db.commit()

    resp = {"import_id": rec.import_id, "parse_status": rec.parse_status}
    if rec.error_message:
        resp["error_message"] = rec.error_message

    # 监控记录（Task 15）
    import_monitor.record_import(success=(rec.parse_status == "success"))
    alerts = import_monitor.check_alerts(db)
    if alerts:
        logger.warning("[materials] import alerts: %s", alerts)

    return JSONResponse(resp)


@router.get("/admin/import/{import_id}/status", summary="轮询导入状态(前端3s一次)")
async def import_status(import_id: int,
                        current_user: SysUser = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _require_admin(current_user)
    rec = db.query(MaterialImportRecord).filter(
        MaterialImportRecord.import_id == import_id).first()
    if not rec:
        raise HTTPException(404, "导入记录不存在")
    elapsed = ((datetime.now() - rec.create_time).total_seconds()
               if rec.create_time else 0)
    return {"parse_status": rec.parse_status, "elapsed_seconds": int(elapsed),
            "error_message": rec.error_message}


@router.get("/admin/import/{import_id}/preview", summary="取解析预览")
async def import_preview(import_id: int,
                         current_user: SysUser = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    _require_admin(current_user)
    rec = db.query(MaterialImportRecord).filter(
        MaterialImportRecord.import_id == import_id).first()
    if not rec:
        raise HTTPException(404, "导入记录不存在")
    if rec.parse_status != "success":
        raise HTTPException(409, f"尚未解析成功: {rec.parse_status}")
    result = _load_result(rec)
    result.pop("_tmp", None)   # 不向前端泄露服务器路径
    payload = {"file_type": rec.file_type, "result": result}
    # D3 澄清：parse_xlsx 已把表头拆进 headers，rows 只含数据行；
    # 这里回传 headers/row_count，管理员可确认表头是否被正确识别。
    if rec.file_type == "xlsx":
        payload["headers"] = result.get("headers") or []
        payload["row_count"] = len(result.get("rows") or [])
    return payload


@router.post("/admin/import/{import_id}/confirm", summary="确认入库(status=0下架态)")
async def import_confirm(import_id: int, body: dict,
                         current_user: SysUser = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    _require_admin(current_user)
    rec = db.query(MaterialImportRecord).filter(
        MaterialImportRecord.import_id == import_id).first()
    if not rec:
        raise HTTPException(404, "导入记录不存在")
    if rec.parse_status != "success":
        raise HTTPException(409, f"尚未解析成功: {rec.parse_status}")
    subject = body.get("subject")
    if subject not in SUBJECTS:
        raise HTTPException(400, "科目必选且有效")
    category = body.get("category")
    badge = body.get("badge")
    result = _load_result(rec)
    created_ids = []
    skipped: list = []          # D4：重复/无效行明细，回传给前端
    publish = bool(body.get("publish"))   # D2：导入即上线（默认 false）

    if rec.file_type == "xlsx":
        mapping = body.get("column_mapping") or {}
        try:
            col_front = int(mapping["front"])
            col_back = int(mapping["back"])
            col_cat = (int(mapping["category"])
                       if mapping.get("category") not in (None, "") else None)
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "列映射不完整（正面列/背面列必填）")
        from ....services.material_parser import build_cards, parse_xlsx
        # preview 只回传前200行；confirm 从原始文件重读全量行
        full = parse_xlsx(result["_tmp"], max_rows=CARD_ROW_LIMIT) \
            if result.get("_tmp") and _Path(result["_tmp"]).exists() else result
        raw_rows = list(full.get("rows") or [])
        # D5：build_cards 会静默丢弃正面或背面为空的行，这里先算出来回报
        invalid_rows = [
            i for i, r in enumerate(raw_rows, start=1)
            if not (r[col_front].strip() if col_front < len(r) else "")
            or not (r[col_back].strip() if col_back < len(r) else "")
        ]
        cards = build_cards(raw_rows, col_front, col_back, col_cat,
                            limit=CARD_ROW_LIMIT)
        if not cards:
            raise HTTPException(400, "按当前列映射未得到有效卡片（正反面均不能为空）")
        base_title = _os.path.splitext(rec.file_name)[0]
        for idx, c in enumerate(cards, start=1):
            # 内容清洗
            card_front = content_cleaner.clean_text(c["card_front"])
            card_back = content_cleaner.clean_text(c["card_back"])
            # 去重检测
            combined = card_front + card_back
            dup_check = deduplicator.check_duplicate(combined, db, user_id=current_user.user_id)
            if dup_check["is_duplicate"]:
                import_monitor.record_duplicate_match()
                skipped.append({"row": idx, "reason": "duplicate"})
                continue  # 跳过重复内容
            # 类型由「正/背面双列」这一输入契约唯一确定，不再交给启发式分类器：
            # 分类器只看扩展名+标题关键词，卡片正文短会判成 article，导致卡片
            # 落入文章区、翻卡 UI 永不触发（D1）。此处只按业务事实写 card。
            content_hash = content_cleaner.calculate_content_hash(combined)
            m = StudyMaterial(
                subject=subject, type="card",
                category=c["category"] or category,
                title=card_front, card_front=card_front,
                card_back=card_back,
                content_hash=content_hash,
                sort_order=idx, status=(1 if publish else 0),
                creator_id=current_user.user_id)
            db.add(m)
            db.flush()          # 立即取自增主键，避免 commit 前为 None
            created_ids.append(m.material_id)
        _ = base_title
    else:
        mtype = body.get("type")
        if mtype not in ("article",):
            raise HTTPException(400, "文档类素材入库类型只能是 article")
        _migrate_images(import_id, result)
        word_count = result.get("word_count", 0)
        # 内容清洗
        raw_content = result.get("html") or ""
        content = content_cleaner.clean_text(raw_content)
        title = (body.get("title") or _os.path.splitext(rec.file_name)[0])[:200]
        summary_text = (body.get("summary") or "")[:500]
        # 去重检测
        content_hash = content_cleaner.calculate_content_hash(content)
        dup_check = deduplicator.check_duplicate(content, db, user_id=current_user.user_id)
        if dup_check["is_duplicate"]:
            import_monitor.record_duplicate_match()
        # 智能分类
        ext = "." + rec.file_type
        classification = classifier.classify(ext, content=content, title=title)
        m = StudyMaterial(
            subject=subject, type=classification["type"],
            category=category, badge=badge,
            title=title, summary=summary_text,
            content=content, content_hash=content_hash,
            status=0, read_time=max(1, word_count // 400),
            creator_id=current_user.user_id)
        db.add(m)
        db.flush()
        created_ids.append(m.material_id)

    db.commit()
    rec.parse_status = "consumed"
    db.commit()
    # 清理临时源文件
    tmp = result.get("_tmp")
    if tmp and _Path(tmp).exists():
        try:
            _os.remove(tmp)
        except OSError:
            pass
    _audit(db, current_user, "import_confirm", f"import:{import_id}",
           f"导入 {len(created_ids)} 条资料")
    db.commit()
    resp = {"created": len(created_ids), "material_ids": created_ids,
            "type": ("card" if rec.file_type == "xlsx" else "article"),
            "published": publish}
    if rec.file_type == "xlsx":
        resp["invalid_rows"] = invalid_rows
        resp["skipped"] = skipped
        resp["skipped_count"] = len(skipped) + len(invalid_rows)
    return JSONResponse(resp)
