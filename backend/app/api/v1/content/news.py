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
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, get_optional_user
from ....models.models import NewsArticle, NewsFavorite, NewsNote, NewsImage, SysUser

router = APIRouter(prefix="/api/news", tags=["新闻资讯"])
logger = logging.getLogger(__name__)


@router.get("", summary="获取新闻列表")
async def get_news(
    source: Optional[str] = Query(None, description="来源: cpd / people"),
    category: Optional[str] = Query(None, description="分类: 理论 / 党史 / 公安报"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取最新新闻列表，支持按来源和分类筛选"""
    query = db.query(NewsArticle).filter(NewsArticle.status == 1)

    if source:
        query = query.filter(NewsArticle.source == source)
    if category:
        query = query.filter(NewsArticle.category == category)

    articles = query.order_by(NewsArticle.create_time.desc()).limit(limit).all()

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

    return {
        "total": len(articles),
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
            }
            for a in articles
        ]
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
    """获取单条新闻完整内容，供收藏弹窗展示"""
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
    if current_user:
        is_favorited = db.query(NewsFavorite).filter(
            NewsFavorite.user_id == current_user.user_id,
            NewsFavorite.news_id == news_id
        ).first() is not None

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
