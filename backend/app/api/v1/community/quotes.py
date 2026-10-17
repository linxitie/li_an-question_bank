"""
申论金句 API
GET    /api/quotes             - 金句列表（分页+分类筛选）
GET    /api/quotes/random      - 随机获取一条金句
GET    /api/quote/daily        - 每日金句（从 Obsidian 知识库读取）
POST   /api/quotes             - 创建金句（管理员）
POST   /api/quotes/{id}/favorite - 切换金句收藏
GET    /api/quotes/favorites   - 我的金句收藏列表
"""
import logging
import os
import re
import hashlib
from ....services.event_consumer import record_user_action
from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ....core.database import get_db
from ....core.security import get_current_user, get_optional_user
from ....models.models import EssayQuote, QuoteFavorite, SysUser

router = APIRouter(prefix="/api/quotes", tags=["申论金句"])
logger = logging.getLogger(__name__)

# Obsidian 知识库配置
# 优先使用环境变量；如果环境变量指向的路径下没有 01-金句素材库 子目录，
# 则自动回退到常见的默认路径
_OB_ENV_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "")
_DEFAULT_VAULT = r"D:\Obsidian仓库\每日金句知识库"

def _resolve_quote_dir() -> str:
    """解析 Obsidian 金句目录，自动检测路径是否正确"""
    candidates = []
    if _OB_ENV_PATH:
        candidates.append(os.path.join(_OB_ENV_PATH, "01-金句素材库"))
    candidates.append(os.path.join(_DEFAULT_VAULT, "01-金句素材库"))
    for path in candidates:
        if os.path.isdir(path):
            return path
    # 都不存在则返回默认值（让后续报错信息更清晰）
    return candidates[-1] if candidates else os.path.join(_DEFAULT_VAULT, "01-金句素材库")

OBSIDIAN_QUOTE_DIR = _resolve_quote_dir()

# 过滤规则
CORRUPTION_PATTERN = re.compile(r'\?{3,}')
PLACEHOLDER_PATTERN = re.compile(
    r'(这句话是|引用的内容|你的引用|此处插入|金句内容|示例|测试|'
    r'这是某个|这是一段|被引用的内容|placeholder|test|example|content)',
    re.IGNORECASE
)
QUOTE_FIELD_PATTERN = re.compile(r'^quote:\s*"(.+?)"\s*$', re.MULTILINE)
STATUS_PATTERN = re.compile(r'^status:\s*(.+)$', re.MULTILINE)
SOURCE_PATTERN = re.compile(r'^source:\s*"?(.+?)"?\s*$', re.MULTILINE)
AUTHOR_PATTERN = re.compile(r'^author:\s*"?(.+?)"?\s*$', re.MULTILINE)
TOPICS_PATTERN = re.compile(r'^applicable_topics:\s*\n((?:\s*-\s*.+\n?)+)', re.MULTILINE)


def _parse_obsidian_quote(content: str) -> Optional[dict]:
    """解析 Obsidian 金句文件的 frontmatter"""
    quote_match = QUOTE_FIELD_PATTERN.search(content)
    if not quote_match:
        return None
    
    quote = quote_match.group(1).strip()
    
    # 过滤乱码
    if CORRUPTION_PATTERN.search(quote):
        return None
    
    # 过滤模板占位符
    if PLACEHOLDER_PATTERN.search(quote):
        return None
    
    # 过滤过短的金句
    if len(quote) < 5:
        return None
    
    # 检查是否已审核
    status_match = STATUS_PATTERN.search(content)
    if status_match:
        status = status_match.group(1).strip()
        if status != "已审核":
            return None
    
    source_match = SOURCE_PATTERN.search(content)
    source = source_match.group(1).strip() if source_match else ""
    
    author_match = AUTHOR_PATTERN.search(content)
    author = author_match.group(1).strip() if author_match else ""
    
    topics_match = TOPICS_PATTERN.search(content)
    topics = []
    if topics_match:
        topics = [
            line.strip().lstrip('- ').strip()
            for line in topics_match.group(1).split('\n')
            if line.strip() and line.strip().startswith('-')
        ]
    
    return {
        "content": quote,
        "source": source,
        "author": author,
        "topics": topics,
    }


