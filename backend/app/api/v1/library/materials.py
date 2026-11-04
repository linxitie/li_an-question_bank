"""备考资料 API。响应风格与 news.py 一致：裸 JSON。

学生组：GET "" 列表 / GET "/{id}" 详情 / GET "/progress-summary" / POST "/progress"
        POST "/{id}/favorite" / GET "/favorites"
管理组：见同文件下半部（admin/import 组，Task3/T6 追加）。
"""
import logging
import re
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, get_optional_user
from ....core.trigger_types import TRIGGER_MATERIAL_OPENED
from ....api.v1.catalog import contract as taxonomy   # 分类法只读契约（P4.1 跨域约定）
from ....models.models import (StudyMaterial, UserMaterialProgress, SysUser,
                               MaterialShare, MaterialAdoptLog)
from ....services.event_consumer import record_user_action

router = APIRouter(prefix="/api/materials", tags=["备考资料"])
logger = logging.getLogger(__name__)

SUBJECTS = {"xingce", "shenlun", "gongzhuan"}
TYPES = {"video_intro", "video_advanced", "article", "card"}

# 卡片配图：第 1 张落 cover_image，第 2 张内嵌在 content 的 <img> 里。
# 列表/详情页都要一次拿全，所以在 brief 里直接给出 image_urls（不额外暴露整段 content）。
_CONTENT_IMG_RE = re.compile(r'<img[^>]*?src=["\']([^"\']+)["\']', re.I)


def _brief_images(m: StudyMaterial) -> List[str]:
    urls: List[str] = []
    cover = (m.cover_image or "").strip()
    if cover:
        urls.append(cover)
    html = m.content or ""
    if "<img" in html:
        for u in _CONTENT_IMG_RE.findall(html):
            u = (u or "").strip()
            if u and u not in urls:
                urls.append(u)
    return urls


