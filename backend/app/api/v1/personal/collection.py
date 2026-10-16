"""
收藏模块 API
GET    /api/collection              - 获取收藏列表
POST   /api/collection/favorite     - 添加/取消收藏
DELETE /api/collection/{fav_id}     - 删除收藏
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ....core.database import get_db, commit_with_retry
from ....core.security import get_current_user
from ....models.models import FavoriteQuestion, SysUser

router = APIRouter(prefix="/api/collection", tags=["收藏模块"])
logger = logging.getLogger(__name__)


@router.get("", summary="获取收藏列表")
async def get_collection(
    collection_type: str = Query("all", description="类型: all/news/question"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分页获取用户收藏列表"""
    from ....models.models import QuestionBank, QuestionSubject, NewsArticle

    items = []
    total = 0

    if collection_type in ["all", "question"]:
        q = db.query(FavoriteQuestion).filter(FavoriteQuestion.user_id == current_user.user_id)
        if collection_type == "question":
            total = q.count()
        question_items = q.order_by(desc(FavoriteQuestion.create_time)).offset((page - 1) * page_size).limit(page_size).all()
        for fav in question_items:
            qu = fav.question
            subj = db.query(QuestionSubject).filter(QuestionSubject.subject_id == qu.subject_id).first() if qu else None
            items.append({
                'fav_id': f"q_{fav.fav_id}",
                'type': 'question',
                'id': qu.question_id if qu else None,
                'title': (qu.question_content[:100] if qu and qu.question_content else ''),
                'subject': subj.subject_name if subj else '',
                'create_time': fav.create_time.isoformat() if fav.create_time else None,
            })
        if collection_type == "question":
            total = len(items)

    if collection_type == "all":
        total = db.query(FavoriteQuestion).filter(FavoriteQuestion.user_id == current_user.user_id).count()

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}


@router.post("/favorite", summary="添加/取消收藏")
async def toggle_favorite(
    payload: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加或取消收藏"""
    from ....models.models import QuestionBank, NewsArticle

    fav_type = payload.get('type')  # question / news
    resource_id = payload.get('id')

    if not fav_type or not resource_id:
        raise HTTPException(status_code=400, detail="type 和 id 不能为空")

    if fav_type == "question":
        question = db.query(QuestionBank).filter(QuestionBank.question_id == resource_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="题目不存在")

        existing = db.query(FavoriteQuestion).filter(
            FavoriteQuestion.user_id == current_user.user_id,
            FavoriteQuestion.question_id == resource_id
        ).first()

        if existing:
            db.delete(existing)
            commit_with_retry(db)
            return {"favorited": False, "message": "已取消收藏"}

        fav = FavoriteQuestion(
            user_id=current_user.user_id,
            question_id=resource_id,
            create_time=datetime.now()
        )
        db.add(fav)
        commit_with_retry(db)
        db.refresh(fav)

        # 触发收藏成就
        try:
            from ....services import achievement_service
            achievement_service.check_and_grant(current_user.user_id, "favorite", db)
        except Exception as e:
            logger.warning(f"收藏成就判定失败: {e}")

        return {"favorited": True, "message": "已收藏", "fav_id": f"q_{fav.fav_id}"}

    elif fav_type == "news":
        from ....models.models import NewsFavorite
        news = db.query(NewsArticle).filter(NewsArticle.news_id == resource_id).first()
        if not news:
            raise HTTPException(status_code=404, detail="新闻不存在")

        existing = db.query(NewsFavorite).filter(
            NewsFavorite.user_id == current_user.user_id,
            NewsFavorite.news_id == resource_id
        ).first()

        if existing:
            db.delete(existing)
            commit_with_retry(db)
            return {"favorited": False, "message": "已取消收藏"}

        fav = NewsFavorite(
            user_id=current_user.user_id,
            news_id=resource_id,
            create_time=datetime.now()
        )
        db.add(fav)
        commit_with_retry(db)
        db.refresh(fav)
        return {"favorited": True, "message": "已收藏", "fav_id": f"n_{fav.fav_id}"}

    else:
        raise HTTPException(status_code=400, detail="不支持的收藏类型，仅支持 question 和 news")


@router.delete("/{fav_id}", summary="删除收藏")
async def delete_favorite(
    fav_id: str,  # 格式: q_123 或 n_456
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除收藏记录"""
    parts = fav_id.split("_")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="无效的收藏ID格式")

    fav_type, pk_id = parts[0], int(parts[1])

    if fav_type == "q":
        from ....models.models import FavoriteQuestion
        fav = db.query(FavoriteQuestion).filter(
            FavoriteQuestion.fav_id == pk_id,
            FavoriteQuestion.user_id == current_user.user_id
        ).first()
    elif fav_type == "n":
        from ....models.models import NewsFavorite
        fav = db.query(NewsFavorite).filter(
            NewsFavorite.fav_id == pk_id,
            NewsFavorite.user_id == current_user.user_id
        ).first()
    else:
        raise HTTPException(status_code=400, detail="不支持的收藏类型")

    if not fav:
        raise HTTPException(status_code=404, detail="收藏记录不存在")

    db.delete(fav)
    commit_with_retry(db)
    return {"message": "已删除"}