def _read_obsidian_quotes() -> list[dict]:
    """从 Obsidian 知识库读取所有已审核的有效金句"""
    quotes = []
    
    if not os.path.exists(OBSIDIAN_QUOTE_DIR):
        logger.warning(f"Obsidian quote dir not found: {OBSIDIAN_QUOTE_DIR}")
        return quotes
    
    try:
        for root, dirs, files in os.walk(OBSIDIAN_QUOTE_DIR):
            for fname in files:
                if not fname.endswith('.md') or fname.startswith('_'):
                    continue
                
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    parsed = _parse_obsidian_quote(content)
                    if parsed:
                        # 用文件名的哈希作为唯一 ID
                        file_hash = hashlib.md5(fname.encode()).hexdigest()[:12]
                        parsed['id'] = f"obsidian_{file_hash}"
                        parsed['filename'] = fname
                        quotes.append(parsed)
                except Exception as e:
                    logger.warning(f"Failed to read quote file {fname}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Failed to list Obsidian quote dir: {e}")
    
    return quotes


def get_random_int(max_value: int) -> int:
    """按日期种子返回 0 到 max_value-1 之间的整数，确保同一天结果稳定"""
    today = date.today()
    return (today.year * 366 + today.month * 31 + today.day) % max_value


def _select_daily_quote(quotes: list[dict]) -> Optional[dict]:
    """按日期轮转选取每日金句（去重）"""
    if not quotes:
        return None
    
    # 用日期作为种子，确保同一天返回相同金句
    day_index = get_random_int(len(quotes))
    return quotes[day_index]


