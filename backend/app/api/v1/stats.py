from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

from fastapi import APIRouter, Depends,Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.database import get_db
from ...models.models import (
    PracticeRecord,
    ExamRecord,
    DailyCheckin,
    StudyGoal,
    SysUser
)

from ...core.security import get_current_user

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