def _item_brief(m: StudyMaterial, prog: Optional[UserMaterialProgress] = None) -> dict:
    d = {
        "id": m.material_id, "subject": m.subject, "type": m.type,
        "category": m.category, "point_id": m.point_id,
        "title": m.title, "summary": m.summary,
        "badge": m.badge, "cover_image": m.cover_image,
        "duration": m.duration or 0, "read_time": m.read_time or 0,
        "difficulty": m.difficulty or 1, "view_count": m.view_count or 0,
        "card_front": m.card_front, "sort_order": m.sort_order or 0,
        "card_back": m.card_back,
        # 全部配图（封面 + 正文附图），PC/手机详情页「看全图」用
        "image_urls": _brief_images(m),
        # A 方案：技巧类卡片允许不挂具体考点（跨考点的通用方法），
        # 用 is_generic 打标，前端展示为「通用技巧」，按子类归集。
        "is_generic": bool(m.type == "card" and not m.point_id and (m.category or "").strip()),
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


@router.get("/taxonomy", summary="分类法：子类→考点（建卡表单下拉用）")
async def material_taxonomy(subject: str = Query(..., description="xingce/shenlun/gongzhuan"),
                            db: Session = Depends(get_db)):
    """只读取自 catalog 域的分类法契约，供学生「创建卡片」表单渲染两级下拉。

    路由必须声明在 `/{material_id}` 之前，否则会被整形路径参数吃掉。
    """
    if subject not in SUBJECTS:
        raise HTTPException(400, "无效科目")
    names = _category_names(db, subject)
    buckets = {n: [] for n in names}
    name_by_id = {}
    for pname, (pid, scid) in taxonomy.point_map(db, subject).items():
        if scid not in name_by_id:
            name_by_id[scid] = taxonomy.category_name_by_id(db, scid)
        cat = name_by_id[scid]
        if cat in buckets:
            buckets[cat].append({"id": pid, "name": pname})
    return {"subject": subject,
            "categories": [{"name": n,
                            "points": sorted(buckets[n], key=lambda x: x["id"])}
                           for n in names]}


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

    from ..reward.contract import grant_coins, has_grant, sum_granted

    already = None if not has_grant(
        db, user.user_id, source_type="MATERIAL",
        related_id=material.material_id) else True
    coins = 0
    if already is None:
        today = _dt.combine(date.today(), _dt.min.time())
        got = sum_granted(db, user.user_id, source_type="MATERIAL", since=today)
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


def _mark_opened(db: Session, user_id: int, material_id: int, *,
                 commit: bool = True) -> bool:
    """记录一次资料打开，返回是否为该用户对该资料的首次打开。

    复用 ``user_material_progress`` 的 ``(user_id, material_id)`` 唯一约束做去重：
    没有进度行说明从未打开过，插入一行作为「已打开」标记并发布事件；
    已有进度行（打开 / 学习 / 收藏任一途径建立）则不再重复发布。
    commit=False 时只 flush，由调用方与事件同事务提交。
    """
    exists = db.query(UserMaterialProgress).filter(
        UserMaterialProgress.user_id == user_id,
        UserMaterialProgress.material_id == material_id).first()
    if exists:
        return False
    db.add(UserMaterialProgress(user_id=user_id, material_id=material_id,
                                status=1, progress_percent=0))
    try:
        db.flush()
    except IntegrityError:
        # 并发下另一个请求先写入：唯一约束兜底，视为非首次
        db.rollback()
        return False
    if commit:
        db.commit()
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
    _finalize_classification(db, data)
    m = StudyMaterial(**data, creator_id=current_user.user_id,
                      status=(1 if body.get("publish") else 2))
    db.add(m)
    db.commit()
    db.refresh(m)
    _audit(db, current_user, "my_create", f"material:{m.material_id}", m.title)
    db.commit()
    return {"id": m.material_id, "status": m.status}


CARD_IMAGES_MAX = 2


@router.post("/my/card", summary="学生手动建卡(免审, 保存后立即公开)")
async def my_create_card(
    subject: str = Form(..., description="xingce/shenlun/gongzhuan"),
    card_front: str = Form(..., description="卡片正面（≤120 字）"),
    card_back: str = Form("", description="卡片背面（≤600 字；背面为空时必须配图）"),
    category: str = Form("", description="子类名，留空按文本自动判定"),
    point_id: str = Form("", description="考点ID，留空自动判定"),
    images: Optional[List[UploadFile]] = File(None),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学生端「创建卡片」：一次提交文本字段 + 0~2 张配图，**免审批**直接公开。

    与 `/my/upload`（表格批量、进待审队列）的区别：
    - 单张、人工填写，Q6 已确认学生建卡免审批 → `status=1` 立即展示；
    - 配图 1~2 张：第 1 张存 `cover_image`（封面），第 2 张进 `content`（详情附图），
      两张都走 `_safe_image_upload` 的扩展名/魔数/≤5MB 校验；
    - 分类可由前端下拉指定，也可留空走与导入一致的两轮自动分类。
    """
    if subject not in SUBJECTS:
        raise HTTPException(400, "无效科目")

    front = (card_front or "").strip()
    back = (card_back or "").strip()
    if not front:
        raise HTTPException(400, "卡片正面必填")
    _check_card_text(front, back)

    uploads = [f for f in (images or []) if f is not None and (f.filename or "").strip()]
    if len(uploads) > CARD_IMAGES_MAX:
        raise HTTPException(400, f"最多上传 {CARD_IMAGES_MAX} 张配图")
    if not back and not uploads:
        raise HTTPException(400, "卡片背面或配图至少填一个")

    # 配额：与学生批量上传共用同一套限额（当日 50 张 / 累计 500 张）
    today = datetime.now().strftime("%Y-%m-%d")
    today_cards = db.query(func.count(StudyMaterial.material_id)).filter(
        StudyMaterial.creator_id == current_user.user_id,
        func.date(StudyMaterial.create_time) == today,
    ).scalar() or 0
    if today_cards >= STUDENT_UPLOAD_DAILY * 10:
        raise HTTPException(
            429, f"今日已新建 {today_cards} 张，达到上限（{STUDENT_UPLOAD_DAILY * 10} 张），明天再试")
    owned = db.query(func.count(StudyMaterial.material_id)).filter(
        StudyMaterial.creator_id == current_user.user_id,
        StudyMaterial.type == "card",
    ).scalar() or 0
    if owned >= STUDENT_UPLOAD_TOTAL:
        raise HTTPException(429, f"你的资料库已达上限（{STUDENT_UPLOAD_TOTAL} 张）")

    from ....services.material_sanitizer import content_cleaner

    combined = front + back
    content_hash = content_cleaner.calculate_content_hash(combined)
    if db.query(StudyMaterial).filter(
            StudyMaterial.content_hash == content_hash).first():
        raise HTTPException(409, "这张卡片与资料库已有内容重复")

    # 分类收敛：显式优先，留空自动判定；非法候选回退自动分类并回报 warnings
    pid = None
    if (point_id or "").strip():
        try:
            pid = int(str(point_id).strip())
        except (TypeError, ValueError):
            raise HTTPException(400, "考点 ID 必须是整数")
    cls = _resolve_classification(
        db, subject, front, front, back,
        explicit_category=(category or "").strip() or None,
        explicit_point=pid, strict=False)
    data = {"subject": subject, "type": "card", "category": cls.get("category"),
            "point_id": cls.get("point_id"), "title": front, "card_front": front,
            "card_back": back}
    _finalize_classification(db, data)

    # 配图：任一失败整单拒绝，回收本单已落盘文件（避免孤儿图）
    urls, written = [], []
    try:
        for fh in uploads:
            url = _safe_image_upload(fh)
            urls.append(url)
            written.append(url)
    except HTTPException:
        for u in written:
            p = UPLOAD_IMG_DIR / _os.path.basename(u)
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        raise

    content = f'<p><img src="{urls[1]}" alt="卡片配图" /></p>' if len(urls) > 1 else None
    m = StudyMaterial(
        subject=subject, type="card", category=data.get("category"),
        point_id=data.get("point_id"), title=front[:200], card_front=front,
        card_back=back, content=content,
        cover_image=urls[0] if urls else None,
        content_hash=content_hash, status=1, creator_id=current_user.user_id,
        difficulty=1, read_time=2)
    db.add(m)
    db.commit()
    db.refresh(m)
    _audit(db, current_user, "create", f"material:{m.material_id}",
           f"学生建卡：{front[:30]}")
    db.commit()

    warnings = []
    if cls.get("rejected_category"):
        warnings.append(f"分类「{cls['rejected_category']}」不在本子类词表内，已按内容自动判定")
    return {"id": m.material_id, "status": m.status, "subject": m.subject,
            "title": m.title, "category": m.category, "point_id": m.point_id,
            "cover_image": m.cover_image, "images": urls,
            "warnings": warnings, "note": "已保存并公开展示（免审批）"}


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
    if "category" in data or "point_id" in data:
        subj = data.get("subject") or m.subject
        if "category" in data:
            data["category"] = _validate_category(db, subj, data["category"])
        if "point_id" in data:
            data["point_id"] = _validate_point(db, subj, data["point_id"])
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
            first_open = _mark_opened(
                db, current_user.user_id, material_id, commit=False
            )
        except Exception as e:  # noqa: BLE001 — 打开记录失败不阻断详情返回
            db.rollback()
            logger.warning("[materials] 记录打开失败 material=%s: %s", material_id, e)

    m.view_count = (m.view_count or 0) + 1

    # F2b：首次打开记录、浏览量、E8 事件同一事务提交。
    if first_open:
        await record_user_action(
            db, current_user.user_id, TRIGGER_MATERIAL_OPENED
        )
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
from ....core.config import settings  # noqa: E402
from ....services import media_service  # noqa: E402

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


def _safe_image_upload(file: UploadFile, db: Session | None = None,
                       user_id: int | None = None) -> str:
    ext = _os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "仅支持 png/jpg/webp 图片")
    content = file.file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 5MB")
    magic = MAGIC_BYTES.get(".jpg" if ext == ".jpeg" else ext)
    if magic and not content.startswith(magic):
        raise HTTPException(400, "文件实际格式与扩展名不符")

    if settings.MEDIA_STORE_ENABLED:
        if db is None:
            raise HTTPException(500, "媒体存储缺少数据库会话")
        try:
            asset = media_service.store_bytes(
                db, content, kind="material_image",
                original_name=file.filename or f"image{ext}",
                created_by=user_id, max_bytes=5 * 1024 * 1024,
            )
        except media_service.MediaTooLarge:
            raise HTTPException(400, "图片不能超过 5MB")
        except media_service.MediaValidationError as exc:
            raise HTTPException(400, str(exc))
        except media_service.ObjectStoreUnavailable:
            raise HTTPException(503, "图片存储暂不可用，请稍后重试")
        return f"/media/{asset.asset_id}"

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
    # 合并解冲突（2026-11-04）：保留远端的 db/user_id 入参（图片落库/审计能力），
    # 同时保留本地审计 target 里带 purpose 的口径，便于区分 cover / inline。
    url = _safe_image_upload(file, db=db, user_id=current_user.user_id)
    _audit(db, current_user, "upload_image", f"{purpose}:{url}")
    db.commit()
    return {"url": url, "purpose": purpose}


def _validate_material_body(body: dict, partial: bool = False) -> dict:
    keys = ("subject", "type", "category", "point_id", "title", "summary", "content",
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
    """按 material_classification_rules 判定子类；无匹配返回 None。

    匹配策略（v2）：标题优先 + 命中数计分。
    - 第一轮只比标题：标题里的词最能代表这张卡讲什么；
    - 第二轮才比「标题+正面+背面」：避免正文里的偶发词（如「辨词义」）把卡带偏；
    - 同一轮内按命中数排序，命中数相同再比 priority。
    """
    from ....models.models import MaterialClassificationRule  # 局部导入

    title = title or ""
    whole = " ".join(x for x in (title, front, back) if x)
    if not whole.strip():
        return None

    rules = (db.query(MaterialClassificationRule)
             .filter(MaterialClassificationRule.enabled == 1,
                     MaterialClassificationRule.rule_type == "keyword")
             .order_by(MaterialClassificationRule.priority.desc()).all())
    if not rules:
        return None

    def _cfg(r):
        try:
            c = r.rule_config or {}
            if isinstance(c, str):
                c = _json.loads(c)
            return c if isinstance(c, dict) else None
        except Exception:
            return None

    def _hits(cfg, text):
        kws = [k for k in (cfg.get("keywords") or []) if k]
        return sum(1 for k in kws if k in text)

    # 第一轮：只看标题
    best, best_key = None, (0, 0)
    for r in rules:
        cfg = _cfg(r)
        if not cfg or (cfg.get("subject") and cfg["subject"] != subject):
            continue
        h = _hits(cfg, title)
        if h <= 0:
            continue
        key = (h, r.priority or 0)
        if key > best_key:
            best, best_key = cfg.get("category"), key

    # 第二轮：标题未命中时，再看全文
    if not best:
        for r in rules:
            cfg = _cfg(r)
            if not cfg or (cfg.get("subject") and cfg["subject"] != subject):
                continue
            h = _hits(cfg, whole)
            if h <= 0:
                continue
            key = (h, r.priority or 0)
            if key > best_key:
                best, best_key = cfg.get("category"), key

    return best


def _resolve_card_category(db, subject, front, back, explicit=None):
    """卡片分类三级优先：显式分类（表格分类列/请求体）> 关键词自动分类 > 空。

    导入场景里 title 就是卡片正面（import_confirm 用 card_front 当 title），
    因此标题优先的匹配策略等价于「先看正面，再看正+背面」。
    """
    if explicit:
        return _validate_category(db, subject, explicit)
    return _auto_classify(db, subject, front, front, back)


# ========== B2：分类法三层贯通（子类词表 → 考点 → 资料）==========
# 2026-10-30 实测：sub_categories 16 条（行测 8 / 申论 5 / 公专 3），
# knowledge_point 94 条（level=2、parent_id=0，是**扁平考点表**），
# 但 study_material 只挂子类、考点层没有任何资料；category 也从未校验过词表，
# 于是出现「方法技巧」这类游离类目（行测 12 张卡）。
# 这里补上第三层：point_id 落库 + 两级自动分类 + 子类词表校验。
SUBJECT_IDS = taxonomy.SUBJECT_IDS


def _category_names(db, subject) -> List[str]:
    return taxonomy.category_names(db, subject)


def _validate_category(db, subject, category):
    """分类必须是 sub_categories 里的合法子类；非法 → 400 并提示最近词。"""
    cat = (category or "").strip()
    if not cat:
        return None
    names = _category_names(db, subject)
    if not names or cat in names:
        # 词表空（新科目尚未配置）时不阻断，保持向前兼容
        return cat
    import difflib
    close = difflib.get_close_matches(cat, names, n=1, cutoff=0.3)
    hint = (f"是否想用「{close[0]}」？" if close else "可选：" + "、".join(names))
    raise HTTPException(400, f"分类「{cat}」不在 {subject} 的子类词表内，{hint}")


def _point_map(db, subject) -> dict:
    """考点名 → KnowledgePoint 行（经 catalog 契约）。"""
    return taxonomy.point_map(db, subject)


def _validate_point(db, subject, point_id) -> int:
    try:
        pid = int(point_id)
    except (TypeError, ValueError):
        raise HTTPException(400, "point_id 必须是整数")
    if not taxonomy.point_belongs_to(db, subject, pid):
        raise HTTPException(400, f"考点 {pid} 不在 {subject} 的考点表内")
    return pid


def _point_row(db, subject, point_id):
    return taxonomy.point_by_id(db, subject, point_id)


def _point_id_by_name(db, subject, name):
    return taxonomy.point_id_by_name(db, subject, name)


def _category_of_point(db, subject, point_id) -> Optional[str]:
    return taxonomy.category_of_point(db, subject, point_id)


def _auto_classify_ex(db, subject, title, front, back):
    """两级自动分类：子类 + 考点。

    规则形态（material_classification_rules.rule_config）：
        {"subject": "xingce", "category": "判断推理", "keywords": [...]}          # 子类级
        {"subject": "xingce", "category": "判断推理", "point": "图形推理",
         "keywords": [...]}                                                      # 考点级

    计分沿用 v2：标题优先 → 全文兜底；同级内 (命中数, priority) 取大。
    返回 {'category', 'point_name', 'point_id'} 或 None。
    """
    from ....models.models import MaterialClassificationRule  # 局部导入

    title = title or ""
    whole = " ".join(x for x in (title, front, back) if x)
    if not whole.strip():
        return None

    rules = (db.query(MaterialClassificationRule)
             .filter(MaterialClassificationRule.enabled == 1,
                     MaterialClassificationRule.rule_type == "keyword")
             .order_by(MaterialClassificationRule.priority.desc()).all())
    if not rules:
        return None

    def _cfg(r):
        try:
            c = r.rule_config or {}
            if isinstance(c, str):
                c = _json.loads(c)
            return c if isinstance(c, dict) else None
        except Exception:
            return None

    cfgs = [(r, _cfg(r)) for r in rules]
    cfgs = [(r, c) for r, c in cfgs
            if c and (not c.get("subject") or c["subject"] == subject)]

    def _hits(cfg, text):
        return sum(1 for k in (cfg.get("keywords") or []) if k and k in text)

    best_cat, best_cat_key = None, (0, 0)
    best_pt, best_pt_key, best_pt_cat = None, (0, 0), None

    # 第一轮：只看标题（标题最能代表这张卡讲什么）
    for r, cfg in cfgs:
        h = _hits(cfg, title)
        if h <= 0:
            continue
        key = (h, r.priority or 0)
        if cfg.get("category") and key > best_cat_key:
            best_cat, best_cat_key = cfg["category"], key
        if cfg.get("point") and key > best_pt_key:
            best_pt, best_pt_key, best_pt_cat = cfg["point"], key, cfg.get("category")

    # 第二轮：标题未命中的那一级，用全文兜底
    if not best_cat or not best_pt:
        for r, cfg in cfgs:
            h = _hits(cfg, whole)
            if h <= 0:
                continue
            key = (h, r.priority or 0)
            if not best_cat and cfg.get("category") and key > best_cat_key:
                best_cat, best_cat_key = cfg["category"], key
            if not best_pt and cfg.get("point") and key > best_pt_key:
                best_pt, best_pt_key, best_pt_cat = cfg["point"], key, cfg.get("category")

    if not best_cat and not best_pt:
        return None

    out = {"category": best_cat, "point_name": best_pt, "point_id": None}
    if best_pt:
        out["point_id"] = _point_id_by_name(db, subject, best_pt)
        if not out["category"] and best_pt_cat:
            out["category"] = best_pt_cat
        if not out["category"] and out["point_id"]:
            out["category"] = _category_of_point(db, subject, out["point_id"])
    return out


def _resolve_classification(db, subject, title, front, back,
                            explicit_category=None, explicit_point=None,
                            strict: bool = True) -> dict:
    """分类收敛：显式 > 自动；返回 {'category','point_id','point_name'}。

    strict=True（交互式建卡/改卡）：显式分类不在词表内 → 400，让用户当场改；
    strict=False（批量导入）：非法显式分类不中断，回退自动分类并在
    `rejected_category` 里回报，由调用方写进行级 warnings。
    """
    out = {"category": None, "point_id": None, "point_name": None,
           "rejected_category": None}
    if explicit_point not in (None, ""):
        try:
            out["point_id"] = _validate_point(db, subject, explicit_point)
        except HTTPException:
            if strict:
                raise
            out["rejected_point"] = explicit_point
        if out["point_id"]:
            row = _point_row(db, subject, out["point_id"])
            out["point_name"] = (row.point_name or "").strip() if row else None
    if explicit_category:
        try:
            out["category"] = _validate_category(db, subject, explicit_category)
        except HTTPException:
            if strict:
                raise
            out["rejected_category"] = (explicit_category or "").strip()

    if not (out["category"] and out["point_id"]):
        auto = _auto_classify_ex(db, subject, title, front, back)
        if auto:
            out["category"] = out["category"] or auto.get("category")
            out["point_id"] = out["point_id"] or auto.get("point_id")
            out["point_name"] = out["point_name"] or auto.get("point_name")

    if out["point_id"] and not out["point_name"]:
        row = _point_row(db, subject, out["point_id"])
        out["point_name"] = (row.point_name or "").strip() if row else None
    if out["point_id"] and not out["category"]:
        out["category"] = _category_of_point(db, subject, out["point_id"])
    return out


def _finalize_classification(db, data: dict) -> dict:
    """建卡/建资料前统一收敛分类字段（原地改 data）。"""
    subject = data.get("subject")
    resolved = _resolve_classification(
        db, subject,
        data.get("title"), data.get("card_front") or data.get("title"),
        data.get("card_back") or data.get("content"),
        explicit_category=data.get("category"), explicit_point=data.get("point_id"))
    if resolved.get("category"):
        data["category"] = resolved["category"]
    if resolved.get("point_id"):
        data["point_id"] = resolved["point_id"]

    # F2 未分类兜底：两级自动分类都没命中时，落到该科目第一个子类并留痕，
    # 避免「分类为空」的卡进库（空分类会让筛选、统计、按考点推荐全部失效）。
    if not data.get("category"):
        names = _category_names(db, subject)
        if names:
            data["category"] = names[0]
            logger.warning("[materials] 分类兜底 material title=%r subject=%s -> %s",
                           (data.get("title") or "")[:40], subject, names[0])
    return data



# ============ 分类规则后台维护（管理员，4 端点） ============
_RULE_SUBJECTS = ("xingce", "shenlun", "gongzhuan")


def _rule_cfg(r) -> dict:
    """rule_config 取成 dict（JSON 列可能是 dict，也可能是历史字符串）。"""
    cfg = r.rule_config or {}
    if isinstance(cfg, str):
        try:
            cfg = _json.loads(cfg)
        except Exception:
            cfg = {}
    return cfg if isinstance(cfg, dict) else {}


def _rule_to_dict(r) -> dict:
    cfg = _rule_cfg(r)
    return {
        "id": r.rule_id,
        "name": r.rule_name,
        "type": r.rule_type,
        "subject": cfg.get("subject"),
        "category": cfg.get("category"),
        "keywords": cfg.get("keywords") or [],
        "priority": r.priority or 0,
        "enabled": int(r.enabled or 0),
        "created_at": str(r.created_at) if getattr(r, "created_at", None) else None,
    }


def _validate_rule_body(body: dict, partial: bool = False) -> dict:
    """校验规则入参：名称唯一、科目合法、分类非空、关键词不能为空列表。"""
    name = (body.get("name") or body.get("rule_name") or "").strip()
    type_ = (body.get("type") or body.get("rule_type") or "keyword").strip()
    subject = (body.get("subject") or "").strip()
    category = (body.get("category") or "").strip()
    keywords = body.get("keywords")
    priority = body.get("priority")
    enabled = body.get("enabled")

    if not partial or name:
        if not name:
            raise HTTPException(400, "规则名称必填")
        if len(name) > 100:
            raise HTTPException(400, "规则名称超过 100 字")
    if type_ not in ("keyword",):
        raise HTTPException(400, "目前仅支持 keyword 类型规则")
    if not partial or subject:
        if subject and subject not in _RULE_SUBJECTS:
            raise HTTPException(400, "无效科目（xingce/shenlun/gongzhuan）")
    if not partial or category:
        if not category:
            raise HTTPException(400, "目标分类（category）必填")
    if not partial or keywords is not None:
        if not isinstance(keywords, list) or not keywords:
            raise HTTPException(400, "关键词至少 1 个（数组）")
        cleaned = []
        for k in keywords:
            k = str(k or "").strip()
            if not k:
                raise HTTPException(400, "关键词不能包含空字符串")
            if len(k) > 30:
                raise HTTPException(400, f"关键词过长（≤30 字）：{k[:10]}…")
            cleaned.append(k)
        keywords = cleaned
    if priority is not None:
        try:
            priority = int(priority)
        except (TypeError, ValueError):
            raise HTTPException(400, "priority 必须是整数")
        if not (0 <= priority <= 100):
            raise HTTPException(400, "priority 取值范围 0–100")

    out = {"name": name, "type": type_}
    if subject or not partial:
        out["subject"] = subject
    if category:
        out["category"] = category
    if keywords is not None:
        out["keywords"] = keywords
    if priority is not None:
        out["priority"] = priority
    if enabled is not None:
        out["enabled"] = 1 if enabled else 0
    return out


def _rule_config_of(data: dict) -> str:
    cfg = {}
    if data.get("subject"):
        cfg["subject"] = data["subject"]
    if data.get("category"):
        cfg["category"] = data["category"]
    if data.get("keywords") is not None:
        cfg["keywords"] = data["keywords"]
    return _json.dumps(cfg, ensure_ascii=False)


@router.get("/admin/rules", summary="分类规则列表(管理员)")
async def admin_rule_list(page: int = Query(1, ge=1),
                          page_size: int = Query(20, ge=1, le=200),
                          enabled: int = Query(-1),
                          keyword: str = Query(""),
                          current_user: SysUser = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    _require_admin(current_user)
    from ....models.models import MaterialClassificationRule  # 局部导入

    q = db.query(MaterialClassificationRule)
    if enabled in (0, 1):
        q = q.filter(MaterialClassificationRule.enabled == enabled)
    if keyword.strip():
        q = q.filter(MaterialClassificationRule.rule_name.like(f"%{keyword.strip()}%"))
    total = q.count()
    rows = (q.order_by(MaterialClassificationRule.priority.desc(),
                       MaterialClassificationRule.rule_id.asc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"total": total, "items": [_rule_to_dict(r) for r in rows]}


@router.post("/admin/rules", summary="新增分类规则(管理员)")
async def admin_rule_create(body: dict,
                            current_user: SysUser = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    _require_admin(current_user)
    from ....models.models import MaterialClassificationRule

    data = _validate_rule_body(body)
    exists = (db.query(MaterialClassificationRule)
              .filter(MaterialClassificationRule.rule_name == data["name"]).first())
    if exists:
        raise HTTPException(409, f"规则名称已存在：{data['name']}")
    r = MaterialClassificationRule(
        rule_name=data["name"], rule_type=data["type"],
        rule_config=_rule_config_of(data),
        priority=data.get("priority", 50),
        enabled=data.get("enabled", 1))
    db.add(r)
    db.commit()
    db.refresh(r)
    _audit(db, current_user, "rule_create", f"rule:{r.rule_id}", r.rule_name)
    db.commit()
    return _rule_to_dict(r)


@router.put("/admin/rules/{rule_id}", summary="更新分类规则(管理员)")
async def admin_rule_update(rule_id: int, body: dict,
                            current_user: SysUser = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    _require_admin(current_user)
    from ....models.models import MaterialClassificationRule

    r = (db.query(MaterialClassificationRule)
         .filter(MaterialClassificationRule.rule_id == rule_id).first())
    if not r:
        raise HTTPException(404, "规则不存在")
    data = _validate_rule_body(body, partial=True)

    if data.get("name") and data["name"] != r.rule_name:
        dup = (db.query(MaterialClassificationRule)
               .filter(MaterialClassificationRule.rule_name == data["name"],
                       MaterialClassificationRule.rule_id != rule_id).first())
        if dup:
            raise HTTPException(409, f"规则名称已存在：{data['name']}")
        r.rule_name = data["name"]
    if data.get("type"):
        r.rule_type = data["type"]
    merged = dict(_rule_cfg(r))
    for k in ("subject", "category", "keywords"):
        if k in data:
            merged[k] = data[k]
    r.rule_config = _json.dumps(merged, ensure_ascii=False)
    if "priority" in data:
        r.priority = data["priority"]
    if "enabled" in data:
        r.enabled = data["enabled"]
    db.commit()
    db.refresh(r)
    _audit(db, current_user, "rule_update", f"rule:{rule_id}", r.rule_name)
    db.commit()
    return _rule_to_dict(r)


@router.patch("/admin/rules/{rule_id}/toggle", summary="启用/停用分类规则(管理员)")
async def admin_rule_toggle(rule_id: int, body: dict,
                            current_user: SysUser = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    _require_admin(current_user)
    from ....models.models import MaterialClassificationRule

    r = (db.query(MaterialClassificationRule)
         .filter(MaterialClassificationRule.rule_id == rule_id).first())
    if not r:
        raise HTTPException(404, "规则不存在")
    enabled = body.get("enabled")
    if enabled is None:
        enabled = 0 if int(r.enabled or 0) == 1 else 1
    r.enabled = 1 if enabled else 0
    db.commit()
    _audit(db, current_user, "rule_toggle", f"rule:{rule_id}",
           f"{r.rule_name} enabled={r.enabled}")
    db.commit()
    return {"id": rule_id, "enabled": int(r.enabled)}


@router.get("/admin/list", summary="管理列表(含下架)")
async def admin_list(subject: Optional[str] = Query(None),
                     type: Optional[str] = Query(None),
                     status: Optional[int] = Query(None),
                     page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=100),
                     current_user: SysUser = Depends(get_current_user),
                     keyword: str = Query(""),
                     db: Session = Depends(get_db)):
    _require_admin(current_user)
    q = db.query(StudyMaterial)
    if subject:
        q = q.filter(StudyMaterial.subject == subject)
    if type:
        q = q.filter(StudyMaterial.type == type)
    if status is not None:
        q = q.filter(StudyMaterial.status == status)
    # 标题 / 分类 模糊搜索（前端 admin_materials 搜索框传 keyword）
    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(StudyMaterial.title.like(like),
                         StudyMaterial.category.like(like)))
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
    _finalize_classification(db, data)
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
    if "category" in data or "point_id" in data:
        subj = data.get("subject") or m.subject
        if "category" in data:
            data["category"] = _validate_category(db, subj, data["category"])
        if "point_id" in data:
            data["point_id"] = _validate_point(db, subj, data["point_id"])
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
        _finalize_classification(db, data)   # P2.4：批量建卡同样走两级自动分类
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


def _migrate_images(import_id: int, result: dict, db: Session | None = None,
                    user_id: int | None = None) -> None:
    """把 parse_result.images 的临时图片迁入正式存储并改写 html 引用。

    F3 开启时写入对象存储，HTML 改写为 /media/{asset_id}；关闭时保留原
    uploads/materials/images/ 目录行为。图片字节只在确认入库时固化。
    """
    html = result.get("html") or ""
    dest_dir = UPLOAD_IMG_DIR / f"import_{import_id}"
    use_media = bool(settings.MEDIA_STORE_ENABLED and db is not None)

    def _persist(src: _Path, original_name: str) -> str:
        if use_media:
            try:
                with open(src, "rb") as fh:
                    asset = media_service.store_file(
                        db, fh, kind="material_image",
                        original_name=original_name, created_by=user_id,
                    )
            except media_service.MediaValidationError as exc:
                raise HTTPException(400, f"导入图片格式不支持: {exc}")
            except media_service.ObjectStoreUnavailable:
                raise HTTPException(503, "图片存储暂不可用，请稍后重试")
            src.unlink(missing_ok=True)
            return f"/media/{asset.asset_id}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / original_name
        _shutil.move(str(src), str(dest))
        return f"/uploads/materials/images/import_{import_id}/{dest.name}"

    for img in result.get("images", []):
        if not isinstance(img, dict):
            continue
        src = _Path(img.get("src_path", ""))
        if not src.exists():
            continue
        name = img.get("name", src.name)
        new_ref = _persist(src, name)
        html = html.replace(f"/uploads/materials/tmp/{src.name}", new_ref)
    # Word 内嵌图引用同样从 tmp 迁移
    for name in result.get("images", []):
        if isinstance(name, str):
            src = UPLOAD_TMP_DIR / name
            if src.exists():
                new_ref = _persist(src, name)
                html = html.replace(f"/uploads/materials/tmp/{name}", new_ref)
    result["html"] = sanitize_html(html)


def _commit_material_import(db: Session, rec: MaterialImportRecord) -> None:
    """业务行与文档投影事件同事务提交，避免文档库与导入记录漂移。"""
    db.flush()
    from ....foundation.document_events import emit_import_snapshot
    emit_import_snapshot(
        db, "material_import_record", rec.import_id,
        producer="library.materials",
    )
    db.commit()


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
    _commit_material_import(db, rec)
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
            _commit_material_import(db, rec)
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
        _commit_material_import(db, rec)
    elif ext == ".xlsx":
        try:
            from ....services.material_parser import parse_xlsx
            out = parse_xlsx(tmp_path)
            out["_tmp"] = tmp_path
            # P2-B：文件级格式校验。上传阶段还不知道科目（confirm 时才选），
            # 所以这里只查结构（缺列/空值/超长/重复/超行数/危险标签）。
            from ....services.material_format_validator import validate_rows
            out["validation"] = validate_rows(out.get("headers") or [],
                                              out.get("rows") or [])
            rec.parse_mode = "sync"
            rec.parse_status = "success"
            rec.parse_result = _json.dumps(out, ensure_ascii=False)
        except Exception as e:
            rec.parse_status = "failed"
            rec.error_message = f"Excel 解析失败（空表或损坏）: {e}"
            rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
        _commit_material_import(db, rec)
    elif ext == ".pdf":
        if scanned:
            from ....services.mineru_material_service import (
                mineru_available, run_mineru, MineruError)
            if not mineru_available():
                rec.parse_status = "failed"
                rec.error_message = ("该 PDF 为扫描图片版且系统 OCR 组件未就绪，"
                                     "请转存为文字版 Word 后重新上传")
                rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
                _commit_material_import(db, rec)
                raise HTTPException(400, rec.error_message)
            rec.parse_mode = "async(mineru)"
            rec.parse_status = "processing"
            rec.parse_result = _json.dumps({"_tmp": tmp_path}, ensure_ascii=False)
            _commit_material_import(db, rec)

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
                    _commit_material_import(s, row)
                except Exception as e:
                    row = s.query(MaterialImportRecord).get(import_id)
                    row.parse_status = "failed"
                    row.error_message = f"OCR 失败({type(e).__name__}): 可点击重试或转存 Word"
                    _commit_material_import(s, row)
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
            _commit_material_import(db, rec)

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
    warnings: list = []         # P2.5：分类列/考点列非法但已回退自动分类的行
    publish = bool(body.get("publish"))   # D2：导入即上线（默认 false）

    if rec.file_type == "xlsx":
        mapping = body.get("column_mapping") or {}
        try:
            col_front = int(mapping["front"])
            col_back = int(mapping["back"])
            col_cat = (int(mapping["category"])
                       if mapping.get("category") not in (None, "") else None)
            col_point = (int(mapping["point"])
                         if mapping.get("point") not in (None, "") else None)
            col_cover = (int(mapping["cover"])
                         if mapping.get("cover") not in (None, "") else None)
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "列映射不完整（正面列/背面列必填）")
        from ....services.material_parser import build_cards, parse_xlsx
        # preview 只回传前200行；confirm 从原始文件重读全量行
        full = parse_xlsx(result["_tmp"], max_rows=CARD_ROW_LIMIT) \
            if result.get("_tmp") and _Path(result["_tmp"]).exists() else result
        raw_rows = list(full.get("rows") or [])
        # P2-B：入库前做一次带词表的全量校验。
        # 整表不可用（缺列/超行数）→ 400；行级问题（空值/超长/重复/危险标签）→ 跳过该行并回报
        from ....services.material_format_validator import (
            BLOCKING_CODES, ROW_CODES, validate_rows)
        full_rows = list(raw_rows)
        _val = validate_rows(full.get("headers") or [], raw_rows,
                             category_names=_category_names(db, subject),
                             point_names=list(taxonomy.point_map(db, subject).keys()),
                             category_as_warning=True)
        _blocking = [e for e in _val["errors"] if e["code"] in BLOCKING_CODES]
        if _blocking:
            head = "；".join(
                f"第{e['row']}行 {e['column']}：{e['message']}" if e["row"]
                else f"{e['column']}：{e['message']}" for e in _blocking[:5])
            raise HTTPException(
                400, f"表格格式校验未通过（共 {_val['stats']['error_count']} 处）：{head}")
        _bad_rows = {e["row"] for e in _val["errors"] if e["code"] in ROW_CODES}
        if _bad_rows:
            raw_rows = [r for i, r in enumerate(raw_rows, start=1)
                        if i not in _bad_rows]
        warnings.extend(_val.get("warnings") or [])
        # D5：build_cards 会静默丢弃正面或背面为空的行，这里先算出来回报
        invalid_rows = [
            i for i, r in enumerate(full_rows, start=1)
            if not (r[col_front].strip() if col_front < len(r) else "")
            or not (r[col_back].strip() if col_back < len(r) else "")
        ]
        invalid_rows = sorted(set(invalid_rows) | set(_bad_rows))
        cards = build_cards(raw_rows, col_front, col_back, col_cat,
                            limit=CARD_ROW_LIMIT, col_point=col_point,
                            col_cover=col_cover)
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
            # 分类三级优先：表格分类列 > 关键词自动分类 > 请求体 category；
            # P2.2：同时解析考点列（表头「考点」），落 point_id
            # 导入是批量场景：非法分类不中断，回退自动分类并记 warning（P2.5 错误行回报）
            cls = _resolve_classification(
                db, subject, card_front, card_front, card_back,
                explicit_category=c.get("category") or category,
                explicit_point=_point_id_by_name(db, subject, c.get("point")),
                strict=False)
            for bad, kind in ((cls.get("rejected_category"), "category"),
                              (cls.get("rejected_point"), "point")):
                if bad:
                    warnings.append({"row": idx, "kind": kind,
                                     "value": str(bad)[:60],
                                     "replaced_by": cls.get("category") or ""})
            m = StudyMaterial(
                subject=subject, type="card",
                category=cls["category"],
                point_id=cls["point_id"],
                cover_image=(c.get("cover") or None),
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
        _migrate_images(import_id, result, db=db, user_id=current_user.user_id)
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
        resp["warnings"] = warnings
    return JSONResponse(resp)

# ============================ P2-C 学生端上传（受限） ============================
STUDENT_UPLOAD_DAILY = 5          # 每人每天最多上传几次文件
STUDENT_UPLOAD_TOTAL = 500        # 每人累计最多 500 张卡
STUDENT_UPLOAD_MAX_MB = 5


@router.post("/my/upload", summary="学生上传卡片表格(默认待审)")
async def my_upload(file: UploadFile = File(...),
                    subject: str = Query(..., description="xingce/shenlun/gongzhuan"),
                    current_user: SysUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """学生上传 xlsx/csv：先过 P2-B 格式校验器，再按考点自动分类，**默认 status=0 待审**。

    与管理员导入的区别：文件更小、次数限额、必须待审，防止学生把内容直接推到公开库。
    """
    from ....services.material_format_validator import (
        BLOCKING_CODES, check_file, validate_rows)

    if subject not in SUBJECTS:
        raise HTTPException(400, "无效科目")

    raw = file.file.read()
    errs = check_file(file.filename or "", len(raw))
    if errs:
        raise HTTPException(400, errs[0]["message"])
    if len(raw) > STUDENT_UPLOAD_MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"文件不能超过 {STUDENT_UPLOAD_MAX_MB}MB")

    # 配额：今日新建卡片数（MaterialImportRecord 无 creator_id 列，改用卡片自身计数）
    today = datetime.now().strftime("%Y-%m-%d")
    today_cards = db.query(func.count(StudyMaterial.material_id)).filter(
        StudyMaterial.creator_id == current_user.user_id,
        func.date(StudyMaterial.create_time) == today,
    ).scalar() or 0
    if today_cards >= STUDENT_UPLOAD_DAILY * 10:
        raise HTTPException(
            429, f"今日已上传 {today_cards} 张，达到上限（{STUDENT_UPLOAD_DAILY * 10} 张），明天再试")
    owned = db.query(func.count(StudyMaterial.material_id)).filter(
        StudyMaterial.creator_id == current_user.user_id,
        StudyMaterial.type == "card",
    ).scalar() or 0
    if owned >= STUDENT_UPLOAD_TOTAL:
        raise HTTPException(429, f"你的资料库已达上限（{STUDENT_UPLOAD_TOTAL} 张）")

    ext = _os.path.splitext(file.filename or "")[1].lower()
    tmp_dir = UPLOAD_TMP_DIR
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = str(tmp_dir / f"stu_{_uuid.uuid4().hex}{ext}")
    with open(tmp_path, "wb") as fh:
        fh.write(raw)

    try:
        if ext == ".xlsx":
            from ....services.material_parser import parse_xlsx
            parsed = parse_xlsx(tmp_path, max_rows=200)
        else:
            import csv as _csv
            import io as _io
            rows = []
            with _io.open(tmp_path, encoding="utf-8-sig", newline="") as fh:
                for r in _csv.reader(fh):
                    rows.append([(c or "").strip() for c in r])
            parsed = {"headers": rows[0] if rows else [], "rows": rows[1:201]}
    finally:
        try:
            _os.remove(tmp_path)
        except OSError:
            pass

    val = validate_rows(parsed.get("headers") or [], parsed.get("rows") or [],
                        category_names=_category_names(db, subject),
                        point_names=list(taxonomy.point_map(db, subject).keys()),
                        category_as_warning=True)
    blocking = [e for e in val["errors"] if e["code"] in BLOCKING_CODES]
    if blocking:
        head = "；".join(f"第{e['row']}行 {e['column']}：{e['message']}" for e in blocking[:5])
        raise HTTPException(400, f"格式校验未通过：{head}")

    bad_rows = {e["row"] for e in val["errors"] if e["row"]}
    created, skipped = [], []
    for idx, r in enumerate(parsed.get("rows") or [], start=1):
        if idx in bad_rows:
            skipped.append({"row": idx, "reason": "invalid"})
            continue
        cols = val["columns"]
        front = (r[cols["front"]] if cols.get("front") is not None and cols["front"] < len(r) else "").strip()
        back = (r[cols["back"]] if cols.get("back") is not None and cols["back"] < len(r) else "").strip()
        if not front or not back:
            skipped.append({"row": idx, "reason": "empty"})
            continue
        from ....services.material_sanitizer import content_cleaner
        front = content_cleaner.clean_text(front)
        back = content_cleaner.clean_text(back)
        combined = front + back
        dup = db.query(StudyMaterial).filter(
            StudyMaterial.content_hash == content_cleaner.calculate_content_hash(combined)
        ).first()
        if dup:
            skipped.append({"row": idx, "reason": "duplicate"})
            continue
        cls = _resolve_classification(db, subject, front, front, back, strict=False)
        m = StudyMaterial(
            subject=subject, type="card", category=cls["category"],
            point_id=cls["point_id"], title=front, card_front=front,
            card_back=back, content_hash=content_cleaner.calculate_content_hash(combined),
            status=0, creator_id=current_user.user_id,
            difficulty=1, read_time=2)
        db.add(m)
        db.flush()
        created.append(m.material_id)
    db.commit()
    _audit(db, current_user, "student_upload", f"created={len(created)}", file.filename)
    db.commit()
    return {"created": len(created), "material_ids": created,
            "skipped": skipped, "skipped_count": len(skipped),
            "warnings": val.get("warnings") or [],
            "status": "pending_review",
            "note": "已进入待审队列，管理员审核后才会公开展示"}
