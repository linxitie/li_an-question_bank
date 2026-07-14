"""
教师端 API — 工作台、题目管理、试卷管理、成绩分析
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case

from ...core.database import get_db
from ...core.security import (
    get_current_teacher, get_current_admin, get_password_hash,
    check_permission, Permission
)
from ...models.models import (
    SysUser, QuestionBank, QuestionSubject, QuestionType,
    ExamPaper, PaperQuestionRelation, PaperApproval, PaperApprovalWorkflow,
    ExamRecord, ExamAnswerDetail, PracticeRecord, ScoreAnalysis,
    Banji, QuestionImportRecord,
)
from ...schemas.teacher import (
    TeacherDashboardStats, TeacherDashboardResponse,
    PendingApprovalItem, RecentStudentActivity,
    TeacherQuestionUpdate,
    TeacherPaperCreate, TeacherPaperUpdate, PaperAddQuestions,
    AutoGenerateRequest, SubmitApprovalRequest,
    ScoreOverviewResponse, ScoreDistribution, QuestionCorrectRate, StudentScoreItem,
)

router = APIRouter(prefix="/api/teacher", tags=["教师端"])
logger = logging.getLogger(__name__)

# ==================== 辅助函数 ====================

def _format_question(q: QuestionBank) -> dict:
    """格式化题目信息"""
    return {
        "question_id": q.question_id,
        "subject_id": q.subject_id,
        "type_id": q.type_id,
        "question_content": q.question_content[:120] if q.question_content else "",
        "full_content": q.question_content,
        "options": q.options,
        "answer": q.answer,
        "answer_analysis": q.answer_analysis,
        "difficulty": q.difficulty,
        "score": float(q.score) if q.score else 0,
        "year": q.year,
        "source": q.source,
        "tags": q.tags,
        "audit_status": q.audit_status,
        "audit_comment": q.audit_comment,
        "xingce_subcategory": q.xingce_subcategory,
        "shenlun_subcategory": q.shenlun_subcategory,
        "gongzhuan_subcategory": q.gongzhuan_subcategory,
        "accuracy_rate": float(q.accuracy_rate) if q.accuracy_rate else 0,
        "create_time": q.create_time.isoformat() if q.create_time else None,
        "update_time": q.update_time.isoformat() if q.update_time else None,
    }


# ==================== 工作台 ====================

@router.get("/dashboard", summary="教师工作台")
async def get_dashboard(
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师工作台核心数据"""
    # 总题目数
    total_questions = db.query(func.count(QuestionBank.question_id)).filter(
        QuestionBank.status == 1
    ).scalar()

    # 本月新增试卷
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1)
    monthly_papers = db.query(func.count(ExamPaper.paper_id)).filter(
        ExamPaper.create_time >= month_start,
        ExamPaper.creator_id == current_user.user_id
    ).scalar()

    # 今日练习人数
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_practice = db.query(func.count(func.distinct(PracticeRecord.user_id))).filter(
        PracticeRecord.practice_time >= today_start
    ).scalar()

    # 待审批试卷
    pending_count = db.query(func.count(PaperApprovalWorkflow.workflow_id)).filter(
        PaperApprovalWorkflow.status == "pending"
    ).scalar()

    # 我的试卷数
    my_papers = db.query(func.count(ExamPaper.paper_id)).filter(
        ExamPaper.creator_id == current_user.user_id
    ).scalar()

    stats = TeacherDashboardStats(
        total_questions=total_questions,
        monthly_new_papers=monthly_papers,
        today_practice_users=today_practice,
        pending_approval_count=pending_count,
        my_papers_count=my_papers,
        total_imported_questions=db.query(func.count(QuestionImportRecord.import_id)).filter(
            QuestionImportRecord.user_id == current_user.user_id
        ).scalar(),
    )

    # 待审批试卷列表
    pending_approvals = []
    workflows = db.query(PaperApprovalWorkflow).filter(
        PaperApprovalWorkflow.status == "pending"
    ).order_by(desc(PaperApprovalWorkflow.submit_time)).limit(5).all()
    for w in workflows:
        paper = db.query(ExamPaper).filter(ExamPaper.paper_id == w.paper_id).first()
        if paper:
            subject = db.query(QuestionSubject).filter(
                QuestionSubject.subject_id == paper.subject_id
            ).first()
            submitter = db.query(SysUser).filter(SysUser.user_id == w.submitter_id).first()
            pending_approvals.append(PendingApprovalItem(
                paper_id=paper.paper_id,
                paper_name=paper.paper_name,
                subject_name=subject.subject_name if subject else "未知",
                creator_name=submitter.username if submitter else "未知",
                question_count=paper.question_count,
                total_score=float(paper.total_score) if paper.total_score else 0,
                create_time=w.submit_time.isoformat() if w.submit_time else "",
            ))

    # 最新学生动态
    recent_activities = []
    practices = db.query(PracticeRecord).order_by(
        desc(PracticeRecord.practice_time)
    ).limit(10).all()
    for p in practices:
        u = db.query(SysUser).filter(SysUser.user_id == p.user_id).first()
        if u:
            recent_activities.append(RecentStudentActivity(
                user_name=u.username,
                action="完成了练习" if p.is_correct else "练习中答错一题",
                action_time=p.practice_time.isoformat() if p.practice_time else "",
            ))

    return TeacherDashboardResponse(
        stats=stats,
        pending_approvals=pending_approvals,
        recent_activities=recent_activities
    )


