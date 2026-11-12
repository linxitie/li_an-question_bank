"""备考资料 API。响应风格与 news.py 一致：裸 JSON。

学生组：GET "" 列表 / GET "/{id}" 详情 / GET "/progress-summary" / POST "/progress"
        POST "/{id}/favorite" / GET "/favorites"
管理组：见同文件下半部（admin/import 组，Task3/T6 追加）。
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
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
# 资料类型白名单。lecture（讲义）/ paper（试卷）为 2026-11-06 v3.1 新增（裁定 D29），零迁移：
# type 是 String(20)，只在这张白名单 + 前端类型映射里出现。
TYPES = {"video_intro", "video_advanced", "article", "card", "lecture", "paper"}
# L1（2026-11-08）投放位：一份试卷资料的去向。审批（status）与去向（placement）正交：
#   · 资料库可见 = status==1 且 placement∈{library,both}
#   · 考试页可考 = exam_paper.paper_type=='PUBLISHED' 且 placement∈{exam,both}
# 非试卷类恒为 library（它们没有"考试页"这回事），上传/建资料时由服务端强制。
PLACEMENTS = {"exam", "library", "both"}
#: 出现在"资料库"里的投放位（NULL 视为 library —— 老数据/直接走 ORM 建的行走这条）
LIBRARY_PLACEMENTS = ("library", "both")

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


# ============================ A2：上传时间 / 发布者（2026-11-07）============================
# 口径（裁定 D37）：对外叫「上传时间」，实现取**入库时间** study_material.create_time（零迁移）。
# 库里存的是 naive 本地时间（default=datetime.now），对外统一补 +08:00，前端才不用猜时区。
_TZ_CN = timezone(timedelta(hours=8))
_PUBLISHER_ROLE_LABEL = {"admin": "管理员", "teacher": "教师", "student": "学生"}
_SUBJECT_LABEL = {"xingce": "行测", "shenlun": "申论", "gongzhuan": "公专"}
_MATERIAL_TYPE_LABEL = {
    "video_intro": "入门视频", "video_advanced": "进阶视频",
    "article": "文章", "card": "知识卡片", "lecture": "讲义", "paper": "试卷",
}
# 「最近 N 天」筛选白名单：只接受这两个值，非法值由 FastAPI 直接 422
CREATED_WITHIN_DAYS = {"7d": 7, "30d": 30}
# 排序白名单：默认按入库时间倒序（最新在上）
LIST_ORDERS = ("created_desc", "created_asc")


def _iso_cn(dt: Optional[datetime]) -> Optional[str]:
    """naive 本地时间 → 带 +08:00 的 ISO-8601；空值返回 None（前端显示 —）。"""
    if not dt:
        return None
    aware = dt.replace(tzinfo=_TZ_CN) if dt.tzinfo is None else dt.astimezone(_TZ_CN)
    return aware.isoformat(timespec="seconds")


def _publisher_map(db: Session, rows: List[StudyMaterial]) -> dict:
    """creator_id → {id,name,role,role_label}，**一次查询**避免 N+1。

    名字取 nickname，空则回退 username（与论坛同一规则）；creator_id 可能为空
    （历史数据/系统导入），此时前端显示「—」。
    """
    ids = {m.creator_id for m in rows if m.creator_id}
    if not ids:
        return {}
    users = (db.query(SysUser.user_id, SysUser.username, SysUser.nickname, SysUser.user_type)
             .filter(SysUser.user_id.in_(ids)).all())
    out = {}
    for u in users:
        out[u.user_id] = {
            "id": u.user_id,
            "name": (u.nickname or "").strip() or u.username,
            "role": u.user_type,
            "role_label": _PUBLISHER_ROLE_LABEL.get(u.user_type, u.user_type),
        }
    return out


def _placement_of(m: StudyMaterial) -> str:
    """取投放位：显式值优先；NULL/脏值按类型归一化（试卷 both、其余 library）。

    与 `services/material_paper_sync.placement_of()` 同一口径，两处必须一致：
    列表过滤用它、同步用它，否则会出现"列表说可见、卷却没发布"的错位。
    """
    value = (getattr(m, "placement", "") or "").strip().lower()
    if value in PLACEMENTS:
        return value
    return "both" if (getattr(m, "type", "") or "") == "paper" else "library"


def _item_brief(m: StudyMaterial, prog: Optional[UserMaterialProgress] = None,
                file_count: Optional[int] = None) -> dict:
    d = {
        "id": m.material_id, "subject": m.subject, "type": m.type,
        "category": m.category, "point_id": m.point_id,
        "title": m.title, "summary": m.summary,
        "badge": m.badge, "cover_image": m.cover_image,
        "duration": m.duration or 0, "read_time": m.read_time or 0,
        "difficulty": m.difficulty or 1, "view_count": m.view_count or 0,
        "card_front": m.card_front, "sort_order": m.sort_order or 0,
        "card_back": m.card_back,
        # A2：入库时间（列表「上传时间」列 / 排序 / 「最近 7·30 天」筛选都靠它）
        "created_at": _iso_cn(m.create_time),
        # 全部配图（封面 + 正文附图），PC/手机详情页「看全图」用
        "image_urls": _brief_images(m),
        # A 方案：技巧类卡片允许不挂具体考点（跨考点的通用方法），
        # 用 is_generic 打标，前端展示为「通用技巧」，按子类归集。
        "is_generic": bool(m.type == "card" and not m.point_id and (m.category or "").strip()),
        # L1（2026-11-08）：投放位 + 是否有原件。
        # 列表就给这两个字段，前端不必逐条拉详情就能决定"显示不显示下载按钮"。
        "placement": _placement_of(m),
        "file_count": int(file_count or 0),
        "has_files": bool(file_count),
        # L2（2026-11-08）：讲义卡要显示「N 章 · M 字」，列表直接给（管理端同名口径）。
        # 取值来自 `doc_meta` 快照，解析失败时为 None，前端不渲染这一行。
        "chapter_count": _doc_meta_of(m).get("chapter_count"),
        "word_count": _doc_meta_of(m).get("word_count"),
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
    # L1（2026-11-08）：资料库只放"投放位含资料页"的行。
    # `placement=exam`（仅考试页）的原卷仍留档在库、管理员可查，但学生资料库不露出。
    # NULL 视为 library：老数据、以及直接走 ORM 建的测试行都不会被误藏。
    q = db.query(StudyMaterial).filter(
        StudyMaterial.subject == subject, StudyMaterial.status == 1,
        or_(StudyMaterial.placement.in_(LIBRARY_PLACEMENTS),
            StudyMaterial.placement.is_(None)))
    if type:
        q = q.filter(StudyMaterial.type == type)
    total = q.count()
    rows = (q.order_by(StudyMaterial.sort_order.asc(), StudyMaterial.material_id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    progs = {}
    file_counts = {}
    # L2（2026-11-08）：试卷行随列表返回 `paper` 区块（年份/地区/卷别/题量/总分/时长/编号/可考）。
    # 为什么在列表里做、而不是让学生逐条拉详情：试卷卡片上就要显示这些，逐条请求会把
    # 一屏 3~10 张卡变成 3~10 个额外请求；量级只有"每科几套卷"，每行一次查询可接受。
    paper_blocks = {}
    for m in rows:
        if m.type == "paper":
            try:
                paper_blocks[m.material_id] = paper_registry.paper_block(db, m)
            except Exception:  # noqa: BLE001 — 元数据解析失败不能拖垮整个列表
                logger.warning("[materials] 列表读取试卷元数据失败 material=%s",
                               m.material_id, exc_info=True)
                paper_blocks[m.material_id] = None
    if rows:
        ids = [r.material_id for r in rows]
        # 一次 group by 拿齐"有没有原件"，避免逐条子查询（列表最多 50 行）
        from ....models.models import MaterialFile
        for mid, cnt in (db.query(MaterialFile.material_id, func.count(MaterialFile.file_id))
                         .filter(MaterialFile.material_id.in_(ids))
                         .group_by(MaterialFile.material_id).all()):
            file_counts[mid] = int(cnt)
    if current_user and rows:
        for p in (db.query(UserMaterialProgress)
                  .filter(UserMaterialProgress.user_id == current_user.user_id,
                          UserMaterialProgress.material_id.in_(ids)).all()):
            progs[p.material_id] = p
    items = []
    for m in rows:
        item = _item_brief(m, progs.get(m.material_id), file_counts.get(m.material_id))
        if m.type == "paper":
            item["paper"] = paper_blocks.get(m.material_id)
        items.append(item)
    return {"total": total, "items": items}


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
            # 合并远端 main 后 MEDIA_STORE_ENABLED 走媒体资产库，必须传 db/user_id
            url = _safe_image_upload(fh, db=db, user_id=current_user.user_id)
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
            url = _safe_image_upload(fh, db=db, user_id=current_user.user_id)  # 复用白名单+魔数+uuid 重命名（媒体库需 db）
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
    """资料详情。

    可见性（W2 / 方案 D3，2026-11-09）：
      · 游客 / 学生：只能看 `status==1` 且投放位含资料库的（原来就有的规则）；
      · **教师 / 管理员**：可以看未上架（`status=0`）的草稿，便于"上架前先看一眼"。
        以前教师只能走管理端预览接口，而那个要管理员权限 —— 教师审核前根本看不到内容。
    注意判据用 `user_type` 而不是 `role_level`：教师与学生的 `role_level` 都是 1（实测），
    按 level 判会把教师一起挡掉（`conftest.test_user` 就是 level=1 的学生，别被它骗了）。
    """
    is_staff = bool(current_user and (current_user.user_type or "") in ("teacher", "admin"))
    q = db.query(StudyMaterial).filter(StudyMaterial.material_id == material_id)
    if not is_staff:
        q = q.filter(
            StudyMaterial.status == 1,
            # L1：仅考试页（placement=exam）的资料不进资料库，直连 URL 也按 404 处理，
            # 避免"列表里没有、地址栏能打开"的不一致。
            or_(StudyMaterial.placement.in_(LIBRARY_PLACEMENTS),
                StudyMaterial.placement.is_(None)))
    else:
        # 回收站里的（status=-1）谁都别在详情里看到，避免"看起来还在"
        q = q.filter(StudyMaterial.status >= 0)
    m = q.first()
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
    # L1/L2（2026-11-08）：学生详情补三样，L2 的讲义/试卷抽屉直接渲染，不用再发第二个请求：
    #   · files        —— 原件清单（含 download_url），"下载原件"按钮用；
    #   · placement    —— 前端据此决定是否显示"去考试"；
    #   · doc_meta     —— 讲义的章节/字数（上传时抽取的快照，没有则为 None）。
    # 只读派生，不新增端点；原件下载仍走 /api/materials/files/{id}/download 的鉴权。
    files = []
    try:
        from ....services import material_files as _mf
        files = [dict(_mf.serialize(f),
                      download_url=f"/api/materials/files/{f.file_id}/download")
                 for f in _mf.list_for_material(db, m.material_id)]
    except Exception:  # noqa: BLE001 — 读原件失败不能拖垮详情
        logger.warning("[materials] 详情读取原件清单失败 material=%s", material_id, exc_info=True)
    d.update({
        "files": files,
        "has_files": bool(files),
        "file_count": len(files),
        "placement": _placement_of(m),
        "doc_meta": _doc_meta_of(m) or None,
    })
    return d


# ============================ 管理端（role=admin）============================

import json as _json  # noqa: E402
import hashlib as _hashlib  # noqa: E402
import os as _os  # noqa: E402
import shutil as _shutil  # noqa: E402
import uuid as _uuid  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

# 2026-11-04：File/UploadFile 原在此处延迟导入，但上面的函数签名（第 340/520 行）已经用到它们，
# 在 Python < 3.14（注解立即求值）下会 NameError；已提到文件顶部导入，这里不再重复。

from ....models.models import MaterialImportRecord, SysOperationLog, MaterialFile  # noqa: E402
from ....services.material_sanitizer import sanitize_html  # noqa: E402
from ....services.material_classifier import classifier  # noqa: E402
from ....services.material_deduplicator import deduplicator  # noqa: E402
from ....services.material_sanitizer import content_cleaner  # noqa: E402
from ....services.material_monitor import import_monitor  # noqa: E402
from ....services import material_files  # noqa: E402  B1：原件留档（存储+下载路径）
from ....services import paper_registry  # noqa: E402  C2/C4：试卷↔可作答卷只读桥（避免 library 直接 import ExamPaper）
from ....services import doc_outline  # noqa: E402  C1：讲义大纲（字数/章节）
from ....services import material_paper_link  # noqa: E402  P1：上传即建卷（资料→可作答卷）
from ....services.material_paper_sync import EXAM_PLACEMENTS  # noqa: E402  P1：考试相关投放位
from ....core.config import settings  # noqa: E402
from ....services import media_service  # noqa: E402

# 上传目录跟随 `settings.UPLOAD_DIR`（B1 修正）。
# 原来写死 `"uploads/..."`：一旦部署换了上传根目录（或被测试指到临时目录）就会"
# 写到另一个地方"，且与 `/uploads` 静态挂载（用 settings.UPLOAD_DIR）口径不一致。
# 实测背景：本机仓库在 OneDrive 里，写 `uploads/materials/tmp` 偶尔会被同步/杀软卡 30s，
# 测试把这个根目录指到临时盘即可彻底摆脱（见 tests/conftest.py）。
UPLOAD_IMG_DIR = _Path(settings.UPLOAD_DIR) / "materials" / "images"
UPLOAD_TMP_DIR = _Path(settings.UPLOAD_DIR) / "materials" / "tmp"

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
        "upload_file": "上传原件",
        "import_confirm": "导入入库",
        "batch_create": "批量创建",
        "batch_delete": "批量删除",
        "restore": "恢复资料",
        # A2（2026-11-08）：试卷资料 → 可作答卷
        "ensure_paper": "生成可作答卷",
        "paper_backfill": "试卷补录",
        # P1（2026-11-09）：上传即建卷（自动触发；跳过时也记一笔原因）
        "auto_create_paper": "自动建卷",
        # P3（2026-11-09）：上传即导题
        "paper_parse": "解析导题",
        "paper_import": "确认入库",
        "paper_parse_discard": "放弃导题",
        # P4（2026-11-09）：答案上传
        "answer_parse": "解析答案",
        "answer_apply": "写入答案",
        "answer_discard": "放弃答案",
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


def _paper_sync_payload(sync: dict | None) -> dict | None:
    """P5：把 `material_paper_sync` 的结果裁成对外回包的 `paper_sync` 字段。

    只暴露前端/测试需要的 6 个键；内部键（enabled/note）不进响应体。
    """
    if not sync:
        return None
    return {key: sync.get(key) for key in
            ("paper_id", "paper_code", "before", "after", "changed", "skipped")}


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


def _material_content_hash(data: dict) -> str:
    """给「建资料 / 批量建资料」算内容哈希（W2 去重口径，2026-11-09）。

    与卡片建卡、文章入库同口径（`content_cleaner.calculate_content_hash`）：
      · 卡片：正面 + 背面（卡片的价值全在这两段）；
      · 其它类型：正文 content，正文为空时退化成 标题 + 摘要（否则所有空正文资料哈希相同）。
    算不出来（全空）返回空串 → 调用方跳过去重，不要因为"算不出"就把人挡住。
    """
    from ....services.material_sanitizer import content_cleaner

    if (data.get("type") or "") == "card":
        raw = f"{data.get('card_front') or ''}{data.get('card_back') or ''}"
    else:
        raw = (data.get("content") or "") or (f"{data.get('title') or ''}{data.get('summary') or ''}")
    if not (raw or "").strip():
        return ""
    return content_cleaner.calculate_content_hash(raw)


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


def _doc_meta_of(m) -> dict:
    """读取讲义大纲快照（C1）；空/损坏都返回 `{}`，调用方按"没有大纲"处理。"""
    return doc_outline.loads(getattr(m, "doc_meta", None)) or {}


def _paper_meta_for_filter(m) -> dict:
    """C3：筛选用的元数据 = `paper_meta` 订正 > 文件名解析。与预览同一口径。"""
    from ....services import paper_meta_edit
    return paper_meta_edit.merge_meta(m)


def _match_paper_filters(m, year, region, book_kind) -> bool:
    """试卷三维筛选：年份 / 地区（code 或中文名都收）/ 卷别。

    口径与预览一致（订正压过解析）。**非试卷类**在带试卷筛选时统一排除——
    请求里既然问了"2019 年的试卷"，卡片/讲义就不该出现。
    """
    if getattr(m, "type", "") != "paper":
        return False
    meta = _paper_meta_for_filter(m)
    if year is not None and meta.get("year") != year:
        return False
    if region:
        want = region.strip().upper()
        codes = {(meta.get("region_code") or "").upper(),
                 (meta.get("region_name") or "")}
        if want not in {c for c in codes if c}:
            return False
    if book_kind:
        if (meta.get("book_kind") or "").upper() != book_kind.strip().upper():
            return False
    return True

@router.get("/admin/list", summary="管理列表(含下架)")
async def admin_list(subject: Optional[str] = Query(None),
                     type: Optional[str] = Query(None),
                     status: Optional[int] = Query(None),
                     page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=100),
                     current_user: SysUser = Depends(get_current_user),
                     keyword: str = Query(""),
                     created_within: Optional[str] = Query(
                         None, pattern="^(7d|30d)$",
                         description="最近 7/30 天（滚动窗口：create_time >= now - N 天）"),
                     order: str = Query("id_desc", pattern="^(id_desc|id_asc|created_desc|created_asc)$",
                                        description="id_desc(默认,按列表时间倒序) / id_asc / created_desc / created_asc"),
                     publisher_id: Optional[int] = Query(None, description="只看某个发布者"),
                     paper_year: Optional[int] = Query(
                         None, ge=1900, le=2100,
                         description="C3：试卷年份（订正优先于文件名解析）"),
                     region: Optional[str] = Query(
                         None, description="C3：试卷地区，地区代码（BJ）或中文（北京）"),
                     book_kind: Optional[str] = Query(
                         None, description="C3：试卷卷别 T=题本 / A=答案 / J=解析"),
                     db: Session = Depends(get_db)):
    _require_admin(current_user)
    q = db.query(StudyMaterial)
    if subject:
        q = q.filter(StudyMaterial.subject == subject)
    if type:
        q = q.filter(StudyMaterial.type == type)
    if status is not None:
        q = q.filter(StudyMaterial.status == status)
    else:
        # 口径（2026-11-07 修正，裁定 A）：不传 status 时**排除软删除**（-1），
        # 与 /admin/stats 的 total 保持一致——否则"删掉的资料还在列表里，却又不计入统计"。
        # 想专门看已删除的，显式传 status=-1。
        q = q.filter(StudyMaterial.status >= 0)
    if publisher_id:
        q = q.filter(StudyMaterial.creator_id == publisher_id)
    # A2：最近 N 天（滚动窗口，不是"本周一"）。create_time 为空的旧行天然被排除。
    if created_within:
        cutoff = datetime.now() - timedelta(days=CREATED_WITHIN_DAYS[created_within])
        q = q.filter(StudyMaterial.create_time >= cutoff)
    # 标题 / 分类 模糊搜索（前端 admin_materials 搜索框传 keyword）
    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(StudyMaterial.title.like(like),
                         StudyMaterial.category.like(like)))
    # 排序（2026-11-08 / ID 方案 A）：
    #   · 默认 `id_desc` —— 按 `list_time`（平时 = create_time，从回收站恢复时刷新为 now → 置顶）
    #     倒序，`material_id` 作确定性 tiebreaker，保证跨页不重不漏（实测翻 12 页 0 重复）。
    #   · `created_*` 保留给「上传时间」列排序（真实上传时间，NULL 恒定排最后）。
    #   为什么不用 create_time 当默认排序键：58 条历史资料 create_time 为 NULL，
    #   会被排到最后一页，页面就出现 `107,106 → 45,44` 的跳号（用户 2026-11-08 反馈的缺陷①）。
    if order in ("created_asc", "created_desc"):
        null_last = StudyMaterial.create_time.is_(None).asc()
        if order == "created_asc":
            q = q.order_by(null_last, StudyMaterial.create_time.asc(),
                           StudyMaterial.material_id.asc())
        else:
            q = q.order_by(null_last, StudyMaterial.create_time.desc(),
                           StudyMaterial.material_id.desc())
    else:
        # id_desc / id_asc：list_time 为空的行同样排最后（理论上不会为空，见启动期回填）
        null_last = StudyMaterial.list_time.is_(None).asc()
        if order == "id_asc":
            q = q.order_by(null_last, StudyMaterial.list_time.asc(),
                           StudyMaterial.material_id.asc())
        else:
            q = q.order_by(null_last, StudyMaterial.list_time.desc(),
                           StudyMaterial.material_id.desc())

    paper_filters_on = any(v not in (None, "") for v in (paper_year, region, book_kind))
    if paper_filters_on:
        # C3：年份/地区/卷别存在 **两种来源**（`paper_meta` 订正 / 文件名解析），
        # SQL 表达不了"订正优先 + 解析兜底"，所以先按其它条件取候选、再在 Python 里精筛。
        # 量级：管理端资料是百级，全量取回可接受；超过 ~5000 条应改成
        # 落库的 year/region 列 + 索引（届时只需换这一段，接口契约不变）。
        candidates = q.all()
        matched = [m for m in candidates
                   if _match_paper_filters(m, paper_year, region, book_kind)]
        total = len(matched)
        rows = matched[(page - 1) * page_size: (page - 1) * page_size + page_size]
    else:
        total = q.count()
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
    publishers = _publisher_map(db, rows)
    # L2 修（2026-11-09）：管理端列表也要真实原件数。
    # 之前调 `_item_brief(m)` 没传 file_count，于是每一行 `file_count` 恒为 0 / `has_files=false`，
    # 而预览抽屉（详情接口）里原件是好的 —— 同一份资料两个接口两种说法。
    # 用一次 group by 取齐（与公共列表同口径），别逐行子查询。
    file_counts = {}
    if rows:
        from ....models.models import MaterialFile
        ids = [r.material_id for r in rows]
        for mid, cnt in (db.query(MaterialFile.material_id, func.count(MaterialFile.file_id))
                         .filter(MaterialFile.material_id.in_(ids))
                         .group_by(MaterialFile.material_id).all()):
            file_counts[mid] = int(cnt)
    items = []
    offset = (page - 1) * page_size
    for idx, m in enumerate(rows):
        item = _item_brief(m, file_count=file_counts.get(m.material_id, 0))
        item.update({"status": m.status, "study_count": m.study_count or 0,
                     "creator_id": m.creator_id,
                     # ID 方案 A（2026-11-08）：连续序号（D2 口径 = 当前筛选结果内）。
                     # 倒序（默认）时首行 = total、往下递减；删 N 条后其后（更旧）的不变、
                     # 其前（更新）的整体 -N；恢复置顶后该行 seq == total（= "最大号"）。
                     # 正序时按 1..N。前端在回收站视图显示「—」（D3）。
                     "seq": (offset + idx + 1) if order == "id_asc" else (total - offset - idx),
                     # A2：发布者（名字 + 角色徽标），creator_id 为空时给 None
                     "publisher": publishers.get(m.creator_id),
                     # C1（2026-11-08）：讲义行显示「N 章 · M 字」；非讲义/未抽到大纲时为 None
                     "chapter_count": _doc_meta_of(m).get("chapter_count"),
                     "word_count": _doc_meta_of(m).get("word_count"),
                     # C3：试卷的年份/地区/卷别（订正优先），非试卷为 None
                     "paper_year": (_paper_meta_for_filter(m).get("year")
                                    if m.type == "paper" else None),
                     "paper_region": (_paper_meta_for_filter(m).get("region_name")
                                      if m.type == "paper" else None),
                     "paper_book_kind": (_paper_meta_for_filter(m).get("book_kind")
                                         if m.type == "paper" else None)})
        # P2（2026-11-09）：试卷行附「考试开关注」状态，列表直接渲染开关与定时摘要。
        # 只在试卷行查一次（每科几套卷），不做的代价是要前端逐行再发请求。
        if m.type == "paper":
            try:
                from ....services import exam_gate
                item["exam"] = exam_gate.state_of(db, m)
            except Exception:  # noqa: BLE001 — 状态算不出来不能拖垮列表
                logger.warning("[materials] 读取考试开关状态失败 material=%s",
                               m.material_id, exc_info=True)
                item["exam"] = None
            # P3（2026-11-09）：附最近一条解析草稿，列表显示「待确认（N 题）」/「解析失败」
            try:
                from ....services import paper_ingest
                draft = paper_ingest.latest_of(db, m.material_id)
                item["parse_draft"] = (paper_ingest.draft_brief(draft, m)
                                       if draft is not None else None)
            except Exception:  # noqa: BLE001
                logger.warning("[materials] 读取解析草稿失败 material=%s",
                               m.material_id, exc_info=True)
                item["parse_draft"] = None
        items.append(item)
    return {"total": total, "items": items}


@router.get("/admin/{material_id}/preview", summary="统一预览契约(管理员)")
async def admin_preview(material_id: int,
                        current_user: SysUser = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """A3（2026-11-07）：管理端**一个**预览契约，6 类资料共用一个抽屉。

    各类型分别给到：
      · `card`             → `card{front,back,images}`（配图含封面 + 正文附图）
      · `article/lecture/paper` → `content_html`（**二次 sanitize**，防历史脏数据）
      · `video_intro/advanced`  → `video{url}`（`/api/video/{id}/stream`）

    尚未接入的三块**先给空值**，契约先定死，后续批次只填数据不改前端分支：
      · `chapters`（讲义章节，C 批）
      · `files`（pdf+docx 双格式，B 批）
      · `paper`（年份/地区/题数/满分，C 批）
    """
    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id).first()
    if not m:
        raise HTTPException(404, "资料不存在")

    from ....services.material_sanitizer import sanitize_html  # noqa: E402

    is_card = m.type == "card"
    is_video = m.type in ("video_intro", "video_advanced")
    return {
        "id": m.material_id,
        "type": m.type,
        "type_label": _MATERIAL_TYPE_LABEL.get(m.type, m.type),
        "title": m.title,
        "summary": m.summary,
        "subject": m.subject,
        "subject_label": _SUBJECT_LABEL.get(m.subject, m.subject),
        "category": m.category,
        "status": m.status,
        # L1：投放位（管理端预览抽屉/列表列用；非试卷类恒 library）
        "placement": _placement_of(m),
        "badge": m.badge,
        "difficulty": m.difficulty or 1,
        "read_time": m.read_time or 0,
        "duration": m.duration or 0,
        "view_count": m.view_count or 0,
        "study_count": m.study_count or 0,
        "publisher": _publisher_map(db, [m]).get(m.creator_id),
        "created_at": _iso_cn(m.create_time),
        # `material_import_record` 只记 uploader_id/file_name，**没有 material_id 外键**，
        # 无法可靠反查「文件上传于何时」→ 先返回 None（前端不渲染这一行）；B 批建
        # material_file 时补关联再回填，契约不用改。
        "uploaded_at": None,
        "content_html": None if (is_card or is_video) else sanitize_html(m.content or ""),
        "card": ({"front": m.card_front, "back": m.card_back,
                  "images": _brief_images(m)} if is_card else None),
        "video": ({"url": (f"/api/video/{m.video_id}/stream" if m.video_id else "")}
                  if is_video else None),
        # C1（2026-11-08）：讲义目录树 + 字数（导入/上传时抽好的快照；pdf/无大纲时为空）
        "chapters": _doc_meta_of(m).get("chapters", []),
        "doc": {
            "word_count": _doc_meta_of(m).get("word_count"),
            "word_count_label": doc_outline.human_word_count(_doc_meta_of(m).get("word_count")),
            "chapter_count": _doc_meta_of(m).get("chapter_count", 0),
        },
        # B1（2026-11-07）：原件留档已落地，这里回真实清单（主文件在前、附件在后）。
        # 没有留档的老资料返回 []，前端按"无原件"渲染，契约不变。
        "files": [material_files.serialize(f)
                  for f in material_files.list_for_material(db, m.material_id)],
        # C2/C4（2026-11-08）：试卷类资料回元数据 + 关联的可作答卷。
        # 关联口径 = `study_material.paper_code == exam_paper.paper_code`（方案 §2.3，一对一）。
        # 非试卷类返回 None，前端分支不变。
        "paper": paper_registry.paper_block(db, m) if m.type == "paper" else None,
    }


@router.get("/files/{file_id}/download", summary="下载资料原件(登录+可见性校验)")
async def download_material_file(file_id: int,
                                 current_user: SysUser = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    """下载 `material_file` 留档的原件（B1，2026-11-07）。

    权限（用户裁定 A）：
      · 管理员（含超管）——不限，含未上架与已删除资料（要先能核对原件才谈得上恢复）；
      · 其他人——只允许 `study_material.status == 1`（已上架）；未上架/已删除一律 403。

    为什么不用 `/uploads` 静态：静态挂载没有鉴权，试卷原卷放进去等于公开。
    路径安全交给 `material_files.resolve_abs_path()`（越界/绝对路径一律当"不存在"404）。
    """
    from fastapi.responses import FileResponse

    row = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
    if not row:
        raise HTTPException(404, "原件不存在")
    material = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == row.material_id).first()
    if not material:
        raise HTTPException(404, "原件不存在")
    if not material_files.can_download(is_admin=_own_or_admin(current_user),
                                       material_status=material.status,
                                       placement=_placement_of(material)):
        raise HTTPException(403, "该资料未上架或不对资料库开放，原件不可下载")
    try:
        path = material_files.resolve_abs_path(row)
    except FileNotFoundError:
        # 库里有行、磁盘没有文件（历史数据/清理脚本误删）→ 当不存在，不暴露内部路径
        logger.warning("[materials] 原件缺失 file_id=%s storage=%s", file_id, row.storage_path)
        raise HTTPException(404, "原件文件已丢失，请联系管理员")
    return FileResponse(
        path,
        media_type=row.mime_type or "application/octet-stream",
        filename=row.file_name or path.name,
        headers={"Cache-Control": "private, max-age=0, must-revalidate"},
    )


@router.post("/admin/papers/backfill", summary="把已发布的可作答卷补录成试卷资料(管理员)")
async def admin_backfill_papers(body: Optional[dict] = None,
                                current_user: SysUser = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    """C4（2026-11-08）：`exam_paper` → `study_material(type=paper)` 的反向补录。

    背景：题库里已有 2 套真实公专真题（各 100 题、已发布、学生能考），
    但资料库 `type=paper` 是 0 条 → 管理员在「资料管理」看不到、也无法统一上架。

    **默认 dry-run**：`{"apply": true}` 才真的写库。
    幂等：已有同 `paper_code`（或同标题）的试卷资料就跳过，可反复调用。
    关联：两侧 `paper_code` 相等即为"这份资料对应的可作答卷"，不需要第二张关联表。
    """
    from ....services import paper_backfill

    payload = body or {}
    apply = bool(payload.get("apply"))
    plan = paper_backfill.apply_backfill(db, apply=apply,
                                         creator_id=current_user.user_id)
    if apply:
        created = [p for p in plan if p.get("action") == "created"]
        _audit(db, current_user, "paper_backfill", f"created={len(created)}",
               "；".join(f"#{p['material_id']}←paper {p['paper_id']}" for p in created)[:500])
        db.commit()
    return JSONResponse({
        "applied": apply,
        "planned": len(plan),
        "to_create": sum(1 for p in plan if p.get("action") == "create"),
        "items": plan,
    })


@router.post("/admin/{material_id}/ensure-paper",
             summary="为试卷资料生成可作答卷(管理员)")
async def admin_ensure_paper(material_id: int,
                             current_user: SysUser = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """A2（2026-11-08）：把一份**试卷类资料**变成题库里的可作答卷。

    背景（实测）：上传试卷只落资料 + 原件 + `paper_code`，**不建 `exam_paper`**，
    于是学生端永远看不到上传的真题（#127「2024国考·公专题本」上传后仍是"有资料无卷"）。

    行为：
      · 用资料的 `paper_code`（回落 `badge`）建一张 `exam_paper`，**状态固定 `DRAFT`**；
        是否可考由「资料上架」经 P5 联动决定（方案 §2.3 的唯一真源）；
      · 元数据取"人工订正 > 文件名解析"（与预览抽屉同口径），缺省 120 分钟 / 100 分；
      · **幂等**：同编号已存在则原样返回（`created=false`），绝不覆盖已有卷的状态与题目；
      · 不 commit 前先 flush 拿 `paper_id`，与审计、提交在同一事务。
    """
    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id).first()
    if not m:
        raise HTTPException(404, "资料不存在")

    from ....services import material_paper_link
    try:
        result = material_paper_link.ensure_paper_for_material(
            db, m, actor_id=current_user.user_id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))

    brief = material_paper_link.paper_brief(result)
    _audit(db, current_user, "ensure_paper", f"material:{material_id}",
           f"{'新建' if brief['created'] else '复用'}可作答卷 {brief['paper_code']}"
           f"（#{brief['paper_id']}，{brief['paper_type']}）")
    db.commit()
    return brief


@router.put("/admin/{material_id}/exam-open", summary="考试开关(管理员)")
async def admin_set_exam_open(material_id: int, body: dict,
                              current_user: SysUser = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """P2（2026-11-09）：切换"学生现在能不能进这场考试"。

    与「资料上架」**互相独立**：
      · 上架只决定资料在不在库里、能不能下载原卷；
      · 本开关只决定学生能否**进入考试**；关闭不动 `exam_record`，历史成绩保留。
    0 题的卷即使打开也进不去（判定在 `exam/contract.exam_ready`，界面把开关灰掉）。
    """
    _require_admin(current_user)
    if "open" not in body:
        raise HTTPException(400, "缺少 open 字段（true/false）")
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not m:
        raise HTTPException(404, "资料不存在或已删除")

    from ....services import exam_gate
    try:
        state = exam_gate.set_open(db, m, open_=bool(body.get("open")))
    except exam_gate.ExamGateError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    _audit(db, current_user, "exam_open", f"material:{material_id}",
           f"考试{'开启' if body.get('open') else '关闭'}"
           f"（{state.get('paper_code')} #{state.get('paper_id')}）")
    db.commit()
    return {"ok": True, "exam": state}


@router.put("/admin/{material_id}/exam-window", summary="考试定时窗口(管理员)")
async def admin_set_exam_window(material_id: int, body: dict,
                                current_user: SysUser = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    """P2：设置/清空定时窗口（如今晚 20:00–22:00）。

    **不建定时任务**：判定在读取时按时间窗计算（`exam/contract.exam_is_open`），
    所以到点自动开关、进程重启也不影响。`open_at`/`close_at` 传空 = 该侧不限。
    """
    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not m:
        raise HTTPException(404, "资料不存在或已删除")

    from ....services import exam_gate
    try:
        open_at = exam_gate.parse_dt(body.get("open_at"))
        close_at = exam_gate.parse_dt(body.get("close_at"))
        state = exam_gate.set_window(db, m, open_at=open_at, close_at=close_at)
    except exam_gate.ExamGateError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    _audit(db, current_user, "exam_window", f"material:{material_id}",
           f"考试定时 {state.get('open_at') or '不限'} → {state.get('close_at') or '不限'}")
    db.commit()
    return {"ok": True, "exam": state}


# ============================ P3：上传即导题（2026-11-09）============================
# 规划见 `docs/plans/上传即建卷_上传即导题_考试开关与定时_方案_v1.md` §3。
# 分工：解析/拆题/入库规则全在 `services/paper_ingest/`，这里只做**鉴权 + 事务 + 审计 + 回包**。
# 为什么不在这里直接写 QuestionBank：跨域写题目会撞 `check_module_boundary`（cross_write），
# 服务层可以 import 任意模型，端点只调服务（与 `paper_registry` 同一套路）。

#: 允许自动导题的扩展名（xlsx 是卡片/表格链路，不在这里）
PARSE_EXTS = ("docx", "pdf")


def _draft_payload(db: Session, draft, material=None) -> dict:
    """草稿的统一回包（列表/明细/动作回执共用一个形状）。"""
    from ....services import paper_ingest
    data = paper_ingest.draft_brief(draft, material)
    data["warnings"] = paper_ingest.warnings_of(draft)
    if material is not None:
        data["paper_code"] = (material.paper_code or material.badge
                              or "").strip() or None
    return data


@router.post("/admin/{material_id}/parse", summary="解析原件生成题目草稿(管理员)")
async def admin_parse_material(material_id: int,
                               current_user: SysUser = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    """把这条资料的**主文件**解析成题目草稿（P3）。

    - 支持 docx / pdf；不是试卷类、没有原件、扩展名不支持 → 400 并说明原因；
    - 解析结果**不直接入库**：先落草稿，管理员看完题号/选项/图片后点「确认入库」；
    - 可重复调用（重试用）：旧的 pending 草稿会先作废，不会积累两条待确认。
    """
    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not m:
        raise HTTPException(404, "资料不存在或已删除")
    if (m.type or "") != "paper":
        raise HTTPException(400, "只有「试卷」类资料需要导题")

    from ....models.models import MaterialFile
    files = (db.query(MaterialFile)
             .filter(MaterialFile.material_id == material_id)
             .order_by(MaterialFile.role.asc(), MaterialFile.file_id.asc()).all())
    primary = next((f for f in files if (f.role or "") == "primary"), None) or (files[0] if files else None)
    if primary is None:
        raise HTTPException(400, "这条资料还没有原件，无法解析（先在「改信息」里上传原件）")
    ext = (primary.file_ext or "").lower().lstrip(".")
    if ext not in PARSE_EXTS:
        raise HTTPException(400, f"暂不支持 .{ext}：目前能自动导题的只有 docx / pdf")

    from ....services import material_files, paper_ingest
    abs_path = str(material_files.resolve_abs_path(primary))

    expected = None
    from ....services import paper_meta_edit
    merged = paper_meta_edit.merge_meta(m, paper_meta_edit.load_override(m))
    if merged.get("question_count"):
        expected = int(merged["question_count"])

    draft = paper_ingest.parse_material(db, m, ext=ext, abs_path=abs_path,
                                        actor_id=current_user.user_id,
                                        expected=expected)
    _audit(db, current_user, "paper_parse", f"material:{material_id}",
           f"解析 {primary.file_name}（{draft.item_count} 题，{draft.status}）")
    db.commit()
    db.refresh(draft)
    payload = _draft_payload(db, draft, m)
    payload["ok"] = draft.status != "failed"
    return payload


@router.get("/admin/parse-drafts", summary="解析草稿列表(管理员)")
async def admin_list_parse_drafts(status: str = "pending",
                                  page: int = Query(1, ge=1),
                                  page_size: int = Query(20, ge=1, le=100),
                                  current_user: SysUser = Depends(get_current_user),
                                  db: Session = Depends(get_db)):
    """按状态列草稿（默认 pending = 待确认）。管理端「待确认（N 题）」入口用它。"""
    _require_admin(current_user)
    from ....models.models import PaperParseDraft
    from ....services import paper_ingest

    q = db.query(PaperParseDraft)
    if status and status != "all":
        q = q.filter(PaperParseDraft.status == status)
    total = q.count()
    rows = (q.order_by(PaperParseDraft.draft_id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    materials = {m.material_id: m for m in db.query(StudyMaterial).filter(
        StudyMaterial.material_id.in_([r.material_id for r in rows] or [0])).all()}
    return {"total": total, "items": [
        _draft_payload(db, r, materials.get(r.material_id)) for r in rows]}


@router.get("/admin/parse-drafts/{draft_id}", summary="解析草稿明细(管理员)")
async def admin_get_parse_draft(draft_id: int,
                                current_user: SysUser = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    """明细：题目草稿 + 告警 + 来源资料/卷。确认页用它渲染逐题对照。"""
    _require_admin(current_user)
    from ....models.models import PaperParseDraft
    from ....services import paper_ingest

    draft = db.query(PaperParseDraft).filter(
        PaperParseDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "草稿不存在")
    material = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == draft.material_id).first()
    pay = _draft_payload(db, draft, material)
    pay["items"] = paper_ingest.items_of(draft)
    pay["can_edit"] = draft.status == "pending"
    return pay


@router.put("/admin/parse-drafts/{draft_id}/items", summary="改草稿题目(管理员)")
async def admin_update_parse_items(draft_id: int, body: dict,
                                   current_user: SysUser = Depends(get_current_user),
                                   db: Session = Depends(get_db)):
    """整表覆盖草稿题目（改题号/题型、删误拆）。

    为什么是整表覆盖而不是逐条 patch：前端确认页本来就把完整列表拿在手里，
    整表提交能一次校验"题号不重复/题型合法/题干非空"，也避免半途失败留半套数据。
    """
    _require_admin(current_user)
    from ....models.models import PaperParseDraft
    from ....services import paper_ingest

    draft = db.query(PaperParseDraft).filter(
        PaperParseDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "草稿不存在")
    items = body.get("items")
    if not isinstance(items, list):
        raise HTTPException(400, "items 必须是数组")
    try:
        paper_ingest.update_items(db, draft, items)
    except paper_ingest.IngestError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(draft)
    material = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == draft.material_id).first()
    return _draft_payload(db, draft, material)


@router.post("/admin/parse-drafts/{draft_id}/confirm", summary="确认入库(管理员)")
async def admin_confirm_parse_draft(draft_id: int, body: dict | None = None,
                                    current_user: SysUser = Depends(get_current_user),
                                    db: Session = Depends(get_db)):
    """确认入库：题目写 `question_bank` + 挂到该卷 + 图片落到 `static/questions/{qid}/`。

    - 卷里已有题目时默认拒绝（409），要重导必须显式 `replace=true`（只删关系，不删题目）；
    - 入库后卷题量按关系表实数重算（`paper_stats`），此时打开考试开关学生才有题可做。
    """
    _require_admin(current_user)
    body = body or {}
    from ....models.models import PaperParseDraft
    from ....services import paper_ingest

    draft = db.query(PaperParseDraft).filter(
        PaperParseDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "草稿不存在")
    try:
        result = paper_ingest.confirm_draft(
            db, draft, actor_id=current_user.user_id,
            replace=bool(body.get("replace")),
            subject_id=body.get("subject_id"))
    except paper_ingest.IngestError as e:
        db.rollback()
        raise HTTPException(409 if "已有" in str(e) else 400, str(e))
    _audit(db, current_user, "paper_import", f"material:{draft.material_id}",
           f"确认入库 {result['created']} 题 → 卷 #{result['paper_id']}"
           + (f"（覆盖 {result['replaced']} 题）" if result.get("replaced") else ""))
    # 入库后卷已有题：如果资料本来就是「已上架」，按 P5 的唯一真源把它推成可作答（PUBLISHED）。
    # 不这么做会出现「资料已上架 + 卷有 100 题，但卷还是 DRAFT」→ 学生看不到，要等下次上/下架才生效。
    from ....services import material_paper_sync
    draft_material = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == draft.material_id).first()
    sync = (material_paper_sync.sync_material(db, draft_material)
            if draft_material is not None else None)
    db.commit()
    return {"ok": True, "paper_sync": _paper_sync_payload(sync), **result}


@router.delete("/admin/parse-drafts/{draft_id}", summary="放弃草稿(管理员)")
async def admin_discard_parse_draft(draft_id: int,
                                    current_user: SysUser = Depends(get_current_user),
                                    db: Session = Depends(get_db)):
    """放弃草稿：标 discarded + 删草稿图片（正式题目/图片目录不受影响）。"""
    _require_admin(current_user)
    from ....models.models import PaperParseDraft
    from ....services import paper_ingest

    draft = db.query(PaperParseDraft).filter(
        PaperParseDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "草稿不存在")
    try:
        paper_ingest.discard_draft(db, draft)
    except paper_ingest.IngestError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    _audit(db, current_user, "paper_parse_discard", f"material:{draft.material_id}",
           f"放弃解析草稿 #{draft_id}")
    db.commit()
    return {"ok": True, "draft_id": draft_id, "status": draft.status}


# ============================ P4：答案上传（2026-11-09）============================
# 方案见 `docs/plans/答案上传_PDF与Excel多通道_方案_v1.md`（用户「按建议」批准 4 条决策）。
# 分工与导题一致：解析/校验/写入全在 `services/answer_ingest/`，端点只做鉴权+事务+审计+回包。
# 用户拍板：① 已有答案不同默认保留；② 推断层只给建议不自动填；③ 解析正文一起入库；
#          ④ 本次不做"按文件名自动匹配卷"（只按卷上传）。

#: 答案文件允许的扩展名（xlsx 走"一行一题"通道；txt 便于小批量手写）
ANSWER_EXTS = ("pdf", "docx", "xlsx", "xls", "txt", "csv")


@router.post("/admin/papers/{paper_id}/answers/parse",
             summary="上传答案文件并解析(管理员)")
async def admin_parse_answers(paper_id: int,
                              file: UploadFile = File(...),
                              current_user: SysUser = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """上传答案解析（**PDF 是一等通道**）→ 解析成「答案草稿」，不直接写库。

    实测（4 套卷 / 397 题）：题号 397/397、答案自动识别 397/397，只有 1 题与题型不符需人看。
    写入前必须预览：答案错一位，学生看到的解析就对不上。
    """
    _require_admin(current_user)
    name = (file.filename or "答案").replace("\\", "/").split("/")[-1][:255]
    ext = _os.path.splitext(name)[1].lower().lstrip(".")
    if ext not in ANSWER_EXTS:
        raise HTTPException(400, "答案文件仅支持 pdf / docx / xlsx / txt / csv")
    raw = file.file.read()
    if not raw:
        raise HTTPException(400, "空文件不能上传")
    if len(raw) > 30 * 1024 * 1024:
        raise HTTPException(400, "答案文件超过 30MB 上限")

    from ....services import answer_ingest
    tmp_dir = _os.path.join(UPLOAD_TMP_DIR, "answers")
    _os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = _os.path.join(tmp_dir, f"{_uuid.uuid4().hex}.{ext}")
    with open(tmp_path, "wb") as fh:
        fh.write(raw)
    try:
        draft = answer_ingest.parse_answers(
            db, paper_id=paper_id, ext=ext, abs_path=tmp_path,
            source_name=name, actor_id=current_user.user_id)
        _audit(db, current_user, "answer_parse", f"paper:{paper_id}",
               f"解析答案 {name}（{draft.item_count} 题，{draft.status}）")
        db.commit()
        db.refresh(draft)
    except answer_ingest.AnswerIngestError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    finally:
        try:
            _os.unlink(tmp_path)
        except OSError:
            pass

    payload = answer_ingest.draft_payload(db, draft)
    payload["ok"] = draft.status != "failed"
    return payload


@router.get("/admin/papers/{paper_id}/answers/latest", summary="取该卷最近一份答案草稿(管理员)")
async def admin_latest_answer_draft(paper_id: int,
                                    current_user: SysUser = Depends(get_current_user),
                                    db: Session = Depends(get_db)):
    """给「补答案」抽屉用：打开时先看有没有**未确认**的草稿，有就直接续上。

    为什么需要：管理员上传后如果先关掉抽屉，草稿会留在库里；没有这个入口就变成
    "看不见的待办"，下次又传一遍，草稿越堆越多。
    """
    _require_admin(current_user)
    from ....services import answer_ingest

    draft = answer_ingest.latest_of(db, paper_id)
    if draft is None:
        return {"exists": False}
    payload = answer_ingest.draft_payload(db, draft, with_items=True)
    payload["exists"] = True
    payload["can_edit"] = draft.status == "pending"
    return payload


@router.get("/admin/answers/drafts/{draft_id}", summary="答案草稿明细(管理员)")
async def admin_get_answer_draft(draft_id: int,
                                 current_user: SysUser = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    """预览：逐题答案 / 来源层级 / 推断建议 / 解析摘要 / 标记（冲突、未识别）。"""
    _require_admin(current_user)
    from ....models.models import PaperAnswerDraft
    from ....services import answer_ingest

    draft = db.query(PaperAnswerDraft).filter(
        PaperAnswerDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "答案草稿不存在")
    return answer_ingest.draft_payload(db, draft, with_items=True)


@router.put("/admin/answers/drafts/{draft_id}/items", summary="改答案草稿(管理员)")
async def admin_update_answer_items(draft_id: int, body: dict,
                                    current_user: SysUser = Depends(get_current_user),
                                    db: Session = Depends(get_db)):
    """整表保存（人工补空 / 改冲突 / 采纳"推断建议"）。

    校验：题号必须属于该卷、题号不重复、答案只允许 A–D；错误一次说清，不留半套数据。
    """
    _require_admin(current_user)
    from ....models.models import PaperAnswerDraft
    from ....services import answer_ingest

    draft = db.query(PaperAnswerDraft).filter(
        PaperAnswerDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "答案草稿不存在")
    items = body.get("items")
    if not isinstance(items, list):
        raise HTTPException(400, "items 必须是数组")
    try:
        answer_ingest.update_items(db, draft, items)
    except answer_ingest.AnswerIngestError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(draft)
    return answer_ingest.draft_payload(db, draft)


@router.post("/admin/answers/drafts/{draft_id}/apply", summary="写入答案解析(管理员)")
async def admin_apply_answer_draft(draft_id: int, body: dict | None = None,
                                   current_user: SysUser = Depends(get_current_user),
                                   db: Session = Depends(get_db)):
    """把答案与解析写进题库（**只动 `answer` / `answer_analysis` 两列**）。

    - 默认**只填空位**；库里已有不同答案计入 `kept`，要覆盖必须 `overwrite=true`（决策 Q1）；
    - **不重算历史成绩**：`exam_record` 一概不动，只影响之后的新考试；
    - 空答案但有解析的题只补解析（素材不浪费）。
    """
    _require_admin(current_user)
    body = body or {}
    from ....models.models import PaperAnswerDraft
    from ....services import answer_ingest

    draft = db.query(PaperAnswerDraft).filter(
        PaperAnswerDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "答案草稿不存在")
    try:
        result = answer_ingest.apply_draft(db, draft, overwrite=bool(body.get("overwrite")))
    except answer_ingest.AnswerIngestError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    _audit(db, current_user, "answer_apply", f"paper:{draft.paper_id}",
           f"写入答案 {result['filled']} 题"
           + (f"、覆盖 {result['overwritten']} 题" if result["overwritten"] else "")
           + (f"、保留 {result['kept']} 题" if result["kept"] else ""))
    db.commit()
    return {"ok": True, **result}


@router.delete("/admin/answers/drafts/{draft_id}", summary="放弃答案草稿(管理员)")
async def admin_discard_answer_draft(draft_id: int,
                                     current_user: SysUser = Depends(get_current_user),
                                     db: Session = Depends(get_db)):
    _require_admin(current_user)
    from ....models.models import PaperAnswerDraft
    from ....services import answer_ingest

    draft = db.query(PaperAnswerDraft).filter(
        PaperAnswerDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(404, "答案草稿不存在")
    try:
        answer_ingest.discard_draft(db, draft)
    except answer_ingest.AnswerIngestError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    _audit(db, current_user, "answer_discard", f"paper:{draft.paper_id}",
           f"放弃答案草稿 #{draft_id}")
    db.commit()
    return {"ok": True, "draft_id": draft_id, "status": draft.status}


@router.delete("/admin/{material_id}/files/{file_id}", summary="删除单份原件(管理员)")
async def admin_delete_file(material_id: int, file_id: int,
                            current_user: SysUser = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """删除资料下的一份原件（C2b 补漏，2026-11-08）。

    场景：验收时把「模拟卷.pdf」误挂到了 2019 北京真题上——没有删除入口就只能删整条资料。
    口径：
      · 只删登记行；**同一内容（sha256）没有别的资料引用时**才删物理文件（存储是内容寻址的，
        别的资料可能引用同一份文件，无条件删会把人家正在用的文件删掉）；
      · 物理文件删失败（占用/权限）不阻断，`orphan_count()` 能对账出来；
      · 写审计（`delete_file`）。
    """
    _require_admin(current_user)
    row = db.query(MaterialFile).filter(
        MaterialFile.file_id == file_id,
        MaterialFile.material_id == material_id).first()
    if not row:
        raise HTTPException(404, "原件不存在或不属于该资料")

    info = material_files.delete_file(db, row)
    db.commit()
    _audit(db, current_user, "delete_file", f"material:{material_id}",
           f"file:{file_id} {info['physical_deleted'] and '物理文件已删' or '物理文件保留'}")
    db.commit()

    remaining = material_files.list_for_material(db, material_id)
    return JSONResponse({
        "ok": True,
        "deleted": info,
        "files": [material_files.serialize(f) for f in remaining],
    })


@router.patch("/admin/{material_id}/meta", summary="改试卷/讲义信息(管理员)")
async def admin_update_meta(material_id: int, body: dict,
                            current_user: SysUser = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """C2b（2026-11-08）：列表「改信息」→ 改标题 / 分类 / 试卷元数据。

    为什么只写 `study_material`、不写 `exam_paper`：见 `services/paper_meta_edit.py` 开头
    （跨域写会被 L4 模块边界门禁拦；且资料描述的是"原卷"，与在线卷的题量本就可能不同）。

    字段（全部非必填，`null`/空串 = 清除该项）：
      · `title` / `category`：普通资料字段；
      · `year` / `region_code`|`region_name` / `book_kind` / `volume` / `question_count` /
        `total_score` / `duration`：写进 `paper_meta`（JSON），优先级高于文件名解析；
      · `paper_code`：人读编号；传空串且资料未关联可作答卷时，系统按新元数据自动重算。
    """
    from ....services import paper_meta_edit

    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id,
        StudyMaterial.status >= 0).first()
    if not m:
        raise HTTPException(404, "资料不存在或已删除")

    changed: list = []

    if "title" in body:
        title = (body.get("title") or "").strip()
        if not title:
            raise HTTPException(400, "标题不能为空")
        if title != (m.title or ""):
            m.title = title[:200]
            changed.append("title")
    if "category" in body:
        category = (body.get("category") or "").strip() or None
        if category != m.category:
            m.category = category[:100] if category else None
            changed.append("category")
    # L1（2026-11-08）：投放位可改（D-L8）。改完立刻同步一次卷状态 —— 例如
    # both→library 要马上把已发布的卷落回 DRAFT，不能等到下次上架。
    if "placement" in body:
        if m.type != "paper":
            raise HTTPException(400, "只有试卷类资料才有投放位")
        want = (body.get("placement") or "").strip().lower()
        if want not in PLACEMENTS:
            raise HTTPException(400, "投放位只能是 exam（仅考试页）/ library（仅资料页）/ both（都投）")
        if want != (m.placement or "library"):
            m.placement = want
            changed.append("placement")
            from ....services import material_paper_sync
            sync = material_paper_sync.sync_material(db, m)
            if sync.get("note"):
                changed.append(sync["note"])

    meta_payload = {k: v for k, v in body.items()
                    if k in ("year", "region_code", "region_name", "book_kind",
                             "book_kind_label", "volume", "question_count",
                             "total_score", "duration")}
    if meta_payload or body.get("paper_meta_reset"):
        try:
            patch = paper_meta_edit.normalize_patch(meta_payload)
        except paper_meta_edit.MetaError as exc:
            raise HTTPException(400, str(exc))
        current = {} if body.get("paper_meta_reset") else paper_meta_edit.load_override(m)
        current.update(patch)
        # 全部清空后不留空 JSON，回到"按文件名解析"的状态
        current = {k: v for k, v in current.items() if v not in (None, "")}
        m.paper_meta = _json.dumps(current, ensure_ascii=False) if current else None
        changed.extend(sorted(patch))

    # 编号：显式传了就用传的；传空 + 未关联 + 能算出 → 自动重算
    if "paper_code" in body:
        want = (body.get("paper_code") or "").strip().upper()
        if want:
            clash = db.query(StudyMaterial).filter(
                StudyMaterial.paper_code == want,
                StudyMaterial.material_id != m.material_id,
                StudyMaterial.status >= 0).first()
            if clash:
                raise HTTPException(400, f"编号 {want} 已被资料 #{clash.material_id} 使用")
            if want != (m.paper_code or ""):
                m.paper_code = want
                m.badge = want
                changed.append("paper_code")
        else:
            merged = paper_meta_edit.merge_meta(m)
            merged["subject"] = m.subject or None
            suggestion = paper_meta_edit.suggest_paper_code(merged)
            if suggestion and suggestion != (m.paper_code or ""):
                m.paper_code = suggestion
                m.badge = suggestion
                changed.append("paper_code")

    db.commit()
    _audit(db, current_user, "update", f"material:{material_id}",
           "改信息：" + (", ".join(changed) if changed else "无变化"))
    db.commit()

    return JSONResponse({
        "ok": True,
        "changed": changed,
        "material": {"id": m.material_id, "title": m.title,
                     "category": m.category, "paper_code": m.paper_code,
                     "status": m.status, "type": m.type},
        "paper": (paper_registry.paper_block(db, m) if m.type == "paper" else None),
    })


@router.post("/admin/files/upload", summary="上传原件并建资料/挂附件(批量导入·单文件)")
async def admin_upload_file(
        file: UploadFile = File(...),
        subject: str = Form(...),
        type: str = Form("lecture"),
        category: str = Form(""),
        title: str = Form(""),
        material_id: Optional[int] = Form(None),
        placement: str = Form(""),
        auto_parse: str = Form("1"),
        publish: str = Form("0"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)):
    """B2（2026-11-07）：**批量导入的单个文件入口**。

    为什么是"一次一个文件"而不是一次 50 个：50 个 × 20MB 放一个请求里既不能显示进度，
    失败整批重来；前端按队列逐个小请求发，进度、失败重试、跳过重复都能精确到行，
    服务端也不必为 2GB 请求体设超时。**数量（≤50）与总量（≤2GB）由前端队列把关**，
    服务端只守单文件上限 20MB（`material_files.MAX_FILE_BYTES`）。

    两种用法：
      · 不带 `material_id` → **建一条资料**（`status=0` 未上架）+ 原件作 `primary`；
      · 带 `material_id` → 只挂 `attachment`（双格式配对：docx 主文件 + pdf 附件）。

    重复内容不报错、也不重复建：返回 `duplicate=true` 与已存在资料的 id
    （批量场景里"跳过"比"整批失败"有用）。
    """
    _require_admin(current_user)
    if subject not in SUBJECTS:
        raise HTTPException(400, "科目必选且有效")
    if type not in ("article", "lecture", "paper"):
        raise HTTPException(400, "文件类资料类型只能是 article / lecture / paper")

    # L1（2026-11-08）投放位：只有试卷类能选"仅考试页/仅资料页/都投"。
    # 默认值按 D-L2：试卷 = both（与改造前完全一致：学生既能看原卷也能考），
    # 其它类型恒 library（文章/讲义没有"考试页"这回事，传别的值直接 400 而不是静默忽略，
    # 因为静默忽略会让前端以为设置生效了）。
    want_placement = (placement or "").strip().lower()
    if want_placement and want_placement not in PLACEMENTS:
        raise HTTPException(400, "投放位只能是 exam（仅考试页）/ library（仅资料页）/ both（都投）")
    if type != "paper":
        if want_placement and want_placement != "library":
            raise HTTPException(400, "只有试卷类资料可以选投放位")
        target_placement = "library"
    else:
        target_placement = want_placement or "both"

    # W2（2026-11-09）：上传时可选「立即上架」。默认不上架（与"上架即审批"一致），
    # 只有显式 publish=1 才直接写成已上架并同步卷状态 —— 省掉"传完再去列表点一次"。
    want_publish = (publish or "0").strip().lower() in ("1", "true", "yes", "on")

    data = file.file.read()
    name = (file.filename or "未命名").replace("\\", "/").split("/")[-1][:255]
    ext = _os.path.splitext(name)[1].lower().lstrip(".")
    if ext not in material_files.ALLOWED_EXT_MIME:
        raise HTTPException(400, "仅支持 docx / doc / pdf / xlsx / xls 原件")
    if not data:
        raise HTTPException(400, "空文件不能上传")
    if len(data) > material_files.MAX_FILE_BYTES:
        raise HTTPException(400,
                            f"文件超过 {material_files.MAX_FILE_BYTES // 1024 // 1024}MB 上限")
    magic = MAGIC_BYTES.get("." + ext)
    if magic and not data.startswith(magic):
        raise HTTPException(400, "文件实际格式与扩展名不符")

    sha = material_files.sha256_of_bytes(data)
    # 同内容已存在（且资料没被删）→ 跳过，回已有 id，便于前端标"重复"
    dup = (db.query(MaterialFile, StudyMaterial)
           .join(StudyMaterial, StudyMaterial.material_id == MaterialFile.material_id)
           .filter(MaterialFile.sha256 == sha, StudyMaterial.status >= 0)
           .order_by(MaterialFile.file_id.asc()).first())
    if dup:
        dup_file, dup_material = dup
        return JSONResponse({
            "duplicate": True, "created": False,
            "material_id": dup_material.material_id,
            "existing_file_id": dup_file.file_id,
            "file_name": dup_file.file_name,
            "title": dup_material.title,
        })

    target_material = None
    created_new = False          # 是否**本次新建**了资料（挂附件时必须为 False）
    if material_id is not None:
        target_material = db.query(StudyMaterial).filter(
            StudyMaterial.material_id == material_id,
            StudyMaterial.status >= 0).first()
        if not target_material:
            raise HTTPException(404, "要挂附件的资料不存在或已删除")
        # C2b：给**还没有任何原件**的资料补档时，这一份应当是主文件，
        # 否则会出现"只有附件、没有主文件"的畸形数据（补 2 套真题原卷时就会遇到）。
        has_files = (db.query(MaterialFile)
                     .filter(MaterialFile.material_id == material_id).first()) is not None
        role = "attachment" if has_files else "primary"
    else:
        role = "primary"

    try:
        paper_auto = None
        if target_material is None:
            stem = _os.path.splitext(name)[0][:200] or "未命名资料"
            # C2a 接线（2026-11-08）：试卷类上传时按**文件名**解析元数据，直接落人读编号。
            # 之前只有补录（C4）与改信息（C2b）会生成编号，B2 上传路径漏了这一步，
            # 结果「2024国考·公专题本.docx」导入后编号为空（验收时发现）。
            parsed_code = None
            if type == "paper":
                from ....services.paper_meta_parser import (
                    PaperMeta, build_paper_code, parse_paper_file_name)
                meta = parse_paper_file_name(stem)
                # ★ P1（2026-11-09）：文件名解析不出**科目**时，用上传表单里选的科目兜底。
                # 实测 #128「2016江西招警考试《人民警察基础知识》真题（部分）.docx」：
                # 年份/地区/卷别都能解析，唯独"人民警察基础知识"不在科目关键词里 →
                # build_paper_code 拒绝生成编号 → 列表里连「建卷」都不出现。
                if not getattr(meta, "subject", None):
                    meta = PaperMeta(**{**meta.as_dict(), "subject": subject})
                parsed_code = build_paper_code(meta)
            target_material = StudyMaterial(
                subject=subject, type=type,
                category=(category or None), title=(title or stem)[:200],
                badge=parsed_code, paper_code=parsed_code,
                placement=target_placement,
                # W2（2026-11-09）：默认未上架；`publish=1` 时直接上架（省掉"传完再点一次"）。
                # 上架仍要过一次 P5 联动，保证卷状态与资料状态一致（见下方 db.flush 之后的同步）。
                content="", status=(1 if want_publish else 0),
                creator_id=current_user.user_id)
            db.add(target_material)
            db.flush()
            created_new = True
        elif type == "paper" and want_placement and (target_material.placement or "library") != target_placement:
            # 给已有试卷补原件时可顺带改投放位；改完必须同步一次卷状态，
            # 否则 both→library 这种"撤出考试页"的操作要等下次上架才生效。
            target_material.placement = target_placement
            from ....services import material_paper_sync
            material_paper_sync.sync_material(db, target_material)

        # ★ P1（2026-11-09）上传即建卷：投放位落在「仅考试页 / 都投」时，上传当场建好可作答卷。
        #   · 用户决策 ①：只在考试相关投放位触发 —— 纯资料库不该平白多出 0 题草稿卷塞满题库；
        #   · 用户决策 ②：卷名 = 文件名去扩展名（不用资料展示标题），与原件同名最好认；
        #   · 幂等：ensure_paper_for_material 以 paper_code 为唯一键，同编号重复上传不建第二张，
        #     也不会把已发布卷改回草稿；
        #   · 编号解析不出来（缺年份/地区）时**绝不阻断上传**：资料照存，回包里给 hint，
        #     管理员在「改信息」补编号后仍可点「建卷」——这是 #128 的真实踩坑路径。
        if created_new and type == "paper" and target_placement in EXAM_PLACEMENTS:
            if not material_paper_link.paper_code_of(target_material):
                paper_auto = {
                    "created": False, "reason": "no_code",
                    "hint": "文件名里没解析出「年份 + 地区」，未自动建卷；"
                            "在「改信息」补编号后可点「建卷」",
                }
            else:
                try:
                    paper_auto = material_paper_link.paper_brief(
                        material_paper_link.ensure_paper_for_material(
                            db, target_material, actor_id=current_user.user_id,
                            paper_name=stem))
                    paper_auto["reason"] = None
                    paper_auto["hint"] = None
                except ValueError as exc:      # 理论上不会走到（已判过编号）
                    paper_auto = {"created": False, "reason": "invalid",
                                  "hint": str(exc)}
        row = material_files.save_bytes(
            db, target_material.material_id, data, name,
            role=role, source="upload", uploader_id=current_user.user_id)
        # C1：讲义 docx 上传后顺手抽大纲（字数/章节），列表与抽屉直接有数据
        if role == "primary" and name.lower().endswith(".docx"):
            try:
                doc_outline.apply_to_material(
                    db, target_material, material_files.resolve_abs_path(row))
            except Exception:      # 抽不出大纲不影响上传成功
                logger.warning("[materials] 讲义大纲抽取失败 material=%s",
                               target_material.material_id, exc_info=True)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    except OSError:
        db.rollback()
        logger.exception("[materials] 原件写盘失败")
        raise HTTPException(503, "原件写入失败（磁盘不可用），请稍后重试")

    _audit(db, current_user, "upload_file",
           f"material:{target_material.material_id}",
           f"{name}（{role}）"
           + ("，立即上架" if want_publish and created_new else ""))
    if paper_auto:
        # 建卷是**独立可追溯**的动作（自动触发也要留痕），失败/跳过同样记一笔原因
        _audit(db, current_user, "auto_create_paper",
               f"material:{target_material.material_id}",
               (f"卷 {paper_auto.get('paper_code')} #{paper_auto.get('paper_id')}"
                if paper_auto.get("created")
                else f"跳过：{paper_auto.get('hint') or paper_auto.get('reason')}"))
    if want_publish and created_new:
        # 立即上架也要走 P5 联动（否则会出现"资料已上架但卷还是 DRAFT"，
        # 学生看不到刚传上来的真题 —— #127 就是这种）。
        from ....services import material_paper_sync
        sync_publish = material_paper_sync.sync_material(db, target_material)
        _audit(db, current_user, "status", f"material:{target_material.material_id}",
               "上传即上架" + (f"（卷 {sync_publish.get('after')}）" if sync_publish.get("after") else ""))
    db.commit()

    # ★ P3（2026-11-09）上传即导题：试卷主文件是 docx/pdf 时**当场解析**成待确认草稿。
    #   · 为什么不放后台任务：`SessionLocal` 在测试里指向**真实库**（conftest 只用 get_db
    #     覆盖了请求会话），后台任务会绕过覆盖写到生产库。同步解析用同一个 request session，
    #     既安全又能把「解析出多少题」直接回给前端；
    #   · 为什么解析失败不报错：上传本身已经成功（资料+原件+卷都在），解析只是增值步骤；
    #   · 耗时：docx 97 题 ≈0.2s，2024 国考 pdf 100 题+25 图 ≈1.5s（实测），可接受；
    #     批量导入是逐文件请求，进度条会照常往前走。
    parse_auto = None
    if (role == "primary" and type == "paper" and ext in PARSE_EXTS
            and (auto_parse or "1").strip().lower() not in ("0", "false", "no")):
        try:
            from ....services import paper_ingest
            draft = paper_ingest.parse_material(
                db, target_material, ext=ext,
                abs_path=material_files.resolve_abs_path(row),
                actor_id=current_user.user_id)
            _audit(db, current_user, "paper_parse",
                   f"material:{target_material.material_id}",
                   f"上传即导题：{draft.item_count} 题（{draft.status}）")
            db.commit()
            db.refresh(draft)
            parse_auto = _draft_payload(db, draft, target_material)
        except Exception:       # noqa: BLE001 — 解析失败绝不影响上传结果
            db.rollback()
            logger.warning("[materials] 上传即导题失败 material=%s",
                           target_material.material_id, exc_info=True)

    return JSONResponse({
        "duplicate": False, "created": created_new,
        "material_id": target_material.material_id,
        "file": material_files.serialize(row),
        "title": target_material.title,
        # P1：投放位∈{exam,both} 的试卷上传会当场建卷；前端据此提示「已建卷/未建卷原因」
        "paper": paper_auto,
        # P3：docx/pdf 试卷上传会当场解析出「待确认」草稿；前端提示「已拆出 N 题，去确认」
        "parse": parse_auto,
        # W2：是否本次就上架了（前端据此提示「已上架 / 仍是未上架」）
        "published": bool(want_publish and created_new),
        "status": target_material.status,
    })


@router.post("/admin", summary="创建资料(管理员)")
async def admin_create(body: dict,
                       current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """建一条资料。**默认未上架**（W2 / 方案 D1，2026-11-09）。

    为什么改默认：以前 `POST /admin` 不带 status 时走模型默认 `status=1`，
    也就是"建好就等于审批通过、学生立刻可见"——与「上架即审批」的唯一真源冲突。
    现在：
      · 不传 status → **0（未上架）**，要上线必须显式点「上架」或传 `status=1`；
      · 同内容（`content_hash`）已存在且未删除 → 409 并回已有 id，不再产生第二条；
      · `status` 只接受 0/1。
    """
    _require_admin(current_user)
    data = _validate_material_body(body)
    _finalize_classification(db, data)

    status = body.get("status", 0)
    if status not in (0, 1):
        raise HTTPException(400, "status 只能是 0（未上架）或 1（已上架）")

    content_hash = _material_content_hash(data)
    if content_hash:
        dup_id = _find_duplicate_material_id(db, content_hash, current_user.user_id)
        if dup_id:
            raise HTTPException(409, f"与已有资料 #{dup_id} 内容重复（同内容不重复建）")

    m = StudyMaterial(**data, status=status, content_hash=(content_hash or None),
                      creator_id=current_user.user_id)
    db.add(m)
    db.commit()
    db.refresh(m)
    _audit(db, current_user, "create", f"material:{m.material_id}",
           f"{m.title}（{'已上架' if status else '未上架'}）")
    db.commit()
    return {"id": m.material_id, "status": status,
            "duplicate": False, "content_hash": content_hash or None}


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
    prev = m.status
    m.status = st
    if prev == -1:
        # ID 方案 A（2026-11-08）：从回收站恢复 → 排到列表最前面。
        # 只改排序键 `list_time`，**不改 `create_time`**（"上传时间"列必须保持真实）；
        # 倒序编号下该行随即拿到"当前最大序号"（= total），等价于"新号"且不复用旧号。
        m.list_time = datetime.now()
    # P5（2026-11-08）：资料可见性 → 可作答性（方案《试卷管理收敛》§2.3）。
    # 与状态变更、审计写在同一个事务里：要么全成，要么全不成。
    from ....services import material_paper_sync
    sync = material_paper_sync.sync_material(db, m)
    # 从回收站（status=-1）回到 0/1 记为「恢复资料」，与普通上/下架在审计里可区分
    base = (("恢复为" + ("上架" if st == 1 else "未上架")) if prev == -1
            else ("上架" if st == 1 else "下架"))
    detail = f"{base}；{sync['note']}" if sync.get("note") else base
    _audit(db, current_user, "restore" if prev == -1 else "status",
           f"material:{material_id}", detail)
    db.commit()
    return {"ok": True, "paper_sync": _paper_sync_payload(sync)}


@router.delete("/admin/batch", summary="批量删除资料(管理员)")
async def admin_batch_delete(
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量删除多条资料（软删除）。body.ids 为资料 ID 数组。

    2026-11-07 裁定 B：与单条删除一致改为 `status=-1`，不再物理删行、不再清学习进度。
    返回 `deleted` = 本次真正被标记为删除的条数（已删除的不重复计数）。

    ⚠️ **路由顺序**：本路由必须声明在 `DELETE /admin/{material_id}` **之前**。
    FastAPI/Starlette 按声明顺序匹配，`/admin/batch` 若排在动态段之后会被当成
    `material_id="batch"` → 422「Input should be a valid integer」（实测：批量删除从来没调通过）。
    """
    _require_admin(current_user)
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "ids 不能为空")

    # 2026-11-08（P5）：改为逐条置 -1（原来是 bulk update），原因是联动要按 ORM 对象
    # 计算「同编号是否还有其它已上架资料」，bulk update 用 synchronize_session=False
    # 会让会话里的 status 仍是旧值，导致该下架的卷没下架。条数由前端勾选，量级很小。
    targets = (db.query(StudyMaterial)
               .filter(StudyMaterial.material_id.in_(ids),
                       StudyMaterial.status >= 0)
               .all())
    for m in targets:
        m.status = -1
    from ....services import material_paper_sync
    syncs = material_paper_sync.sync_materials(db, targets)
    deleted = len(targets)
    note = material_paper_sync.note_of_many(syncs)
    _audit(db, current_user, "batch_delete",
           f"deleted={deleted}" + (f"；{note}" if note else ""))
    db.commit()
    changed = [p for p in (_paper_sync_payload(s) for s in syncs)
               if p and p.get("changed")]
    return {"deleted": deleted, "paper_sync": changed}


