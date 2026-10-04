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
    subject_id: Optional[int] = Query(None, description="科目ID"),
    year: Optional[int] = Query(None, description="考试年份"),
    keyword: Optional[str] = Query(None, description="试卷名称关键词"),
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
    if subject_id:
        query = query.filter(ExamPaper.subject_id == subject_id)
    if keyword:
        query = query.filter(ExamPaper.paper_name.ilike(f"%{keyword}%"))
    if year:
        # 筛选包含该年份题目的试卷
        from ...models.models import PaperQuestionRelation, QuestionBank
        year_paper_ids = db.query(PaperQuestionRelation.paper_id).join(
            QuestionBank, PaperQuestionRelation.question_id == QuestionBank.question_id
        ).filter(QuestionBank.year == year).distinct().subquery()
        query = query.filter(ExamPaper.paper_id.in_(year_paper_ids))

    total = query.count()
    papers = query.order_by(ExamPaper.create_time.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    # 手动序列化，避免返回 SQLAlchemy ORM 对象导致 JSON 序列化 500
    items = []
    for p in papers:
        items.append({
            "paper_id": p.paper_id,
            "paper_name": p.paper_name,
            "paper_code": p.paper_code,
            "subject_id": p.subject_id,
            "subject_name": p.subject.subject_name if p.subject else "",
            "exam_type": p.exam_type,
            "paper_type": p.paper_type,
            "question_count": p.question_count,
            "duration": p.duration,
            "total_score": float(p.total_score) if p.total_score else 0,
            "difficulty": p.difficulty,
            "create_time": p.create_time.isoformat() if p.create_time else None,
            "publish_time": p.publish_time.isoformat() if p.publish_time else None,
        })

    return {"total": total,
            "page": page,
            "page_size": page_size,
            "data": items}



@router.get("/{paper_id:int}", response_model=Dict[str, Any], summary="获取考试详情")
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


@router.get("/{paper_id}/questions", response_model=Dict[str, Any], summary="获取试卷题目列表（考试模式）")
async def get_paper_questions(
    paper_id: int,
    db: Session = Depends(get_db)
):
    """
    获取试卷的全部题目（按顺序），用于学生答题。

    - **不含**正确答案和解析（考试模式）
    - 返回试卷基本信息和题目列表
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.paper_type == "PUBLISHED"
    ).first()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或未发布")

    # 获取试卷题目关联（按顺序）
    relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).order_by(PaperQuestionRelation.question_order).all()

    if not relations:
        raise HTTPException(status_code=404, detail="该试卷暂无题目")

    question_ids = [r.question_id for r in relations]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all()

    question_dict = {q.question_id: q for q in questions}
    relation_dict = {r.question_id: r for r in relations}

    # 按顺序组装题目列表（不含答案和解析）
    paper_questions = []
    for relation in relations:
        q = question_dict.get(relation.question_id)
        if not q:
            continue

        # 获取题型名称
        qtype = db.query(QuestionType).filter(
            QuestionType.type_id == q.type_id
        ).first()
        type_name = qtype.type_name if qtype else "单选题"

        paper_questions.append({
            "question_id": q.question_id,
            "question_order": relation.question_order,
            "question_score": float(relation.question_score),
            "question_content": q.question_content,
            "options": q.options,
            "type_name": type_name,
            "type_id": q.type_id,
            "difficulty": q.difficulty,
            "subject_id": q.subject_id,
            "year": q.year,
            "source": q.source,
        })

    return {
        "paper_id": paper.paper_id,
        "paper_name": paper.paper_name,
        "subject_id": paper.subject_id,
        "duration": paper.duration,
        "total_score": float(paper.total_score),
        "question_count": len(paper_questions),
        "questions": paper_questions,
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
    # B1修复: 从试卷启动的统一使用 SELF_TEST（避免SIMULATION/PRACTICE/FORMAL与SELF_TEST/MOCK_EXAM枚举不匹配）
    exam_record = ExamRecord(
        paper_id=paper_id,
        user_id=current_user.user_id,
        exam_type="SELF_TEST",
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

    # 自动将错题写入个人错题集
    from .practice import _auto_record_wrong
    for question_id, student_answer in answers.items():
        question = question_dict.get(question_id)
        if not question:
            continue
        detail = db.query(ExamAnswerDetail).filter(
            ExamAnswerDetail.record_id == record_id,
            ExamAnswerDetail.question_id == question_id
        ).first()
        if detail and not detail.is_correct:
            _auto_record_wrong(current_user.user_id, question_id, question.subject_id, db)

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

    # 手动序列化，避免返回 SQLAlchemy ORM 对象导致 JSON 序列化 500
    # （与上方 /list 同一处理。此前此处直塞 ORM 对象，学生端历年试卷页
    #  loadUserProgress 拿到 500 后对错误对象调 forEach，抛 TypeError）
    items = []
    for r in records:
        items.append({
            "record_id": r.record_id,
            "paper_id": r.paper_id,
            "user_id": r.user_id,
            "exam_type": r.exam_type,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "end_time": r.end_time.isoformat() if r.end_time else None,
            "submit_time": r.submit_time.isoformat() if r.submit_time else None,
            "create_time": r.create_time.isoformat() if r.create_time else None,
            "duration_used": r.duration_used,
            "total_score": float(r.total_score) if r.total_score is not None else 0,
            "is_completed": r.is_completed,
            "is_scored": r.is_scored,
            "is_late": r.is_late,
            "attempt_count": r.attempt_count,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": items
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


# ==================== 新增考试接口 ====================

@router.post("/start", response_model=dict, summary="开始/继续考试")
async def start_exam_new(
        paper_id: int,
        exam_type: str = "SELF_TEST",
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    开始考试（支持继续未完成的考试）
    """
    from ...services.exam_service import ExamService
    try:
        result = ExamService.start_exam(db, paper_id, current_user.user_id, exam_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{exam_id}/submit", response_model=dict, summary="提交考试")
async def submit_exam_new(
        exam_id: int,
        answers: Optional[List[Dict]] = None,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    提交考试并自动评分
    """
    from ...services.exam_service import ExamService
    try:
        result = ExamService.submit_exam(db, exam_id, current_user.user_id, answers)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{exam_id}/progress", response_model=dict, summary="保存答题进度")
async def save_exam_progress(
        exam_id: int,
        answers: List[Dict],
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    保存答题进度（断点续答）
    
    answers: [{"question_id": 123, "answer": "A", "time_spent": 45}, ...]
    """
    from ...services.exam_service import ExamService
    try:
        result = ExamService.save_progress(db, exam_id, answers, current_user.user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/preview/{paper_id}", response_model=dict, summary="预览试卷")
async def preview_exam(
        paper_id: int,
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    学生端预览试卷（不含答案）
    """
    from ...services.exam_service import ExamService
    try:
        result = ExamService.get_exam_preview(db, paper_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))