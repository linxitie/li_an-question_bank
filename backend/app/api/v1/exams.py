import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.models import (
    ExamPaper,
    ExamRecord,
    ExamAnswerDetail,
    QuestionBank,
    SysUser
)
from ...schemas.schemas import (
    ExamRecordResponse,
    AnswerDetailResponse,
    SuccessResponse
)
from ...core.security import get_current_user,require_teacher_or_admin

router = APIRouter(prefix="/api/exams",tags=["考试执行"])
logger = logging.getLogger(__name__)


@router.get("/list", response_model=Dict[str, Any],summary="获取考试列表")
async def get_exams_list(
    paper_type: Optional[str] = Query(None, description="试卷状态"),
    exam_type: Optional[str] = Query(None, description="考试类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取可参考的考试"""
    query = db.query(ExamPaper).filter(
        ExamPaper.paper_type == "PUBLISHED"
    )

    if exam_type:
        query = query.filter(ExamPaper.exam_type == exam_type)
    
    total = query.count()
    papers = query.order_by(ExamPaper.create_time.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    
    return {"total":total,
            "page": page,
            "page_size":page_size,
            "data":papers}



@router.get("/{paper_id}", response_model=Dict[str, Any], summary="获取考试详情")
async def get_exam_detail(
        paper_id: int,
        db: Session = Depends(get_db)
):
    """
    获取考试（试卷）详细信息，包含题目列表

    - 考试模式下不返回答案
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.paper_type == "PUBLISHED"
    ).first()

    if not paper:
        raise HTTPException(status_code=404, detail="考试不存在或未发布")

    return {
        "paper_id": paper.paper_id,
        "paper_name": paper.paper_name,
        "subject_id": paper.subject_id,
        "duration": paper.duration,
        "total_score": float(paper.total_score),
        "difficulty": paper.difficulty,
        "question_count": paper.question_count,
        "exam_type": paper.exam_type,
        "description": paper.description,
        "start_time": paper.start_time,
        "end_time": paper.end_time,
        "shuffle_questions": bool(paper.shuffle_questions),
        "shuffle_options": bool(paper.shuffle_options),
        "max_attempts": paper.max_attempts,
    }


@router.post("/{paper_id}/start", response_model=ExamRecordResponse, summary="开始考试")
async def start_exam(
        paper_id: int,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    开始一场考试

    - 检查试卷是否存在且已发布
    - 检查是否超过最大答题次数
    - 创建考试记录
    """
    # 验证试卷
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.paper_type == "PUBLISHED"
    ).first()

    if not paper:
        raise HTTPException(status_code=404, detail="考试不存在或未发布")

    # 检查是否在考试时间范围内
    now = datetime.now()
    if paper.start_time and now < paper.start_time:
        raise HTTPException(status_code=400, detail="考试尚未开始")
    if paper.end_time and now > paper.end_time:
        raise HTTPException(status_code=400, detail="考试已结束")

    # 检查答题次数
    attempt_count = db.query(ExamRecord).filter(
        ExamRecord.paper_id == paper_id,
        ExamRecord.user_id == current_user.user_id
    ).count()

    if attempt_count >= paper.max_attempts:
        raise HTTPException(
            status_code=400,
            detail=f"已达到最大答题次数({paper.max_attempts}次)"
        )

    # 创建考试记录
    exam_record = ExamRecord(
        paper_id=paper_id,
        user_id=current_user.user_id,
        exam_type=paper.exam_type,
        start_time=now,
        attempt_count=attempt_count + 1
    )

    db.add(exam_record)
    db.commit()
    db.refresh(exam_record)

    logger.info(f"用户 {current_user.username} 开始考试 ID: {exam_record.record_id}")

    return exam_record


@router.post("/{record_id}/submit", response_model=SuccessResponse, summary="提交答案")
async def submit_answers(
        record_id: int,
        answers: Dict[int, str],
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    提交考试答案

    - **answers**: 题目ID到答案的映射，如 {1: "A", 2: "B,C"}
    - 自动评分（客观题）
    - 主观题标记为待批改
    """
    # 验证考试记录
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == record_id,
        ExamRecord.user_id == current_user.user_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    if exam_record.is_completed:
        raise HTTPException(status_code=400, detail="考试已提交，不能重复提交")

    # 获取试卷信息
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == exam_record.paper_id
    ).first()

    # 检查是否超时
    now = datetime.now()
    time_elapsed = (now - exam_record.start_time).total_seconds() / 60

    is_late = False
    if time_elapsed > paper.duration and not paper.allow_late_submit:
        raise HTTPException(status_code=400, detail="考试已超时，不允许迟交")
    elif time_elapsed > paper.duration:
        is_late = True

    # 获取题目
    question_ids = list(answers.keys())
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all()

    question_dict = {q.question_id: q for q in questions}

    # 评分
    total_score = 0.0
    scored_count = 0

    for question_id, student_answer in answers.items():
        question = question_dict.get(question_id)
        if not question:
            continue

        is_correct = None
        score_obtained = 0.0

        # 客观题自动评分
        from ..models import QuestionType
        qtype = db.query(QuestionType).filter(
            QuestionType.type_id == question.type_id
        ).first()

        if qtype and qtype.is_objective:
            # 标准化答案对比
            correct_answer = question.answer.strip() if question.answer else ""
            student_answer_clean = student_answer.strip()

            # 多选题支持乱序判断
            if "," in correct_answer:
                correct_set = set(correct_answer.split(","))
                student_set = set(student_answer_clean.split(","))
                is_correct = correct_set == student_set
            else:
                is_correct = correct_answer.upper() == student_answer_clean.upper()

            if is_correct:
                # 按题目分值或平均分
                score_obtained = float(question.score) if question.score else (
                            float(paper.total_score) / len(question_ids))
                total_score += score_obtained

        # 创建答题详情
        answer_detail = ExamAnswerDetail(
            record_id=record_id,
            question_id=question_id,
            student_answer=student_answer,
            is_correct=1 if is_correct else (0 if is_correct is not None else None),
            score_obtained=score_obtained,
            create_time=now
        )
        db.add(answer_detail)
        scored_count += 1

    # 更新考试记录
    exam_record.end_time = now
    exam_record.duration_used = int(time_elapsed)
    exam_record.total_score = total_score
    exam_record.is_completed = 1
    exam_record.is_scored = 1 if scored_count == len(questions) else 0
    exam_record.submit_time = now
    exam_record.is_late = 1 if is_late else 0

    db.commit()

    logger.info(
        f"用户 {current_user.username} 提交考试 ID: {record_id}, "
        f"得分: {total_score}/{paper.total_score}"
    )

    return SuccessResponse(
        message="提交成功",
        data={
            "record_id": record_id,
            "total_score": total_score,
            "max_score": float(paper.total_score),
            "time_used": int(time_elapsed),
            "is_late": is_late,
            "scored_count": scored_count
        }
    )


@router.get("/records", response_model=Dict[str, Any], summary="获取我的考试记录")
async def get_my_exam_records(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取当前用户的考试记录
    """
    query = db.query(ExamRecord).filter(
        ExamRecord.user_id == current_user.user_id
    )

    total = query.count()
    records = query.order_by(
        ExamRecord.create_time.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": records
    }


@router.get("/records/{record_id}", response_model=Dict[str, Any], summary="获取考试记录详情")
async def get_exam_record_detail(
        record_id: int,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取单次考试的详细答题记录

    包含每道题的作答情况和正确答案
    """
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

    # 获取答题详情
    answer_details = db.query(ExamAnswerDetail).filter(
        ExamAnswerDetail.record_id == record_id
    ).all()

    question_ids = [a.question_id for a in answer_details]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all()

    question_dict = {q.question_id: q for q in questions}

    # 组装详细结果
    details = []
    for answer in answer_details:
        question = question_dict.get(answer.question_id)
        detail = {
            "question_id": answer.question_id,
            "question_content": question.question_content if question else "",
            "student_answer": answer.student_answer,
            "correct_answer": question.answer if question and exam_record.is_completed else None,
            "is_correct": bool(answer.is_correct) if answer.is_correct is not None else None,
            "score_obtained": float(answer.score_obtained),
            "answer_analysis": question.answer_analysis if question and exam_record.is_completed else None,
        }
        details.append(detail)

    return {
        "record_id": exam_record.record_id,
        "paper_id": exam_record.paper_id,
        "paper_name": paper.paper_name if paper else "",
        "exam_type": exam_record.exam_type,
        "start_time": exam_record.start_time,
        "end_time": exam_record.end_time,
        "duration_used": exam_record.duration_used,
        "total_score": float(exam_record.total_score),
        "max_score": float(paper.total_score) if paper else 0,
        "is_completed": bool(exam_record.is_completed),
        "is_scored": bool(exam_record.is_scored),
        "is_late": bool(exam_record.is_late),
        "attempt_count": exam_record.attempt_count,
        "details": details
    }


@router.get("/all", response_model=Dict[str, Any], summary="查看所有考试记录（教师/管理员）")
async def get_all_exam_records(
        paper_id: Optional[int] = Query(None, description="按试卷筛选"),
        user_id: Optional[int] = Query(None, description="按用户筛选"),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    教师/管理员查看所有考试记录

    支持按试卷和用户筛选
    """
    query = db.query(ExamRecord)

    if paper_id:
        query = query.filter(ExamRecord.paper_id == paper_id)
    if user_id:
        query = query.filter(ExamRecord.user_id == user_id)

    total = query.count()
    records = query.order_by(
        ExamRecord.create_time.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": records
    }