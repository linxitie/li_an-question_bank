"""
成绩记录API模块
提供用户自测/模考成绩查询、错题详情、成绩统计、AI分析预留接口
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ...core.database import get_db
from ...models.models import (
    ExamRecord,
    ExamAnswerDetail,
    ExamPaper,
    QuestionBank,
    SysUser
)
from ...core.security import get_current_user, get_optional_user

router = APIRouter(prefix="/api/exam-records", tags=["成绩记录"])
logger = logging.getLogger(__name__)


@router.get("/self", summary="获取自测成绩记录")
async def get_self_test_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取用户自测成绩记录
    exam_type = 'SELF_TEST' 的考试记录
    """
    query = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id,
        ExamRecord.exam_type == "SELF_TEST",
        ExamRecord.is_completed == 1
    )

    total = query.count()
    records = query.order_by(desc(ExamRecord.submit_time)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # 获取试卷名称
    paper_ids = [r.paper_id for r in records]
    papers = db.query(ExamPaper).filter(ExamPaper.paper_id.in_(paper_ids)).all() if paper_ids else []
    paper_map = {p.paper_id: p for p in papers}

    data = []
    for r in records:
        paper = paper_map.get(r.paper_id)
        max_score = float(paper.total_score) if paper else 100
        accuracy = round(float(r.total_score) / max_score * 100, 1) if max_score > 0 else 0

        data.append({
            "record_id": r.record_id,
            "paper_id": r.paper_id,
            "paper_name": paper.paper_name if paper else "未知试卷",
            "exam_type": r.exam_type,
            "start_time": r.start_time.strftime("%Y-%m-%d %H:%M:%S") if r.start_time else None,
            "submit_time": r.submit_time.strftime("%Y-%m-%d %H:%M:%S") if r.submit_time else None,
            "total_score": float(r.total_score),
            "max_score": max_score,
            "accuracy": accuracy,
            "duration_used": r.duration_used or 0,
            "is_completed": bool(r.is_completed)
        })

    return {"total": total, "page": page, "page_size": page_size, "records": data}


@router.get("/mock", summary="获取模考成绩记录")
async def get_mock_exam_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取用户模拟考试成绩记录
    exam_type = 'MOCK_EXAM' 的考试记录
    """
    query = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id,
        ExamRecord.exam_type == "MOCK_EXAM",
        ExamRecord.is_completed == 1
    )

    total = query.count()
    records = query.order_by(desc(ExamRecord.submit_time)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # 获取试卷名称
    paper_ids = [r.paper_id for r in records]
    papers = db.query(ExamPaper).filter(ExamPaper.paper_id.in_(paper_ids)).all() if paper_ids else []
    paper_map = {p.paper_id: p for p in papers}

    # 计算排名（相对于所有模考用户）
    all_mock_records = db.query(ExamRecord).filter(
        ExamRecord.exam_type == "MOCK_EXAM",
        ExamRecord.is_completed == 1
    ).all()

    data = []
    for r in records:
        paper = paper_map.get(r.paper_id)
        max_score = float(paper.total_score) if paper else 100
        accuracy = round(float(r.total_score) / max_score * 100, 1) if max_score > 0 else 0

        # 计算排名（分数 >= 当前用户分数的人数占比）
        higher_count = sum(1 for rec in all_mock_records if float(rec.total_score) > float(r.total_score))
        total_count = len(all_mock_records) if all_mock_records else 1
        rank_percent = round((1 - higher_count / total_count) * 100, 1)

        data.append({
            "record_id": r.record_id,
            "paper_id": r.paper_id,
            "paper_name": paper.paper_name if paper else "未知试卷",
            "exam_type": r.exam_type,
            "start_time": r.start_time.strftime("%Y-%m-%d %H:%M:%S") if r.start_time else None,
            "submit_time": r.submit_time.strftime("%Y-%m-%d %H:%M:%S") if r.submit_time else None,
            "total_score": float(r.total_score),
            "max_score": max_score,
            "accuracy": accuracy,
            "duration_used": r.duration_used or 0,
            "is_completed": bool(r.is_completed),
            "rank_percent": rank_percent  # 超越前X%
        })

    return {"total": total, "page": page, "page_size": page_size, "records": data}


@router.get("/stats", summary="获取成绩统计")
async def get_exam_stats(
    exam_type: str = Query(None, description="考试类型: SELF_TEST 或 MOCK_EXAM"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取用户成绩统计：最高分、平均分、正确率、超越比例等
    """
    query = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id,
        ExamRecord.is_completed == 1
    )

    if exam_type:
        query = query.filter(ExamRecord.exam_type == exam_type)

    records = query.all()

    if not records:
        return {
            "total_exams": 0,
            "highest_score": 0,
            "average_score": 0,
            "average_accuracy": 0,
            "total_questions": 0,
            "correct_questions": 0,
            "accuracy_rate": 0,
            "rank_percent": None
        }

    # 计算统计数据
    scores = [float(r.total_score) for r in records]
    highest_score = max(scores)
    average_score = round(sum(scores) / len(scores), 1)

    # 获取所有答题详情计算正确率
    record_ids = [r.record_id for r in records]
    answer_details = db.query(ExamAnswerDetail).filter(
        ExamAnswerDetail.record_id.in_(record_ids),
        ExamAnswerDetail.is_correct.isnot(None)
    ).all() if record_ids else []

    total_questions = len(answer_details)
    correct_questions = sum(1 for a in answer_details if a.is_correct == 1)
    accuracy_rate = round(correct_questions / total_questions * 100, 1) if total_questions > 0 else 0

    # 计算排名（模考模式）
    rank_percent = None
    if exam_type == "MOCK_EXAM":
        all_mock = db.query(ExamRecord).filter(
            ExamRecord.exam_type == "MOCK_EXAM",
            ExamRecord.is_completed == 1
        ).all()
        if all_mock:
            my_best = highest_score
            higher_count = sum(1 for r in all_mock if float(r.total_score) > my_best)
            rank_percent = round((1 - higher_count / len(all_mock)) * 100, 1)

    return {
        "total_exams": len(records),
        "highest_score": highest_score,
        "average_score": average_score,
        "average_accuracy": accuracy_rate,
        "total_questions": total_questions,
        "correct_questions": correct_questions,
        "accuracy_rate": accuracy_rate,
        "rank_percent": rank_percent
    }


