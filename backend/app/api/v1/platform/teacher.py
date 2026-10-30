"""
教师端 API — 工作台、题目管理、试卷管理、成绩分析、个人设置、班级管理、消息中心、数据分析
"""
import os
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case, text as sql_text

from ....core.database import get_db, engine
from ....services import media_service
from ....services.paper_group_selector import (
    select_questions_with_groups,
    summarize_group_selection,
)
from ....core.security import (
    get_current_teacher, get_current_admin, get_password_hash,
    check_permission, Permission
)
from ....models.models import (
    SysUser, QuestionBank, QuestionSubject, QuestionType,
    ExamPaper, PaperQuestionRelation, PaperApproval, PaperApprovalWorkflow,
    ExamRecord, ExamAnswerDetail, PracticeRecord, ScoreAnalysis,
    Banji, QuestionImportRecord, KnowledgePoint, QuestionImage,
    QuestionDetailCategory, QuestionEditLog,
)
from ....schemas.teacher import (
    TeacherDashboardStats, TeacherDashboardResponse,
    PendingApprovalItem, RecentStudentActivity,
    PracticeTrend, SubjectAccuracyItem,
    TeacherQuestionUpdate, TeacherQuestionCreate,
    TeacherPaperCreate, TeacherPaperUpdate, PaperAddQuestions,
    AutoGenerateRequest, SubmitApprovalRequest, PublishPaperRequest,
    PaperQuestionScoreUpdate, PaperQuestionOrderUpdate,
    PaperQuestionContentUpdate,
    ScoreOverviewResponse, ScoreDistribution, QuestionCorrectRate, StudentScoreItem,
    TeacherProfileResponse, TeacherProfileUpdate, ChangePasswordRequest,
    ClassItem, ClassDetailResponse, ClassCreateRequest, ClassStudentAdd,
    MessageItem, MessageListResponse,
    AnalyticsOverview, QuestionUsageItem, KnowledgeMasteryItem,
)

router = APIRouter(prefix="/api/teacher", tags=["教师端"])
logger = logging.getLogger(__name__)

# ==================== 辅助函数 ====================

from ....services.text_parser import clean_question_text
from ....services.question_stats import QuestionStatsService
from ....services.question_ingest.groups import upsert_question_material
import re as _re

# 题干摘要里必须**先剥图再截断**。
# 症状：列表页把 <img src="/static/questions/3211/img_ 直接当文本显示成
#       '<img src="/static/questions/3211/img_...'。
# 原因：此处原为 cleaned_content[:120]，硬截断会把 <img ...> 标签拦腰砍断，
#       产出一个**没有 '>' 的残缺标签**。而前端 renderSummary/stripPromoText
#       的替换正则都是 <img[^>]*\/?>，要求闭合尖括号 —— 对残缺标签在数学上
#       不可能匹配，于是原样落进 DOM（实测 3 题命中，全库含 <img> 题 230 道）。
# 修法：截断前把完整 img 标签与 [IMAGE:...] 占位符都换成 [图片]，
#       再截断，保证摘要里既不会出现残缺标签、也不会撑爆表格。
_IMG_TAG_RE = _re.compile(r'<img[^>]*>', _re.IGNORECASE)
_IMG_PLACEHOLDER_RE = _re.compile(r'\[IMAGE:[^\]]*\]', _re.IGNORECASE)


def _summarize_content(content: str, limit: int = 120) -> str:
    """生成列表摘要：先剥图、再截断。

    完整内容仍由 full_content 原样返回，详情弹窗据此渲染真实图片，
    故这里只影响列表单元格，不丢任何信息。
    """
    if not content:
        return ''
    s = _IMG_TAG_RE.sub('[图片]', content)
    s = _IMG_PLACEHOLDER_RE.sub('[图片]', s)
    return s[:limit] if s else ''