# ==================== 题目管理 ====================

@router.get("/questions", summary="题目管理列表")
async def list_teacher_questions(
    keyword: Optional[str] = Query(None, description="题干关键词"),
    subject_id: Optional[int] = Query(None),
    type_id: Optional[int] = Query(None),
    difficulty: Optional[int] = Query(None),
    audit_status: Optional[int] = Query(None),
    xingce_subcategory: Optional[str] = Query(None),
    shenlun_subcategory: Optional[str] = Query(None),
    gongzhuan_subcategory: Optional[str] = Query(None),
    sort_by: str = Query("create_time"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """按多条件筛选题目列表"""
    query = db.query(QuestionBank).filter(QuestionBank.status == 1)

    if keyword:
        query = query.filter(QuestionBank.question_content.contains(keyword))
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    if type_id:
        query = query.filter(QuestionBank.type_id == type_id)
    if difficulty:
        query = query.filter(QuestionBank.difficulty == difficulty)
    if audit_status is not None:
        query = query.filter(QuestionBank.audit_status == audit_status)
    if xingce_subcategory:
        query = query.filter(QuestionBank.xingce_subcategory == xingce_subcategory)
    if shenlun_subcategory:
        query = query.filter(QuestionBank.shenlun_subcategory == shenlun_subcategory)
    if gongzhuan_subcategory:
        query = query.filter(QuestionBank.gongzhuan_subcategory == gongzhuan_subcategory)

    # 排序
    sort_col = getattr(QuestionBank, sort_by, QuestionBank.create_time)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    total = query.count()
    questions = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_format_question(q) for q in questions],
    }