# === 聚合查询接口（供前端收藏聚合页使用）===

def _get_subcategory(question) -> str:
    """根据科目ID返回对应的子科目名称"""
    if not question:
        return ''
    if question.subject_id == 1:
        return question.xingce_subcategory if question.xingce_subcategory and question.xingce_subcategory != '无' else ''
    elif question.subject_id == 2:
        return question.shenlun_subcategory if question.shenlun_subcategory and question.shenlun_subcategory != '无' else ''
    elif question.subject_id == 3:
        return question.gongzhuan_subcategory if question.gongzhuan_subcategory and question.gongzhuan_subcategory != '无' else ''
    return ''


def _read_obsidian_quote_by_filename(filename: str) -> Optional[dict]:
    """根据文件名读取 Obsidian 金句"""
    import os
    from ..community.quotes import OBSIDIAN_QUOTE_DIR, _parse_obsidian_quote

    if not filename or not os.path.exists(OBSIDIAN_QUOTE_DIR):
        return None

    # 递归搜索整个目录树，匹配文件名（basename）
    fpath = None
    for root, dirs, files in os.walk(OBSIDIAN_QUOTE_DIR):
        if filename in files:
            fpath = os.path.join(root, filename)
            break
    if not fpath:
        return None

    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        return _parse_obsidian_quote(content)
    except Exception as e:
        logger.warning(f"Failed to read Obsidian quote {filename}: {e}")
        return None


