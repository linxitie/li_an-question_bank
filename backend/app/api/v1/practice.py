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
from sqlalchemy import func, desc, case, distinct

from ...core.database import get_db, commit_with_retry
from ...core.security import get_current_user
from ...models.models import (
    PracticeRecord, QuestionBank, QuestionSubject, QuestionType, SysUser,
    WrongQuestionPersonal, SmartExamRecord, ExamRecord, ExamAnswerDetail,
    YearPaper, ExamPaper, KnowledgePoint, QuestionKnowledge, SubCategory
)
from ...services.growth_service import add_growth, GROWTH_RULES

router = APIRouter(prefix="/api/practice", tags=["练习记录"])
logger = logging.getLogger(__name__)


def _after_practice(user_id: int, db: Session, total: int, correct: int) -> list:
    """练习后处理：成长值 + 会话正确率streak + 成就判定。返回 newly_unlocked。"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        return []

    # 成长值（对+2 错+1）
    wrong = total - correct
    add_growth(db, user, GROWTH_RULES["correct_answer"] * correct)
    add_growth(db, user, GROWTH_RULES["wrong_answer"] * wrong)

    # 会话正确率 streak 更新（连续≥80% / 连续全对）
    if total > 0:
        accuracy = correct / total * 100
        if accuracy >= 80:
            user.accuracy80_streak = (user.accuracy80_streak or 0) + 1
        else:
            user.accuracy80_streak = 0
        if correct == total:
            user.perfect_streak = (user.perfect_streak or 0) + 1
        else:
            user.perfect_streak = 0
    commit_with_retry(db)

    # 成就判定
    try:
        from ...services import achievement_service
        return achievement_service.check_and_grant(
            user_id, "do_question", db, session={"total": total, "correct": correct}
        )
    except Exception as e:
        logger.warning(f"做题成就判定失败: {e}")
        return []


def _auto_record_wrong(user_id: int, question_id: int, subject_id: int, db: Session,
                       user_answer: str = '') -> str:
    """自动将错题收录到个人错题集（内部辅助函数）

    返回操作结果: 'new' | 'updated' | 'skipped' | 'error'
    """
    try:
        # 兜底处理：subject_id 为 None 时从 QuestionBank 反查
        if not subject_id:
            q = db.query(QuestionBank).filter(
                QuestionBank.question_id == question_id
            ).first()
            if q:
                subject_id = q.subject_id
            else:
                logger.warning(f"自动收录错题失败(qid={question_id}): 题目不存在")
                return 'skipped'

        existing = db.query(WrongQuestionPersonal).filter(
            WrongQuestionPersonal.user_id == user_id,
            WrongQuestionPersonal.question_id == question_id,
            WrongQuestionPersonal.collection_type == "WRONG"
        ).first()
        if existing:
            existing.error_count = (existing.error_count or 0) + 1
            existing.last_review_time = datetime.now()
            existing.review_count = (existing.review_count or 0) + 1
            # 记录最近一次错选：错题本据此把用户选错的选项标红。
            # 用本次作答覆盖，保证反映的是最新一次错误而非陈旧值。
            if user_answer:
                existing.user_answer = user_answer
            return 'updated'
        else:
            db.add(WrongQuestionPersonal(
                user_id=user_id,
                question_id=question_id,
                subject_id=subject_id,
                collection_type="WRONG",
                error_count=1,
                accuracy_rate=0.0,
                # 首次收录即记下用户错选，错题本可直接标红
                user_answer=user_answer or '',
                add_time=datetime.now(),
                last_review_time=datetime.now(),
                review_count=1,
            ))
            return 'new'
    except Exception as e:
        logger.warning(f"自动收录错题失败(qid={question_id}): {e}")
        return 'error'


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
    commit_with_retry(db)

    # 自动收录错题
    if not is_correct and question_id:
        _auto_record_wrong(current_user.user_id, question_id,
                          subject_id or (question.subject_id if question else None), db,
                          payload.get('user_answer', ''))
        commit_with_retry(db)

    newly = _after_practice(current_user.user_id, db, 1, 1 if is_correct else 0)

    # 目标进度自动追踪：按真实刷题量重算未完成目标（幂等，失败不影响刷题结果）
    try:
        from ...services.goal_progress import sync_goal_progress
        sync_goal_progress(current_user.user_id, db)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        print(f"[practice] 目标进度同步失败(非阻断): {e}")

    # 三端实时同步：练习记录是私有数据，必须定向广播给该用户，
    # 而不是 broadcast_all —— 否则所有在线用户都会被触发重拉，
    # 既浪费带宽，也会通过刷新行为泄露「谁在练习」。
    # 事件体只含统计量，不含题目正文。广播失败不阻断答题。
    try:
        from ...services.scheduler import _broadcast_personal_sync
        _broadcast_personal_sync(
            current_user.user_id,
            "练习记录已更新",
            {"scope": "practice", "action": "record", "count": 1},
        )
    except Exception as e:  # noqa: BLE001
        print(f"[practice] 三端同步广播失败(非阻断): {e}")

    return {"status": "ok", "record_id": record.record_id, "newly_unlocked": newly}


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

        # 自动收录错题
        if not is_correct and question_id:
            _auto_record_wrong(current_user.user_id, question_id,
                              subject_id or (question.subject_id if question else None), db,
                              item.get('user_answer', ''))

    commit_with_retry(db)

    # 与 POST /record 保持一致：批量交卷同样要触发目标进度重算。
    # 此前只在 /record 里挂了 sync_goal_progress，导致走批量端点的交卷
    # （如电脑端整卷提交）不会推进今日/本周目标，也不会触发完成奖励。
    # 放在 commit 之后：目标进度是按刚落库的练习记录重算的。
    try:
        from ...services.goal_progress import sync_goal_progress
        sync_goal_progress(current_user.user_id, db)
    except Exception as e:
        # 目标进度同步失败不应让整卷交卷失败，记录告警即可
        logger.warning(f"批量交卷后同步目标进度失败: {e}")

    correct = sum(1 for i in records_data if i.get("is_correct", False))
    newly = _after_practice(current_user.user_id, db, len(records_data), correct)

    # 三端实时同步：整卷交卷（如电脑端提交）同样要让手机/平板刷新，
    # 否则用户在手机上看到的进度会停在交卷之前。与 /record 一致，
    # 定向广播给该用户，事件体只含条数等统计量。
    try:
        from ...services.scheduler import _broadcast_personal_sync
        _broadcast_personal_sync(
            current_user.user_id,
            "练习记录已更新",
            {"scope": "practice", "action": "batch_record", "count": count},
        )
    except Exception as e:
        logger.warning(f"批量交卷后广播三端同步失败: {e}")

    return {"status": "ok", "count": count, "newly_unlocked": newly}


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

        # 按子科目分组（v2.1：无效子科目直接跳过，不再产生"综合"兜底类型）
        subcategories = {}
        for q in questions:
            # 确定子科目
            if subj.subject_id == 1:  # 行测
                sc = q.xingce_subcategory
            elif subj.subject_id == 2:  # 申论
                sc = q.shenlun_subcategory
            elif subj.subject_id == 3:  # 公专
                sc = q.gongzhuan_subcategory
            else:
                sc = None

            # 子科目缺失或占位值('无')的题目不参与类型进度统计
            # （系统中不存在"综合"这一真实分类，兜底会产生幻影徽章）
            if not sc or sc == '无':
                continue

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


# ============================================================
# 统一聚合统计（读时聚合，覆盖：快速练习/智能组卷/历年试卷/小模考）
# 设计规格: docs/superpowers/specs/2026-08-24-practice-records-v2-design.md §3
# 约束: 只读端点；不改任何写入路径；时间一律返回秒；来源标签沿用库内中文值
# ============================================================

def _smart_linked_record_ids(db: Session) -> List[int]:
    """智能组卷已关联的考试记录ID集合。

    智能组卷交卷时会按题写入 practice_record(source_type='智能组卷')，
    其关联的 exam_record/exam_answer_detail 若同时计入会造成双计，
    统计时必须排除（规格 §3.2 注记）。
    """
    rows = db.query(SmartExamRecord.exam_record_id).filter(
        SmartExamRecord.exam_record_id.isnot(None)
    ).all()
    return [r[0] for r in rows]


@router.get("/unified-stats", summary="四来源统一练习统计")
async def get_unified_practice_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    聚合四来源的 今日/本周/累计 做题量、用时(秒)、正确率 及近7日趋势。
    - 刷题流（随机/章节/错题/快速/智能组卷按题流水）→ practice_record
    - 历年试卷/小模考 → exam_answer_detail JOIN exam_record（排除智能组卷关联记录）
    SQL 预算 ≤5 条；无逐日循环 N+1。
    """
    user_id = current_user.user_id
    today = date.today()
    week_ago = today - timedelta(days=7)

    # ---- 来源A: 刷题流水 ----
    # 近7日按日分组（今日/本周/趋势一次取回）
    drill_daily = db.query(
        PracticeRecord.practice_date,
        func.count(PracticeRecord.record_id),
        func.coalesce(func.sum(PracticeRecord.is_correct), 0),
        func.coalesce(func.sum(PracticeRecord.time_spent), 0),
    ).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.practice_date >= week_ago,
    ).group_by(PracticeRecord.practice_date).all()

    # 全历史累计（单行）
    drill_total = db.query(
        func.count(PracticeRecord.record_id),
        func.coalesce(func.sum(PracticeRecord.is_correct), 0),
        func.coalesce(func.sum(PracticeRecord.time_spent), 0),
    ).filter(PracticeRecord.user_id == user_id).one()

    # ---- 来源B: 试卷作答明细（排除智能组卷关联记录防双计）----
    smart_ids = _smart_linked_record_ids(db)

    detail_q = db.query(
        func.date(ExamRecord.start_time),
        func.count(ExamAnswerDetail.detail_id),
        func.coalesce(func.sum(ExamAnswerDetail.is_correct), 0),
    ).join(
        ExamRecord, ExamAnswerDetail.record_id == ExamRecord.record_id
    ).filter(
        ExamRecord.user_id == user_id,
    )
    time_q = db.query(
        func.date(ExamRecord.start_time),
        func.sum(ExamRecord.duration_used),
    ).filter(
        ExamRecord.user_id == user_id,
        # 只统计有作答明细的记录，与题数口径一致
        ExamRecord.record_id.in_(
            db.query(ExamAnswerDetail.record_id).distinct().scalar_subquery()
        ),
    )
    if smart_ids:
        detail_q = detail_q.filter(~ExamRecord.record_id.in_(smart_ids))
        time_q = time_q.filter(~ExamRecord.record_id.in_(smart_ids))
    paper_daily = detail_q.group_by(
        func.date(ExamRecord.start_time)
    ).all()
    paper_time_daily = time_q.group_by(
        func.date(ExamRecord.start_time)
    ).all()

    # ---- 合并 ----
    daily_map = {}

    def _cell(dd):
        return daily_map.setdefault(dd, {"count": 0, "correct": 0, "seconds": 0})

    for d, cnt, correct, secs in drill_daily:
        if d is None:
            continue
        cell = _cell(d)
        cell["count"] += int(cnt or 0)
        cell["correct"] += int(correct or 0)
        cell["seconds"] += int(secs or 0)

    def _parse_day(v):
        try:
            return date.fromisoformat(str(v)[:10])
        except Exception:
            return None

    for d, cnt, correct in paper_daily:
        dd = _parse_day(d)
        if dd is None:
            continue
        cell = _cell(dd)
        cell["count"] += int(cnt or 0)
        cell["correct"] += int(correct or 0)
    for d, secs in paper_time_daily:
        dd = _parse_day(d)
        if dd is None:
            continue
        _cell(dd)["seconds"] += int(secs or 0)

    def _acc(cnt, correct):
        cnt = int(cnt or 0)
        correct = int(correct or 0)
        return round(correct * 100 / cnt, 1) if cnt > 0 else 0

    today_row = daily_map.get(today, {"count": 0, "correct": 0, "seconds": 0})

    trend = []
    week_cnt = week_corr = week_secs = 0
    trend_start = today - timedelta(days=6)  # 近7天窗口，含今日
    for i in range(7):
        d = trend_start + timedelta(days=i)
        row = daily_map.get(d, {"count": 0, "correct": 0, "seconds": 0})
        week_cnt += row["count"]
        week_corr += row["correct"]
        week_secs += row["seconds"]
        trend.append({
            "date": d.isoformat(),
            "weekday": ["一", "二", "三", "四", "五", "六", "日"][d.weekday()],
            "count": row["count"],
            "correct": row["correct"],
        })

    # 全历史合计 = 刷题全历史 + 试卷明细全历史（paper_* 查询本身覆盖全历史）
    tot_cnt = int(drill_total[0] or 0) + sum(int(c or 0) for _, c, _ in paper_daily)
    tot_corr = int(drill_total[1] or 0) + sum(int(cc or 0) for _, _, cc in paper_daily)
    tot_secs = int(drill_total[2] or 0) + sum(int(s or 0) for _, s in paper_time_daily)

    return {
        "today": {
            "count": today_row["count"],
            "correct": today_row["correct"],
            "accuracy": _acc(today_row["count"], today_row["correct"]),
            "time_spent_seconds": today_row["seconds"],
        },
        "week": {
            "count": week_cnt,
            "correct": week_corr,
            "accuracy": _acc(week_cnt, week_corr),
            "time_spent_seconds": week_secs,
        },
        "total": {
            "count": tot_cnt,
            "correct": tot_corr,
            "accuracy": _acc(tot_cnt, tot_corr),
            "time_spent_seconds": tot_secs,
        },
        "daily_trend": trend,
    }


