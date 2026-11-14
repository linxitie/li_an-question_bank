from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from fastapi import APIRouter, Depends,Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ....core.database import get_db
from ....models.models import (
    PracticeRecord,
    ExamRecord,
    DailyCheckin,
    StudyGoal,
    SysUser,
    CoinRecord,
    QuestionType
)

from ....core.security import get_current_user, get_optional_user
from ....services import growth_service, weakpoint_reader
from ....services.growth_service import add_growth, get_level_info, GROWTH_RULES
from ....services.coin_ledger import grant as grant_coins

router = APIRouter(prefix="/api/stats",tags=["学习统计"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=Dict[str, Any], summary="学习统计概览")
async def get_study_stats(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取用户整体学习统计数据

    包含：今日/本周/本月/累计刷题量、正确率、学习时长、连续签到天数
    """
    now = datetime.now()
    today = now.date()
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    # 今日刷题数
    today_questions = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id,
        func.DATE(PracticeRecord.practice_time) == today
    ).count()

    # 本周刷题数
    weekly_questions = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_time >= week_start
    ).count()

    # 本月刷题数
    monthly_questions = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_time >= month_start
    ).count()

    # 累计刷题数
    total_questions = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id
    ).count()

    # 正确率（基于练习记录）
    correct_count = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.is_correct == 1
    ).count()

    accuracy_rate = round(correct_count / total_questions * 100, 1) if total_questions > 0 else 0

    # 总学习时长（分钟）
    total_study_time = db.query(
        func.coalesce(func.sum(PracticeRecord.time_spent), 0)
    ).filter(
        PracticeRecord.user_id == current_user.user_id
    ).scalar() or 0

    study_hours = round(total_study_time / 60, 1)  # 转为小时

    # 连续签到天数
    today_checkin = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id,
        DailyCheckin.checkin_date == today.strftime("%Y-%m-%d")
    ).first()

    streak = today_checkin.continuous_days if today_checkin else 0

    # 考试记录统计
    exam_records = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id
    ).all()

    exam_count = len(exam_records)
    exam_avg_score = round(
        sum(float(r.total_score) for r in exam_records if r.is_completed) /
        max(sum(1 for r in exam_records if r.is_completed), 1),
        1
    ) if exam_records else 0

    # 目标完成统计
    total_goals = db.query(StudyGoal).filter(
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.status == 1
    ).count()

    completed_goals = db.query(StudyGoal).filter(
        StudyGoal.user_id == current_user.user_id,
        StudyGoal.is_completed == 1,
        StudyGoal.status == 1
    ).count()

    return {
        "todayQuestions": today_questions,
        "weeklyQuestions": weekly_questions,
        "monthlyQuestions": monthly_questions,
        "totalQuestions": total_questions,
        "accuracyRate": accuracy_rate,
        "totalStudyHours": study_hours,
        "streak": streak,
        "examCount": exam_count,
        "examAvgScore": exam_avg_score,
        "totalGoals": total_goals,
        "completedGoals": completed_goals,
        "goalCompletionRate": round(completed_goals / total_goals * 100, 1) if total_goals > 0 else 0,
    }


@router.get("/level", response_model=Dict[str, Any], summary="学习等级与成长值")
async def get_level(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回当前学习等级、称号、成长值、进度"""
    return get_level_info(current_user.growth_points or 0)


@router.get("/weekly", response_model=Dict[str, Any], summary="每周学习统计")
async def get_weekly_stats(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取最近7天的详细学习统计

    包含：每日刷题数、正确率趋势、连续打卡
    """
    week_start = datetime.now() - timedelta(days=7)

    # 本周刷题记录
    weekly_records = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_time >= week_start
    ).all()

    questions_done = len(weekly_records)
    correct_count = sum(1 for r in weekly_records if r.is_correct)
    accuracy = round(correct_count / questions_done * 100, 1) if questions_done > 0 else 0

    # 学习时长（小时）
    study_minutes = sum(r.time_spent or 0 for r in weekly_records)
    study_hours = round(study_minutes / 60, 1)

    # 连续签到（从 DailyCheckin 表获取）
    today = datetime.now().date()
    today_checkin = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id,
        DailyCheckin.checkin_date == today.strftime("%Y-%m-%d")
    ).first()

    streak = today_checkin.continuous_days if today_checkin else 0

    # 每日刷题趋势（最近7天）
    daily_trend = []
    for i in range(7):
        date = today - timedelta(days=6 - i)
        day_count = db.query(PracticeRecord).filter(
            PracticeRecord.user_id == current_user.user_id,
            func.DATE(PracticeRecord.practice_time) == date
        ).count()

        day_correct = db.query(PracticeRecord).filter(
            PracticeRecord.user_id == current_user.user_id,
            PracticeRecord.is_correct == 1,
            func.DATE(PracticeRecord.practice_time) == date
        ).count()

        has_checkin = db.query(DailyCheckin).filter(
            DailyCheckin.user_id == current_user.user_id,
            DailyCheckin.checkin_date == date.strftime("%Y-%m-%d")
        ).first() is not None

        daily_trend.append({
            "date": date.strftime("%m-%d"),
            "weekday": ["一", "二", "三", "四", "五", "六", "日"][date.weekday()],
            "questionsDone": day_count,
            "correctCount": day_correct,
            "accuracy": round(day_correct / day_count * 100, 1) if day_count > 0 else 0,
            "checkedIn": has_checkin,
        })

    return {
        "questionsDone": questions_done,
        "studyHours": study_hours,
        "accuracy": accuracy,
        "streak": streak,
        "dailyTrend": daily_trend,
    }

@router.get("/learning-report", response_model=Dict[str, Any], summary="学习报告（周/月真实聚合）")
async def get_learning_report(
        period: str = Query("week", pattern="^(day|week|month)$",
                            description="day=昨天一整天；week=最近 7 天；month=最近 30 天"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """学习报告：时长/题量/正确率/趋势/短板，全部来自 practice_record 真实聚合。

    为什么要新增这个接口：study_plan.vue 的「学习报告」原先写死 326 分钟 / 148 题 /
    78% 等前端模拟数，用户看到的是假数据。这里用三条聚合 SQL 出真值，
    不再逐个日期循环查询（旧 /weekly 是 7 天 × 3 次查询，月报会放大到 90 次）。
    """
    days = 1 if period == "day" else (7 if period == "week" else 30)
    now = datetime.now()
    # day 的语义是「昨天一整天」而不是「最近 24 小时」：AI 教练日报的四个数字
    # （昨日学习/正确率/完成题目/连续打卡）必须能和日历对得上，故用自然日窗口。
    if period == "day":
        window_end = datetime(now.year, now.month, now.day)
        window_start = window_end - timedelta(days=1)
    else:
        window_end = now
        window_start = now - timedelta(days=days)

    totals = db.query(
        func.count(PracticeRecord.record_id),
        func.coalesce(func.sum(PracticeRecord.time_spent), 0),
        func.coalesce(func.sum(func.coalesce(PracticeRecord.is_correct, 0)), 0),
        func.count(PracticeRecord.is_correct)
    ).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_time >= window_start,
        PracticeRecord.practice_time < window_end
    ).one()
    questions_done = int(totals[0] or 0)
    study_minutes = int(totals[1] or 0)
    correct_count = int(totals[2] or 0)
    graded_count = int(totals[3] or 0)
    accuracy = round(correct_count / graded_count * 100, 1) if graded_count else 0.0

    # 按日聚合一次，趋势与标签都在内存里切，避免逐日查库
    day_rows = db.query(
        func.date(PracticeRecord.practice_time).label("d"),
        func.count(PracticeRecord.record_id),
        func.coalesce(func.sum(func.coalesce(PracticeRecord.is_correct, 0)), 0),
        func.count(PracticeRecord.is_correct)
    ).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_time >= (now - timedelta(days=7) if period == "day" else window_start)
    ).group_by("d").all()
    day_map = {str(r[0]): (int(r[1] or 0), int(r[2] or 0), int(r[3] or 0)) for r in day_rows}

    def _acc(q: int, c: int, graded: int) -> float:
        return round(c / graded * 100, 1) if graded else 0.0

    trend: List[float] = []
    labels: List[str] = []
    if period in ("week", "day"):
        for i in range(7):
            date = (now - timedelta(days=6 - i)).date()
            q, c, g = day_map.get(str(date), (0, 0, 0))
            trend.append(_acc(q, c, g))
            labels.append(["一", "二", "三", "四", "五", "六", "日"][date.weekday()])
    else:
        # 30 天切成 4 个 7 天桶（最后一桶含今天及其前 8 天），判断的是"最近四周走势"
        for bucket in range(4):
            end = now - timedelta(days=7 * (3 - bucket))
            start = end - timedelta(days=7)
            q = c = g = 0
            for offset in range(7):
                date = (start + timedelta(days=offset + 1)).date()
                dq, dc, dg = day_map.get(str(date), (0, 0, 0))
                q += dq
                c += dc
                g += dg
            trend.append(_acc(q, c, g))
            labels.append(f"第{bucket + 1}周")

    # 短板：按子科目聚合，样本 >=3 题且正确率最低的 3 个（无子科目的记录不计）
    # 短板用「至少 30 天」的窗口：day 视图只有 1 天样本时几乎必然为空，
    # 而用户要的是「我现在该补什么」，用 30 天更稳定（week/month 不变）。
    weak_window_start = min(window_start, now - timedelta(days=30))
    weak_rows = db.query(
        PracticeRecord.sub_category_id,
        func.count(PracticeRecord.record_id),
        func.coalesce(func.sum(func.coalesce(PracticeRecord.is_correct, 0)), 0),
        func.count(PracticeRecord.is_correct)
    ).filter(
        PracticeRecord.user_id == current_user.user_id,
        PracticeRecord.practice_time >= weak_window_start,
        PracticeRecord.practice_time < now,
        PracticeRecord.sub_category_id.isnot(None)
    ).group_by(PracticeRecord.sub_category_id).all()

    from ....models.models import SubCategory  # 局部导入：避免顶层 import 分组变化

    subcat_names = {
        row[0]: row[1]
        for row in db.query(SubCategory.id, SubCategory.name).filter(
            SubCategory.id.in_([r[0] for r in weak_rows] or [0])
        ).all()
    }
    weak_pool = []
    for sid, q, c, g in weak_rows:
        if int(g or 0) < 3:
            continue
        weak_pool.append({
            "name": subcat_names.get(sid) or f"子科目{sid}",
            "rate": _acc(int(q or 0), int(c or 0), int(g or 0)),
        })
    weak_pool.sort(key=lambda item: item["rate"])
    weak = weak_pool[:3]

    checkin = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id
    ).order_by(DailyCheckin.checkin_date.desc()).first()
    streak = checkin.continuous_days if checkin else 0

    # 结论文案由数据决定，不编造：没数据时说没数据
    scope_text = "昨天" if period == "day" else f"最近 {days} 天"
    if questions_done == 0:
        comment = f"{scope_text}还没有练习记录，先做 20 道题，报告就会有内容。"
    else:
        head = (f"{scope_text}做了 {questions_done} 题，正确率 {accuracy}%，"
                f"累计 {study_minutes} 分钟")
        if weak:
            comment = head + "；短板：" + "、".join(f"{w['name']}({w['rate']}%)" for w in weak) + "，建议优先加练。"
        else:
            comment = head + "；样本还不够定位短板，继续积累到每科 3 题以上。"

    return {
        "period": period,
        "days": days,
        "minutes": study_minutes,
        "questions": questions_done,
        "accuracy": accuracy,
        "streak": streak,
        "trend": trend,
        "labels": labels,
        "weak": weak,
        "comment": comment,
    }


@router.get("/all-time", response_model=Dict[str, Any], summary="全时段学习统计")
async def get_all_time_stats(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取**全部历史**的学习统计（不只是最近 7 天）

    与 `/weekly` 的区别：weekly 只看近 7 天，本接口覆盖用户自注册以来的
    全部练习记录，并按跨度自适应选择时间桶粒度，避免把几年的数据压进
    一张图导致 x 轴标签糊成一片。

    设计要点
    --------
    1. **按 practice_date 分桶，而非 DATE(practice_time)**：
       practice_date 是入库时落库的纯 Date 字段（实测 100% 填充），
       跨时区/夏令时场景下用 DATE(practice_time) 分组容易把凌晨记录
       划到错误日期。与 goal_progress 的口径保持一致。
    2. **粒度自适应**：跨度 ≤90 天按日、≤2 年按月、更长按年。
    3. **单条 group by 查询**：不分 N 次查询，桶数上限即粒度数量。
    4. **只返回聚合结果**，不含逐条记录，避免响应体随历史线性膨胀。
    """
    uid = current_user.user_id

    # 先取跨度，用于决定粒度。min/max 走 idx_practice_date 索引。
    span = db.query(
        func.min(PracticeRecord.practice_date),
        func.max(PracticeRecord.practice_date),
        func.count(PracticeRecord.record_id),
        func.sum(PracticeRecord.is_correct),
        func.coalesce(func.sum(PracticeRecord.time_spent), 0),
    ).filter(PracticeRecord.user_id == uid).one()

    first_date, last_date, total, correct_sum, seconds_sum = span
    total = int(total or 0)
    correct_sum = int(correct_sum or 0)
    seconds_sum = int(seconds_sum or 0)

    total_minutes = round(seconds_sum / 60)
    accuracy = round(correct_sum / total * 100, 1) if total > 0 else 0

    base = {
        "totalCount": total,
        "correctCount": correct_sum,
        # 同时给出精确秒数与便于展示的分钟数：只有 minutes 时，
        # 前端无法把各桶的 seconds 合计与总量对账（各桶独立四舍五入会累积误差）。
        "totalSeconds": seconds_sum,
        "totalMinutes": total_minutes,
        "totalHours": round(total_minutes / 60, 1),
        "accuracy": accuracy,
        "firstDate": first_date.isoformat() if first_date else None,
        "lastDate": last_date.isoformat() if last_date else None,
    }

    # 无任何记录：返回明确的空桶结构，前端据此渲染空态而非报错
    if not total or first_date is None or last_date is None:
        base.update({"granularity": "day", "spanDays": 0, "buckets": []})
        return base

    span_days = (last_date - first_date).days
    if span_days <= 90:
        granularity, fmt = "day", "%Y-%m-%d"
    elif span_days <= 730:
        granularity, fmt = "month", "%Y-%m"
    else:
        granularity, fmt = "year", "%Y"

    rows = db.query(
        func.strftime(fmt, PracticeRecord.practice_date).label("period"),
        func.count(PracticeRecord.record_id),
        func.sum(PracticeRecord.is_correct),
        func.coalesce(func.sum(PracticeRecord.time_spent), 0),
    ).filter(
        PracticeRecord.user_id == uid,
        PracticeRecord.practice_date.isnot(None),
    ).group_by("period").order_by("period").all()

    buckets = [
        {
            "period": r[0],
            "count": int(r[1] or 0),
            "correct": int(r[2] or 0),
            "accuracy": round(int(r[2] or 0) / int(r[1] or 1) * 100, 1) if r[1] else 0,
            # 同时给出精确秒数与便于展示的分钟数。
            # 只给 minutes 会出现「各桶分钟数之和对不上总分钟数」——
            # 每个桶独立四舍五入会累积误差（60+120+30=210s 时分桶得 1+2+0=3，
            # 而总量 round(3.5)=4）。前端若要合计请用 seconds。
            "seconds": int(r[3] or 0),
            "minutes": round(int(r[3] or 0) / 60),
        }
        for r in rows if r[0]
    ]

    base.update({"granularity": granularity, "spanDays": span_days, "buckets": buckets})
    return base


@router.get("/type-mastery", response_model=List[Dict[str, Any]], summary="题型维度掌握度")
async def get_type_mastery(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    按题型统计**用户维度**的掌握情况。

    与其他易混接口的区别（务必分清）：
    - `/api/questions` 里的按题型计数：统计**题库库存量**（每个题型有多少道题），
      与用户练没练过无关。
    - `/api/practice/type-summary`：按**科目 + 子科目**统计（行测/申论/公专下的
      二级分类进度），并非 type_id 维度。
    - 本接口：**题型（type_id）** 维度上，用户**实际练过多少、正确多少**。

    只返回用户实际练习过的题型；未练过的题型不占位，避免前端出现一排 0%。
    """
    rows = (
        db.query(
            PracticeRecord.type_id,
            QuestionType.type_name,
            QuestionType.sort_order,
            func.count(PracticeRecord.record_id),
            func.sum(PracticeRecord.is_correct),
            func.coalesce(func.sum(PracticeRecord.time_spent), 0),
            func.max(PracticeRecord.practice_date),
        )
        .join(QuestionType, PracticeRecord.type_id == QuestionType.type_id, isouter=True)
        .filter(
            PracticeRecord.user_id == current_user.user_id,
            PracticeRecord.type_id.isnot(None),
        )
        .group_by(PracticeRecord.type_id, QuestionType.type_name, QuestionType.sort_order)
        # 排序：先按 sort_order 升序；`is_(None)` 为真的行（历史记录关联到
        # 已被删除的题型，outer join 后 sort_order 为 NULL）排到最后。
        # 不加这一段的话 SQLite 把 NULL 视为最小值，孤儿题型会占据列表首位，
        # 把真实题型全部挤到下面。
        .order_by(QuestionType.sort_order.is_(None), QuestionType.sort_order)
        .all()
    )

    items = []
    for r in rows:
        count = int(r[3] or 0)
        correct = int(r[4] or 0)
        items.append({
            "typeId": r[0],
            # 历史记录可能关联到已被删除的题型，outer join 下 type_name 为 NULL，
            # 回退为可读占位而不是把该行丢掉（丢掉会让用户的练习量凭空消失）
            "typeName": r[1] or f"未知题型({r[0]})",
            "count": count,
            "correct": correct,
            "wrong": count - correct,
            "accuracy": round(correct / count * 100, 1) if count > 0 else 0,
            "minutes": round(int(r[5] or 0) / 60),
            "lastPracticeDate": r[6].isoformat() if r[6] else None,
        })
    return items


@router.get("/calendar", response_model=List[Dict[str, Any]], summary="考试日历")
async def get_exam_calendar(
        db: Session = Depends(get_db)
):
    """
    获取考试日历数据

    包含：模拟考试、报名截止、招考信息等
    """
    # 从数据库获取已发布考试
    upcoming_exams = db.query(ExamRecord).filter(
        ExamRecord.is_completed == 0
    ).limit(10).all() if hasattr(ExamRecord, 'paper_id') else []

    # 静态考试日历 + 动态数据
    calendar = [
        {"date": "2026-06-15", "title": "公安联考模拟考试", "type": "exam"},
        {"date": "2026-06-20", "title": "报名截止", "type": "deadline"},
        {"date": "2026-07-01", "title": "省考报名开始", "type": "registration"},
        {"date": "2026-07-15", "title": "国考报名开始", "type": "registration"},
        {"date": "2026-12-20", "title": "公安联考", "type": "exam"},
    ]

    return calendar


@router.get("/messages", response_model=List[Dict[str, Any]], summary="系统消息")
async def get_system_messages(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(5, ge=1, le=50, description="每页数量")
):
    """
    获取系统通知消息

    未来可从数据库 sys_operation_log 或专门的通知表获取
    """
    messages = [
        {
            "id": 1,
            "title": "考试通知",
            "content": "2026年公安联考报名即将开始，请做好准备",
            "type": "info",
            "createdAt": "2026-05-10T10:00:00"
        },
        {
            "id": 2,
            "title": "重要提醒",
            "content": "模拟考试成绩已公布，请登录查看",
            "type": "success",
            "createdAt": "2026-05-08T14:30:00"
        },
        {
            "id": 3,
            "title": "系统更新",
            "content": "题库已更新，新增100道公安专业知识题目",
            "type": "info",
            "createdAt": "2026-05-05T09:00:00"
        },
    ]

    # 分页
    total = len(messages)
    start = (page - 1) * page_size
    end = start + page_size

    return messages[start:end]


@router.get("/dashboard", response_model=Dict[str, Any], summary="仪表盘数据")
async def get_dashboard(
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    获取仪表盘综合数据

    包含：今日/本周/总计刷题量、正确率、本月学习天数、连续签到天数
    """
    if current_user is None:
        return {"todayQuestions": 0, "weeklyQuestions": 0, "monthlyQuestions": 0,
                "totalQuestions": 0, "accuracyRate": 0, "totalStudyHours": 0,
                "streak": 0, "examCount": 0, "examAvgScore": 0,
                "totalGoals": 0, "completedGoals": 0, "goalCompletionRate": 0,
                # 薄弱点为附加字段，未登录时返回空集合而不是报错（E13 读链路兜底）
                "weakPoints": []}

    now = datetime.now()
    today = now.date()
    week_start = now - timedelta(days=7)
    month_start = now.replace(day=1)

    # 今日刷题数
    today_questions = (
        db.query(PracticeRecord)
        .filter(
            PracticeRecord.user_id == current_user.user_id,
            func.DATE(PracticeRecord.practice_time) == today,
        )
        .count()
    )

    # 本周刷题数
    weekly_questions = (
        db.query(PracticeRecord)
        .filter(
            PracticeRecord.user_id == current_user.user_id,
            PracticeRecord.practice_time >= week_start,
        )
        .count()
    )

    # 累计刷题数
    total_questions = (
        db.query(PracticeRecord)
        .filter(PracticeRecord.user_id == current_user.user_id)
        .count()
    )

    # 正确率
    correct_count = (
        db.query(PracticeRecord)
        .filter(
            PracticeRecord.user_id == current_user.user_id,
            PracticeRecord.is_correct == 1,
        )
        .count()
    )
    accuracy_rate = round(correct_count / total_questions * 100, 1) if total_questions > 0 else 0

    # 本月学习天数（当月有刷题记录的天数）
    month_days_query = (
        db.query(func.DATE(PracticeRecord.practice_time))
        .filter(
            PracticeRecord.user_id == current_user.user_id,
            PracticeRecord.practice_time >= month_start,
        )
        .group_by(func.DATE(PracticeRecord.practice_time))
    )
    month_days = month_days_query.count()

    # 连续签到天数
    today_checkin = (
        db.query(DailyCheckin)
        .filter(
            DailyCheckin.user_id == current_user.user_id,
            DailyCheckin.checkin_date == today.strftime("%Y-%m-%d"),
        )
        .first()
    )
    streak_days = today_checkin.continuous_days if today_checkin else (current_user.continuous_checkin_days or 0)

    return {
        "todayQuestions": today_questions,
        "weeklyQuestions": weekly_questions,
        "totalQuestions": total_questions,
        "accuracyRate": accuracy_rate,
        "monthDays": month_days,
        "streakDays": streak_days,
        # ⑧ 薄弱点唯一输出口径；⑤ 推荐位不 import 本 api 模块，而是复用同一个
        # weakpoint_reader 服务（E13 是读依赖，不是写依赖）。
        "weakPoints": weakpoint_reader.get_weakpoints(db, current_user.user_id),
    }


@router.get("/practice-trend", response_model=Dict[str, Any], summary="练习趋势")
async def get_practice_trend(
    days: int = Query(7, ge=7, le=30, description="统计天数(7或30)"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取练习趋势数据

    按天统计最近7天或30天的刷题量和正确率趋势
    """
    now = datetime.now()
    today = now.date()
    trend_start = now - timedelta(days=days)

    daily_trend = []
    for i in range(days):
        date = today - timedelta(days=days - 1 - i)

        day_count = (
            db.query(PracticeRecord)
            .filter(
                PracticeRecord.user_id == current_user.user_id,
                func.DATE(PracticeRecord.practice_time) == date,
            )
            .count()
        )

        day_correct = (
            db.query(PracticeRecord)
            .filter(
                PracticeRecord.user_id == current_user.user_id,
                PracticeRecord.is_correct == 1,
                func.DATE(PracticeRecord.practice_time) == date,
            )
            .count()
        )

# 单日累计用时（秒）：PracticeRecord.time_spent 为整型秒数，缺失时按 0 计入
        day_seconds = (
            db.query(func.coalesce(func.sum(PracticeRecord.time_spent), 0))
            .filter(
                PracticeRecord.user_id == current_user.user_id,
                func.DATE(PracticeRecord.practice_time) == date,
            )
            .scalar()
            or 0
        )

        daily_trend.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "questionsDone": day_count,
                "correctCount": day_correct,
                "accuracy": round(day_correct / day_count * 100, 1) if day_count > 0 else 0,
                "timeSpent": int(day_seconds),
            }
        )

    return {"days": days, "trend": daily_trend}


# ========== 自动签到公共函数（供其他模块调用） ==========

def ensure_daily_checkin(user_id: int, db: Session) -> bool:
    """
    自动签到：检查用户当日是否已签到，未签到则自动签到。
    每个自然日（北京时间 0:00 - 23:59:59）仅记录一次。
    返回 True 表示签到成功（或已签到），False 表示失败。
    """
    from datetime import date as date_obj
    today_str = date_obj.today().strftime("%Y-%m-%d")

    # 检查是否已签到
    existing = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == user_id,
        DailyCheckin.checkin_date == today_str
    ).first()

    if existing:
        # 今日已签到，不重复计数
        return True

    # 查询用户连续签到天数
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        logger.warning(f"自动签到失败：用户 {user_id} 不存在")
        return False

    # 计算连续天数
    yesterday_str = (date_obj.today() + timedelta(days=-1)).strftime("%Y-%m-%d")
    yesterday_checkin = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == user_id,
        DailyCheckin.checkin_date == yesterday_str
    ).first()

    if yesterday_checkin:
        continuous_days = yesterday_checkin.continuous_days + 1
    else:
        continuous_days = 1

    total_days = (user.total_checkin_days or 0) + 1

    # 计算金币奖励：基础5币 + 连续满7天额外20币
    base_coins = 5
    streak_bonus = 20 if (continuous_days % 7 == 0) else 0
    coin_reward = base_coins + streak_bonus

    # 创建签到记录
    checkin = DailyCheckin(
        user_id=user_id,
        checkin_date=today_str,
        checkin_time=datetime.now(),
        continuous_days=continuous_days,
        total_days=total_days,
        has_makeup=0,
        coin_reward=coin_reward,
        streak_bonus=streak_bonus
    )
    db.add(checkin)

    # 更新用户签到统计 + 发放金币
    user.continuous_checkin_days = continuous_days
    user.total_checkin_days = total_days
    if coin_reward > 0:
        # 2026-11-04 M1：走金币台账，生成批次以支持 12 个月到期清零
        grant_coins(
            db,
            user,
            coin_reward,
            source_type="CHECKIN",
            description="每日签到奖励" + (f"（连续{continuous_days}天）" if streak_bonus else ""),
        )
    # 成长值
    add_growth(db, user, GROWTH_RULES["checkin"])
    if streak_bonus:
        add_growth(db, user, GROWTH_RULES["checkin_7day"])
    db.commit()

    # 触发成就判定（学习坚持类）
    try:
        from ....services import achievement_service
        achievement_service.check_and_grant(user_id, "sign_in", db)
    except Exception as e:
        logger.warning(f"签到成就判定失败: {e}")

    logger.info(f"自动签到成功: user_id={user_id}, 连续{continuous_days}天, 奖励{coin_reward}金币")
    return True


@router.post("/auto-checkin", summary="自动签到（核心行为触发）")
async def auto_checkin(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    由各核心功能行为触发（答题、看新闻、导入题目等）。
    每个自然日仅签到一次，重复调用无副作用。
    返回：{ checked_in: true/false, continuous_days: N, is_today_first: true/false }
    """
    from datetime import date as date_obj
    today_str = date_obj.today().strftime("%Y-%m-%d")

    # 检查今日是否已签到
    existing = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id,
        DailyCheckin.checkin_date == today_str
    ).first()

    is_first = not bool(existing)
    success = ensure_daily_checkin(current_user.user_id, db)

    # 获取最新连续天数
    days = existing.continuous_days if existing else 1
    if not existing and success:
        # 查询刚创建的记录
        latest = db.query(DailyCheckin).filter(
            DailyCheckin.user_id == current_user.user_id
        ).order_by(DailyCheckin.checkin_id.desc()).first()
        if latest:
            days = latest.continuous_days

    return {
        "checked_in": success,
        "is_today_first": is_first,
        "continuous_days": days,
        "message": "今日已签到 ✓" if not is_first else "签到成功！连续" + str(days) + "天"
    }


@router.get("/weekly-checkin", summary="获取本周签到数据")
async def get_weekly_checkin(
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    获取本周（周一至周日）签到状态，用于前端日历展示
    返回 7 天签到状态：[{dayOfWeek: 1-7, date: 'YYYY-MM-DD', signed: true/false}]
    """
    if current_user is None:
        return {"weekDays": [], "streakDays": 0, "weekSigned": 0, "progressPercent": 0}

    from datetime import date as date_obj
    today = date_obj.today()
    # 计算本周一
    monday = today - timedelta(days=today.weekday())

    # 查询本周签到记录
    records = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id,
        DailyCheckin.checkin_date >= monday.strftime("%Y-%m-%d"),
        DailyCheckin.checkin_date <= today.strftime("%Y-%m-%d")
    ).all()

    signed_dates = {r.checkin_date for r in records}
    total_signed = len(signed_dates)

    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        is_today = date_str == today.strftime("%Y-%m-%d")
        is_future = d > today
        days.append({
            "dayOfWeek": i + 1,  # 1=周一, 7=周日
            "date": date_str,
            "signed": date_str in signed_dates,
            "isToday": is_today,
            "isFuture": is_future
        })

    return {
        "weekStart": monday.strftime("%Y-%m-%d"),
        "weekEnd": (monday + timedelta(days=6)).strftime("%Y-%m-%d"),
        "totalSigned": total_signed,
        "progress": round(total_signed / 7 * 100),
        "days": days
    }


@router.get("/subject-distribution", summary="科目题量比例（饼图/环形图）")
async def get_subject_distribution(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """按科目聚合做题量与对错数量，供「我的」页饼图 + 对错环形图。

    口径与 `/api/practice/unified-stats` 保持一致（合并统计范围）：
      - 刷题流水：practice_record（全部 source_type）
      - 试卷作答：exam_answer_detail JOIN exam_record，并排除智能组卷关联的 exam_record
    SQL 固定 3 条；不逐科目循环。
    """
    from ....models.models import QuestionBank, QuestionSubject, ExamAnswerDetail, SmartExamRecord

    user_id = current_user.user_id
    acc: Dict[int, Dict[str, int]] = {}

    def _cell(sid) -> Dict[str, int]:
        return acc.setdefault(int(sid), {"total": 0, "correct": 0})

    # ① 刷题流水
    drill = db.query(
        PracticeRecord.subject_id,
        func.count(PracticeRecord.record_id),
        func.coalesce(func.sum(PracticeRecord.is_correct), 0),
    ).filter(
        PracticeRecord.user_id == user_id
    ).group_by(PracticeRecord.subject_id).all()
    for sid, cnt, corr in drill:
        if sid is None:
            continue
        cell = _cell(sid)
        cell["total"] += int(cnt or 0)
        cell["correct"] += int(corr or 0)

    # ② 试卷作答（排除智能组卷关联记录，避免与刷题流水双计）
    smart_ids = [
        r[0] for r in db.query(SmartExamRecord.exam_record_id).filter(
            SmartExamRecord.exam_record_id.isnot(None)
        ).all()
    ]
    paper_q = db.query(
        QuestionBank.subject_id,
        func.count(ExamAnswerDetail.detail_id),
        func.coalesce(func.sum(ExamAnswerDetail.is_correct), 0),
    ).join(
        QuestionBank, QuestionBank.question_id == ExamAnswerDetail.question_id
    ).join(
        ExamRecord, ExamRecord.record_id == ExamAnswerDetail.record_id
    ).filter(
        ExamRecord.user_id == user_id
    )
    if smart_ids:
        paper_q = paper_q.filter(~ExamRecord.record_id.in_(smart_ids))
    for sid, cnt, corr in paper_q.group_by(QuestionBank.subject_id).all():
        if sid is None:
            continue
        cell = _cell(sid)
        cell["total"] += int(cnt or 0)
        cell["correct"] += int(corr or 0)

    # ③ 科目名称
    subjects = {
        int(s.subject_id): s
        for s in db.query(QuestionSubject).filter(QuestionSubject.status == 1).all()
    }

    items = []
    for sid, cell in acc.items():
        subj = subjects.get(sid)
        if not subj or cell["total"] <= 0:
            continue  # 停用科目 / 空科目不进饼图（避免 0 值扇区）
        total = cell["total"]
        correct = min(cell["correct"], total)
        items.append({
            "subject_id": sid,
            "subject_name": subj.subject_name,
            "subject_code": subj.subject_code,
            "total": total,
            "correct": correct,
            "wrong": total - correct,
            "accuracy": round(correct * 100 / total, 1),
        })

    items.sort(key=lambda x: x["total"], reverse=True)
    total_all = sum(i["total"] for i in items)
    correct_all = sum(i["correct"] for i in items)
    for i in items:
        i["ratio"] = round(i["total"] * 100 / max(total_all, 1), 1)

    return {
        "source": "unified",
        "total": total_all,
        "correct": correct_all,
        "wrong": total_all - correct_all,
        "accuracy": round(correct_all * 100 / max(total_all, 1), 1),
        "items": items,
    }