"""
笔记模块 API
GET    /api/notes              - 获取笔记列表
POST   /api/notes              - 创建/更新笔记
PUT    /api/notes/{note_id}    - 更新笔记
DELETE /api/notes/{note_id}    - 删除笔记
"""
import logging
import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ...core.database import get_db, commit_with_retry
from ...core.security import get_current_user
from ...models.models import SysUser

router = APIRouter(prefix="/api/notes", tags=["笔记模块"])
logger = logging.getLogger(__name__)


@router.get("", summary="获取笔记列表")
async def get_notes(
    note_type: str = Query("all", description="类型: all/question/news"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分页获取用户笔记列表"""
    from ...models.models import QuestionNote, NewsNote, QuestionBank, NewsArticle, QuestionSubject

    items = []
    total = 0

    # 题目笔记
    if note_type in ["all", "question"]:
        q = db.query(QuestionNote).filter(QuestionNote.user_id == current_user.user_id)
        note_items = q.order_by(desc(QuestionNote.update_time)).offset((page - 1) * page_size).limit(page_size).all()
        for note in note_items:
            qu = db.query(QuestionBank).filter(QuestionBank.question_id == note.question_id).first()
            subj = db.query(QuestionSubject).filter(QuestionSubject.subject_id == qu.subject_id).first() if qu else None
            items.append({
                'note_id': f"q_{note.note_id}",
                'type': 'question',
                'question_id': note.question_id,
                'title': (qu.question_content[:100] if qu and qu.question_content else ''),
                'subject': subj.subject_name if subj else '',
                'note_text': note.note_text,
                'create_time': note.create_time.isoformat() if note.create_time else None,
                'update_time': note.update_time.isoformat() if note.update_time else None,
            })

    # 新闻笔记
    if note_type in ["all", "news"]:
        nq = db.query(NewsNote).filter(NewsNote.user_id == current_user.user_id)
        news_note_items = nq.order_by(desc(NewsNote.update_time)).offset((page - 1) * page_size).limit(page_size).all()
        for note in news_note_items:
            news = db.query(NewsArticle).filter(NewsArticle.news_id == note.news_id).first()
            items.append({
                'note_id': f"n_{note.note_id}",
                'type': 'news',
                'news_id': note.news_id,
                'title': (news.title if news else '已删除'),
                'note_text': note.note_text,
                'quote_text': note.quote_text or '',
                'color': note.color or '#FFD700',
                'line_style': note.line_style or 'wavy',
                'create_time': note.create_time.isoformat() if note.create_time else None,
                'update_time': note.update_time.isoformat() if note.update_time else None,
            })

    # 总数统计
    if note_type == "question":
        total = db.query(QuestionNote).filter(QuestionNote.user_id == current_user.user_id).count()
    elif note_type == "news":
        total = db.query(NewsNote).filter(NewsNote.user_id == current_user.user_id).count()
    else:
        q_total = db.query(QuestionNote).filter(QuestionNote.user_id == current_user.user_id).count()
        n_total = db.query(NewsNote).filter(NewsNote.user_id == current_user.user_id).count()
        total = q_total + n_total

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}


@router.post("", summary="创建/更新笔记")
async def create_or_update_note(
    payload: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建或更新笔记（按 type+id 唯一）"""
    from ...models.models import QuestionNote, NewsNote, QuestionBank, NewsArticle

    note_type = payload.get('type')  # question / news
    resource_id = payload.get('id')
    note_text = payload.get('note_text', '').strip()
    quote_text = payload.get('quote_text', '')
    color = payload.get('color', '#FFD700')
    line_style = payload.get('line_style', 'wavy')

    if not note_type or not resource_id:
        raise HTTPException(status_code=400, detail="type 和 id 不能为空")
    if not note_text:
        raise HTTPException(status_code=400, detail="笔记内容不能为空")

    if note_type == "question":
        question = db.query(QuestionBank).filter(QuestionBank.question_id == resource_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="题目不存在")

        existing = db.query(QuestionNote).filter(
            QuestionNote.user_id == current_user.user_id,
            QuestionNote.question_id == resource_id
        ).first()

        if existing:
            existing.note_text = note_text
            existing.update_time = datetime.now()
            commit_with_retry(db)
            return {"note_id": f"q_{existing.note_id}", "message": "笔记已更新", "updated": True}

        note = QuestionNote(
            user_id=current_user.user_id,
            question_id=resource_id,
            note_text=note_text,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        db.add(note)
        commit_with_retry(db)
        db.refresh(note)

        # 触发笔记成就
        try:
            from ...services import achievement_service
            achievement_service.check_and_grant(current_user.user_id, "note", db)
        except Exception as e:
            logger.warning(f"笔记成就判定失败: {e}")

        return {"note_id": f"q_{note.note_id}", "message": "笔记已创建", "created": True}

    elif note_type == "news":
        news = db.query(NewsArticle).filter(NewsArticle.news_id == resource_id).first()
        if not news:
            raise HTTPException(status_code=404, detail="新闻不存在")

        existing = db.query(NewsNote).filter(
            NewsNote.user_id == current_user.user_id,
            NewsNote.news_id == resource_id
        ).first()

        if existing:
            existing.note_text = note_text
            existing.quote_text = quote_text
            existing.color = color
            existing.line_style = line_style
            existing.update_time = datetime.now()
            commit_with_retry(db)
            return {"note_id": f"n_{existing.note_id}", "message": "笔记已更新", "updated": True}

        note = NewsNote(
            user_id=current_user.user_id,
            news_id=resource_id,
            note_text=note_text,
            quote_text=quote_text,
            color=color,
            line_style=line_style,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        db.add(note)
        commit_with_retry(db)
        db.refresh(note)

        # 触发笔记成就
        try:
            from ...services import achievement_service
            achievement_service.check_and_grant(current_user.user_id, "note", db)
        except Exception as e:
            logger.warning(f"笔记成就判定失败: {e}")

        return {"note_id": f"n_{note.note_id}", "message": "笔记已创建", "created": True}

    else:
        raise HTTPException(status_code=400, detail="不支持的笔记类型，仅支持 question 和 news")


@router.put("/{note_id}", summary="更新笔记")
async def update_note(
    note_id: str,
    payload: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新笔记内容"""
    from ...models.models import QuestionNote, NewsNote

    parts = note_id.split("_")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="无效的笔记ID格式")

    note_type, pk_id = parts[0], int(parts[1])
    note_text = payload.get('note_text', '').strip()

    if not note_text:
        raise HTTPException(status_code=400, detail="笔记内容不能为空")

    if note_type == "q":
        note = db.query(QuestionNote).filter(
            QuestionNote.note_id == pk_id,
            QuestionNote.user_id == current_user.user_id
        ).first()
    elif note_type == "n":
        note = db.query(NewsNote).filter(
            NewsNote.note_id == pk_id,
            NewsNote.user_id == current_user.user_id
        ).first()
    else:
        raise HTTPException(status_code=400, detail="不支持的笔记类型")

    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    note.note_text = note_text
    note.update_time = datetime.now()
    commit_with_retry(db)
    return {"message": "笔记已更新"}


@router.delete("/{note_id}", summary="删除笔记")
async def delete_note(
    note_id: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除笔记"""
    from ...models.models import QuestionNote, NewsNote

    parts = note_id.split("_")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="无效的笔记ID格式")

    note_type, pk_id = parts[0], int(parts[1])

    if note_type == "q":
        note = db.query(QuestionNote).filter(
            QuestionNote.note_id == pk_id,
            QuestionNote.user_id == current_user.user_id
        ).first()
    elif note_type == "n":
        note = db.query(NewsNote).filter(
            NewsNote.note_id == pk_id,
            NewsNote.user_id == current_user.user_id
        ).first()
    else:
        raise HTTPException(status_code=400, detail="不支持的笔记类型")

    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    db.delete(note)
    commit_with_retry(db)
    return {"message": "已删除"}


# === 聚合查询接口（供前端笔记聚合页使用）===

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


@router.get("/news", summary="新闻笔记列表")
async def get_news_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回当前用户的所有新闻笔记，包含划线原文、想法、来源新闻信息"""
    from ...models.models import NewsNote, NewsArticle
    from sqlalchemy import func

    base_query = db.query(NewsNote).filter(NewsNote.user_id == current_user.user_id)
    total = base_query.count()

    notes = base_query.order_by(desc(NewsNote.update_time))\
        .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for note in notes:
        news = db.query(NewsArticle).filter(NewsArticle.news_id == note.news_id).first()
        items.append({
            'note_id': note.note_id,
            'note_text': note.note_text,
            'quote_text': note.quote_text or '',
            'color': note.color or '#FFD700',
            'line_style': note.line_style or 'wavy',
            'news_id': note.news_id,
            'news_title': news.title if news else '已删除',
            'news_source': news.source if news else '',
            'create_time': note.create_time.isoformat() if note.create_time else '',
            'update_time': note.update_time.isoformat() if note.update_time else '',
        })

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}


@router.get("/question", summary="典题笔记列表")
async def get_question_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    subject_id: Optional[int] = Query(None, description="科目ID筛选"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回当前用户的所有题目笔记，包含笔记内容、来源题目信息、知识点面包屑"""
    from ...models.models import (
        QuestionNote, QuestionBank, QuestionSubject,
        QuestionDetailCategory, QuestionKnowledge, KnowledgePoint,
        SubCategory, PracticeRecord
    )
    from sqlalchemy import func

    logger.warning(f"[DEBUG] /api/notes/question 被调用, user_id={current_user.user_id}, username={current_user.username}")

    base_query = db.query(QuestionNote).filter(QuestionNote.user_id == current_user.user_id)
    if subject_id:
        # 通过 question_id join QuestionBank 过滤科目
        base_query = base_query.join(
            QuestionBank, QuestionNote.question_id == QuestionBank.question_id
        ).filter(QuestionBank.subject_id == subject_id)
    total = base_query.count()
    logger.warning(f"[DEBUG] 查询到 {total} 条典题笔记 (user_id={current_user.user_id})")

    notes = base_query.order_by(desc(QuestionNote.update_time))\
        .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for note in notes:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == note.question_id).first()
        subj = db.query(QuestionSubject).filter(QuestionSubject.subject_id == q.subject_id).first() if q else None

        # 题型（从 QuestionDetailCategory 取，没有则回退到默认）
        detail_row = db.query(QuestionDetailCategory).filter(
            QuestionDetailCategory.question_id == note.question_id
        ).first() if q else None
        question_type = detail_row.question_type_detail if detail_row and detail_row.question_type_detail else '选择题'

        # 知识点面包屑：科目 > 子科目 > 考点
        kp_path = _build_knowledge_path(db, q) if q else ''

        # 正确率：accuracy_rate 字段（暂为0%，预留算法）
        correct_rate = float(q.accuracy_rate) if q and q.accuracy_rate else 0.0

        items.append({
            'note_id': note.note_id,
            'note_text': note.note_text,
            'question_id': note.question_id,
            'question_content': (q.question_content[:200] + '...' if q and q.question_content and len(q.question_content) > 200 else (q.question_content if q else '题目已删除')),
            'subject_name': subj.subject_name if subj else '',
            'subcategory': _get_subcategory(q),
            'question_type': question_type,
            'knowledge_path': kp_path,
            'answer': q.answer if q else '',
            'difficulty': q.difficulty if q else 3,
            'correct_rate': round(correct_rate, 1),
            'create_time': note.create_time.isoformat() if note.create_time else '',
            'update_time': note.update_time.isoformat() if note.update_time else '',
        })

    return {'total': total, 'page': page, 'page_size': page_size, 'items': items}


def _build_knowledge_path(db: Session, question) -> str:
    """构建知识点面包屑：科目 > 子科目 > 考点
    例如：公专 > 基础知识 > 中国特色社会主义法治理论
    """
    if not question:
        return ''
    parts = []
    # 1. 科目名
    from ...models.models import QuestionSubject, QuestionKnowledge, KnowledgePoint, SubCategory
    subj = db.query(QuestionSubject).filter(
        QuestionSubject.subject_id == question.subject_id
    ).first()
    if subj:
        parts.append(subj.subject_name)

    # 2. 子科目名（优先从 detail 表取，其次从 knowledge_point 反查 sub_category）
    subcat_name = _get_subcategory(question)
    if not subcat_name:
        # 通过 question_knowledge 反查
        qk = db.query(QuestionKnowledge).filter(
            QuestionKnowledge.question_id == question.question_id
        ).first()
        if qk:
            kp = db.query(KnowledgePoint).filter(
                KnowledgePoint.point_id == qk.knowledge_point_id
            ).first()
            if kp and kp.sub_category_id:
                sc = db.query(SubCategory).filter(SubCategory.id == kp.sub_category_id).first()
                if sc:
                    subcat_name = sc.name
    if subcat_name:
        parts.append(subcat_name)

    # 3. 考点名（取第一个关联的知识点）
    qk = db.query(QuestionKnowledge).filter(
        QuestionKnowledge.question_id == question.question_id
    ).first()
    if qk:
        kp = db.query(KnowledgePoint).filter(
            KnowledgePoint.point_id == qk.knowledge_point_id
        ).first()
        if kp and kp.point_name:
            parts.append(kp.point_name)
    elif question.point_id:
        kp = db.query(KnowledgePoint).filter(
            KnowledgePoint.point_id == question.point_id
        ).first()
        if kp and kp.point_name:
            parts.append(kp.point_name)

    return ' > '.join(parts) if parts else ''


@router.get("/question/{question_id}", summary="获取题目完整详情")
async def get_question_detail(
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回题目完整详情（供笔记弹窗展示）：题干、选项（高亮正确答案）、解析、正确率。
    图片经过 sanitize_content_images 预检，确保前端稳定显示。
    """
    from ...models.models import (
        QuestionBank, QuestionSubject, QuestionDetailCategory,
        QuestionKnowledge, KnowledgePoint, SubCategory, PracticeRecord
    )
    from ...services.image_service import sanitize_content_images, sanitize_options_images
    from ...services.option_utils import render_image_placeholder
    from sqlalchemy import func

    q = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id,
        QuestionBank.status == 1
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在或已删除")

    subj = db.query(QuestionSubject).filter(
        QuestionSubject.subject_id == q.subject_id
    ).first()

    # 题型
    detail_row = db.query(QuestionDetailCategory).filter(
        QuestionDetailCategory.question_id == question_id
    ).first()
    question_type = detail_row.question_type_detail if detail_row and detail_row.question_type_detail else '选择题'

    # 标准化选项 + 图片预检
    from .questions import _normalize_options, _detect_multi_from_content
    raw_opts = _normalize_options(q.options, q.question_content)
    raw_opts = [render_image_placeholder(o) for o in raw_opts]
    sanitized_opts = sanitize_options_images(raw_opts, question_id, db)

    # 高亮正确答案：根据 answer 标记 correct 标志
    answer_str = (q.answer or '').strip().upper()
    correct_letters = set(re.sub(r'[^A-Z]', '', answer_str)) if answer_str else set()

    options_with_correct = []
    for opt_text in sanitized_opts:
        # 提取选项字母 A/B/C/D
        letter = ''
        if opt_text and len(opt_text) > 1 and opt_text[0] in 'ABCDEFGH':
            letter = opt_text[0]
        options_with_correct.append({
            'text': opt_text,
            'letter': letter,
            'is_correct': letter in correct_letters,
        })

    # 题干图片预检
    content_sanitized = sanitize_content_images(
        render_image_placeholder(q.question_content or ''), question_id, db
    )
    analysis_sanitized = sanitize_content_images(
        render_image_placeholder(q.answer_analysis or ''), question_id, db
    )

    # 知识点面包屑
    kp_path = _build_knowledge_path(db, q)

    # 正确率算法（预留）：accuracy_rate 字段 + PracticeRecord 统计
    correct_rate = float(q.accuracy_rate) if q.accuracy_rate else 0.0
    # 若 accuracy_rate 为 0，尝试从 PracticeRecord 实时统计
    if correct_rate == 0.0:
        total_attempts = db.query(func.count(PracticeRecord.record_id)).filter(
            PracticeRecord.question_id == question_id
        ).scalar() or 0
        if total_attempts > 0:
            correct_attempts = db.query(func.count(PracticeRecord.record_id)).filter(
                PracticeRecord.question_id == question_id,
                PracticeRecord.is_correct == 1
            ).scalar() or 0
            correct_rate = round((correct_attempts / total_attempts) * 100, 1)

    return {
        'question_id': question_id,
        'subject_name': subj.subject_name if subj else '',
        'question_type': question_type,
        'question_content': content_sanitized,
        'options': options_with_correct,
        'answer': q.answer or '',
        'answer_analysis': analysis_sanitized or '暂未提供解析，请参考题目来源',
        'knowledge_path': kp_path,
        'difficulty': q.difficulty or 3,
        'correct_rate': round(correct_rate, 1),
        'source': q.source or '',
        'year': q.year,
    }


@router.get("/stats", summary="笔记统计")
async def get_notes_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回当前用户的笔记数量统计"""
    from ...models.models import QuestionNote, NewsNote

    logger.warning(f"[DEBUG] /api/notes/stats 被调用, user_id={current_user.user_id}, username={current_user.username}")

    question_count = db.query(QuestionNote).filter(QuestionNote.user_id == current_user.user_id).count()
    news_count = db.query(NewsNote).filter(NewsNote.user_id == current_user.user_id).count()
    logger.warning(f"[DEBUG] 统计结果: question_count={question_count}, news_count={news_count}")

    return {
        'question_notes': question_count,
        'news_notes': news_count,
        'total': question_count + news_count
    }