"""
错题集 API
GET  /api/wrong-questions          - 获取错题列表
POST /api/wrong-questions/collect  - 收录错题
DELETE /api/wrong-questions/{id}   - 删除错题
PUT  /api/wrong-questions/{id}/mastery - 更新掌握度
"""
import logging
from ....services.event_consumer import record_user_action
from ....core.trigger_types import (
    TRIGGER_LEGACY_CHOP,
    TRIGGER_LEGACY_VIEW_WRONG,
    TRIGGER_WRONG_REVIEWED,
)
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ....core.database import get_db, commit_with_retry
from ....core.security import get_current_user
from ....models.models import (
    WrongQuestionPersonal, QuestionBank, QuestionSubject, QuestionDetailCategory,
    QuestionType, QuestionImage, SysUser
)

router = APIRouter(prefix="/api/wrong-questions", tags=["错题集"])
logger = logging.getLogger(__name__)


@router.get("", summary="获取错题列表")
async def get_wrong_questions(
    subject_id: Optional[int] = Query(None, description="科目ID筛选"),
    collection_type: str = Query("WRONG", description="类型: WRONG/FAVORITE/ESSAY"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分页获取用户的错题列表"""
    query = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == current_user.user_id,
        WrongQuestionPersonal.collection_type == collection_type,
        WrongQuestionPersonal.status == 1
    )

    if subject_id:
        query = query.filter(WrongQuestionPersonal.subject_id == subject_id)

    total = query.count()
    items = query.order_by(desc(WrongQuestionPersonal.add_time))\
        .offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for wq in items:
        q = wq.question
        subj = db.query(QuestionSubject).filter(QuestionSubject.subject_id == wq.subject_id).first()
        # 获取子科目名称（从 question_bank ENUM 字段）
        sc_name = ''
        if q:
            if wq.subject_id == 1:
                sc_name = q.xingce_subcategory if q.xingce_subcategory != '无' else ''
            elif wq.subject_id == 2:
                sc_name = q.shenlun_subcategory if q.shenlun_subcategory != '无' else ''
            elif wq.subject_id == 3:
                sc_name = q.gongzhuan_subcategory if q.gongzhuan_subcategory != '无' else ''
        result.append({
            'wrong_id': wq.wrong_id,
            'question_id': q.question_id if q else None,
            'question_content': q.question_content[:200] if q and q.question_content else '',
            'question_type_detail': _get_question_type_detail(q, db),
            'options': q.options if q else None,
            'answer': q.answer if q else '',
            # 移动端错题本需要用户自己的错选渲染红色选项；此前列表接口缺失，
            # 只能拿到正确答案，无法区分「用户选错」与「用户未作答」。
            'user_answer': wq.user_answer or '',
            'answer_analysis': q.answer_analysis if q else '',
            'subject_id': wq.subject_id,
            'subject_name': subj.subject_name if subj else '',
            'sub_category': sc_name,
            'error_count': wq.error_count,
            'mastery_level': wq.mastery_level,
            'is_cut': bool(wq.is_cut),
            'accuracy_rate': float(wq.accuracy_rate or 0),
            'review_count': wq.review_count,
            'last_review_time': wq.last_review_time.isoformat() if wq.last_review_time else None,
            'add_time': wq.add_time.isoformat() if wq.add_time else None,
            'note': wq.note,
        })

    # 触发「直面错误」成就（首次查看错题集）
    try:
        await record_user_action(db, current_user.user_id, TRIGGER_LEGACY_VIEW_WRONG)
    except Exception as e:
        logger.warning(f"查看错题成就判定失败: {e}")

    return {'total': total, 'page': page, 'page_size': page_size, 'items': result}


@router.post("/collect", summary="收录错题")
async def collect_wrong_question(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    收录错题到个人错题集
    - 答错时自动调用
    - 如果题目已存在则更新错误次数
    - 如果答对则标记为已掌握
    """
    question_id = payload.get('question_id')
    subject_id = payload.get('subject_id')
    is_correct = payload.get('is_correct', False)

    if not question_id:
        raise HTTPException(status_code=400, detail="question_id 不能为空")

    # 获取题目信息
    question = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 查找是否已存在
    existing = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == current_user.user_id,
        WrongQuestionPersonal.question_id == question_id,
        WrongQuestionPersonal.collection_type == "WRONG"
    ).first()

    if existing:
        if is_correct:
            # 答对了，更新为已掌握
            existing.mastery_level = "MASTERED"
            existing.is_cut = 1
            existing.cut_time = datetime.now()
            commit_with_retry(db)
            return {"message": "答对了，已标记为已掌握", "wrong_id": existing.wrong_id, "removed": False, "mastered": True}
        else:
            # 答错了，增加错误次数，修复accuracy_rate计算逻辑
            existing.error_count = (existing.error_count or 0) + 1
            existing.review_count = (existing.review_count or 0) + 1
            # 正确率 = (复习次数 - 错误次数) / 复习次数 * 100
            total_attempts = existing.review_count
            correct_count = max(0, total_attempts - existing.error_count)
            existing.accuracy_rate = round((correct_count / total_attempts) * 100, 2) if total_attempts > 0 else 0
            existing.last_review_time = datetime.now()
            commit_with_retry(db)
            return {"message": "错题已更新", "wrong_id": existing.wrong_id, "updated": True}

    # 新增错题记录
    if not is_correct:
        wrong_q = WrongQuestionPersonal(
            user_id=current_user.user_id,
            question_id=question_id,
            subject_id=subject_id or question.subject_id,
            collection_type="WRONG",
            error_count=1,
            accuracy_rate=0.0,
            add_time=datetime.now(),
            last_review_time=datetime.now(),
        )
        db.add(wrong_q)
        commit_with_retry(db)
        db.refresh(wrong_q)
        return {"message": "错题已收录", "wrong_id": wrong_q.wrong_id, "created": True}

    return {"message": "答对了，无需收录", "skipped": True}


@router.delete("/{wrong_id}", summary="删除错题")
async def delete_wrong_question(
    wrong_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """从错题集删除"""
    wq = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.wrong_id == wrong_id,
        WrongQuestionPersonal.user_id == current_user.user_id
    ).first()

    if not wq:
        raise HTTPException(status_code=404, detail="错题记录不存在")

    wq.status = 0  # 软删除
    commit_with_retry(db)
    return {"message": "已删除"}


@router.put("/{wrong_id}/mastery", summary="更新掌握度")
async def update_mastery(
    wrong_id: int,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新错题掌握程度"""
    mastery_level = payload.get('mastery_level', 'UNMASTERED')
    valid_levels = ['UNMASTERED', 'PARTIAL', 'MASTERED']
    if mastery_level not in valid_levels:
        raise HTTPException(status_code=400, detail=f"mastery_level 可选值: {', '.join(valid_levels)}")

    wq = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.wrong_id == wrong_id,
        WrongQuestionPersonal.user_id == current_user.user_id
    ).first()

    if not wq:
        raise HTTPException(status_code=404, detail="错题记录不存在")

    wq.mastery_level = mastery_level
    if mastery_level == 'MASTERED':
        wq.is_cut = 1
        wq.cut_time = datetime.now()
    commit_with_retry(db)

    return {"message": "掌握度已更新", "mastery_level": mastery_level}


# === 辅助函数 ===

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


def _get_question_type_detail(question, db) -> str:
    """查询题目的题型名称，增加基于 options/answer 的智能识别"""
    if not question:
        return '单选题'

    # 1. 先查 question_detail_category
    detail_row = db.query(QuestionDetailCategory).filter(
        QuestionDetailCategory.question_id == question.question_id
    ).first()
    db_type = str(detail_row.question_type_detail) if (detail_row and detail_row.question_type_detail) else '单选题'
    if not question.type_id and not detail_row:
        return db_type

    # 2. 智能校验：基于实际内容修正数据库标记错误
    import json as _json
    import re as _re
    options = []
    if question.options:
        try:
            options = _json.loads(question.options) if isinstance(question.options, str) else question.options
        except Exception:
            options = []

    answer = question.answer or ''
    content = question.question_content or ''

    # 有选项（≥2）→ 选择题，根据答案字母数量区分单选/多选
    if options and len(options) >= 2:
        letters = _re.findall(r'[A-Z]', answer.upper())
        if len(letters) > 1:
            return '多选题'
        return '单选题'

    # 无选项或选项不足 → 论述/写作
    if not options or len(options) < 2:
        if any(kw in content for kw in ['写作', '作文', '为题', '写一篇', '谈谈你的看法']):
            return '写作题'
        if len(content) > 80 or any(kw in content for kw in ['论述', '分析', '简答', '阐述', '说明', '概括']):
            return '论述题'

    return db_type


def _serialize_wrong_question(wq, question, subject_name='', db=None):
    """序列化错题记录为字典"""
    return {
        'wrong_id': wq.wrong_id,
        'question_id': question.question_id if question else None,
        'question_content': question.question_content[:200] if question and question.question_content else '',
        'question_type_detail': _get_question_type_detail(question, db) if db else '单选题',
        'question_options': question.options if question else None,
        'question_answer': question.answer if question else '',
        'question_difficulty': question.difficulty if question else 3,
        'answer_analysis': question.answer_analysis if question else '',
        'subject_id': wq.subject_id,
        'subject_name': subject_name,
        'subcategory': _get_subcategory(question),
        'error_count': wq.error_count,
        'mastery_level': wq.mastery_level,
        'is_cut': bool(wq.is_cut),
        'accuracy_rate': float(wq.accuracy_rate or 0),
        'review_count': wq.review_count,
        'last_review_time': wq.last_review_time.isoformat() if wq.last_review_time else None,
        'add_time': wq.add_time.isoformat() if wq.add_time else None,
        'note': wq.note,
    }


# === 新增接口 ===

@router.get("/subcategories", summary="获取用户错题子科目分类")
async def get_subcategories(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回用户错题中涉及的子科目统计，用于精准分类"""
    wrong_items = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == current_user.user_id,
        WrongQuestionPersonal.collection_type == "WRONG",
        WrongQuestionPersonal.status == 1,
        WrongQuestionPersonal.is_cut == 0
    ).all()

    subject_map = {1: '行测', 2: '申论', 3: '公专'}
    stats = {}
    for wq in wrong_items:
        q = wq.question
        if not q:
            continue
        sc = _get_subcategory(q)
        if not sc:
            continue
        key = f"{wq.subject_id}_{sc}"
        if key not in stats:
            stats[key] = {
                'subject_id': wq.subject_id,
                'subject_name': subject_map.get(wq.subject_id, ''),
                'subcategory': sc,
                'count': 0
            }
        stats[key]['count'] += 1

    return {'items': list(stats.values())}


@router.get("/review/queue", summary="获取错题复习队列")
async def get_review_queue(
    mode: str = Query("mixed", description="复习模式: knowledge/time/subject/mixed"),
    subject_id: Optional[int] = Query(None, description="科目ID筛选"),
    subcategory: Optional[str] = Query(None, description="子科目筛选"),
    limit: int = Query(50, ge=1, le=200),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """按模式返回复习队列"""
    query = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == current_user.user_id,
        WrongQuestionPersonal.collection_type == "WRONG",
        WrongQuestionPersonal.status == 1,
        WrongQuestionPersonal.is_cut == 0
    )

    if subject_id:
        query = query.filter(WrongQuestionPersonal.subject_id == subject_id)

    items = query.all()

    # 按子科目筛选
    if subcategory:
        filtered = []
        for wq in items:
            q = wq.question
            if q and _get_subcategory(q) == subcategory:
                filtered.append(wq)
        items = filtered

    # 按模式排序
    if mode == "time":
        items.sort(key=lambda x: x.add_time or datetime.min, reverse=True)
    elif mode == "knowledge":
        items.sort(key=lambda x: (_get_subcategory(x.question) or 'zzz', -(x.error_count or 0)))
    elif mode == "subject":
        items.sort(key=lambda x: (x.subject_id or 0, -(x.error_count or 0)))
    else:  # mixed
        import random
        random.shuffle(items)

    items = items[:limit]

    result = []
    for wq in items:
        q = wq.question
        subj = db.query(QuestionSubject).filter(QuestionSubject.subject_id == wq.subject_id).first() if wq.subject_id else None
        result.append(_serialize_wrong_question(wq, q, subj.subject_name if subj else '', db))

    return {'total': len(result), 'items': result}


@router.put("/{wrong_id}/chop", summary="斩题（标记已掌握，10天后自动删除）")
async def chop_question(
    wrong_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """斩题：设置is_cut=1, cut_time, auto_delete_time=10天后"""
    wq = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.wrong_id == wrong_id,
        WrongQuestionPersonal.user_id == current_user.user_id
    ).first()

    if not wq:
        raise HTTPException(status_code=404, detail="错题记录不存在")

    wq.is_cut = 1
    wq.cut_time = datetime.now()
    wq.mastery_level = "MASTERED"
    wq.auto_delete_time = datetime.now().replace(
        hour=23, minute=59, second=59
    )
    # 10天后自动删除
    from datetime import timedelta
    wq.auto_delete_time = datetime.now() + timedelta(days=10)
    commit_with_retry(db)

    # 触发斩题成就
    try:
        await record_user_action(db, current_user.user_id, TRIGGER_LEGACY_CHOP)
    except Exception as e:
        logger.warning(f"斩题成就判定失败: {e}")

    return {"message": "已斩题，10天后自动删除", "wrong_id": wrong_id, "auto_delete_time": wq.auto_delete_time.isoformat()}


@router.get("/zhanti/list", summary="获取我的斩题列表")
async def get_zhanti_list(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取已斩题列表，含剩余天数和过期提醒"""
    now = datetime.now()
    items = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == current_user.user_id,
        WrongQuestionPersonal.is_cut == 1,
        WrongQuestionPersonal.status == 1
    ).all()

    result = []
    for wq in items:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == wq.question_id).first()
        if not q:
            continue
        # 联表查询科目名称
        subject = db.query(QuestionSubject).filter(
            QuestionSubject.subject_id == q.subject_id
        ).first()
        subject_name = subject.subject_name if subject else ''
        # 联表查询题型名称
        qtype = db.query(QuestionType).filter(
            QuestionType.type_id == q.type_id
        ).first()
        type_name = qtype.type_name if qtype else '单选题'
        # 联表查询子科目分类
        detail_cat = db.query(QuestionDetailCategory).filter(
            QuestionDetailCategory.question_id == q.question_id
        ).first()
        subcategory = ''
        if detail_cat:
            # 按科目取对应子科目字段
            if q.subject_id == 1:  # 行测
                subcategory = detail_cat.xingce_subcategory or ''
            elif q.subject_id == 2:  # 申论
                subcategory = detail_cat.shenlun_subcategory or ''
            elif q.subject_id == 3:  # 公专
                subcategory = detail_cat.gongzhuan_subcategory or ''
            if not subcategory:
                subcategory = detail_cat.question_type_detail or ''
        days_left = (wq.auto_delete_time - now).days if wq.auto_delete_time else 0
        result.append({
            'wrong_id': wq.wrong_id,
            'question_id': wq.question_id,
            'question_content': (q.question_content[:200] if q.question_content else ''),
            'subject_id': q.subject_id,
            'subject_name': subject_name,
            'type': type_name,
            'subcategory': subcategory,
            'cut_time': wq.cut_time.strftime('%Y-%m-%d %H:%M') if wq.cut_time else '',
            'auto_delete_time': wq.auto_delete_time.strftime('%Y-%m-%d %H:%M') if wq.auto_delete_time else '',
            'days_left': max(0, days_left),
            'is_expiring': days_left <= 2
        })
    return {'total': len(result), 'items': result}


@router.get("/zhanti/expiring", summary="获取即将过期的斩题提醒")
async def get_zhanti_expiring(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回2天内即将过期的斩题数量和列表"""
    now = datetime.now()
    threshold = now + timedelta(days=2)
    items = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == current_user.user_id,
        WrongQuestionPersonal.is_cut == 1,
        WrongQuestionPersonal.status == 1,
        WrongQuestionPersonal.auto_delete_time <= threshold,
        WrongQuestionPersonal.auto_delete_time > now
    ).all()

    return {
        'count': len(items),
        'message': '您有斩题进入观察期，请去看看' if items else '',
        'items': [{'wrong_id': wq.wrong_id, 'days_left': (wq.auto_delete_time - now).days if wq.auto_delete_time else 0} for wq in items]
    }


@router.get("/{wrong_id}/detail", summary="获取错题详情（完整题目信息）")
async def get_wrong_question_detail(
    wrong_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取错题完整详情：题干、选项、正确答案、用户答案、解析、难度、类型、全网正确率"""
    wq = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.wrong_id == wrong_id,
        WrongQuestionPersonal.user_id == current_user.user_id
    ).first()
    if not wq:
        raise HTTPException(status_code=404, detail="错题记录不存在")

    q = db.query(QuestionBank).filter(QuestionBank.question_id == wq.question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    subject = db.query(QuestionSubject).filter(
        QuestionSubject.subject_id == q.subject_id
    ).first()
    qtype = db.query(QuestionType).filter(
        QuestionType.type_id == q.type_id
    ).first()

    # 统一映射到4种类型
    raw_type = qtype.type_name if qtype else '单选题'
    type_map = {
        '单选题': '单选题', '选择题': '单选题', '无': '单选题',
        '多选题': '多选题', '不定项': '多选题',
        '论述题': '论述题', '简答题': '论述题', '案例分析题': '论述题',
        '写作题': '写作题'
    }
    unified_type = type_map.get(raw_type, '单选题')

    # 解析选项（options 是 JSON 字段）
    import json as _json
    options = []
    if q.options:
        try:
            if isinstance(q.options, str):
                options = _json.loads(q.options)
            else:
                options = q.options
        except Exception:
            options = []

    # 解析用户答案
    user_answer = wq.user_answer or ''

    # 查询题目图片映射（[IMAGE:x_y] → 真实路径）
    import re as _re_img
    images = db.query(QuestionImage).filter(
        QuestionImage.question_id == q.question_id
    ).all()
    image_map = {}
    for img in images:
        m = _re_img.search(r'img_docx_(\d+)_(\d+)_', img.image_path or '')
        if m:
            key = f"{m.group(1)}_{m.group(2)}"
            image_map[key] = img.image_path

    return {
        'wrong_id': wq.wrong_id,
        'question_id': q.question_id,
        'content': q.question_content or '',
        'options': options,
        'correct_answer': q.answer or '',
        'user_answer': user_answer,
        'analysis': q.answer_analysis or '',
        'difficulty': q.difficulty or 3,
        'type': unified_type,
        'raw_type': raw_type,
        'subject_name': subject.subject_name if subject else '',
        'subject_id': q.subject_id,
        'global_accuracy': float(q.accuracy_rate) if q.accuracy_rate else 0.0,
        'error_count': wq.error_count,
        'add_time': wq.add_time.strftime('%Y-%m-%d %H:%M') if wq.add_time else '',
        'is_cut': bool(wq.is_cut),
        'mastery_level': wq.mastery_level or 'NONE',
        'image_map': image_map
    }


@router.post("/{wrong_id}/unchop", summary="取消斩题，恢复到错题列表")
async def unchop_question(
    wrong_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消斩题：is_cut=0, 清除auto_delete_time"""
    wq = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.wrong_id == wrong_id,
        WrongQuestionPersonal.user_id == current_user.user_id
    ).first()
    if not wq:
        raise HTTPException(status_code=404, detail="错题记录不存在")

    wq.is_cut = 0
    wq.cut_time = None
    wq.auto_delete_time = None
    wq.mastery_level = "PARTIAL"
    commit_with_retry(db)
    return {"message": "已恢复到错题列表", "wrong_id": wrong_id}


@router.post("/review/submit", summary="提交错题复习答案（批量判分+自动斩题）")
async def submit_review(
    payload: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交错题复习答案，批量判分，答对3次自动斩题

    请求体:
    {
        "mode": "knowledge|time|subject|mixed",
        "answers": [
            {"wrong_id": 1, "question_id": 101, "user_answer": "A"},
            ...
        ]
    }

    返回:
    {
        "total": 10,
        "correct_count": 7,
        "wrong_count": 3,
        "results": [
            {
                "wrong_id": 1, "question_id": 101,
                "user_answer": "A", "correct_answer": "B",
                "is_correct": false, "analysis": "...",
                "options": [...], "type": "单选题"
            }
        ],
        "auto_chopped": [201, 202],  // 答对3次自动斩题的 wrong_id 列表
        "stats": {"new_wrong": 0, "updated": 2}
    }
    """
    import json as _json
    from datetime import timedelta

    mode = payload.get('mode', 'mixed')
    answers = payload.get('answers', [])
    if not answers:
        raise HTTPException(status_code=400, detail="答案列表不能为空")

    results = []
    correct_count = 0
    auto_chopped = []

    for ans in answers:
        wrong_id = ans.get('wrong_id')
        question_id = ans.get('question_id')
        user_answer = (ans.get('user_answer') or '').strip()

        wq = db.query(WrongQuestionPersonal).filter(
            WrongQuestionPersonal.wrong_id == wrong_id,
            WrongQuestionPersonal.user_id == current_user.user_id
        ).first()
        if not wq:
            continue

        q = db.query(QuestionBank).filter(
            QuestionBank.question_id == question_id
        ).first()
        if not q:
            continue

        # 获取题型
        qtype = db.query(QuestionType).filter(
            QuestionType.type_id == q.type_id
        ).first()
        raw_type = qtype.type_name if qtype else '单选题'
        type_map = {
            '单选题': '单选题', '选择题': '单选题', '无': '单选题',
            '多选题': '多选题', '不定项': '多选题',
            '论述题': '论述题', '简答题': '论述题', '案例分析题': '论述题',
            '写作题': '写作题'
        }
        unified_type = type_map.get(raw_type, '单选题')

        # 客观题判分（基于统一题型名称，不依赖 is_objective 字段）
        correct_answer = (q.answer or '').strip()
        is_correct = False
        import re as _re_judge
        if unified_type == '多选题':
            # 多选题：提取字母排序后比较（支持 "A,B,C" 和 "ABC" 两种格式）
            correct_letters = sorted(_re_judge.findall(r'[A-Z]', correct_answer.upper()))
            user_letters = sorted(_re_judge.findall(r'[A-Z]', user_answer.upper()))
            is_correct = (correct_letters == user_letters) and len(correct_letters) > 0
        elif unified_type == '单选题':
            # 单选题：直接比较
            is_correct = correct_answer.upper() == user_answer.upper()
        # 论述题/写作题：主观题不自动判分，is_correct 保持 False

        # 更新错题记录
        wq.user_answer = user_answer
        if is_correct:
            correct_count += 1
            wq.correct_count = (wq.correct_count or 0) + 1
            wq.last_review_time = datetime.now()
            wq.mastery_level = "MASTERED" if wq.correct_count >= 3 else "PARTIAL"

            # 答对3次自动斩题
            if wq.correct_count >= 3 and not wq.is_cut:
                wq.is_cut = 1
                wq.cut_time = datetime.now()
                wq.auto_delete_time = datetime.now() + timedelta(days=10)
                auto_chopped.append(wrong_id)
        else:
            wq.error_count = (wq.error_count or 0) + 1
            wq.last_review_time = datetime.now()
            wq.mastery_level = "UNMASTERED"

        # 解析选项
        options = []
        if q.options:
            try:
                if isinstance(q.options, str):
                    options = _json.loads(q.options)
                else:
                    options = q.options
            except Exception:
                options = []

        results.append({
            'wrong_id': wrong_id,
            'question_id': question_id,
            'content': q.question_content or '',
            'options': options,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'analysis': q.answer_analysis or '',
            'type': unified_type,
            'difficulty': q.difficulty or 3
        })

    commit_with_retry(db)

    # 触发错题重练成就
    try:
        await record_user_action(db, current_user.user_id, TRIGGER_WRONG_REVIEWED)
    except Exception as e:
        logger.warning(f"错题重练成就判定失败: {e}")

    return {
        'total': len(answers),
        'correct_count': correct_count,
        'wrong_count': len(answers) - correct_count,
        'results': results,
        'auto_chopped': auto_chopped,
        'stats': {
            'new_wrong': 0,
            'updated': len(answers)
        }
    }