@router.get("/trend", summary="获取成绩趋势")
async def get_exam_trend(
    exam_type: str = Query("SELF_TEST", description="考试类型"),
    limit: int = Query(10, ge=5, le=30, description="返回条数"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取最近N次成绩趋势，用于图表展示
    """
    records = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id,
        ExamRecord.exam_type == exam_type,
        ExamRecord.is_completed == 1
    ).order_by(desc(ExamRecord.submit_time)).limit(limit).all()

    # 倒序（按时间正序）
    records = list(reversed(records))

    # 获取试卷信息
    paper_ids = [r.paper_id for r in records]
    papers = db.query(ExamPaper).filter(ExamPaper.paper_id.in_(paper_ids)).all() if paper_ids else []
    paper_map = {p.paper_id: p for p in papers}

    trend = []
    for i, r in enumerate(records):
        paper = paper_map.get(r.paper_id)
        max_score = float(paper.total_score) if paper else 100
        accuracy = round(float(r.total_score) / max_score * 100, 1) if max_score > 0 else 0

        trend.append({
            "index": i + 1,
            "record_id": r.record_id,
            "paper_name": paper.paper_name if paper else "未知",
            "submit_time": r.submit_time.strftime("%Y-%m-%d") if r.submit_time else None,
            "total_score": float(r.total_score),
            "max_score": max_score,
            "accuracy": accuracy,
            "duration_used": r.duration_used or 0
        })

    # 计算平均分趋势线
    avg_score = round(sum(float(r.total_score) for r in records) / len(records), 1) if records else 60
    avg_trend = [avg_score] * len(records)

    return {
        "exam_type": exam_type,
        "trend": trend,
        "avg_score": avg_score,
        "avg_trend": avg_trend
    }


@router.get("/{record_id}/wrong-questions", summary="获取错题详情")
async def get_wrong_questions(
    record_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取某次考试的错题详情
    用于错误看板展示
    """
    # 验证考试记录归属
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == record_id,
        ExamRecord.user_id == current_user.user_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    # 获取试卷信息
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == exam_record.paper_id
    ).first()

    # 获取答题详情（仅错题）
    answer_details = db.query(ExamAnswerDetail).filter(
        ExamAnswerDetail.record_id == record_id,
        ExamAnswerDetail.is_correct == 0
    ).all()

    if not answer_details:
        return {
            "record_id": record_id,
            "paper_name": paper.paper_name if paper else "未知",
            "total_score": float(exam_record.total_score),
            "max_score": float(paper.total_score) if paper else 100,
            "total_questions": 0,
            "wrong_count": 0,
            "wrong_rate": 0,
            "wrong_questions": [],
            "ai_suggestion": None
        }

    # 获取错题详情
    question_ids = [a.question_id for a in answer_details]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all()
    question_map = {q.question_id: q for q in questions}

    wrong_questions = []
    for answer in answer_details:
        question = question_map.get(answer.question_id)
        if question:
            wrong_questions.append({
                "question_id": question.question_id,
                "question_content": question.question_content[:200] + "..." if len(question.question_content) > 200 else question.question_content,
                "question_type": question.type_id,
                "student_answer": answer.student_answer,
                "correct_answer": question.answer,
                "score_obtained": float(answer.score_obtained or 0),
                "question_score": float(question.score or 5),
                "answer_analysis": question.answer_analysis or "暂无解析",
                "knowledge_point": getattr(question, 'knowledge_point', None)  # 预留知识点字段
            })

    # 计算错误率
    all_answers = db.query(ExamAnswerDetail).filter(
        ExamAnswerDetail.record_id == record_id
    ).count()
    wrong_rate = round(len(wrong_questions) / all_answers * 100, 1) if all_answers > 0 else 0

    return {
        "record_id": record_id,
        "paper_name": paper.paper_name if paper else "未知",
        "total_score": float(exam_record.total_score),
        "max_score": float(paper.total_score) if paper else 100,
        "total_questions": all_answers,
        "wrong_count": len(wrong_questions),
        "wrong_rate": wrong_rate,
        "wrong_questions": wrong_questions,
        "ai_suggestion": None  # 预留AI分析结果
    }


@router.get("/{record_id}/details", summary="获取考试完整详情")
async def get_exam_record_details(
    record_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取单次考试的完整答题详情（包含对错题）
    """
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == record_id,
        ExamRecord.user_id == current_user.user_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == exam_record.paper_id
    ).first()

    answer_details = db.query(ExamAnswerDetail).filter(
        ExamAnswerDetail.record_id == record_id
    ).all()

    question_ids = [a.question_id for a in answer_details]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all() if question_ids else []
    question_map = {q.question_id: q for q in questions}

    details = []
    for answer in answer_details:
        question = question_map.get(answer.question_id)
        details.append({
            "question_id": answer.question_id,
            "question_content": question.question_content[:200] + "..." if question and len(question.question_content) > 200 else (question.question_content if question else ""),
            "student_answer": answer.student_answer,
            "correct_answer": question.answer if question else None,
            "is_correct": bool(answer.is_correct) if answer.is_correct is not None else None,
            "score_obtained": float(answer.score_obtained or 0),
            "question_score": float(question.score or 5) if question else 5,
            "answer_analysis": question.answer_analysis if question else None
        })

    return {
        "record_id": exam_record.record_id,
        "paper_name": paper.paper_name if paper else "未知",
        "exam_type": exam_record.exam_type,
        "start_time": exam_record.start_time.strftime("%Y-%m-%d %H:%M:%S") if exam_record.start_time else None,
        "submit_time": exam_record.submit_time.strftime("%Y-%m-%d %H:%M:%S") if exam_record.submit_time else None,
        "total_score": float(exam_record.total_score),
        "max_score": float(paper.total_score) if paper else 100,
        "duration_used": exam_record.duration_used or 0,
        "is_completed": bool(exam_record.is_completed),
        "details": details
    }


# ========== AI分析预留接口 ==========

@router.post("/ai/analyze", summary="AI智能分析（预留接口）")
async def ai_analyze_wrong_questions(
    record_id: int = Query(..., description="考试记录ID"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    AI智能分析错题（预留接口）

    后期可对接AI服务，分析用户错题模式，提供个性化学习建议

    请求参数：
    - record_id: 考试记录ID

    返回结构：
    {
        "summary": "整体分析摘要",
        "weak_areas": ["薄弱知识点1", "薄弱知识点2"],
        "suggestions": ["建议1", "建议2"],
        "practice_plan": [{"topic": "主题", "count": 10}]
    }
    """
    # 验证考试记录归属
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == record_id,
        ExamRecord.user_id == current_user.user_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    # 获取错题
    wrong_details = db.query(ExamAnswerDetail).filter(
        ExamAnswerDetail.record_id == record_id,
        ExamAnswerDetail.is_correct == 0
    ).all()

    question_ids = [a.question_id for a in wrong_details]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all() if question_ids else []
    question_map = {q.question_id: q for q in questions}

    # 预留返回结构（后期对接AI服务）
    return {
        "code": 200,
        "message": "AI分析功能预留中，后期对接AI服务后可用",
        "data": {
            "record_id": record_id,
            "summary": f"您在本次考试中错了{len(wrong_details)}道题，主要集中在{len(set(q.type_id for q in questions if q))}个知识点",
            "weak_areas": [],  # 后期AI分析填充
            "suggestions": [
                "建议针对错题涉及的知识点进行专项练习",
                "注意总结错题原因，避免同类错误重复出现"
            ],
            "practice_plan": [],  # 后期AI生成
            "ai_enabled": False,  # 标记AI功能是否启用
            "raw_wrong_questions": [
                {
                    "question_id": q.question_id,
                    "content_preview": q.question_content[:100] + "..." if len(q.question_content) > 100 else q.question_content,
                    "knowledge_point": getattr(q, 'knowledge_point', None)
                }
                for q in [question_map.get(a.question_id) for a in wrong_details]
                if q
            ]
        }
    }


@router.get("/summary", summary="获取成绩概览（综合数据）")
async def get_exam_summary(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取综合成绩概览
    包含自测和模考的汇总数据
    """
    # 自测统计
    self_records = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id,
        ExamRecord.exam_type == "SELF_TEST",
        ExamRecord.is_completed == 1
    ).all()

    # 模考统计
    mock_records = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id,
        ExamRecord.exam_type == "MOCK_EXAM",
        ExamRecord.is_completed == 1
    ).all()

    def calc_stats(records):
        if not records:
            return {"count": 0, "highest": 0, "average": 0}
        scores = [float(r.total_score) for r in records]
        return {
            "count": len(records),
            "highest": max(scores),
            "average": round(sum(scores) / len(scores), 1)
        }

    self_stats = calc_stats(self_records)
    mock_stats = calc_stats(mock_records)

    # 模考排名
    rank_percent = None
    if mock_records and mock_stats["highest"] > 0:
        all_mock = db.query(ExamRecord).filter(
            ExamRecord.exam_type == "MOCK_EXAM",
            ExamRecord.is_completed == 1
        ).all()
        if all_mock:
            higher = sum(1 for r in all_mock if float(r.total_score) > mock_stats["highest"])
            rank_percent = round((1 - higher / len(all_mock)) * 100, 1)

    return {
        "self_test": self_stats,
        "mock_exam": mock_stats,
        "mock_rank_percent": rank_percent,
        "total_exams": len(self_records) + len(mock_records)
    }