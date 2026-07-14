"""
题目交互操作 API — 收藏 / 笔记 / 标记
"""
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import (
    QuestionBank, FavoriteQuestion, QuestionNote, QuestionMarker, SysUser
)

router = APIRouter(prefix="/api/questions", tags=["题目交互"])


# ==================== 收藏 ====================

@router.post("/{question_id}/favorite", summary="切换收藏状态")
async def toggle_favorite(
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """收藏/取消收藏题目，返回当前收藏状态"""
    question = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    existing = db.query(FavoriteQuestion).filter(
        FavoriteQuestion.user_id == current_user.user_id,
        FavoriteQuestion.question_id == question_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False, "message": "已取消收藏"}

    fav = FavoriteQuestion(
        user_id=current_user.user_id,
        question_id=question_id
    )
    db.add(fav)
    db.commit()
    return {"favorited": True, "message": "已收藏"}


@router.get("/favorites", summary="收藏列表")
async def list_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分页查询收藏题目"""
    q = db.query(FavoriteQuestion).filter(FavoriteQuestion.user_id == current_user.user_id)
    total = q.count()
    items = q.order_by(FavoriteQuestion.create_time.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    result = []
    for fav in items:
        question = fav.question
        result.append({
            'fav_id': fav.fav_id,
            'question_id': question.question_id,
            'question_content': question.question_content[:200] if question else '',
            'answer': question.answer if question else '',
            'create_time': fav.create_time.isoformat() if fav.create_time else None,
        })

    return {'total': total, 'page': page, 'page_size': page_size, 'items': result}


# ==================== 笔记 ====================

@router.post("/{question_id}/note", summary="创建/更新笔记")
async def upsert_note(
    question_id: int,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建或更新题目笔记"""
    note_text = payload.get('note_text', '').strip()
    if not note_text:
        raise HTTPException(status_code=400, detail="笔记内容不能为空")

    question = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    existing = db.query(QuestionNote).filter(
        QuestionNote.user_id == current_user.user_id,
        QuestionNote.question_id == question_id
    ).first()

    if existing:
        existing.note_text = note_text
        existing.update_time = datetime.now()
        db.commit()
        return {"note_id": existing.note_id, "message": "笔记已更新"}

    note = QuestionNote(
        user_id=current_user.user_id,
        question_id=question_id,
        note_text=note_text
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"note_id": note.note_id, "message": "笔记已创建"}


@router.get("/{question_id}/note", summary="获取笔记")
async def get_note(
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户对该题的笔记"""
    note = db.query(QuestionNote).filter(
        QuestionNote.user_id == current_user.user_id,
        QuestionNote.question_id == question_id
    ).first()

    if not note:
        return {"note_id": None, "note_text": "", "has_note": False}

    return {
        "note_id": note.note_id,
        "note_text": note.note_text,
        "has_note": True,
        "update_time": note.update_time.isoformat() if note.update_time else None
    }


@router.delete("/{question_id}/note", summary="删除笔记")
async def delete_note(
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除题目笔记"""
    note = db.query(QuestionNote).filter(
        QuestionNote.user_id == current_user.user_id,
        QuestionNote.question_id == question_id
    ).first()

    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    db.delete(note)
    db.commit()
    return {"message": "笔记已删除"}


# ==================== 标记 ====================

@router.post("/{question_id}/marker", summary="创建/更新标记")
async def upsert_marker(
    question_id: int,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """标记题目（重要/疑难/易错等）"""
    marker_type = payload.get('marker_type', 'important').strip()
    marker_label = payload.get('marker_label', '').strip()

    valid_types = ['difficult', 'important', 'confusing', 'tricky', 'frequent']
    if marker_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"标记类型无效，可选: {', '.join(valid_types)}")

    question = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    existing = db.query(QuestionMarker).filter(
        QuestionMarker.user_id == current_user.user_id,
        QuestionMarker.question_id == question_id
    ).first()

    if existing:
        existing.marker_type = marker_type
        existing.marker_label = marker_label or existing.marker_label
        db.commit()
        return {"marker_id": existing.marker_id, "message": "标记已更新", "marker_type": marker_type}

    marker = QuestionMarker(
        user_id=current_user.user_id,
        question_id=question_id,
        marker_type=marker_type,
        marker_label=marker_label
    )
    db.add(marker)
    db.commit()
    db.refresh(marker)
    return {"marker_id": marker.marker_id, "message": "已标记", "marker_type": marker_type}


@router.delete("/{question_id}/marker", summary="取消标记")
async def remove_marker(
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消题目标记"""
    marker = db.query(QuestionMarker).filter(
        QuestionMarker.user_id == current_user.user_id,
        QuestionMarker.question_id == question_id
    ).first()

    if not marker:
        raise HTTPException(status_code=404, detail="标记不存在")

    db.delete(marker)
    db.commit()
    return {"message": "标记已取消"}


# ==================== 综合查询（exercise 页面用） ====================

@router.get("/{question_id}/actions", summary="获取题目交互状态")
async def get_question_actions(
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户对某题的收藏/笔记/标记状态。
    用于答题页面展示初始状态。
    """
    fav = db.query(FavoriteQuestion).filter(
        FavoriteQuestion.user_id == current_user.user_id,
        FavoriteQuestion.question_id == question_id
    ).first()

    note = db.query(QuestionNote).filter(
        QuestionNote.user_id == current_user.user_id,
        QuestionNote.question_id == question_id
    ).first()

    marker = db.query(QuestionMarker).filter(
        QuestionMarker.user_id == current_user.user_id,
        QuestionMarker.question_id == question_id
    ).first()

    return {
        'question_id': question_id,
        'favorited': fav is not None,
        'note': {
            'note_id': note.note_id,
            'note_text': note.note_text,
            'has_note': note is not None,
        } if note else {'has_note': False, 'note_text': ''},
        'marker': {
            'marker_id': marker.marker_id,
            'marker_type': marker.marker_type,
            'marker_label': marker.marker_label,
            'has_marker': marker is not None,
        } if marker else {'has_marker': False},
    }
