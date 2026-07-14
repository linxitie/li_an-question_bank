"""
练习记录 API
POST /api/practice/record — 记录练习行为
GET /api/practice/records — 查询用户练习历史
GET /api/practice/type-summary — 按题目类型统计完成/未完成状态
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import PracticeRecord, QuestionBank, QuestionSubject, QuestionType, SysUser

router = APIRouter(prefix="/api/practice", tags=["练习记录"])
logger = logging.getLogger(__name__)


@router.post("/record", summary="记录练习行为")
async def record_practice(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """记录每次答题练习"""
    question_id = payload.get('question_id')
    subject_id = payload.get('subject_id')
    is_correct = payload.get('is_correct', False)
    time_spent = payload.get('time_spent', 0)  # 秒

    # 获取题目信息（若未传 subject_id 则从题目推断）
    question = None
    if question_id:
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == question_id
        ).first()

    record = PracticeRecord(
        user_id=current_user.user_id,
        question_id=question_id,
        subject_id=subject_id or (question.subject_id if question else None),
        type_id=question.type_id if question else None,
        is_correct=1 if is_correct else 0,
        time_spent=int(time_spent) if time_spent else 0,
        answer=payload.get('user_answer', ''),
        practice_date=date.today(),
        practice_time=datetime.now(),
        source_type=payload.get('source', '随机练习'),
    )
    db.add(record)
    db.commit()

    return {"status": "ok", "record_id": record.record_id}


@router.post("/batch-record", summary="批量记录练习行为")
async def batch_record_practice(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量记录多条答题记录（用于交卷时一次性提交）"""
    records_data = payload.get('records', [])
    if not records_data:
        return {"status": "ok", "count": 0}

    today = date.today()
    now = datetime.now()
    count = 0

    for item in records_data:
        question_id = item.get('question_id')
        is_correct = item.get('is_correct', False)
        subject_id = item.get('subject_id')

        question = None
        if question_id:
            question = db.query(QuestionBank).filter(
                QuestionBank.question_id == question_id
            ).first()

        record = PracticeRecord(
            user_id=current_user.user_id,
            question_id=question_id,
            subject_id=subject_id or (question.subject_id if question else None),
            type_id=question.type_id if question else None,
            is_correct=1 if is_correct else 0,
            time_spent=int(item.get('time_spent', 0)),
            answer=item.get('user_answer', ''),
            practice_date=today,
            practice_time=now,
            source_type=item.get('source', '随机练习'),
        )
        db.add(record)
        count += 1

    db.commit()
    return {"status": "ok", "count": count}