@router.delete("/admin/{material_id}", summary="删除资料(管理员)")
async def admin_delete(material_id: int,
                       current_user: SysUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """软删除（`status=-1`），不物理删行。

    2026-11-07 用户裁定 B：统一为软删除，与《试卷管理收敛_单一入口与上架即审批_方案_v1.md》§2.2
    「（删除）|-1|软删除，不参与列表与统计」一致。原实现是 `db.delete(m)` 物理删除 + 清学习进度，
    误删后无法恢复（实测 121/122 两条就是这样消失的）。

    - **不移除 `UserMaterialProgress`**：恢复后学生学习进度还在；彻底清理由后续「回收站·彻底删除」承担。
    - **幂等**：对已删除行再次删除返回 `{"ok": true, "already_deleted": true}`，不报 404。
    - **恢复**：`PUT /admin/{id}/status` 传 `status=0`（恢复为未上架）。
    """
    _require_admin(current_user)
    m = db.query(StudyMaterial).filter(
        StudyMaterial.material_id == material_id).first()
    if not m:
        raise HTTPException(404, "资料不存在")
    if m.status == -1:
        return {"ok": True, "already_deleted": True}
    title = m.title
    m.status = -1
    # P5（2026-11-08）：删除即"不可见"，与下架同语义 → 关联卷同步 DRAFT（同事务）
    from ....services import material_paper_sync
    sync = material_paper_sync.sync_material(db, m)
    detail = f"{title}；{sync['note']}" if sync.get("note") else title
    _audit(db, current_user, "delete", f"material:{material_id}", detail)
    db.commit()
    return {"ok": True, "paper_sync": _paper_sync_payload(sync)}


# ============================ 统计概览 & 批量操作（Task3/4）============================

@router.get("/admin/stats", summary="统计概览(管理员)")
async def admin_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回资料总量、按类型/科目/状态的分布统计。

    口径（2026-11-07 修正，用户裁定 A）：**全部聚合统一排除软删除（status = -1）**。
    原实现 `total = count(*)` 把已删除也算进总数，而 `by_status` 只取 1/0 两档，
    导致「已上架 + 未上架 ≠ 总资料」（实测差 5 条：114 vs 119），`by_type` 也虚高。
    现在 total / by_type / by_subject / by_status 用同一个过滤条件，满足：
        total == sum(by_type) == sum(by_subject) == published + draft + 其它在用状态
    """
    _require_admin(current_user)

    alive = StudyMaterial.status >= 0   # 排除软删除（-1）；学生个人库 status=2 仍计入

    total = (db.query(func.count(StudyMaterial.material_id))
             .filter(alive).scalar() or 0)

    type_rows = (
        db.query(StudyMaterial.type, func.count(StudyMaterial.material_id))
        .filter(alive)
        .group_by(StudyMaterial.type)
        .all()
    )
    type_stats = dict(type_rows)

    subject_rows = (
        db.query(StudyMaterial.subject, func.count(StudyMaterial.material_id))
        .filter(alive)
        .group_by(StudyMaterial.subject)
        .all()
    )
    subject_stats = dict(subject_rows)

    status_rows = (
        db.query(StudyMaterial.status, func.count(StudyMaterial.material_id))
        .filter(alive)
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
            "lecture": type_stats.get("lecture", 0),
            "paper": type_stats.get("paper", 0),
        },
        "by_subject": {
            "xingce": subject_stats.get("xingce", 0),
            "shenlun": subject_stats.get("shenlun", 0),
            "gongzhuan": subject_stats.get("gongzhuan", 0),
        },
        "by_status": {
            "published": status_stats.get(1, 0),
            "draft": status_stats.get(0, 0),
            # 学生个人库（status=2）单列，避免它悄悄混进"未上架"里
            "personal": status_stats.get(2, 0),
            "deleted": (db.query(func.count(StudyMaterial.material_id))
                        .filter(StudyMaterial.status == -1).scalar() or 0),
        },
    }


@router.post("/admin/batch", summary="批量创建资料(管理员)")
async def admin_batch_create(
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量创建多条资料。body.items 为资料对象数组。

    W2（2026-11-09）与单条创建对齐：
      · **默认未上架**（`status=0`，可在 items 里显式传 1）；
      · 同内容（`content_hash`）**跳过**而不是整批失败 —— 批量场景里"跳过重复"比"整批回滚"有用，
        跳过的会在回包里以 `skipped_duplicates` 列出来（含已存在的 id）。
    """
    _require_admin(current_user)
    items = body.get("items", [])
    if not items:
        raise HTTPException(400, "items 不能为空")
    limit = 100
    if len(items) > limit:
        raise HTTPException(400, f"单次最多 {limit} 条")

    # 2026-11-09（用户点单）：一键上架。`publish=true` 覆盖 items 里各自的 status，
    # 并且**必须走 P5 联动**——否则会出现"资料已上架、卷还是 DRAFT、学生考不了"
    # （#127 那次就是这种：状态写 1 但没同步卷）。
    publish = bool(body.get("publish"))

    created_ids = []
    created_objs = []
    skipped = []
    for item in items:
        data = _validate_material_body(item)
        _finalize_classification(db, data)   # P2.4：批量建卡同样走两级自动分类
        status = 1 if publish else item.get("status", 0)
        if status not in (0, 1):
            raise HTTPException(400, "status 只能是 0（未上架）或 1（已上架）")
        content_hash = _material_content_hash(data)
        if content_hash:
            dup_id = _find_duplicate_material_id(db, content_hash, current_user.user_id)
            if dup_id:
                skipped.append({"title": data.get("title"), "existing_id": dup_id})
                continue
        # 2026-11-09：批量建「试卷资料」时也要能带上关联键与投放位，
        # 否则 P5 联动取不到卷（`paper_code` 为空 → skipped=empty_code），
        # 一键上架就只改了资料状态、卷仍是 DRAFT。两个字段都做显式校验。
        placement = (item.get("placement") or "").strip().lower()
        if placement and placement not in ("exam", "library", "both"):
            raise HTTPException(400, "placement 只能是 exam（仅考试页）/ library（仅资料页）/ both")
        paper_code = (item.get("paper_code") or "").strip() or None
        m = StudyMaterial(**data, status=status, content_hash=(content_hash or None),
                          creator_id=current_user.user_id,
                          paper_code=paper_code, placement=(placement or None))
        db.add(m)
        db.flush()
        created_ids.append(m.material_id)
        created_objs.append(m)

    db.commit()
    _audit(db, current_user, "batch_create", f"created={len(created_ids)}",
           f"批量建资料 {len(created_ids)} 条"
           + ("，一键上架" if publish and created_ids else "")
           + (f"，跳过重复 {len(skipped)} 条" if skipped else ""))
    db.commit()

    # P5 联动：批量上架时把对应可作答卷一并置为 PUBLISHED（不 commit 由这里统一提交）
    syncs: list = []
    if publish and created_objs:
        from ....services import material_paper_sync
        syncs = material_paper_sync.sync_materials(db, created_objs)
        note = material_paper_sync.note_of_many(syncs)
        if note:
            _audit(db, current_user, "status", f"materials:{len(created_objs)}", note)
        db.commit()

    return {"created": len(created_ids), "material_ids": created_ids,
            "skipped_duplicates": skipped,
            "published": len(created_objs) if publish else 0,
            "paper_sync": [s for s in syncs if s.get("changed")]}


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
    """落临时文件并返回 `(路径, 扩展名, sha256)`。

    B3（2026-11-07）新增 sha256：用于**同一文件重复上传**的拦截。
    为什么用文件字节哈希而不是标题/内容：用户重复上传同一个 docx 时，文件名、
    大小、字节都相同，这是最不容易误判的"同一份东西"证据；
    不同文件名的同内容仍由 confirm 阶段的内容哈希去重负责。
    """
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
    return str(UPLOAD_TMP_DIR / tmp_name), ext, _hashlib.sha256(content).hexdigest()


# 重复上传检测只看「已确认入库」的记录。
# 为什么不含 success（已解析未确认）：管理员解析完关掉对话框/换个科目再来一次是正常操作，
# 若把未确认记录也算"导入过"，他会被自己刚才那次上传挡住（实测踩到）。
# 已经建出资料的记录一定是 consumed，所以真重复仍然拦得住。
_IMPORT_DONE_STATUS = ("consumed",)


def _find_same_file_import(db: Session, file_name: str, file_size: int,
                           sha256: str) -> Optional[MaterialImportRecord]:
    """找"同一个文件"此前**已确认入库**的导入记录（同名 + 同大小 + 同 sha256）。

    候选按同名同大小先过滤（通常只有个位数），再逐个比对 parse_result._sha256，
    避免为了一个字段加列迁移（`material_file` 表在 B1 才建，届时改用正式列）。
    """
    candidates = (db.query(MaterialImportRecord)
                  .filter(MaterialImportRecord.file_name == file_name,
                          MaterialImportRecord.file_size == file_size,
                          MaterialImportRecord.parse_status.in_(_IMPORT_DONE_STATUS))
                  .order_by(MaterialImportRecord.import_id.desc())
                  .all())
    for rec in candidates:
        try:
            stored = _json.loads(rec.parse_result or "{}").get("_sha256")
        except (TypeError, ValueError):
            stored = None
        if stored == sha256:
            return rec
    return None


def _stash_fingerprint(db: Session, rec: MaterialImportRecord, sha256: str) -> None:
    """把文件指纹写进 parse_result（JSON 列，零迁移），供下次上传比对。"""
    result = _load_result(rec)
    result["_sha256"] = sha256
    result.setdefault("_tmp", "")
    rec.parse_result = _json.dumps(result, ensure_ascii=False)
    _commit_material_import(db, rec)


def _row_content_hash(m, *, allow_title_fallback: bool = True) -> str:
    """按**已入库行**重算内容哈希（与 `_material_content_hash` 同口径）。

    为什么需要：W2（2026-11-09）之前入库的 98 条资料 `content_hash` 是 NULL，
    而 `_find_duplicate_material_id` 只比这一列 → 老资料永远查不到重。
    回填脚本与"去重兜底"共用本函数，保证两处算法一致（改口径只改这一处）。
    """
    if (getattr(m, "type", "") or "") == "card":
        raw = f"{getattr(m, 'card_front', '') or ''}{getattr(m, 'card_back', '') or ''}"
    else:
        raw = getattr(m, "content", "") or ""
        if not raw and allow_title_fallback:
            # 与 `_material_content_hash` 的兜底一致：正文为空时用 标题+摘要。
            # 回填脚本会传 False，避免"无正文的试卷行"按标题算出一个可被误撞的 hash。
            raw = f"{getattr(m, 'title', '') or ''}{getattr(m, 'summary', '') or ''}"
    raw = (raw or "").strip()
    if not raw:
        return ""
    from ....services.material_sanitizer import content_cleaner
    return content_cleaner.calculate_content_hash(raw)


def _find_duplicate_material_id(db: Session, content_hash: str,
                                user_id: Optional[int] = None) -> Optional[int]:
    """按内容哈希找已入库的同内容资料 id。

    与 `MaterialDeduplicator.check_duplicate` 的差别：这里**直接比 `content_hash` 列**，
    与入库时写入的哈希同一口径（`calculate_content_hash` 会再清洗一次，
    拿原始字符串去算 MD5 有可能对不上）。口径同样排除软删除（status=-1），
    否则"删掉后重新导入"会被自己挡住。

    **兜底（2026-11-12）**：W2 之前入库的老资料该列为 NULL，按列比永远查不到；
    列匹配未命中时，只扫 `content_hash IS NULL` 的未删除行逐行重算（回填后是空集，
    成本≈0；上限 500 行防意外），命中即视为重复。
    """
    q = db.query(StudyMaterial.material_id).filter(
        StudyMaterial.content_hash == content_hash,
        StudyMaterial.status >= 0)
    if user_id is not None:
        # 私有卡（status=2）只在"自己的库"内参与去重，避免泄露别人有同内容
        q = q.filter(or_(StudyMaterial.status != 2,
                         StudyMaterial.creator_id == user_id))
    row = q.order_by(StudyMaterial.material_id.asc()).first()
    if row:
        return row[0]

    if not content_hash:
        return None
    legacy = db.query(StudyMaterial).filter(
        StudyMaterial.content_hash.is_(None),
        StudyMaterial.status >= 0)
    if user_id is not None:
        legacy = legacy.filter(or_(StudyMaterial.status != 2,
                                   StudyMaterial.creator_id == user_id))
    for m in legacy.order_by(StudyMaterial.material_id.asc()).limit(500).all():
        if _row_content_hash(m) == content_hash:
            return m.material_id
    return None


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
                        force: bool = Form(False),
                        current_user: SysUser = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """上传并解析。B3（2026-11-07）新增**同一文件重复上传拦截**。

    判定口径：**文件名 + 字节大小 + sha256 全同**，且该文件此前已解析成功或已入库。
    命中即 409，并在消息里给出旧记录号与入库条数，管理端直接就能判断"是不是我已经导过了"。
    `force=true`（表单字段）可强制再传一份——给"文件没变但我确实要再建一条"的场景留口子。
    """
    _require_admin(current_user)
    tmp_path, ext, sha256 = _save_tmp(file)
    fsize = _os.path.getsize(tmp_path)
    prev = _find_same_file_import(db, file.filename, fsize, sha256)
    if prev and not force:
        try:
            _os.remove(tmp_path)
        except OSError:
            pass
        when = prev.update_time or prev.create_time
        raise HTTPException(
            409,
            f"该文件已于 {when:%Y-%m-%d %H:%M} 导入过（记录 #{prev.import_id}，"
            f"状态 {prev.parse_status}），已拒绝重复上传。"
            f"想找它：去资料管理搜文件名即可；确需再存一份："
            f"用同一接口带 force=true 重传（B2 会做成向导里的勾选项）。")
    rec = MaterialImportRecord(
        file_name=file.filename, file_type=ext.lstrip("."),
        file_size=fsize, parse_status="pending",
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

            def _ocr_job(import_id: int, path: str, workdir: str, sha: str):
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
                                   "_seconds": r["seconds"],
                                   # B3：后台回写会整段覆盖 parse_result，
                                   # 指纹必须带着走，否则异步 OCR 的文件永远查不到重复
                                   "_sha256": sha})
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
                                      str(UPLOAD_TMP_DIR), sha256)
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

    # B3：把文件指纹写进 parse_result，供下次同名同大小上传比对（异步 OCR 分支已自带）
    if rec.parse_status != "processing":
        _stash_fingerprint(db, rec, sha256)

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
        # B3（2026-11-07）根因修复：原来这里只允许 article，却在下面用
        # `classifier.classify()` 的结果覆盖了管理员的显式选择，而分类器把
        # **短文档一律判成 card**（`_classify_document`：len<500 → card），
        # 于是「作为文章」导入的 docx 落在卡片区、翻卡 UI 反而永不触发
        # （实测样本 04_讲义_正常.docx 两次导入 → material 121/122 都是 card）。
        # 现在：显式选择优先（白名单 article / lecture），不传则默认 **lecture（讲义）**。
        mtype = body.get("type") or "lecture"
        if mtype not in ("article", "lecture"):
            raise HTTPException(400, "文档类素材入库类型只能是 article（文章）或 lecture（讲义）")
        _migrate_images(import_id, result, db=db, user_id=current_user.user_id)
        word_count = result.get("word_count", 0)
        # 内容清洗
        raw_content = result.get("html") or ""
        content = content_cleaner.clean_text(raw_content)
        title = (body.get("title") or _os.path.splitext(rec.file_name)[0])[:200]
        summary_text = (body.get("summary") or "")[:500]
        # 去重：同一份内容第二次入库必须被拦（原来只记指标、照样创建重复行）
        content_hash = content_cleaner.calculate_content_hash(content)
        dup_id = _find_duplicate_material_id(db, content_hash,
                                             user_id=current_user.user_id)
        force = bool(body.get("force"))
        if dup_id is not None:
            import_monitor.record_duplicate_match()
            if not force:
                dup = db.query(StudyMaterial).filter(
                    StudyMaterial.material_id == dup_id).first()
                dup_title = (dup.title if dup else "")[:60]
                raise HTTPException(
                    409,
                    f"内容与已存在资料《{dup_title}》(#{dup_id}) 完全相同（内容哈希一致），"
                    f"已拒绝重复入库。确需保留两份：confirm 时带 force=true。")
            try:
                deduplicator.record_duplicate(dup_id, dup_id, "exact", 1.0, db)
            except Exception:      # 去重记录表写失败不应阻断入库
                logger.warning("[materials] record_duplicate failed", exc_info=True)
        m = StudyMaterial(
            subject=subject, type=mtype,
            category=category, badge=badge,
            title=title, summary=summary_text,
            content=content, content_hash=content_hash,
            # 2026-11-12 修：文档分支原来写死 status=0（`publish` 只对 xlsx 卡片生效），
            # 于是"批量上传文章"永远要逐条再点上架；而回包还照传 `published: publish`
            # —— 传了 publish=true 会谎报已上架。现在与卡片分支同口径。
            status=(1 if publish else 0),
            read_time=max(1, word_count // 400),
            creator_id=current_user.user_id)
        db.add(m)
        db.flush()
        created_ids.append(m.material_id)

    db.commit()
    rec.parse_status = "consumed"
    db.commit()
    # B1（2026-11-07）：**原件留档**——先落档，再删临时文件。
    # 只对文档类（docx/pdf）留档：一条资料 ? 一份源文件，语义清晰；
    # xlsx 是一张表转 N 张卡（源表与单卡不是一对一），留档放 B2 的批量导入按"批次"处理。
    if rec.file_type != "xlsx" and created_ids:
        tmp = result.get("_tmp")
        if tmp and _Path(tmp).exists():
            try:
                saved = material_files.save_from_path(
                    db, created_ids[0], tmp, rec.file_name,
                    role="primary", source="import",
                    uploader_id=current_user.user_id)
                # C1：导入的讲义同样抽大纲
                if rec.file_type == "docx":
                    target = db.query(StudyMaterial).filter(
                        StudyMaterial.material_id == created_ids[0]).first()
                    if target is not None:
                        try:
                            doc_outline.apply_to_material(
                                db, target, material_files.resolve_abs_path(saved))
                        except Exception:
                            logger.warning("[materials] 导入大纲抽取失败 import=%s",
                                           import_id, exc_info=True)
                db.commit()
            except (ValueError, OSError) as exc:
                # 留档失败不能回滚"资料已建好"这件事，但必须留痕，便于按记录补档
                logger.warning("[materials] 原件留档失败 import=%s: %s", import_id, exc)
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
            # B3：文档类回传真实落库类型（article/lecture），不再写死 "article"
            "type": ("card" if rec.file_type == "xlsx" else mtype),
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