@router.get("/knowledge-progress", summary="知识点粒度练习进度")
async def get_knowledge_progress(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    返回 科目→考点 两级进度（仅含 total>0 的考点），组内按完成率升序（薄弱优先）。
    done 口径 = 去重做过题数（不论对错），与 /type-summary 一致。
    SQL 预算 ≤2 条。
    """
    kp_rows = db.query(
        KnowledgePoint.point_id,
        KnowledgePoint.point_name,
        QuestionSubject.subject_id,
        QuestionSubject.subject_name,
        QuestionSubject.subject_code,
    ).join(
        SubCategory, KnowledgePoint.sub_category_id == SubCategory.id
    ).join(
        QuestionSubject, SubCategory.subject_id == QuestionSubject.subject_id
    ).filter(
        QuestionSubject.status == 1
    ).order_by(
        QuestionSubject.subject_id, KnowledgePoint.sort_order
    ).all()

    if not kp_rows:
        return {"subjects": []}

    point_ids = [r.point_id for r in kp_rows]
    stat_rows = db.query(
        QuestionKnowledge.knowledge_point_id,
        func.count(distinct(QuestionKnowledge.question_id)).label("total"),
        func.count(distinct(PracticeRecord.question_id)).label("done"),
        func.coalesce(
            func.sum(case((PracticeRecord.is_correct == 1, 1), else_=0)), 0
        ).label("corrects"),
        func.count(PracticeRecord.record_id).label("attempts"),
    ).outerjoin(
        PracticeRecord,
        (PracticeRecord.question_id == QuestionKnowledge.question_id) &
        (PracticeRecord.user_id == current_user.user_id)
    ).filter(
        QuestionKnowledge.knowledge_point_id.in_(point_ids)
    ).group_by(
        QuestionKnowledge.knowledge_point_id
    ).all()

    stat_map = {r[0]: r for r in stat_rows}

    subjects, subject_order = {}, []
    for pid, pname, sid, sname, scode in kp_rows:
        if sid not in subjects:
            subjects[sid] = {
                "subject_id": sid,
                "subject_name": sname,
                "subject_code": scode,
                "kps": [],
            }
            subject_order.append(sid)
        st = stat_map.get(pid)
        total = int(st[1]) if st else 0
        if total <= 0:
            continue
        done = int(st[2]) if st else 0
        attempts = int(st[4] or 0) if st else 0
        corrects = int(st[3] or 0) if st else 0
        subjects[sid]["kps"].append({
            "point_id": pid,
            "point_name": pname,
            "total": total,
            "done": done,
            "done_pct": round(done * 100 / total, 1),
            "accuracy": round(corrects * 100 / attempts, 1) if attempts > 0 else 0,
        })

    for sid in subject_order:
        subjects[sid]["kps"].sort(key=lambda k: k["done_pct"])

    return {"subjects": [subjects[sid] for sid in subject_order]}


# 最近记录条目统一结构键（前端契约）
_ALLOWED_SOURCES = ("快速练习", "历年试卷", "小模考", "智能组卷")
_RECORD_PRE_LIMIT = 50  # 各来源预查询上限，内存合并后分页


def _fmt_dt(v):
    """datetime/date → 展示字符串；None 透传"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _recency_dt(v):
    """统一排序键（date 归一化为当日零点）"""
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    return datetime.min


@router.get("/recent-records", summary="多来源最近做题记录")
async def get_recent_records(
    source: Optional[str] = Query(None, pattern="^(快速练习|历年试卷|小模考|智能组卷)$"),
    status: Optional[str] = Query(None, pattern="^(completed|in_progress)$"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    UNION 四来源最近做题记录（读时聚合，不改任何写入路径）：
    - 历年试卷: exam_record(SELF_TEST) LEFT JOIN year_paper 取真题标题
    - 小模考:   exam_record(MOCK_EXAM) JOIN exam_paper
    - 智能组卷: smart_exam_record（状态/得分/断点字段现成）
    - 快速练习: practice_record(source_type='快速练习') 按 日期+科目 聚合
    跳转映射严格遵循规格 §5（真实路由）。
    """
    uid = current_user.user_id
    want = set(_ALLOWED_SOURCES) if source is None else {source}
    merged = []

    exam_rows = []  # (record, name, badge_source)

    if "历年试卷" in want:
        past_q = (
            db.query(ExamRecord, ExamPaper.paper_name, YearPaper.paper_title)
            .outerjoin(YearPaper, YearPaper.record_id == ExamRecord.record_id)
            .outerjoin(ExamPaper, ExamPaper.paper_id == ExamRecord.paper_id)
            .filter(
                ExamRecord.user_id == uid,
                ExamRecord.exam_type == "SELF_TEST",
            )
            .order_by(desc(func.coalesce(ExamRecord.submit_time, ExamRecord.start_time)))
            .limit(_RECORD_PRE_LIMIT)
        ).all()
        for er, paper_name, yp_title in past_q:
            name = yp_title or paper_name or "历年试卷"
            exam_rows.append((er, name, "历年试卷"))

    if "小模考" in want:
        mock_q = (
            db.query(ExamRecord, ExamPaper.paper_name)
            .outerjoin(ExamPaper, ExamPaper.paper_id == ExamRecord.paper_id)
            .filter(
                ExamRecord.user_id == uid,
                ExamRecord.exam_type == "MOCK_EXAM",
            )
            .order_by(desc(func.coalesce(ExamRecord.submit_time, ExamRecord.start_time)))
            .limit(_RECORD_PRE_LIMIT)
        ).all()
        for er, paper_name in mock_q:
            exam_rows.append((er, paper_name or "小模考", "小模考"))

    # 试卷类共用的每记录题目数/正确数
    exam_ids = [er.record_id for er, _, _ in exam_rows]
    detail_stats = {}
    if exam_ids:
        for rid, cnt, corr in db.query(
            ExamAnswerDetail.record_id,
            func.count(ExamAnswerDetail.detail_id),
            func.coalesce(func.sum(ExamAnswerDetail.is_correct), 0),
        ).filter(
            ExamAnswerDetail.record_id.in_(exam_ids)
        ).group_by(ExamAnswerDetail.record_id).all():
            detail_stats[rid] = (int(cnt or 0), int(corr or 0))

    for er, name, badge in exam_rows:
        completed = bool(er.is_completed)
        q_cnt, q_corr = detail_stats.get(er.record_id, (0, 0))
        rec_dt = er.submit_time or er.end_time or er.start_time
        if completed:
            jump = {"path": "/paper-result", "params": {"record_id": er.record_id}}
        else:
            jump = {
                "path": "/paper-answer",
                "params": {"record_id": er.record_id, "paper_id": er.paper_id},
            }
        merged.append({
            "record_key": f"exam_{er.record_id}",
            "source": badge,
            "name": name,
            "status": "completed" if completed else "in_progress",
            "score": float(er.total_score or 0),
            "accuracy": round(q_corr * 100 / q_cnt, 1) if q_cnt > 0 else 0,
            "question_count": q_cnt,
            "time_spent_seconds": int(er.duration_used or 0),
            "started_at": _fmt_dt(er.start_time),
            "completed_at": _fmt_dt(rec_dt),
            "jump": jump,
            "_sort": _recency_dt(rec_dt),
        })

    if "智能组卷" in want:
        srows = db.query(SmartExamRecord).filter(
            SmartExamRecord.user_id == uid
        ).order_by(
            desc(SmartExamRecord.create_time)
        ).limit(_RECORD_PRE_LIMIT).all()
        for s in srows:
            completed = (s.status == "completed")
            merged.append({
                "record_key": f"smart_{s.id}",
                "source": "智能组卷",
                "name": s.paper_name or "智能组卷",
                "status": "completed" if completed else "in_progress",
                "score": float(s.earned_score) if s.earned_score is not None else None,
                "accuracy": None,
                "question_count": int(s.total_questions or 0),
                "time_spent_seconds": int(s.time_spent or 0),
                "started_at": _fmt_dt(s.start_time),
                "completed_at": _fmt_dt(s.end_time or s.create_time),
                "jump": {
                    "path": "/smart-answer",
                    "params": {
                        "paper_id": s.paper_id,
                        "record_id": s.id,
                        "paper_name": s.paper_name or "",
                    },
                },
                "_sort": _recency_dt(s.end_time or s.create_time or s.start_time),
            })

    if "快速练习" in want:
        # 跳转参数需用 exercise 页约定的科目键(xc/sl/ga)；
        # 种子数据的 subject_code 可能为 auto_* 形式，不能直接透传
        _cat_by_id = {1: "xc", 2: "sl", 3: "ga"}
        subj_map = {
            s.subject_id: (s.subject_name, s.subject_code)
            for s in db.query(QuestionSubject).all()
        }
        qrows = (
            db.query(
                PracticeRecord.practice_date,
                PracticeRecord.subject_id,
                func.count(PracticeRecord.record_id),
                func.coalesce(func.sum(PracticeRecord.is_correct), 0),
                func.coalesce(func.sum(PracticeRecord.time_spent), 0),
            )
            .filter(
                PracticeRecord.user_id == uid,
                PracticeRecord.source_type == "快速练习",
                PracticeRecord.practice_date.isnot(None),
            )
            .group_by(
                PracticeRecord.practice_date, PracticeRecord.subject_id
            )
            .order_by(desc(PracticeRecord.practice_date))
            .limit(_RECORD_PRE_LIMIT)
        ).all()
        for d, sid, cnt, corr, secs in qrows:
            sname, scode = subj_map.get(sid, ("综合", ""))
            merged.append({
                "record_key": f"qp_{d.isoformat()}_{sid}",
                "source": "快速练习",
                "name": f"{d.month}月{d.day}日·{sname}·快速练习",
                "status": "completed",
                "score": None,
                "accuracy": round(int(corr or 0) * 100 / int(cnt or 1), 1),
                "question_count": int(cnt or 0),
                "time_spent_seconds": int(secs or 0),
                "started_at": _fmt_dt(d),
                "completed_at": _fmt_dt(d),
                "jump": {"path": "/exercise",
                         "params": {"subject": _cat_by_id.get(sid, scode or "")}},
                "_sort": _recency_dt(d),
            })

    if status is not None:
        merged = [m for m in merged if m["status"] == status]

    merged.sort(key=lambda m: m["_sort"], reverse=True)
    total = len(merged)
    page_items = [
        {k: v for k, v in m.items() if k != "_sort"}
        for m in merged[offset:offset + limit]
    ]

    return {"total": total, "limit": limit, "offset": offset, "items": page_items}