@router.get("/records", summary="查询练习记录")
async def get_practice_records(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    subject_id: Optional[int] = Query(None),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询用户练习历史，按日期分组统计"""
    query = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id
    )
    if subject_id:
        query = query.filter(PracticeRecord.subject_id == subject_id)

    total = query.count()
    records = query.order_by(desc(PracticeRecord.practice_time)).offset(offset).limit(limit).all()

    items = []
    for r in records:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == r.question_id).first() if r.question_id else None
        items.append({
            "record_id": r.record_id,
            "question_id": r.question_id,
            "subject_id": r.subject_id,
            "type_id": r.type_id,
            "is_correct": bool(r.is_correct),
            "time_spent": r.time_spent,
            "user_answer": r.answer,
            "question_content": q.question_content[:100] if q and q.question_content else '',
            "correct_answer": q.answer if q else '',
            "practice_date": r.practice_date.isoformat() if r.practice_date else None,
            "practice_time": r.practice_time.isoformat() if r.practice_time else None,
            "source": r.source_type,
        })

    # 每日统计
    daily_stats = db.query(
        PracticeRecord.practice_date,
        func.count(PracticeRecord.record_id).label('total'),
        func.sum(PracticeRecord.is_correct).label('correct')
    ).filter(
        PracticeRecord.user_id == current_user.user_id
    ).group_by(PracticeRecord.practice_date).order_by(
        desc(PracticeRecord.practice_date)
    ).limit(30).all()

    daily = [{
        "date": d[0].isoformat() if d[0] else None,
        "total": int(d[1]),
        "correct": int(d[2] or 0),
        "accuracy": round(int(d[2] or 0) * 100 / max(int(d[1]), 1), 1)
    } for d in daily_stats]

    return {"total": total, "items": items, "daily_stats": daily}


@router.get("/type-summary", summary="按题目类型统计")
async def get_practice_type_summary(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    按科目+子科目统计用户做题情况
    返回每个类型的完成/未完成状态
    """
    # 获取所有科目的子科目分类
    subjects = db.query(QuestionSubject).filter(QuestionSubject.status == 1).all()

    type_stats = []
    for subj in subjects:
        subj_name = subj.subject_name  # 行测/申论/公专

        # 获取该科目下所有题目
        questions = db.query(QuestionBank).filter(
            QuestionBank.subject_id == subj.subject_id,
            QuestionBank.status == 1
        ).all()

        # 按子科目分组
        subcategories = {}
        for q in questions:
            # 确定子科目
            if subj.subject_id == 1:  # 行测
                sc = q.xingce_subcategory or '综合'
            elif subj.subject_id == 2:  # 申论
                sc = q.shenlun_subcategory or '综合'
            elif subj.subject_id == 3:  # 公专
                sc = q.gongzhuan_subcategory or '综合'
            else:
                sc = '其他'

            if sc == '无':
                sc = '综合'

            if sc not in subcategories:
                subcategories[sc] = {'total': 0, 'done': 0, 'question_ids': []}
            subcategories[sc]['total'] += 1
            subcategories[sc]['question_ids'].append(q.question_id)

        # 统计用户在该子科目下的做题情况
        for sc_name, sc_data in subcategories.items():
            # 用户做过的该子科目题目数
            done_count = db.query(func.count(PracticeRecord.record_id)).filter(
                PracticeRecord.user_id == current_user.user_id,
                PracticeRecord.question_id.in_(sc_data['question_ids'])
            ).scalar() or 0

            # 去重题目数（同一题可能做多次）
            unique_done = db.query(func.count(func.distinct(PracticeRecord.question_id))).filter(
                PracticeRecord.user_id == current_user.user_id,
                PracticeRecord.question_id.in_(sc_data['question_ids'])
            ).scalar() or 0

            is_completed = unique_done >= sc_data['total'] if sc_data['total'] > 0 else False

            type_stats.append({
                "subject_id": subj.subject_id,
                "subject_name": subj_name,
                "subject_code": subj.subject_code,
                "subcategory": sc_name,
                "total_questions": sc_data['total'],
                "done_count": unique_done,
                "is_completed": is_completed,
                "completion_rate": round(unique_done * 100 / max(sc_data['total'], 1), 1)
            })

    # 按科目排序，再按完成率排序
    type_stats.sort(key=lambda x: (x['subject_id'], -x['completion_rate']))

    return {
        "total_types": len(type_stats),
        "types": type_stats
    }


@router.get("/stats-card", summary="练习记录统计卡片")
async def get_practice_stats_card(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    返回练习记录卡片所需的所有统计数据
    包括：今日/本周/累计做题量、用时、正确率
    """
    today = date.today()
    week_ago = today - timedelta(days=7)

    base_query = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id
    )

    # 今日统计
    today_query = base_query.filter(PracticeRecord.practice_date == today)
    today_count = today_query.count()
    today_correct = today_query.filter(PracticeRecord.is_correct == 1).count()
    today_time = db.query(func.coalesce(func.sum(PracticeRecord.time_spent), 0)).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_date == today
    ).scalar() or 0

    # 本周统计
    week_query = base_query.filter(PracticeRecord.practice_date >= week_ago)
    week_count = week_query.count()
    week_correct = week_query.filter(PracticeRecord.is_correct == 1).count()
    week_time = db.query(func.coalesce(func.sum(PracticeRecord.time_spent), 0)).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_date >= week_ago
    ).scalar() or 0

    # 累计统计
    total_count = base_query.count()
    total_correct = base_query.filter(PracticeRecord.is_correct == 1).count()
    total_time = db.query(func.coalesce(func.sum(PracticeRecord.time_spent), 0)).filter(
        PracticeRecord.user_id == current_user.user_id
    ).scalar() or 0

    # 正确率
    today_accuracy = round(today_correct * 100 / max(today_count, 1), 1)
    week_accuracy = round(week_correct * 100 / max(week_count, 1), 1)
    total_accuracy = round(total_correct * 100 / max(total_count, 1), 1)

    # 本周每日趋势（用于图表）
    daily_trend = []
    for i in range(7):
        d = week_ago + timedelta(days=i)
        day_count = base_query.filter(PracticeRecord.practice_date == d).count()
        day_correct = base_query.filter(
            PracticeRecord.practice_date == d,
            PracticeRecord.is_correct == 1
        ).count()
        daily_trend.append({
            "date": d.isoformat(),
            "weekday": ["一", "二", "三", "四", "五", "六", "日"][d.weekday()],
            "count": day_count,
            "correct": day_correct,
            "accuracy": round(day_correct * 100 / max(day_count, 1), 1)
        })

    return {
        "today": {
            "count": today_count,
            "correct": today_correct,
            "accuracy": today_accuracy,
            "time_spent_minutes": round(today_time / 60, 1)
        },
        "week": {
            "count": week_count,
            "correct": week_correct,
            "accuracy": week_accuracy,
            "time_spent_minutes": round(week_time / 60, 1)
        },
        "total": {
            "count": total_count,
            "correct": total_correct,
            "accuracy": total_accuracy,
            "time_spent_minutes": round(total_time / 60, 1)
        },
        "daily_trend": daily_trend
    }
