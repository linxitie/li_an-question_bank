"""
新闻资讯 API
GET  /api/news             — 获取最新新闻列表
POST /api/news/{id}/favorite — 收藏/取消收藏
GET  /api/news/favorites   — 获取收藏列表
POST /api/news/{id}/note   — 保存笔记
GET  /api/news/{id}/notes  — 获取笔记列表
DELETE /api/news/notes/{id}  — 删除笔记
"""
import logging
from typing import List, Optional
from datetime import datetime, date as date_cls

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, get_optional_user
from ....core.trigger_types import TRIGGER_NEWS_READ
from ....models.models import (
    NewsArticle, NewsFavorite, NewsNote, NewsImage, NewsRead, SysUser,
)
from ....services.event_consumer import record_user_action
from ....services import news_search_service

router = APIRouter(prefix="/api/news", tags=["新闻资讯"])
logger = logging.getLogger(__name__)


def _read_ids(db: Session, user_id, news_ids) -> set:
    """批量取该用户已读的新闻 ID，避免逐条查询。"""
    if not news_ids:
        return set()
    rows = db.query(NewsRead.news_id).filter(
        NewsRead.user_id == user_id,
        NewsRead.news_id.in_(news_ids)
    ).all()
    return {row[0] for row in rows}


def _mark_read(db: Session, user_id: int, news_id: int, *, commit: bool = True) -> bool:
    """记录一次阅读，返回是否为首次阅读（幂等）。

    (user_id, news_id) 唯一约束兜底并发重复写入：唯一冲突说明另一请求
    已记录过，本次不视为首次阅读。commit=False 时只 flush，由调用方把
    阅读记录与成就事件放在同一事务里提交。
    """
    exists = db.query(NewsRead).filter(
        NewsRead.user_id == user_id,
        NewsRead.news_id == news_id
    ).first()
    if exists:
        return False
    db.add(NewsRead(user_id=user_id, news_id=news_id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    if commit:
        db.commit()
    return True


@router.get("", summary="获取新闻列表")
async def get_news(
    source: Optional[str] = Query(None, description="来源: cpd / people"),
    category: Optional[str] = Query(None, description="分类: 理论 / 党史 / 公安报"),
    q: Optional[str] = Query(None, description="标题/摘要/正文模糊搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    limit: Optional[int] = Query(None, ge=1, le=50, description="兼容旧参数：等价 page_size"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取新闻列表，支持来源/分类筛选、模糊搜索与分页。"""
    query = db.query(NewsArticle).filter(NewsArticle.status == 1)

    if source:
        query = query.filter(NewsArticle.source == source)
    if category:
        query = query.filter(
            or_(NewsArticle.category == category, NewsArticle.category_code == category)
        )
    query = news_search_service.apply_keyword(query, db, q)

    size = limit or page_size
    total = query.count()
    articles = (
        query.order_by(NewsArticle.create_time.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    # 批量预取图片与收藏状态，消除 N+1 查询
    news_ids = [a.news_id for a in articles]
    images_by_news = {}
    if news_ids:
        all_images = db.query(NewsImage).filter(
            NewsImage.news_id.in_(news_ids)
        ).order_by(NewsImage.image_order).all()
        for img in all_images:
            images_by_news.setdefault(img.news_id, []).append(img)

    favorite_ids = set()
    if news_ids and current_user:
        favs = db.query(NewsFavorite.news_id).filter(
            NewsFavorite.user_id == current_user.user_id,
            NewsFavorite.news_id.in_(news_ids)
        ).all()
        favorite_ids = {f[0] for f in favs}

    read_ids = _read_ids(db, current_user.user_id, news_ids) if current_user else set()

    return {
        "total": total,
        "page": page,
        "page_size": size,
        "has_more": page * size < total,
        "items": [
            {
                "id": a.news_id,
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "category": a.category,
                "publish_date": a.publish_date.isoformat() if a.publish_date else None,
                "summary": a.summary,
                "content": a.content or "",
                "images": [{"url": '/' + img.image_path.lstrip('/'), "order": img.image_order}
                           for img in images_by_news.get(a.news_id, [])],
                "is_favorited": a.news_id in favorite_ids,
                "is_read": a.news_id in read_ids,
            }
            for a in articles
        ]
    }


@router.get("/categories", summary="新闻分类字典")
async def get_news_categories(
    db: Session = Depends(get_db),
):
    """返回当前启用新闻的分类及数量，供前端筛选栏使用。"""
    return news_search_service.category_counts(db)


@router.get("/digest", summary="新闻日报")
async def news_digest(
    day: Optional[str] = Query(None, description="YYYY-MM-DD；缺省取最近发布日"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """按日聚合已发布新闻，供日报/时间线页面使用。"""
    target = None
    if day:
        try:
            target = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
    base = db.query(NewsArticle).filter(
        NewsArticle.status == 1,
        NewsArticle.review_status == "published",
    )
    if target is None:
        latest = base.with_entities(func.max(NewsArticle.publish_date)).scalar()
        target = latest.date() if latest else date_cls.today()
    daily = base.filter(func.date(NewsArticle.publish_date) == target.isoformat())
    total = daily.count()
    rows = (
        daily.with_entities(
            NewsArticle.category,
            NewsArticle.category_code,
            func.count(NewsArticle.news_id),
        )
        .group_by(NewsArticle.category, NewsArticle.category_code)
        .all()
    )
    items = (
        daily.order_by(NewsArticle.news_id.desc())
        .limit(limit)
        .all()
    )
    return {
        "date": target.isoformat(),
        "total": total,
        "categories": [
            {"category": category or "未分类", "category_code": code, "count": count}
            for category, code, count in rows
        ],
        "items": [
            {
                "news_id": item.news_id,
                "title": item.title,
                "source": item.source,
                "category": item.category,
                "url": item.url,
                "ai_summary": item.ai_summary or "",
            }
            for item in items
        ],
    }


@router.get("/timeline", summary="新闻时间线")
async def news_timeline(
    category: Optional[str] = Query(None, description="分类 code/名称"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """按发布日期聚合已发布新闻，供时间线页面使用。"""
    query = db.query(NewsArticle).filter(
        NewsArticle.status == 1,
        NewsArticle.review_status == "published",
    )
    if category:
        query = query.filter(
            or_(NewsArticle.category == category, NewsArticle.category_code == category)
        )
    articles = (
        query.order_by(NewsArticle.publish_date.desc(), NewsArticle.news_id.desc())
        .limit(limit)
        .all()
    )
    groups: dict[str, list] = {}
    for article in articles:
        key = article.publish_date.date().isoformat() if article.publish_date else "未分期"
        groups.setdefault(key, []).append({
            "news_id": article.news_id,
            "title": article.title,
            "source": article.source,
            "category": article.category,
            "url": article.url,
            "ai_summary": article.ai_summary or "",
        })
    return {
        "total": len(articles),
        "items": [{"date": key, "items": value} for key, value in groups.items()],
    }


@router.get("/today", summary="获取今日新闻")
async def get_today_news(
    limit: int = Query(20, ge=1, le=50),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取今日所有来源的新闻"""
    today = datetime.now().date()
    articles = db.query(NewsArticle).filter(
        NewsArticle.status == 1,
        NewsArticle.create_time >= today
    ).order_by(NewsArticle.create_time.desc()).limit(limit).all()

    # 批量预取图片与收藏状态，消除 N+1 查询
    news_ids = [a.news_id for a in articles]
    images_by_news = {}
    if news_ids:
        all_images = db.query(NewsImage).filter(
            NewsImage.news_id.in_(news_ids)
        ).order_by(NewsImage.image_order).all()
        for img in all_images:
            images_by_news.setdefault(img.news_id, []).append(img)

    favorite_ids = set()
    if news_ids and current_user:
        favs = db.query(NewsFavorite.news_id).filter(
            NewsFavorite.user_id == current_user.user_id,
            NewsFavorite.news_id.in_(news_ids)
        ).all()
        favorite_ids = {f[0] for f in favs}

    read_ids = _read_ids(db, current_user.user_id, news_ids) if current_user else set()

    return {
        "total": len(articles),
        "date": today.isoformat(),
        "items": [
            {
                "id": a.news_id,
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "category": a.category,
                "summary": a.summary,
                "content": a.content or "",
                "images": [{"url": '/' + img.image_path.lstrip('/'), "order": img.image_order}
                           for img in images_by_news.get(a.news_id, [])],
                "is_favorited": a.news_id in favorite_ids,
                "is_read": a.news_id in read_ids,
            }
            for a in articles
        ]
    }


# ════════════════════════════════════════════════════════════
#  收藏功能
# ════════════════════════════════════════════════════════════

@router.post("/{news_id}/favorite", summary="收藏/取消收藏新闻")
async def toggle_favorite(
    news_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle favorite: add if not exists, remove if exists"""
    existing = db.query(NewsFavorite).filter(
        NewsFavorite.user_id == current_user.user_id,
        NewsFavorite.news_id == news_id
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False, "message": "已取消收藏"}
    db.add(NewsFavorite(user_id=current_user.user_id, news_id=news_id))
    db.commit()
    return {"favorited": True, "message": "收藏成功"}


@router.get("/favorites", summary="获取收藏列表")
async def get_favorites(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100)
):
    """获取当前用户的新闻收藏列表"""
    rows = db.query(NewsFavorite, NewsArticle).join(
        NewsArticle, NewsFavorite.news_id == NewsArticle.news_id
    ).filter(
        NewsFavorite.user_id == current_user.user_id
    ).order_by(NewsFavorite.create_time.desc()).limit(limit).all()

    items = []
    for fav, article in rows:
        items.append({
            "fav_id": fav.fav_id,
            "fav_time": fav.create_time.isoformat() if fav.create_time else None,
            "id": article.news_id,
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "category": article.category,
            "publish_date": article.publish_date.isoformat() if article.publish_date else None,
            "summary": article.summary,
            "content": article.content or ""
        })

    return {"total": len(items), "items": items}


@router.get("/{news_id}", summary="获取新闻详情")
async def get_news_detail(
    news_id: int,
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取单条新闻完整内容，供收藏弹窗展示。

    详情接口即「阅读」动作：登录用户首次打开某篇新闻时记录已读并发布
    一次 E7 ``news.read``；同篇再次打开只返回内容、不重复发事件。
    列表类只读接口（/ 与 /today）不发事件。
    """
    article = db.query(NewsArticle).filter(
        NewsArticle.news_id == news_id,
        NewsArticle.status == 1
    ).first()
    if not article:
        raise HTTPException(status_code=404, detail="新闻不存在")

    images = db.query(NewsImage).filter(
        NewsImage.news_id == news_id
    ).order_by(NewsImage.image_order).all()

    is_favorited = False
    is_read = False
    if current_user:
        is_favorited = db.query(NewsFavorite).filter(
            NewsFavorite.user_id == current_user.user_id,
            NewsFavorite.news_id == news_id
        ).first() is not None

        try:
            first_read = _mark_read(db, current_user.user_id, news_id, commit=False)
            if first_read:
                # F2b：阅读记录与阅读成就事件同一事务提交。
                await record_user_action(
                    db, current_user.user_id, TRIGGER_NEWS_READ
                )
            db.commit()
        except Exception as e:  # noqa: BLE001 — 阅读记录失败不阻断正文返回
            db.rollback()
            logger.warning(f"记录新闻已读失败 news={news_id}: {e}")
            first_read = False
        is_read = True

    return {
        "id": article.news_id,
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "category": article.category,
        "publish_date": article.publish_date.isoformat() if article.publish_date else None,
        "summary": article.summary,
        "content": article.content or "",
        "images": [{"url": '/' + img.image_path.lstrip('/'), "order": img.image_order} for img in images],
        "is_favorited": is_favorited,
        "is_read": is_read,
    }


# ════════════════════════════════════════════════════════════
#  笔记功能（划线+想法）
# ════════════════════════════════════════════════════════════

@router.post("/{news_id}/note", summary="保存新闻笔记")
async def save_note(
    news_id: int,
    note_data: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """保存划线笔记：可同时记录划线原文和想法"""
    # 验证新闻存在
    news = db.query(NewsArticle).filter(NewsArticle.news_id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")

    note = NewsNote(
        user_id=current_user.user_id,
        news_id=news_id,
        note_text=note_data.get("note_text", ""),
        quote_text=note_data.get("quote_text"),
        quote_position=note_data.get("quote_position"),
        color=note_data.get("color", "#FFD700"),
        line_style=note_data.get("line_style", "wavy")
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"note_id": note.note_id, "message": "笔记已保存"}


@router.get("/{news_id}/notes", summary="获取新闻笔记列表")
async def get_notes(
    news_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户在某条新闻下的所有笔记"""
    notes = db.query(NewsNote).filter(
        NewsNote.user_id == current_user.user_id,
        NewsNote.news_id == news_id
    ).order_by(NewsNote.quote_position).all()

    return {
        "total": len(notes),
        "items": [
            {
                "note_id": n.note_id,
                "note_text": n.note_text,
                "quote_text": n.quote_text,
                "quote_position": n.quote_position,
                "color": n.color,
                "line_style": n.line_style or 'wavy',
                "create_time": n.create_time.isoformat() if n.create_time else None,
                "update_time": n.update_time.isoformat() if n.update_time else None
            }
            for n in notes
        ]
    }


@router.delete("/notes/{note_id}", summary="删除笔记")
async def delete_note(
    note_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除当前用户的某条笔记"""
    note = db.query(NewsNote).filter(
        NewsNote.note_id == note_id,
        NewsNote.user_id == current_user.user_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在或无权操作")
    db.delete(note)
    db.commit()
    return {"message": "笔记已删除"}