@router.put("/questions/{question_id}", summary="编辑题目")
async def update_question(
    question_id: int,
    data: TeacherQuestionUpdate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师编辑题目"""
    q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(q, key, value)
    q.update_time = datetime.now()
    db.commit()

    return {"success": True, "message": "题目已更新", "question": _format_question(q)}


@router.delete("/questions/{question_id}", summary="删除题目")
async def delete_question(
    question_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师软删除题目"""
    q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    q.status = 0
    q.update_time = datetime.now()
    db.commit()

    return {"success": True, "message": "题目已删除"}


# ==================== 试卷管理 ====================

@router.get("/papers", summary="试卷列表")
async def list_teacher_papers(
    status: Optional[str] = Query(None, description="试卷状态: DRAFT/PENDING/APPROVED/PUBLISHED"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师查看自己的试卷列表"""
    query = db.query(ExamPaper).filter(ExamPaper.creator_id == current_user.user_id)
    if status:
        query = query.filter(ExamPaper.paper_type == status)

    total = query.count()
    papers = query.order_by(desc(ExamPaper.create_time)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = []
    for p in papers:
        subject = db.query(QuestionSubject).filter(QuestionSubject.subject_id == p.subject_id).first()
        items.append({
            "paper_id": p.paper_id,
            "paper_name": p.paper_name,
            "paper_code": p.paper_code,
            "subject_id": p.subject_id,
            "subject_name": subject.subject_name if subject else "",
            "composition_method": p.composition_method,
            "duration": p.duration,
            "total_score": float(p.total_score) if p.total_score else 0,
            "difficulty": p.difficulty,
            "question_count": p.question_count,
            "exam_type": p.exam_type,
            "paper_type": p.paper_type,
            "create_time": p.create_time.isoformat() if p.create_time else None,
            "publish_time": p.publish_time.isoformat() if p.publish_time else None,
        })

    return {"success": True, "total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/papers", summary="创建试卷")
async def create_paper(
    data: TeacherPaperCreate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师手动创建试卷"""
    import uuid
    paper_code = f"P-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    paper = ExamPaper(
        paper_name=data.paper_name,
        paper_code=paper_code,
        subject_id=data.subject_id,
        composition_method="MANUAL",
        creator_id=current_user.user_id,
        duration=data.duration,
        total_score=data.total_score,
        difficulty=data.difficulty,
        question_count=0,
        exam_type=data.exam_type,
        paper_type="DRAFT",
        description=data.description,
        shuffle_questions=data.shuffle_questions,
        shuffle_options=data.shuffle_options,
        max_attempts=data.max_attempts,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    return {"success": True, "message": "试卷创建成功", "paper_id": paper.paper_id, "paper_code": paper_code}


@router.put("/papers/{paper_id}", summary="编辑试卷")
async def update_paper(
    paper_id: int,
    data: TeacherPaperUpdate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师编辑试卷信息"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(paper, key, value)
    paper.update_time = datetime.now()
    db.commit()

    return {"success": True, "message": "试卷已更新"}


@router.delete("/papers/{paper_id}", summary="删除试卷")
async def delete_paper(
    paper_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """删除草稿状态试卷"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type == "PUBLISHED":
        raise HTTPException(status_code=400, detail="已发布试卷不能删除，请先下线")

    paper.paper_type = "ENDED"
    db.commit()
    return {"success": True, "message": "试卷已删除"}


@router.post("/papers/{paper_id}/questions", summary="添加题目到试卷")
async def add_questions_to_paper(
    paper_id: int,
    data: PaperAddQuestions,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """添加题目到试卷"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")

    for item in data.questions:
        relation = db.query(PaperQuestionRelation).filter(
            PaperQuestionRelation.paper_id == paper_id,
            PaperQuestionRelation.question_id == item.question_id
        ).first()
        if relation:
            relation.question_order = item.question_order
            relation.question_score = item.question_score
        else:
            db.add(PaperQuestionRelation(
                paper_id=paper_id,
                question_id=item.question_id,
                question_order=item.question_order,
                question_score=item.question_score,
            ))

    paper.question_count = db.query(func.count(PaperQuestionRelation.relation_id)).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).scalar()
    paper.total_score = db.query(func.sum(PaperQuestionRelation.question_score)).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).scalar() or paper.total_score
    db.commit()

    return {"success": True, "message": "题目已添加", "question_count": paper.question_count}


@router.post("/papers/auto-generate", summary="AI智能组卷")
async def auto_generate_paper(
    data: AutoGenerateRequest,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """智能组卷：根据配置从题库中抽取题目"""
    import uuid
    paper_code = f"PA-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    paper = ExamPaper(
        paper_name=data.paper_name,
        paper_code=paper_code,
        subject_id=data.subject_id,
        composition_method="AUTO",
        creator_id=current_user.user_id,
        duration=data.duration,
        total_score=data.total_score,
        difficulty=data.difficulty,
        question_count=0,
        exam_type=data.exam_type,
        paper_type="DRAFT",
        shuffle_questions=1,
        shuffle_options=1,
    )
    db.add(paper)
    db.flush()

    # 按题型配置抽取题目
    order = 0
    total_questions = 0
    for type_name, count in data.question_config.items():
        # 根据题型名称找到type_id
        type_obj = db.query(QuestionType).filter(
            QuestionType.type_name.contains(type_name.replace('_', ''))
        ).first()
        if not type_obj:
            continue

        questions = db.query(QuestionBank).filter(
            QuestionBank.subject_id == data.subject_id,
            QuestionBank.type_id == type_obj.type_id,
            QuestionBank.difficulty == data.difficulty,
            QuestionBank.status == 1,
            QuestionBank.audit_status == 1,
        ).order_by(func.random()).limit(count).all()

        for q in questions:
            order += 1
            db.add(PaperQuestionRelation(
                paper_id=paper.paper_id,
                question_id=q.question_id,
                question_order=order,
                question_score=float(data.total_score) / sum(data.question_config.values()) if data.question_config else 5.0,
            ))
            total_questions += 1

    paper.question_count = total_questions
    db.commit()
    db.refresh(paper)

    return {
        "success": True,
        "message": f"智能组卷完成，共 {total_questions} 道题目",
        "paper_id": paper.paper_id,
        "paper_code": paper_code,
        "question_count": total_questions,
    }


@router.post("/papers/{paper_id}/submit-approval", summary="提交试卷审批")
async def submit_for_approval(
    paper_id: int,
    data: SubmitApprovalRequest,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师提交试卷进入审批流程"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    if paper.question_count == 0:
        raise HTTPException(status_code=400, detail="试卷没有题目，请先添加题目")

    # 创建审批工作流
    workflow = PaperApprovalWorkflow(
        paper_id=paper_id,
        submitter_id=current_user.user_id,
        approver_id=data.approver_id,
        step=1,
        status="pending",
    )
    db.add(workflow)

    paper.paper_type = "PENDING"
    paper.update_time = datetime.now()
    db.commit()

    return {"success": True, "message": "已提交审批", "workflow_id": workflow.workflow_id}


# ==================== 成绩管理 ====================

@router.get("/scores/overview", summary="成绩总览")
async def get_score_overview(
    paper_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师查看成绩概览：分布图 + 各题正确率 + 学生明细"""
    # 考试记录查询
    records_query = db.query(ExamRecord).filter(ExamRecord.is_completed == 1)

    if paper_id:
        records_query = records_query.filter(ExamRecord.paper_id == paper_id)
    if start_date:
        records_query = records_query.filter(ExamRecord.start_time >= datetime.fromisoformat(start_date))
    if end_date:
        records_query = records_query.filter(ExamRecord.start_time <= datetime.fromisoformat(end_date))

    all_records = records_query.all()
    if class_id:
        class_users = db.query(SysUser).filter(SysUser.class_name.contains(
            db.query(Banji.class_name).filter(Banji.class_id == class_id).scalar() or ""
        )).all()
        class_user_ids = [u.user_id for u in class_users]
        all_records = [r for r in all_records if r.user_id in class_user_ids]

    if not all_records:
        return ScoreOverviewResponse(
            distribution=ScoreDistribution(score_ranges=["0-60", "60-70", "70-80", "80-90", "90-100"],
                                           student_counts=[0, 0, 0, 0, 0]),
            total_students=0, avg_score=0, max_score=0, min_score=0, pass_rate=0
        )

    # 成绩分布
    ranges = [(0, 60), (60, 70), (70, 80), (80, 90), (90, 101)]
    range_labels = ["0-60", "60-70", "70-80", "80-90", "90-100"]
    dist_counts = []
    for low, high in ranges:
        cnt = sum(1 for r in all_records if low <= float(r.total_score or 0) < high)
        dist_counts.append(cnt)

    scores = [float(r.total_score or 0) for r in all_records]

    # 学生成绩明细
    student_items = []
    for rank, r in enumerate(sorted(all_records, key=lambda x: float(x.total_score or 0), reverse=True), 1):
        u = db.query(SysUser).filter(SysUser.user_id == r.user_id).first()
        student_items.append(StudentScoreItem(
            rank=rank,
            user_id=r.user_id,
            user_no=u.user_no if u else "",
            user_name=u.username if u else "未知",
            class_name=u.class_name if u else "",
            total_score=float(r.total_score or 0),
            duration_used=r.duration_used,
            submit_time=r.submit_time.isoformat() if r.submit_time else None,
        ))

    # 各题正确率
    question_rates = []
    if paper_id:
        details = db.query(ExamAnswerDetail).join(
            ExamRecord, ExamAnswerDetail.record_id == ExamRecord.record_id
        ).filter(ExamRecord.paper_id == paper_id).all()
        # 按题目分组统计
        q_stats = {}
        for d in details:
            if d.question_id not in q_stats:
                q_stats[d.question_id] = {"correct": 0, "total": 0}
            q_stats[d.question_id]["total"] += 1
            if d.is_correct:
                q_stats[d.question_id]["correct"] += 1
        for qid, stat in q_stats.items():
            q = db.query(QuestionBank).filter(QuestionBank.question_id == qid).first()
            question_rates.append(QuestionCorrectRate(
                question_id=qid,
                question_content=q.question_content[:50] if q else f"题目{qid}",
                correct_rate=round(stat["correct"] / stat["total"] * 100, 1) if stat["total"] > 0 else 0,
                total_attempts=stat["total"],
            ))

    return ScoreOverviewResponse(
        distribution=ScoreDistribution(score_ranges=range_labels, student_counts=dist_counts),
        question_rates=question_rates,
        student_scores=student_items,
        total_students=len(all_records),
        avg_score=round(sum(scores) / len(scores), 1) if scores else 0,
        max_score=max(scores) if scores else 0,
        min_score=min(scores) if scores else 0,
        pass_rate=round(sum(1 for s in scores if s >= 60) / len(scores) * 100, 1) if scores else 0,
    )


@router.get("/scores/class/{class_id}", summary="班级成绩")
async def get_class_scores(
    class_id: int,
    paper_id: Optional[int] = Query(None),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """查看特定班级的成绩"""
    banji = db.query(Banji).filter(Banji.class_id == class_id).first()
    if not banji:
        raise HTTPException(status_code=404, detail="班级不存在")

    users = db.query(SysUser).filter(SysUser.class_name == banji.class_name).all()
    user_ids = [u.user_id for u in users]

    records_query = db.query(ExamRecord).filter(
        ExamRecord.user_id.in_(user_ids),
        ExamRecord.is_completed == 1
    )
    if paper_id:
        records_query = records_query.filter(ExamRecord.paper_id == paper_id)

    records = records_query.all()
    scores = [float(r.total_score or 0) for r in records]

    return {
        "success": True,
        "class_name": banji.class_name,
        "student_count": len(users),
        "exam_count": len(records),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "pass_rate": round(sum(1 for s in scores if s >= 60) / len(scores) * 100, 1) if scores else 0,
    }


@router.get("/scores/student/{user_id}", summary="学生成绩详情")
async def get_student_score_detail(
    user_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """查看特定学生的详细成绩"""
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="学生不存在")

    records = db.query(ExamRecord).filter(
        ExamRecord.user_id == user_id,
        ExamRecord.is_completed == 1
    ).order_by(desc(ExamRecord.submit_time)).all()

    exam_list = []
    for r in records:
        paper = db.query(ExamPaper).filter(ExamPaper.paper_id == r.paper_id).first()
        exam_list.append({
            "record_id": r.record_id,
            "paper_name": paper.paper_name if paper else "未知试卷",
            "total_score": float(r.total_score or 0),
            "duration_used": r.duration_used,
            "is_late": r.is_late,
            "submit_time": r.submit_time.isoformat() if r.submit_time else None,
        })

    return {
        "success": True,
        "user_name": user.username,
        "user_no": user.user_no,
        "class_name": user.class_name,
        "exam_count": len(exam_list),
        "exams": exam_list,
    }


@router.get("/scores/question-stats/{paper_id}", summary="各题正确率统计")
async def get_question_stats(
    paper_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取某试卷的各题正确率详细统计"""
    details = db.query(ExamAnswerDetail).join(
        ExamRecord, ExamAnswerDetail.record_id == ExamRecord.record_id
    ).filter(ExamRecord.paper_id == paper_id).all()

    q_stats = {}
    for d in details:
        if d.question_id not in q_stats:
            q_stats[d.question_id] = {"correct": 0, "total": 0, "wrong_answers": {}}
        q_stats[d.question_id]["total"] += 1
        if d.is_correct:
            q_stats[d.question_id]["correct"] += 1
        else:
            wrong = d.student_answer or "空"
            q_stats[d.question_id]["wrong_answers"][wrong] = q_stats[d.question_id]["wrong_answers"].get(wrong, 0) + 1

    result = []
    for qid, stat in q_stats.items():
        q = db.query(QuestionBank).filter(QuestionBank.question_id == qid).first()
        result.append({
            "question_id": qid,
            "question_content": q.question_content[:80] if q else f"题目{qid}",
            "correct_answer": q.answer if q else "",
            "correct_rate": round(stat["correct"] / stat["total"] * 100, 1) if stat["total"] > 0 else 0,
            "total_attempts": stat["total"],
            "correct_count": stat["correct"],
            "common_mistakes": sorted(stat["wrong_answers"].items(), key=lambda x: x[1], reverse=True)[:3],
        })

    return {"success": True, "paper_id": paper_id, "question_count": len(result), "questions": result}