def _format_question(q: QuestionBank) -> dict:
    """格式化题目信息（含内容清洗：移除UTB ID等系统噪音）"""
    raw_content = q.question_content or ''
    cleaned_content = clean_question_text(raw_content)
    # full_content 供详情弹窗渲染完整正文，必须把裸 [IMAGE:...] 占位符
    # 解析成真实 <img>，否则弹窗里只会显示占位符文字（选项图同样）。
    # 复用 image_service.sanitize_image_placeholders —— 它按既有约定
    # 逐级定位磁盘上真实存在的文件（{qid}/marker.png -> marker.png ->
    # 行号_序号.png -> 子目录匹配），找不到则剔除，宁可少图不要裂图。
    # 此处不传 db：_format_question 只拿到 ORM 对象，第7层 question_image
    # 表兜底用不上，但前四层已覆盖 docx 抽图的真实落点。
    try:
        from ....services.image_service import sanitize_image_placeholders
        _qid = q.question_id if isinstance(q.question_id, int) else None
        full_content = sanitize_image_placeholders(cleaned_content, _qid)
    except Exception:
        full_content = cleaned_content
    return {
        "question_id": q.question_id,
        "subject_id": q.subject_id,
        "subject_name": q.subject.subject_name if q.subject else "",
        "type_id": q.type_id,
        "type_name": q.type.type_name if q.type else "",
        "question_content": _summarize_content(cleaned_content),
        "full_content": full_content,
        "options": q.options,
        "answer": q.answer,
        "answer_analysis": q.answer_analysis or "",
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
        # B4: 题组标记（>0 表示复合题小题，前端据此显示题组徽标并拉取聚合详情）
        "group_id": q.group_id or 0,
        # P3b: 待复核标记。1=题型判定置信度不足，需教师人工确认题型
        "need_review": 1 if q.need_review else 0,
        # P1c: 原题号（可追溯到源文档），列表「序号」列优先用它而非行号
        "question_number": q.question_number or "",
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

    # 近7天每日练习人数趋势
    trend_dates = []
    trend_counts = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        trend_dates.append(d.strftime("%m-%d"))
        day_start = datetime.combine(d, datetime.min.time())
        day_end = datetime.combine(d + timedelta(days=1), datetime.min.time())
        cnt = db.query(func.count(func.distinct(PracticeRecord.user_id))).filter(
            PracticeRecord.practice_time >= day_start,
            PracticeRecord.practice_time < day_end
        ).scalar() or 0
        trend_counts.append(cnt)
    practice_trend = PracticeTrend(dates=trend_dates, counts=trend_counts)

    # 三大科目正确率（仅刷题记录，join question_bank 兜底 subject_id）
    subject_names = {1: "行测", 2: "申论", 3: "公专"}
    accuracy_rows = db.query(
        QuestionBank.subject_id,
        func.count(PracticeRecord.record_id).label('total'),
        func.coalesce(func.sum(PracticeRecord.is_correct), 0).label('correct')
    ).join(QuestionBank, PracticeRecord.question_id == QuestionBank.question_id
    ).filter(QuestionBank.subject_id.in_([1, 2, 3])
    ).group_by(QuestionBank.subject_id).all()
    subject_accuracy = []
    for sid, total, correct in accuracy_rows:
        total = int(total or 0)
        correct = int(correct or 0)
        acc = round(correct / total * 100, 1) if total > 0 else 0.0
        subject_accuracy.append(SubjectAccuracyItem(
            subject_id=sid,
            subject_name=subject_names.get(sid, f"科目{sid}"),
            total=total,
            correct=correct,
            accuracy=acc,
        ))

    return TeacherDashboardResponse(
        stats=stats,
        pending_approvals=pending_approvals,
        recent_activities=recent_activities,
        practice_trend=practice_trend,
        subject_accuracy=subject_accuracy,
    )


# ==================== 题目管理 ====================

@router.get("/question-types", summary="题型列表")
async def list_question_types(
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """返回题型列表（供下拉，含判断/填空/情境等独立题型）"""
    fixed_types = [
        {"type_name": "单选题", "is_objective": 1},
        {"type_name": "多选题", "is_objective": 1},
        {"type_name": "判断题", "is_objective": 1},
        {"type_name": "填空题", "is_objective": 1},
        {"type_name": "论述题", "is_objective": 0},
        {"type_name": "写作题", "is_objective": 0},
        {"type_name": "情境题", "is_objective": 0},
    ]
    return {"success": True, "items": fixed_types}


@router.get("/knowledge-points", summary="知识点列表")
async def list_knowledge_points(
    subject_id: int = Query(..., description="科目ID"),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """返回某科目的 canonical L3 知识点列表（仅含有可见题目的考点）"""
    visible_point_ids = db.query(QuestionBank.point_id).filter(
        QuestionBank.status == 1,
        QuestionBank.audit_status == 1,
        QuestionBank.point_id.isnot(None),
    ).distinct()
    kps = db.query(KnowledgePoint).filter(
        KnowledgePoint.subject_id == subject_id,
        KnowledgePoint.status == 1,
        KnowledgePoint.level == 3,
        KnowledgePoint.point_id.in_(visible_point_ids),
    ).order_by(KnowledgePoint.sort_order).all()
    items = [{"point_id": kp.point_id, "point_name": kp.point_name} for kp in kps]
    return {"success": True, "total": len(items), "items": items}


@router.get("/questions", summary="题目管理列表")
async def list_teacher_questions(
    keyword: Optional[str] = Query(None, description="题干关键词"),
    subject_id: Optional[int] = Query(None),
    type_id: Optional[int] = Query(None),
    type_name: Optional[str] = Query(None, description="题型名称（单选题/多选题/论述题/写作题）"),
    point_id: Optional[int] = Query(None, description="知识点ID"),
    difficulty: Optional[int] = Query(None),
    need_review: Optional[int] = Query(
        None, description="待复核标记：1=仅待复核 0=仅已确认 不传=不限"),
    audit_status: Optional[int] = Query(None),
    xingce_subcategory: Optional[str] = Query(None),
    shenlun_subcategory: Optional[str] = Query(None),
    gongzhuan_subcategory: Optional[str] = Query(None),
    sort_by: str = Query("create_time"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_offline: bool = Query(False, description="包含禁用/草稿题目"),
    include_pending: bool = Query(False, description="包含待审核题目"),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """按多条件筛选题目列表"""
    base_query = QuestionStatsService.visible_query(
        db, include_offline=include_offline, include_pending=include_pending
    )

    if keyword:
        base_query = base_query.filter(QuestionBank.question_content.contains(keyword))
    if subject_id:
        base_query = base_query.filter(QuestionBank.subject_id == subject_id)
    if type_id:
        base_query = base_query.filter(QuestionBank.type_id == type_id)
    if type_name:
        base_query = base_query.join(
            QuestionType, QuestionBank.type_id == QuestionType.type_id
        ).filter(QuestionType.type_name == type_name)
    if difficulty:
        base_query = base_query.filter(QuestionBank.difficulty == difficulty)
    # P3b：待复核筛选。导入时题型判定置信度 < 0.60 的题被置 need_review=1，
    # 教师在这里集中确认后 need_review 归零。
    if need_review is not None:
        base_query = base_query.filter(
            (QuestionBank.need_review == 1) if need_review
            else (QuestionBank.need_review != 1))
    if point_id:
        base_query = base_query.filter(QuestionBank.point_id == point_id)
    if audit_status is not None:
        base_query = base_query.filter(QuestionBank.audit_status == audit_status)
    if xingce_subcategory:
        base_query = base_query.filter(QuestionBank.xingce_subcategory == xingce_subcategory)
    if shenlun_subcategory:
        base_query = base_query.filter(QuestionBank.shenlun_subcategory == shenlun_subcategory)
    if gongzhuan_subcategory:
        base_query = base_query.filter(QuestionBank.gongzhuan_subcategory == gongzhuan_subcategory)

    # 计数：在无ORDER BY的base_query上执行
    total = base_query.count()

    # 排序 + tiebreaker（确保分页确定性）
    sort_col = getattr(QuestionBank, sort_by, QuestionBank.create_time)
    if sort_order == "asc":
        paginated_query = base_query.order_by(sort_col.asc(), QuestionBank.question_id.asc())
    else:
        paginated_query = base_query.order_by(sort_col.desc(), QuestionBank.question_id.desc())

    questions = paginated_query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_format_question(q) for q in questions],
    }


@router.post("/questions", summary="自设计题目")
async def create_teacher_question(
    data: TeacherQuestionCreate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师自设计题目（复用导入建题逻辑，默认通过审核）"""
    subject = db.query(QuestionSubject).filter(QuestionSubject.subject_id == data.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")
    # 按 科目+题型名 解析 type_id（题型表按科目冗余，type_id 非全局唯一）
    qtype = db.query(QuestionType).filter(
        QuestionType.type_name == data.type_name,
        QuestionType.subject_id == data.subject_id
    ).first()
    if not qtype:
        qtype = db.query(QuestionType).filter(QuestionType.type_name == data.type_name).first()
    if not qtype:
        qtype = QuestionType(type_name=data.type_name, subject_id=data.subject_id)
        db.add(qtype)
        db.flush()

    # 子科目归类：教师自建题也自动分类，避免落「无」
    from ....services.question_classifier import detect_subcategory_enhanced
    _sc = detect_subcategory_enhanced(data.subject_id, data.question_content, data.type_name)
    question = QuestionBank(
        subject_id=data.subject_id,
        type_id=qtype.type_id,
        question_content=data.question_content,
        options=data.options,
        answer=data.answer,
        answer_analysis=data.answer_analysis or "",
        point_id=data.point_id,
        difficulty=data.difficulty,
        score=data.score,
        year=data.year,
        source=data.source or "教师自建",
        tags=data.tags,
        creator_id=current_user.user_id,
        audit_status=1,  # 教师自建题默认通过审核
        xingce_subcategory=_sc if data.subject_id == 1 else "无",
        shenlun_subcategory=_sc if data.subject_id == 2 else "无",
        gongzhuan_subcategory=_sc if data.subject_id == 3 else "无",
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return {"success": True, "message": "题目创建成功", "question": _format_question(question)}


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

    try:
        update_data = data.model_dump(exclude_unset=True)
        material_keys = ("group_id", "shared_content", "shared_content_images")
        material_data = {k: update_data.pop(k) for k in material_keys if k in update_data}
        for key, value in update_data.items():
            setattr(q, key, value)
        if material_data:
            upsert_question_material(
                db,
                q,
                group_id=material_data.get("group_id"),
                shared_content=material_data.get("shared_content"),
                shared_content_images=material_data.get("shared_content_images"),
                current_user=current_user,
            )
        q.update_time = datetime.now()
        db.commit()
        return {"success": True, "message": "题目已更新", "question": _format_question(q)}
    except PermissionError:
        db.rollback()
        raise HTTPException(status_code=403, detail="无权修改此题目材料")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"更新题目 {question_id} 失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


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


@router.post("/questions/batch-delete", summary="批量删除题目（教师端批量处理）")
async def batch_delete_questions(
    question_ids: List[int] = Body(..., embed=True),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师批量软删除题目（真实功能，非前端硬编码）。"""
    if not question_ids or len(question_ids) > 500:
        raise HTTPException(status_code=400, detail="题目ID列表无效（1~500 个）")
    now = datetime.now()
    cnt = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids),
        QuestionBank.status == 1,
    ).update(
        {QuestionBank.status: 0, QuestionBank.update_time: now},
        synchronize_session=False,
    )
    db.commit()
    return {"success": True, "deleted_count": cnt, "message": f"已删除 {cnt} 道题目"}


@router.post("/questions/batch-reclassify", summary="批量修改科目分类（教师端批量处理）")
async def batch_reclassify_questions(
    question_ids: List[int] = Body(..., embed=True),
    subject_id: int = Body(..., embed=True),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师批量修改题目科目（真实功能）。type_id 按题型名在新科目下重新解析，
    解析不到则置空（前端编辑时再补）。"""
    if not question_ids or len(question_ids) > 500:
        raise HTTPException(status_code=400, detail="题目ID列表无效（1~500 个）")
    subject = db.query(QuestionSubject).filter(QuestionSubject.subject_id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")
    updated = 0
    for qid in question_ids:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == qid).first()
        if q is None or q.status != 1:
            continue
        q.subject_id = subject_id
        if q.type_id:
            tname = db.query(QuestionType.type_name).filter(
                QuestionType.type_id == q.type_id).scalar()
            new_tid = db.query(QuestionType.type_id).filter(
                QuestionType.subject_id == subject_id,
                QuestionType.type_name == tname).scalar() if tname else None
            q.type_id = new_tid
        q.update_time = datetime.now()
        updated += 1
    db.commit()
    return {"success": True, "updated_count": updated, "message": f"已修改 {updated} 道题目科目"}


@router.get("/questions/{question_id}/images", summary="获取题目图片列表")
async def get_question_images(
    question_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取指定题目的所有图片路径（用于前端图片加载失败重试）"""
    q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    import re
    images = []
    content = q.question_content or ''
    
    # 提取 [IMAGE:xxx] 占位符
    for match in re.finditer(r'\[IMAGE:(\d+)_(\d+)\]', content):
        qid = match.group(1)
        idx = match.group(2)
        # 检查文件是否存在
        img_path = f'/static/questions/{qid}/{qid}_{idx}.png'
        abs_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', img_path.lstrip('/'))
        if os.path.exists(abs_path):
            images.append({"path": img_path, "type": "placeholder"})
    
    # 提取 <img> 标签
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', content):
        src = match.group(1)
        images.append({"path": src, "type": "inline"})
    
    # 检查 question_images 表
    try:
        from ....models.models import QuestionImage
        db_images = db.query(QuestionImage).filter(
            QuestionImage.question_id == question_id
        ).all()
        for img in db_images:
            if img.image_path:
                images.append({"path": img.image_path, "type": "db"})
    except Exception:
        pass
    
    return {"success": True, "images": images}


# ==================== 试卷管理 ====================

@router.get("/papers", summary="试卷列表")
async def list_teacher_papers(
    status: Optional[str] = Query(None, description="试卷状态: DRAFT/PENDING/APPROVED/PUBLISHED"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师查看试卷列表（不限制creator_id，教师可查看所有试卷）"""
    query = db.query(ExamPaper)
    if status:
        query = query.filter(ExamPaper.paper_type == status)
    else:
        # 默认不显示已删除(ENDED)试卷，需显式按 ENDED 筛选才可见
        query = query.filter(ExamPaper.paper_type != "ENDED")

    total = query.count()
    papers = query.order_by(desc(ExamPaper.create_time)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = []
    for p in papers:
        subject = db.query(QuestionSubject).filter(QuestionSubject.subject_id == p.subject_id).first()
        latest_wf = db.query(PaperApprovalWorkflow).filter(
            PaperApprovalWorkflow.paper_id == p.paper_id
        ).order_by(desc(PaperApprovalWorkflow.workflow_id)).first()

        # 派生审批态，便于教师在 DRAFT 态区分「被驳回」与「未提交」
        approval_status = "draft"
        if p.paper_type == "PENDING":
            approval_status = "pending"
        elif p.paper_type in ("APPROVED", "PUBLISHED"):
            approval_status = "approved"
        elif p.paper_type == "DRAFT" and latest_wf and latest_wf.status == "rejected":
            approval_status = "rejected"

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
            "approval_status": approval_status,
            "approval_opinion": latest_wf.opinion if latest_wf else "",
            "create_time": p.create_time.isoformat() if p.create_time else None,
            "publish_time": p.publish_time.isoformat() if p.publish_time else None,
        })

    return {"success": True, "total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/papers/stats", summary="试卷各状态统计")
async def paper_stats(
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师查看各状态试卷数量（不限制creator_id）"""
    from sqlalchemy import func
    rows = db.query(
        ExamPaper.paper_type, func.count(ExamPaper.paper_id)
    ).group_by(ExamPaper.paper_type).all()

    stats = {r[0]: r[1] for r in rows}
    return {
        "success": True,
        "total": sum(stats.values()),
        "draft": stats.get("DRAFT", 0),
        "pending": stats.get("PENDING", 0),
        "approved": stats.get("APPROVED", 0),
        "published": stats.get("PUBLISHED", 0),
        "ended": stats.get("ENDED", 0),
    }


@router.get("/papers/{paper_id}", summary="试卷详情")
async def get_teacher_paper_detail(
    paper_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师查看自己的试卷详情（含题目，用于预览）"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")

    subject = db.query(QuestionSubject).filter(QuestionSubject.subject_id == paper.subject_id).first()
    relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).order_by(PaperQuestionRelation.question_order).all()

    questions = []
    for rel in relations:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == rel.question_id).first()
        if not q:
            continue
        questions.append({
            "question_id": q.question_id,
            "question_order": rel.question_order,
            "question_score": float(rel.question_score) if rel.question_score else 0,
            "type_name": q.type.type_name if q.type else "",
            "question_content": q.question_content,
            "options": q.options,
            "answer": q.answer,
            "answer_analysis": q.answer_analysis or "",
            "difficulty": q.difficulty,
        })

    return {
        "success": True,
        "paper": {
            "paper_id": paper.paper_id,
            "paper_name": paper.paper_name,
            "paper_code": paper.paper_code,
            "subject_id": paper.subject_id,
            "subject_name": subject.subject_name if subject else "",
            "duration": paper.duration,
            "total_score": float(paper.total_score) if paper.total_score else 0,
            "difficulty": paper.difficulty,
            "question_count": paper.question_count,
            "exam_type": paper.exam_type,
            "paper_type": paper.paper_type,
            "publish_target": paper.publish_target,
            "create_time": paper.create_time.isoformat() if paper.create_time else None,
        },
        "questions": questions,
    }


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
    """删除试卷（已发布/已结束的试卷不可删除）"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type == "PUBLISHED":
        raise HTTPException(status_code=400, detail="已发布的试卷不可删除，请先下架")
    if paper.paper_type == "ENDED":
        raise HTTPException(status_code=400, detail="已移入回收站的试卷请使用彻底删除")
    if paper.paper_type not in ("DRAFT", "PENDING", "APPROVED"):
        raise HTTPException(status_code=400, detail="当前状态不可删除")

    paper.paper_type = "ENDED"
    db.commit()
    return {"success": True, "message": "试卷已删除"}


@router.post("/papers/{paper_id}/restore", summary="回收站恢复")
async def restore_paper(
    paper_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """回收站恢复试卷（ENDED→DRAFT）"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type != "ENDED":
        raise HTTPException(status_code=400, detail="仅已结束试卷可恢复")

    paper.paper_type = "DRAFT"
    paper.update_time = datetime.now()
    db.commit()
    return {"success": True, "message": "试卷已恢复为草稿"}


@router.delete("/papers/{paper_id}/permanent", summary="彻底删除")
async def permanent_delete_paper(
    paper_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """彻底删除试卷（物理删除 paper + 关联 + 审批流）"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type != "ENDED":
        raise HTTPException(status_code=400, detail="仅已结束试卷可彻底删除")

    db.query(PaperQuestionRelation).filter(PaperQuestionRelation.paper_id == paper_id).delete()
    db.query(PaperApprovalWorkflow).filter(PaperApprovalWorkflow.paper_id == paper_id).delete()
    db.query(PaperApproval).filter(PaperApproval.paper_id == paper_id).delete()
    db.delete(paper)
    db.commit()
    return {"success": True, "message": "试卷已彻底删除"}


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

    # autoflush=False 下需先 flush，否则新增关联对后续 count/sum 不可见，导致 question_count 恒为 0
    db.flush()
    paper.question_count = db.query(func.count(PaperQuestionRelation.relation_id)).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).scalar()
    paper.total_score = db.query(func.sum(PaperQuestionRelation.question_score)).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).scalar() or paper.total_score
    db.commit()

    return {"success": True, "message": "题目已添加", "question_count": paper.question_count}


@router.delete("/papers/{paper_id}/questions/{question_id}", summary="从试卷移除题目")
async def remove_question_from_paper(
    paper_id: int,
    question_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师从草稿试卷移除题目"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="仅草稿状态可移除题目")

    rel = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id,
        PaperQuestionRelation.question_id == question_id
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="题目不在试卷中")

    db.delete(rel)
    db.flush()
    paper.question_count = db.query(func.count(PaperQuestionRelation.relation_id)).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).scalar()
    total = db.query(func.sum(PaperQuestionRelation.question_score)).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).scalar()
    paper.total_score = total if total else 0
    db.commit()
    return {"success": True, "message": "题目已移除", "question_count": paper.question_count}


@router.put("/papers/{paper_id}/questions/order", summary="调整题目顺序")
async def reorder_paper_questions(
    paper_id: int,
    data: PaperQuestionOrderUpdate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """按 question_ids 列表顺序重写 question_order"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="仅草稿状态可调整顺序")

    for order, qid in enumerate(data.question_ids, 1):
        rel = db.query(PaperQuestionRelation).filter(
            PaperQuestionRelation.paper_id == paper_id,
            PaperQuestionRelation.question_id == qid
        ).first()
        if rel:
            rel.question_order = order
    db.commit()
    return {"success": True, "message": "题目顺序已更新"}


@router.put("/papers/{paper_id}/questions/{question_id}", summary="调整题目分值")
async def update_paper_question_score(
    paper_id: int,
    question_id: int,
    data: PaperQuestionScoreUpdate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """调整试卷题目分值"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="仅草稿状态可调整分值")

    rel = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id,
        PaperQuestionRelation.question_id == question_id
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="题目不在试卷中")

    rel.question_score = data.question_score
    db.flush()
    total = db.query(func.sum(PaperQuestionRelation.question_score)).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).scalar()
    paper.total_score = total if total else 0
    db.commit()
    return {"success": True, "message": "分值已更新", "total_score": float(paper.total_score)}


@router.put("/papers/{paper_id}/questions/{question_id}/content",
            summary="P5 编辑试卷内题目内容（题干/选项/答案/解析/题型/难度/分值）")
async def update_paper_question_content(
    paper_id: int,
    question_id: int,
    data: PaperQuestionContentUpdate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """编辑试卷内某题的内容。

    为什么需要这个端点
    ------------------
    步骤2 原本只能改分值/顺序/换一题/删除，**改不了题干与答案**，
    教师发现导入错误时只能退回「题目管理」逐题改再回来重排，
    这就是"试卷编辑无法对试卷进行增删改查"里"改"缺失的那一环。

    设计要点
    --------
    1. 权限与状态：与改分值一致 —— 仅本人创建的 DRAFT 试卷可改。
       已发布/已审批的试卷不允许就地改题，避免学生已作答的记录失真。
    2. 题型走注册表：type_name 必须能在 question_type 中命中，
       命中不到直接 400，不静默新建垃圾题型行（P1 修复过的老问题）。
    3. 题型与 detail_category 同步写，保证双字段不再分裂。
    4. 每次编辑写 question_edit_log（old_data/new_data 全量快照），
       该表原本 0 行，P1 已建立审计基线，此处延续。
    5. 人工确认题型即视为"已复核"：need_review 归零。
    6. 分值改动后同步重算 paper.total_score（与改分值端点口径一致）。
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="仅草稿状态可编辑题目内容")

    rel = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id,
        PaperQuestionRelation.question_id == question_id
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="题目不在试卷中")

    q = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    # ---- 题型：必须在注册表里命中，禁止静默新建 ----
    new_type_name = None
    if payload.get('type_name'):
        want = payload['type_name'].strip()
        qtype = db.query(QuestionType).filter(
            QuestionType.type_name == want).first()
        if not qtype:
            raise HTTPException(
                status_code=400,
                detail=f"题型「{want}」不存在，请先在题型设置中创建")
        if qtype.type_id != q.type_id:
            new_type_name = want

    # ---- 审计快照（改前） ----
    old_snapshot = {
        'question_content': q.question_content,
        'options': q.options,
        'answer': q.answer,
        'answer_analysis': q.answer_analysis,
        'type_id': q.type_id,
        'difficulty': q.difficulty,
    }

    if 'question_content' in payload and payload['question_content'] is not None:
        new_c = str(payload['question_content']).strip()
        if not new_c:
            raise HTTPException(status_code=400, detail="题干不能为空")
        q.question_content = new_c
    if 'options' in payload:
        q.options = payload['options']
    if 'answer' in payload and payload['answer'] is not None:
        q.answer = str(payload['answer']).strip()
    if 'answer_analysis' in payload and payload['answer_analysis'] is not None:
        q.answer_analysis = payload['answer_analysis']
    if 'difficulty' in payload and payload['difficulty'] is not None:
        q.difficulty = int(payload['difficulty'])
    if new_type_name:
        q.type_id = qtype.type_id
        d = db.query(QuestionDetailCategory).filter(
            QuestionDetailCategory.question_id == question_id).first()
        if d is None:
            d = QuestionDetailCategory(question_id=question_id)
            db.add(d)
        d.question_type_detail = new_type_name
        # 教师人工确认题型 = 已复核
        q.need_review = 0

    # ---- 分值（试卷维度） ----
    if 'score' in payload and payload['score'] is not None:
        rel.question_score = float(payload['score'])

    q.update_time = datetime.now()
    db.flush()

    if 'score' in payload and payload['score'] is not None:
        total = db.query(func.sum(PaperQuestionRelation.question_score)).filter(
            PaperQuestionRelation.paper_id == paper_id
        ).scalar()
        paper.total_score = total if total else 0

    new_snapshot = {
        'question_content': q.question_content,
        'options': q.options,
        'answer': q.answer,
        'answer_analysis': q.answer_analysis,
        'type_id': q.type_id,
        'difficulty': q.difficulty,
    }
    changed = [k for k in old_snapshot if old_snapshot[k] != new_snapshot.get(k)]

    db.add(QuestionEditLog(
        question_id=question_id,
        editor_id=current_user.user_id,
        action_type='UPDATE',
        old_data=old_snapshot,
        new_data={**new_snapshot, 'changed_fields': changed,
                  'score': float(rel.question_score)},
        edit_time=datetime.now(),
        remark=f"P5 试卷内编辑（paper_id={paper_id}）变更字段: {changed}"[:500],
    ))
    db.commit()
    return {
        "success": True,
        "message": f"已保存（变更 {len(changed) + (1 if 'score' in payload else 0)} 项）",
        "changed_fields": changed,
        "total_score": float(paper.total_score) if paper.total_score else 0,
    }


@router.post("/papers/{paper_id}/questions/{question_id}/replace", summary="换一题")
async def replace_paper_question(
    paper_id: int,
    question_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """删除原题并随机替换一道同科目/题型/难度的题"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="仅草稿状态可换一题")

    old_rel = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id,
        PaperQuestionRelation.question_id == question_id
    ).first()
    if not old_rel:
        raise HTTPException(status_code=404, detail="题目不在试卷中")

    old_q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not old_q:
        raise HTTPException(status_code=404, detail="原题不存在")

    existing_ids = [r[0] for r in db.query(PaperQuestionRelation.question_id).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).all()]

    candidate_query = db.query(QuestionBank).filter(
        QuestionBank.subject_id == old_q.subject_id,
        QuestionBank.type_id == old_q.type_id,
        QuestionBank.difficulty == old_q.difficulty,
        QuestionBank.status == 1,
        QuestionBank.question_id != question_id,
    )
    if existing_ids:
        candidate_query = candidate_query.filter(~QuestionBank.question_id.in_(existing_ids))
    candidate = candidate_query.order_by(func.random()).first()

    if not candidate:
        raise HTTPException(status_code=400, detail="无可用替换题（同科目/题型/难度下已无剩余）")

    old_rel.question_id = candidate.question_id
    db.commit()
    return {"success": True, "message": "已换一题", "new_question_id": candidate.question_id}


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
    # 题组感知：命中 group_id>0 的复合题时整组带入，避免资料分析/申论材料题被拆散。
    order = 0
    total_questions = 0
    requested_questions = sum(int(c) for c in data.question_config.values())
    selected_ids = set()
    for type_name, count in data.question_config.items():
        # 根据题型名称找到type_id
        type_obj = db.query(QuestionType).filter(
            QuestionType.type_name.contains(type_name.replace('_', ''))
        ).first()
        if not type_obj:
            continue

        query = db.query(QuestionBank).filter(
            QuestionBank.subject_id == data.subject_id,
            QuestionBank.type_id == type_obj.type_id,
            QuestionBank.difficulty == data.difficulty,
            QuestionBank.status == 1,
            QuestionBank.audit_status == 1,
        )
        if selected_ids:
            query = query.filter(~QuestionBank.question_id.in_(selected_ids))

        questions, selected_ids = select_questions_with_groups(
            db=db,
            query=query,
            count=count,
            selected_ids=selected_ids,
        )

        for q in questions:
            order += 1
            db.add(PaperQuestionRelation(
                paper_id=paper.paper_id,
                question_id=q.question_id,
                question_order=order,
                question_score=0,  # 先占位，组卷完成后按实际题数统一均分
            ))
            total_questions += 1

    # 组展开后实际题数可能多于配置数，总分按实际题数均分，避免总分超发
    per_score = round(float(data.total_score) / total_questions, 2) if total_questions else 5.0
    for rel in db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper.paper_id
    ).all():
        rel.question_score = per_score

    paper.question_count = total_questions
    db.commit()
    db.refresh(paper)

    quota = summarize_group_selection(requested_questions, total_questions)
    message = f"智能组卷完成，共 {total_questions} 道题目"
    if quota["over_quota"]:
        message += f"（{quota['over_quota_reason']}，请核对后再发布）"

    return {
        "success": True,
        "message": message,
        "paper_id": paper.paper_id,
        "paper_code": paper_code,
        "question_count": total_questions,
        **quota,
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

    paper.publish_target = "mock_exam"
    paper.paper_type = "PENDING"
    paper.update_time = datetime.now()
    db.commit()

    return {"success": True, "message": "已提交审批", "workflow_id": workflow.workflow_id}


@router.post("/papers/{paper_id}/publish", summary="发布试卷（双轨制）")
async def publish_teacher_paper(
    paper_id: int,
    data: PublishPaperRequest,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """发布试卷：past_paper 免审批直发；mock_exam 需走审批"""
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")
    if paper.question_count == 0:
        raise HTTPException(status_code=400, detail="试卷没有题目，请先添加题目")

    if data.publish_target == "past_paper":
        if paper.paper_type not in ("DRAFT", "APPROVED"):
            raise HTTPException(status_code=400, detail="当前状态不可直接发布")
        paper.publish_target = "past_paper"
        paper.paper_type = "PUBLISHED"
        paper.publish_time = datetime.now()
    elif data.publish_target == "mock_exam":
        raise HTTPException(status_code=400, detail="小模考需提交审批，请调用提交审批接口")
    else:
        raise HTTPException(status_code=400, detail="发布目标无效，应为 past_paper 或 mock_exam")

    paper.update_time = datetime.now()
    db.commit()
    return {"success": True, "message": "试卷已发布到历年试卷", "paper_type": paper.paper_type}


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


# ==================== 个人设置 ====================

@router.get("/profile", summary="获取教师个人信息")
async def get_teacher_profile(
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取当前教师的完整个人信息"""
    # 统计所带班级数
    class_count = db.query(func.count(func.distinct(Banji.class_id))).filter(
        Banji.teacher_id == current_user.user_id
    ).scalar() or 0

    # 统计学生数
    teacher_classes = db.query(Banji.class_name).filter(
        Banji.teacher_id == current_user.user_id
    ).all()
    class_names = [c[0] for c in teacher_classes]
    student_count = 0
    if class_names:
        student_count = db.query(func.count(SysUser.user_id)).filter(
            SysUser.class_name.in_(class_names),
            SysUser.user_type == 'student'
        ).scalar() or 0

    # 统计试卷数
    paper_count = db.query(func.count(ExamPaper.paper_id)).filter(
        ExamPaper.creator_id == current_user.user_id
    ).scalar() or 0

    # 统计题目数（教师自建）
    question_count = db.query(func.count(QuestionBank.question_id)).filter(
        QuestionBank.creator_id == current_user.user_id,
        QuestionBank.status == 1
    ).scalar() or 0

    return TeacherProfileResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        user_no=getattr(current_user, 'user_no', None),
        avatar=getattr(current_user, 'avatar', None),
        phone=getattr(current_user, 'phone', None),
        email=getattr(current_user, 'email', None),
        department=getattr(current_user, 'department', None),
        hire_date=str(getattr(current_user, 'hire_date', '')) if getattr(current_user, 'hire_date', None) else None,
        role=getattr(current_user, 'role', 'teacher'),
        class_count=class_count,
        student_count=student_count,
        paper_count=paper_count,
        question_count=question_count,
    )


@router.put("/profile", summary="更新教师个人信息")
async def update_teacher_profile(
    data: TeacherProfileUpdate,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """更新教师个人信息（姓名、手机号、邮箱、所属院系）"""
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(current_user, key) and value is not None:
            setattr(current_user, key, value)
    current_user.update_time = datetime.now()
    db.commit()
    return {"success": True, "message": "个人信息已更新"}


_TEACHER_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_TEACHER_AVATAR_MAX = 2 * 1024 * 1024


@router.post("/profile/avatar", summary="上传头像")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """上传教师头像图片（与学生端同样的白名单/大小/文件头校验）"""
    import uuid
    from app.core.config import settings

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _TEACHER_AVATAR_EXT:
        raise HTTPException(400, "仅支持 jpg/jpeg/png/gif/webp 格式")
    content = await file.read()
    if not content:
        raise HTTPException(400, "文件内容为空")
    if len(content) > _TEACHER_AVATAR_MAX:
        raise HTTPException(400, "头像大小不能超过 2MB")
    if not media_service.image_magic_ok(ext, content):
        raise HTTPException(400, "文件实际格式与扩展名不符")

    if settings.MEDIA_STORE_ENABLED:
        try:
            asset = media_service.store_bytes(
                db,
                content,
                kind="avatar",
                original_name=file.filename or f"avatar{ext}",
                created_by=current_user.user_id,
                max_bytes=_TEACHER_AVATAR_MAX,
            )
        except media_service.MediaTooLarge:
            raise HTTPException(400, "头像大小不能超过 2MB")
        except media_service.MediaValidationError as exc:
            raise HTTPException(400, str(exc))
        except media_service.ObjectStoreUnavailable:
            raise HTTPException(503, "头像存储暂不可用，请稍后重试")

        old_url = current_user.avatar
        avatar_url = f"/media/{asset.asset_id}"
        current_user.avatar = avatar_url
        media_service.retire_url(db, old_url)
        db.commit()
    else:
        # 回滚分支：保留原 uploads 写路径。
        filename = f"avatar_{current_user.user_id}_{uuid.uuid4().hex[:8]}{ext}"
        upload_dir = os.path.join(settings.UPLOAD_DIR, 'avatars')
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(content)
        avatar_url = f"/uploads/avatars/{filename}"
        current_user.avatar = avatar_url
        db.commit()
    return {"success": True, "message": "头像上传成功", "avatar_url": avatar_url}


@router.post("/profile/change-password", summary="修改密码")
async def change_password(
    data: ChangePasswordRequest,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """修改教师密码"""
    from ....core.security import verify_password, get_password_hash
    if not verify_password(data.old_password, current_user.password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    current_user.password = get_password_hash(data.new_password)
    db.commit()
    return {"success": True, "message": "密码修改成功"}


# ==================== 班级管理 ====================

@router.get("/classes", summary="班级列表")
async def list_teacher_classes(
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取教师所带班级列表"""
    classes = db.query(Banji).filter(
        Banji.teacher_id == current_user.user_id
    ).order_by(desc(Banji.create_time)).all()

    items = []
    for cls in classes:
        student_count = db.query(func.count(SysUser.user_id)).filter(
            SysUser.class_name == cls.class_name,
            SysUser.user_type == 'student'
        ).scalar() or 0

        # 计算班级平均分
        user_ids = [u.user_id for u in db.query(SysUser.user_id).filter(
            SysUser.class_name == cls.class_name,
            SysUser.user_type == 'student'
        ).all()]
        avg_score = 0
        if user_ids:
            records = db.query(ExamRecord).filter(
                ExamRecord.user_id.in_(user_ids),
                ExamRecord.is_completed == 1
            ).all()
            scores = [float(r.total_score or 0) for r in records]
            avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        items.append(ClassItem(
            class_id=cls.class_id,
            class_name=cls.class_name,
            student_count=student_count,
            avg_score=avg_score,
            create_time=cls.create_time.isoformat() if cls.create_time else None,
        ))

    return {"success": True, "total": len(items), "items": [i.dict() for i in items]}


@router.post("/classes", summary="创建班级")
async def create_class(
    data: ClassCreateRequest,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """教师创建新班级"""
    existing = db.query(Banji).filter(Banji.class_name == data.class_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="班级名称已存在")

    new_class = Banji(
        class_name=data.class_name,
        teacher_id=current_user.user_id,
        create_time=datetime.now(),
    )
    db.add(new_class)
    db.commit()
    db.refresh(new_class)
    return {"success": True, "message": "班级创建成功", "class_id": new_class.class_id}


@router.get("/classes/{class_id}", summary="班级详情")
async def get_class_detail(
    class_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取班级详情（含学生列表）"""
    cls = db.query(Banji).filter(
        Banji.class_id == class_id,
        Banji.teacher_id == current_user.user_id
    ).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在或无权操作")

    students = db.query(SysUser).filter(
        SysUser.class_name == cls.class_name,
        SysUser.user_type == 'student'
    ).all()

    student_list = []
    for s in students:
        # 计算学生平均正确率
        records = db.query(ExamRecord).filter(
            ExamRecord.user_id == s.user_id,
            ExamRecord.is_completed == 1
        ).all()
        scores = [float(r.total_score or 0) for r in records]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        student_list.append({
            "user_id": s.user_id,
            "username": s.username,
            "user_no": getattr(s, 'user_no', ''),
            "avg_score": avg_score,
            "exam_count": len(records),
        })

    return ClassDetailResponse(
        class_id=cls.class_id,
        class_name=cls.class_name,
        student_count=len(students),
        avg_score=round(sum(s["avg_score"] for s in student_list) / len(student_list), 1) if student_list else 0,
        create_time=cls.create_time.isoformat() if cls.create_time else None,
        students=student_list,
    )


@router.delete("/classes/{class_id}", summary="删除班级")
async def delete_class(
    class_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """删除班级"""
    cls = db.query(Banji).filter(
        Banji.class_id == class_id,
        Banji.teacher_id == current_user.user_id
    ).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在或无权操作")
    db.delete(cls)
    db.commit()
    return {"success": True, "message": "班级已删除"}


@router.post("/classes/{class_id}/students", summary="添加学生到班级")
async def add_students_to_class(
    class_id: int,
    data: ClassStudentAdd,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """添加学生到班级"""
    cls = db.query(Banji).filter(
        Banji.class_id == class_id,
        Banji.teacher_id == current_user.user_id
    ).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在或无权操作")

    added = 0
    for uid in data.user_ids:
        user = db.query(SysUser).filter(SysUser.user_id == uid).first()
        if user and user.role == 'student':
            user.class_name = cls.class_name
            added += 1
    db.commit()
    return {"success": True, "message": f"已添加 {added} 名学生", "added_count": added}


@router.delete("/classes/{class_id}/students/{user_id}", summary="从班级移除学生")
async def remove_student_from_class(
    class_id: int,
    user_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """从班级移除学生"""
    cls = db.query(Banji).filter(
        Banji.class_id == class_id,
        Banji.teacher_id == current_user.user_id
    ).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在或无权操作")

    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if user and user.class_name == cls.class_name:
        user.class_name = ''
        db.commit()
    return {"success": True, "message": "学生已移除"}


# ==================== 消息中心 ====================

@router.get("/messages", summary="消息列表")
async def list_teacher_messages(
    message_type: Optional[str] = Query(None, description="消息类型: system/approval/student"),
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取教师消息列表"""
    # 动态创建消息表（如果不存在）
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS teacher_message (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER NOT NULL,
                    message_type VARCHAR(20) NOT NULL DEFAULT 'system',
                    title VARCHAR(200) NOT NULL,
                    content TEXT,
                    is_read INTEGER DEFAULT 0,
                    related_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
    except Exception:
        pass

    base_query = text("SELECT * FROM teacher_message WHERE teacher_id = :tid")
    params = {"tid": current_user.user_id}

    if message_type:
        base_query = text(str(base_query) + " AND message_type = :mt")
        params["mt"] = message_type
    if is_read is not None:
        base_query = text(str(base_query) + " AND is_read = :ir")
        params["ir"] = 1 if is_read else 0

    count_query = text(str(base_query).replace("SELECT *", "SELECT COUNT(*)"))
    total = 0
    items = []

    try:
        from sqlalchemy import text as sql_text
        with engine.connect() as conn:
            total = conn.execute(count_query, params).scalar() or 0
            list_query = text(str(base_query) + " ORDER BY created_at DESC LIMIT :limit OFFSET :offset")
            params["limit"] = page_size
            params["offset"] = (page - 1) * page_size
            rows = conn.execute(list_query, params).fetchall()
            for row in rows:
                items.append({
                    "message_id": row[0],
                    "message_type": row[2],
                    "title": row[3],
                    "content": row[4],
                    "is_read": bool(row[5]),
                    "related_id": row[6],
                    "created_at": str(row[7]) if row[7] else None,
                })
    except Exception as e:
        logger.error(f"查询消息列表失败: {e}")

    unread_count = 0
    try:
        with engine.connect() as conn:
            unread_count = conn.execute(
                text("SELECT COUNT(*) FROM teacher_message WHERE teacher_id = :tid AND is_read = 0"),
                {"tid": current_user.user_id}
            ).scalar() or 0
    except Exception:
        pass

    return {"success": True, "total": total, "unread_count": unread_count, "items": items}


@router.get("/messages/unread-count", summary="未读消息数")
async def get_unread_count(
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取未读消息数量"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM teacher_message WHERE teacher_id = :tid AND is_read = 0"),
                {"tid": current_user.user_id}
            ).scalar() or 0
        return {"success": True, "unread_count": count}
    except Exception:
        return {"success": True, "unread_count": 0}


@router.put("/messages/{message_id}/read", summary="标记消息已读")
async def mark_message_read(
    message_id: int,
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """标记单条消息为已读"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE teacher_message SET is_read = 1 WHERE message_id = :mid AND teacher_id = :tid"),
                {"mid": message_id, "tid": current_user.user_id}
            )
            conn.commit()
        return {"success": True, "message": "已标记为已读"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.put("/messages/read-all", summary="全部标记已读")
async def mark_all_read(
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """全部标记为已读"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE teacher_message SET is_read = 1 WHERE teacher_id = :tid AND is_read = 0"),
                {"tid": current_user.user_id}
            )
            conn.commit()
        return {"success": True, "message": "已全部标记为已读"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


# ==================== 数据分析 ====================

@router.get("/analytics/overview", summary="学情总览")
async def get_analytics_overview(
    class_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取学情总览数据"""
    # 获取教师所带班级的学生
    teacher_classes = db.query(Banji.class_name).filter(
        Banji.teacher_id == current_user.user_id
    ).all()
    class_names = [c[0] for c in teacher_classes]

    if not class_names:
        return AnalyticsOverview()

    # 如果指定了班级
    if class_id:
        cls = db.query(Banji).filter(Banji.class_id == class_id).first()
        if cls:
            class_names = [cls.class_name]

    user_class_map = {
        row[0]: row[1]
        for row in db.query(SysUser.user_id, SysUser.class_name).filter(
            SysUser.class_name.in_(class_names),
            SysUser.user_type == 'student'
        ).all()
    }
    user_ids = list(user_class_map.keys())

    if not user_ids:
        return AnalyticsOverview()

    # 最近N天的考试记录
    since = datetime.now() - timedelta(days=days)
    records = db.query(ExamRecord).filter(
        ExamRecord.user_id.in_(user_ids),
        ExamRecord.is_completed == 1,
        ExamRecord.start_time >= since
    ).all()

    scores = [float(r.total_score or 0) for r in records]
    total_students = len(set(r.user_id for r in records))

    # 按完整日期统计平均分趋势（内部用可排序的完整日期键，避免 days>30 时跨月/跨年同日被静默合并）
    date_scores = {}
    for r in records:
        if r.start_time:
            date_key = r.start_time.strftime("%Y-%m-%d")
            if date_key not in date_scores:
                date_scores[date_key] = []
            date_scores[date_key].append(float(r.total_score or 0))

    sorted_date_keys = sorted(date_scores.keys())
    # 跨度跨年时统一输出完整日期，避免 X 轴出现无法区分的重复 "09-01"；
    # 全局一次性判定，确保全站趋势与各班级序列使用同一种日期格式
    spans_years = len({d[:4] for d in sorted_date_keys}) > 1
    trend_dates = [d if spans_years else d[5:] for d in sorted_date_keys]
    trend_scores = [round(sum(date_scores[d]) / len(date_scores[d]), 1) for d in sorted_date_keys]

    # 分班级趋势序列：学生与班级的唯一关联是 SysUser.class_name 字符串
    class_date_scores = {}
    for r in records:
        if not r.start_time:
            continue
        cname = user_class_map.get(r.user_id)
        if not cname:
            continue
        per_date = class_date_scores.setdefault(cname, {})
        per_date.setdefault(r.start_time.strftime("%Y-%m-%d"), []).append(
            float(r.total_score or 0)
        )

    class_id_map = {
        c.class_name: c.class_id
        for c in db.query(Banji).filter(Banji.class_name.in_(class_names)).all()
    }

    class_trend = []
    for cname in class_names:
        per_date = class_date_scores.get(cname)
        if not per_date:
            # 该班在时间窗内无完成记录，不输出空折线
            continue
        class_trend.append({
            "class_id": class_id_map.get(cname),
            "class_name": cname,
            "points": [
                {
                    "date": d if spans_years else d[5:],
                    "avg_score": round(sum(per_date[d]) / len(per_date[d]), 1),
                }
                for d in sorted(per_date.keys())
            ],
        })

    # 按科目统计（一次性批量查询试卷，避免在记录循环内逐条查询造成 N+1）
    subject_names = {1: "行测", 2: "申论", 3: "公专"}
    subject_stats = {}
    paper_ids = {r.paper_id for r in records if r.paper_id}
    paper_subject_map = {}
    if paper_ids:
        for pid, sid in db.query(ExamPaper.paper_id, ExamPaper.subject_id).filter(
            ExamPaper.paper_id.in_(paper_ids)
        ).all():
            paper_subject_map[pid] = sid

    for r in records:
        sid = paper_subject_map.get(r.paper_id)
        if sid is None:
            continue
        if sid not in subject_stats:
            subject_stats[sid] = {"scores": [], "count": 0}
        subject_stats[sid]["scores"].append(float(r.total_score or 0))
        subject_stats[sid]["count"] += 1

    subject_comparison = []
    for sid, stat in subject_stats.items():
        avg = round(sum(stat["scores"]) / len(stat["scores"]), 1) if stat["scores"] else 0
        subject_comparison.append({
            "subject_name": subject_names.get(sid, f"科目{sid}"),
            "avg_score": avg,
            "exam_count": stat["count"],
        })

    return AnalyticsOverview(
        total_students=total_students,
        total_exams=len(records),
        avg_score=round(sum(scores) / len(scores), 1) if scores else 0,
        pass_rate=round(sum(1 for s in scores if s >= 60) / len(scores) * 100, 1) if scores else 0,
        score_trend={"dates": trend_dates, "scores": trend_scores},
        class_trend=class_trend,
        subject_comparison=subject_comparison,
    )


@router.get("/analytics/question-usage", summary="题目使用频率")
async def get_question_usage(
    subject_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取题目使用频率统计"""
    query = db.query(
        ExamAnswerDetail.question_id,
        func.count(ExamAnswerDetail.detail_id).label('usage_count'),
        func.sum(case((ExamAnswerDetail.is_correct == 1, 1), else_=0)).label('correct_count'),
    ).group_by(ExamAnswerDetail.question_id).order_by(
        desc('usage_count')
    ).limit(limit)

    rows = query.all()
    items = []
    for qid, usage_count, correct_count in rows:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == qid).first()
        if q and (subject_id is None or q.subject_id == subject_id):
            items.append({
                "question_id": qid,
                "question_content": (q.question_content or "")[:60],
                "usage_count": usage_count,
                "correct_rate": round((correct_count or 0) / usage_count * 100, 1) if usage_count > 0 else 0,
                "subject_name": q.subject.subject_name if q.subject else "",
            })

    return {"success": True, "total": len(items), "items": items}


@router.get("/analytics/knowledge-mastery", summary="知识点掌握度")
async def get_knowledge_mastery(
    subject_id: Optional[int] = Query(None),
    current_user: SysUser = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """获取知识点掌握度统计"""
    # 获取知识点列表
    kp_query = db.query(KnowledgePoint).filter(
        KnowledgePoint.status == 1,
        KnowledgePoint.level == 3,
    )
    if subject_id:
        kp_query = kp_query.filter(KnowledgePoint.subject_id == subject_id)
    knowledge_points = kp_query.all()

    items = []
    for kp in knowledge_points:
        # 统计该知识点下的答题情况（canonical point_id 单一归属）
        questions = db.query(QuestionBank.question_id).filter(
            QuestionBank.point_id == kp.point_id,
            QuestionBank.status == 1,
            QuestionBank.audit_status == 1,
        ).all()
        qids = [q[0] for q in questions]

        if not qids:
            continue

        total = db.query(func.count(ExamAnswerDetail.detail_id)).filter(
            ExamAnswerDetail.question_id.in_(qids)
        ).scalar() or 0

        if total <= 0:
            continue

        correct = db.query(func.count(ExamAnswerDetail.detail_id)).filter(
            ExamAnswerDetail.question_id.in_(qids),
            ExamAnswerDetail.is_correct == 1
        ).scalar() or 0

        items.append({
            "point_id": kp.point_id,
            "point_name": kp.point_name,
            "total_attempts": total,
            "correct_count": correct,
            "mastery_rate": round(correct / total * 100, 1) if total > 0 else 0,
            "subject_name": kp.subject.subject_name if kp.subject else "",
        })

    return {"success": True, "total": len(items), "items": items}