@router.get("/news-favorites", summary="金句/新闻收藏列表")
async def get_news_favorites(
    type: str = Query("all", description="all/quote/news"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """合并查询金句收藏和新闻收藏"""
    from ....models.models import QuoteFavorite, NewsFavorite, EssayQuote, NewsArticle

    all_items = []

    # 金句收藏（数据库金句）
    if type in ["all", "quote"]:
        quote_favs = db.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == current_user.user_id,
            QuoteFavorite.quote_id.isnot(None)  # 只查数据库金句
        ).order_by(desc(QuoteFavorite.create_time)).all()

        for fav in quote_favs:
            quote = db.query(EssayQuote).filter(
                EssayQuote.quote_id == fav.quote_id,
                EssayQuote.status == 1
            ).first()
            if quote:
                all_items.append({
                    'fav_type': 'quote',
                    'fav_id': fav.fav_id,
                    'quote_id': quote.quote_id,
                    'content': quote.content,
                    'source': quote.source or '',
                    'category': quote.category or '',
                    'author': quote.author or '',
                    'create_time': fav.create_time.isoformat() if fav.create_time else '',
                    'source_type': 'database',
                })

    # Obsidian 金句收藏
    if type in ["all", "quote"]:
        obsidian_favs = db.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == current_user.user_id,
            QuoteFavorite.obsidian_source.isnot(None)  # 只查 Obsidian 金句
        ).order_by(desc(QuoteFavorite.create_time)).all()

        for fav in obsidian_favs:
            # 从 Obsidian 知识库读取金句内容
            obsidian_quote = _read_obsidian_quote_by_filename(fav.obsidian_source)
            if obsidian_quote:
                all_items.append({
                    'fav_type': 'quote',
                    'fav_id': fav.fav_id,
                    'quote_id': 0,
                    'obsidian_id': f"obsidian_{fav.obsidian_source}",
                    'content': obsidian_quote['content'],
                    'source': obsidian_quote['source'],
                    'category': ', '.join(obsidian_quote['topics'][:2]) if obsidian_quote.get('topics') else '',
                    'author': obsidian_quote['author'],
                    'create_time': fav.create_time.isoformat() if fav.create_time else '',
                    'source_type': 'obsidian',
                    'obsidian_source': fav.obsidian_source,
                })

    # 新闻收藏
    if type in ["all", "news"]:
        news_favs = db.query(NewsFavorite).filter(
            NewsFavorite.user_id == current_user.user_id
        ).order_by(desc(NewsFavorite.create_time)).all()

        for fav in news_favs:
            news = db.query(NewsArticle).filter(NewsArticle.news_id == fav.news_id).first()
            if news:
                all_items.append({
                    'fav_type': 'news',
                    'fav_id': fav.fav_id,
                    'news_id': news.news_id,
                    'content': news.title,
                    'title': news.title,
                    'source': news.source or '',
                    'category': news.category or '',
                    'summary': news.summary or '',
                    'create_time': fav.create_time.isoformat() if fav.create_time else '',
                })

    # 按收藏时间倒序
    all_items.sort(key=lambda x: x.get('create_time', ''), reverse=True)

    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    items = all_items[start:end]

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}


@router.get("/question-favorites", summary="典题收藏列表（含完整题目信息）")
async def get_question_favorites(
    subject_id: Optional[int] = Query(None, description="科目ID筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询用户收藏的题目列表，含完整题目信息用于弹窗展示"""
    from ....models.models import QuestionBank, QuestionSubject

    query = db.query(FavoriteQuestion).filter(
        FavoriteQuestion.user_id == current_user.user_id
    )

    if subject_id:
        query = query.join(QuestionBank).filter(QuestionBank.subject_id == subject_id)

    total = query.count()
    favs = query.order_by(desc(FavoriteQuestion.create_time))\
        .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for fav in favs:
        q = fav.question
        if not q:
            continue
        subj = db.query(QuestionSubject).filter(
            QuestionSubject.subject_id == q.subject_id
        ).first()

        items.append({
            'fav_id': fav.fav_id,
            'question_id': q.question_id,
            'question_content': q.question_content or '',
            'options': q.options or [],
            'answer': q.answer or '',
            'answer_analysis': q.answer_analysis or '',
            'difficulty': q.difficulty or 3,
            'accuracy_rate': float(q.accuracy_rate or 0),
            'subject_id': q.subject_id,
            'subject_name': subj.subject_name if subj else '',
            'subcategory': _get_subcategory(q),
            'create_time': fav.create_time.isoformat() if fav.create_time else '',
        })

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}


@router.get("/stats", summary="收藏统计")
async def get_collection_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回当前用户的收藏数量统计"""
    from ....models.models import QuoteFavorite, NewsFavorite

    question_count = db.query(FavoriteQuestion).filter(
        FavoriteQuestion.user_id == current_user.user_id
    ).count()
    news_count = db.query(NewsFavorite).filter(
        NewsFavorite.user_id == current_user.user_id
    ).count()
    quote_count = db.query(QuoteFavorite).filter(
        QuoteFavorite.user_id == current_user.user_id
    ).count()

    return {
        'question_favorites': question_count,
        'news_favorites': news_count,
        'quote_favorites': quote_count,
        'news_quote_total': news_count + quote_count,
        'total': question_count + news_count + quote_count
    }