@router.get("/quote/daily", summary="每日金句（从 Obsidian 知识库读取）")
async def get_daily_quote(
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    获取每日金句：
    1. 优先从 Obsidian 知识库读取已审核的有效金句
    2. 按日期轮转选取（同一天返回相同金句）
    3. 如果 Obsidian 不可用，回退到 SQLite 数据库
    """
    # 1. 尝试从 Obsidian 读取
    obsidian_quotes = _read_obsidian_quotes()
    if obsidian_quotes:
        selected = _select_daily_quote(obsidian_quotes)
        if selected:
            # 使用文件名作为稳定 ID
            obsidian_id = f"obsidian_{selected['filename']}"

            # 检查收藏状态（按 obsidian_source 查询）
            favorited = False
            if current_user:
                fav = db.query(QuoteFavorite).filter(
                    QuoteFavorite.user_id == current_user.user_id,
                    QuoteFavorite.obsidian_source == selected['filename']
                ).first()
                favorited = fav is not None

            return {
                'quote_id': 0,  # Obsidian 金句没有数据库 ID，保持兼容
                'obsidian_id': obsidian_id,  # 稳定的 Obsidian 金句 ID
                'content': selected['content'],
                'source': selected['source'],
                'category': ', '.join(selected['topics'][:2]) if selected['topics'] else '',
                'author': selected['author'],
                'favorited': favorited,
                'source_type': 'obsidian',  # 标记来源
                'obsidian_source': selected['filename'],  # 文件名标识
            }
    
    # 2. 回退到 SQLite 数据库
    quote = db.query(EssayQuote).filter(EssayQuote.status == 1)\
        .order_by(func.random()).first()
    
    if not quote:
        return {
            'quote_id': 0,
            'content': '暂无金句',
            'source': '',
            'category': '',
            'author': '',
            'favorited': False,
            'source_type': 'database',
        }
    
    favorited = False
    if current_user:
        favorited = db.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == current_user.user_id,
            QuoteFavorite.quote_id == quote.quote_id
        ).first() is not None
    
    return {
        'quote_id': quote.quote_id,
        'content': quote.content,
        'source': quote.source or '',
        'category': quote.category or '',
        'author': quote.author or '',
        'favorited': favorited,
        'source_type': 'database',
    }


@router.get("", summary="金句列表")
async def get_quotes(
    category: Optional[str] = Query(None, description="分类筛选: 哲理/治国/民生/法治/品德"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分页获取金句列表"""
    query = db.query(EssayQuote).filter(EssayQuote.status == 1)
    if category:
        query = query.filter(EssayQuote.category == category)

    total = query.count()
    items = query.order_by(desc(EssayQuote.create_time))\
        .offset((page - 1) * page_size).limit(page_size).all()

    # 标记当前用户是否已收藏
    favorited_ids = set()
    if items:
        favs = db.query(QuoteFavorite.quote_id).filter(
            QuoteFavorite.user_id == current_user.user_id,
            QuoteFavorite.quote_id.in_([q.quote_id for q in items])
        ).all()
        favorited_ids = {f[0] for f in favs}

    result = []
    for q in items:
        result.append({
            'quote_id': q.quote_id,
            'content': q.content,
            'source': q.source or '',
            'category': q.category or '',
            'author': q.author or '',
            'create_time': q.create_time.isoformat() if q.create_time else '',
            'favorited': q.quote_id in favorited_ids,
        })

    return {'total': total, 'page': page, 'page_size': page_size, 'items': result}


import random as _random


def _format_obsidian_quote(selected: dict, favorited: bool = False) -> dict:
    """将 Obsidian 金句格式化为统一的 API 返回格式"""
    return {
        'quote_id': 0,
        'obsidian_id': f"obsidian_{selected['filename']}",
        'content': selected['content'],
        'source': selected.get('source', ''),
        'category': ', '.join(selected['topics'][:2]) if selected['topics'] else '',
        'author': selected['author'],
        'favorited': favorited,
        'source_type': 'obsidian',
        'obsidian_source': selected['filename'],
    }


def _format_db_quote(quote, favorited: bool = False) -> dict:
    """将数据库金句格式化为统一的 API 返回格式"""
    return {
        'quote_id': quote.quote_id,
        'content': quote.content,
        'source': quote.source or '',
        'category': quote.category or '',
        'author': quote.author or '',
        'favorited': favorited,
        'source_type': 'database',
    }


def _get_empty_quote() -> dict:
    return {
        'quote_id': 0,
        'content': '暂无金句',
        'source': '',
        'category': '',
        'author': '',
        'favorited': False,
        'source_type': 'database',
    }


@router.get("/random", summary="随机获取一条金句")
async def get_random_quote(
    exclude: Optional[str] = Query(None, description="排除的当前金句内容，保证「换一句」一定换掉"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """随机获取一条金句：优先从 Obsidian 读取，回退到数据库

    exclude 用于首页「换一句」交互：传入当前展示的句子，
    从候选池中剔除它，避免随机到同一句导致「点了没反应」。
    仅剩一条候选时不剔除，避免无可用结果。
    """
    import random as _rnd

    # 1. 尝试从 Obsidian 随机读取
    obsidian_quotes = _read_obsidian_quotes()
    if obsidian_quotes:
        pool = [q for q in obsidian_quotes
                if q.get('content', '').strip() != (exclude or '').strip()]
        if not pool:
            pool = obsidian_quotes
        selected = _rnd.choice(pool)
        favorited = False
        if current_user:
            fav = db.query(QuoteFavorite).filter(
                QuoteFavorite.user_id == current_user.user_id,
                QuoteFavorite.obsidian_source == selected['filename']
            ).first()
            favorited = fav is not None
        return _format_obsidian_quote(selected, favorited)

    # 2. 回退到数据库
    query = db.query(EssayQuote).filter(EssayQuote.status == 1)
    if exclude:
        query = query.filter(EssayQuote.content != exclude)
    quote = query.order_by(func.random()).first()

    if not quote:
        return _get_empty_quote()

    favorited = False
    if current_user:
        favorited = db.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == current_user.user_id,
            QuoteFavorite.quote_id == quote.quote_id
        ).first() is not None

    return _format_db_quote(quote, favorited)


@router.post("", summary="创建金句（管理员）")
async def create_quote(
    payload: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建金句（仅管理员）"""
    if current_user.role_level < 2:
        raise HTTPException(status_code=403, detail="仅管理员可创建金句")

    content = payload.get('content', '').strip()
    if not content:
        raise HTTPException(status_code=400, detail="金句内容不能为空")

    quote = EssayQuote(
        content=content,
        source=payload.get('source', ''),
        category=payload.get('category', ''),
        author=payload.get('author', ''),
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)

    return {
        'quote_id': quote.quote_id,
        'content': quote.content,
        'source': quote.source,
        'category': quote.category,
        'author': quote.author,
        'message': '金句创建成功'
    }


@router.post("/{quote_id}/favorite", summary="切换金句收藏")
async def toggle_quote_favorite(
    quote_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加或取消金句收藏"""
    quote = db.query(EssayQuote).filter(EssayQuote.quote_id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="金句不存在")

    existing = db.query(QuoteFavorite).filter(
        QuoteFavorite.user_id == current_user.user_id,
        QuoteFavorite.quote_id == quote_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False, "message": "已取消收藏"}

    fav = QuoteFavorite(
        user_id=current_user.user_id,
        quote_id=quote_id,
    )
    db.add(fav)
    db.commit()

    # 触发金句收藏成就
    try:
        await record_user_action(db, current_user.user_id, "quote_favorite")
    except Exception as e:
        logger.warning(f"金句收藏成就判定失败: {e}")

    return {"favorited": True, "message": "已收藏"}


@router.post("/obsidian/{obsidian_source}/favorite", summary="切换 Obsidian 金句收藏")
async def toggle_obsidian_quote_favorite(
    obsidian_source: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加或取消 Obsidian 金句收藏（以文件名作为稳定 ID）"""
    # 校验参数格式（只允许文件名，不允许路径分隔符）
    if not re.match(r'^[\w\-\.]+\.md$', obsidian_source):
        raise HTTPException(status_code=400, detail="无效的金句来源标识")

    # 检查是否已收藏
    existing = db.query(QuoteFavorite).filter(
        QuoteFavorite.user_id == current_user.user_id,
        QuoteFavorite.obsidian_source == obsidian_source
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False, "message": "已取消收藏"}

    # 新增收藏（quote_id 为空）
    fav = QuoteFavorite(
        user_id=current_user.user_id,
        quote_id=None,  # Obsidian 金句无数据库 ID
        obsidian_source=obsidian_source,
    )
    db.add(fav)
    db.commit()

    # 触发金句收藏成就
    try:
        await record_user_action(db, current_user.user_id, "quote_favorite")
    except Exception as e:
        logger.warning(f"金句收藏成就判定失败: {e}")

    return {"favorited": True, "message": "已收藏"}


@router.get("/favorites", summary="我的金句收藏列表")
async def get_quote_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的金句收藏列表"""
    query = db.query(QuoteFavorite).filter(
        QuoteFavorite.user_id == current_user.user_id
    )

    total = query.count()
    favs = query.order_by(desc(QuoteFavorite.create_time))\
        .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for fav in favs:
        quote = fav.quote
        if quote and quote.status == 1:
            items.append({
                'fav_id': fav.fav_id,
                'quote_id': quote.quote_id,
                'content': quote.content,
                'source': quote.source or '',
                'category': quote.category or '',
                'author': quote.author or '',
                'create_time': fav.create_time.isoformat() if fav.create_time else '',
            })

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}
