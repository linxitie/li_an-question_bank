"""
管理员端试卷审批 API — 审批列表、详情、通过、驳回、日志、不合格检测

复用现有表：状态机用 exam_paper.paper_type，审批历史用 paper_approval_workflow。
本模块对接教师端 submit-approval 所写的 PaperApprovalWorkflow（Flow B），
使其从 write-only 变为可被管理员处理，打通 教师提交→管理员审批→发布 的闭环。
"""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc

from ...core.database import get_db
from ...core.security import get_current_admin
from ...models.models import (
    ExamPaper, PaperApprovalWorkflow, PaperQuestionRelation, QuestionBank, SysUser,
)
from ...schemas.admin import PaperApproveRequest, PaperRejectRequest
from ...services.paper_issue_detector import detect_paper_issues

router = APIRouter(prefix="/api/admin/approval", tags=["管理员端-试卷审批"])
logger = logging.getLogger(__name__)


def _derive_approval_status(paper_type: str, workflow_status: str) -> str:
    """由 paper_type 与最新工作流状态派生审批态（pending/approved/rejected/其他）"""
    if paper_type == "PENDING":
        return "pending"
    if paper_type in ("APPROVED", "PUBLISHED"):
        return "approved"
    if paper_type == "DRAFT" and workflow_status == "rejected":
        return "rejected"
    return "other"


def _latest_workflow_subquery(db: Session):
    """返回「每卷最新 workflow 行」的子查询（按 max(workflow_id) 分组）"""
    return (
        db.query(
            PaperApprovalWorkflow.paper_id.label("paper_id"),
            func.max(PaperApprovalWorkflow.workflow_id).label("max_wid"),
        )
        .group_by(PaperApprovalWorkflow.paper_id)
        .subquery()
    )


def _get_latest_pending_workflow(db: Session, paper_id: int):
    """取某卷最新一条 pending 工作流（审批要处理的对象）"""
    return (
        db.query(PaperApprovalWorkflow)
        .filter(
            PaperApprovalWorkflow.paper_id == paper_id,
            PaperApprovalWorkflow.status == "pending",
        )
        .order_by(desc(PaperApprovalWorkflow.workflow_id))
        .first()
    )


@router.get("/papers", summary="试卷审批列表")
async def list_approval_papers(
    status: Optional[str] = Query(None, description="pending/approved/rejected，默认全部"),
    subject_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None, description="按试卷名或教师名搜索"),
    start_date: Optional[str] = Query(None, description="创建时间起（ISO 日期）"),
    end_date: Optional[str] = Query(None, description="创建时间止（ISO 日期）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """列出所有进入过审批流程的试卷（至少存在一条 workflow 记录）"""
    latest_wf = _latest_workflow_subquery(db)

    query = (
        db.query(ExamPaper, PaperApprovalWorkflow)
        .join(latest_wf, latest_wf.c.paper_id == ExamPaper.paper_id)
        .join(PaperApprovalWorkflow, PaperApprovalWorkflow.workflow_id == latest_wf.c.max_wid)
    )

    if status == "pending":
        query = query.filter(ExamPaper.paper_type == "PENDING")
    elif status == "approved":
        query = query.filter(ExamPaper.paper_type.in_(["APPROVED", "PUBLISHED"]))
    elif status == "rejected":
        query = query.filter(
            ExamPaper.paper_type == "DRAFT",
            PaperApprovalWorkflow.status == "rejected",
        )

    if subject_id:
        query = query.filter(ExamPaper.subject_id == subject_id)

    if keyword:
        creator_ids = db.query(SysUser.user_id).filter(
            SysUser.username.contains(keyword)
        ).subquery()
        query = query.filter(or_(
            ExamPaper.paper_name.contains(keyword),
            ExamPaper.creator_id.in_(creator_ids),
        ))

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(ExamPaper.create_time >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(ExamPaper.create_time <= ed)
        except ValueError:
            pass

    total = query.count()
    rows = (
        query.order_by(desc(ExamPaper.create_time))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for paper, wf in rows:
        items.append({
            "paper_id": paper.paper_id,
            "paper_name": paper.paper_name,
            "subject_id": paper.subject_id,
            "subject_name": paper.subject.subject_name if paper.subject else "",
            "creator_id": paper.creator_id,
            "creator_name": paper.creator.username if paper.creator else "",
            "question_count": paper.question_count,
            "total_score": float(paper.total_score) if paper.total_score else 0,
            "paper_type": paper.paper_type,
            "approval_status": _derive_approval_status(paper.paper_type, wf.status),
            "approval_opinion": wf.opinion or "",
            "submit_time": wf.submit_time.isoformat() if wf.submit_time else None,
            "create_time": paper.create_time.isoformat() if paper.create_time else None,
        })

    return {"success": True, "total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/papers/{paper_id}", summary="试卷审批详情")
async def get_approval_detail(
    paper_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """试卷完整详情（含题目与答案）+ 不合格检测结果 + 最新审批记录"""
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    rels = (
        db.query(PaperQuestionRelation)
        .filter(PaperQuestionRelation.paper_id == paper_id)
        .order_by(PaperQuestionRelation.question_order)
        .all()
    )

    questions = []
    for rel in rels:
        q = rel.question
        if not q:
            continue
        questions.append({
            "question_id": q.question_id,
            "question_no": rel.question_order,
            "type_id": q.type_id,
            "type_name": q.type.type_name if q.type else "",
            "question_content": q.question_content,
            "options": q.options,
            "answer": q.answer,
            "answer_analysis": q.answer_analysis or "",
            "score": float(rel.question_score) if rel.question_score else 0,
            "difficulty": q.difficulty,
        })

    issues = detect_paper_issues(questions)

    wf = (
        db.query(PaperApprovalWorkflow)
        .filter(PaperApprovalWorkflow.paper_id == paper_id)
        .order_by(desc(PaperApprovalWorkflow.workflow_id))
        .first()
    )

    return {
        "success": True,
        "paper": {
            "paper_id": paper.paper_id,
            "paper_name": paper.paper_name,
            "paper_code": paper.paper_code,
            "subject_id": paper.subject_id,
            "subject_name": paper.subject.subject_name if paper.subject else "",
            "creator_id": paper.creator_id,
            "creator_name": paper.creator.username if paper.creator else "",
            "creator_no": paper.creator.user_no if paper.creator else "",
            "composition_method": paper.composition_method,
            "duration": paper.duration,
            "total_score": float(paper.total_score) if paper.total_score else 0,
            "difficulty": paper.difficulty,
            "question_count": paper.question_count,
            "exam_type": paper.exam_type,
            "paper_type": paper.paper_type,
            "description": paper.description or "",
            "create_time": paper.create_time.isoformat() if paper.create_time else None,
            "publish_time": paper.publish_time.isoformat() if paper.publish_time else None,
        },
        "questions": questions,
        "issues": issues,
        "approval": {
            "status": wf.status if wf else None,
            "opinion": (wf.opinion or "") if wf else "",
            "approver_name": wf.approver.username if wf and wf.approver else "",
            "submit_time": wf.submit_time.isoformat() if wf and wf.submit_time else None,
            "approve_time": wf.approve_time.isoformat() if wf and wf.approve_time else None,
        },
    }


@router.post("/papers/{paper_id}/approve", summary="审批通过（自动发布）")
async def approve_paper(
    paper_id: int,
    data: PaperApproveRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """通过审批：paper_type → PUBLISHED（自动对学生可见），并更新最新 pending 工作流"""
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    if paper.paper_type != "PENDING":
        raise HTTPException(status_code=409, detail="试卷当前状态不可审批（仅待审批可操作）")

    wf = _get_latest_pending_workflow(db, paper_id)

    paper.paper_type = "PUBLISHED"
    paper.approver_id = current_user.user_id
    paper.publish_time = datetime.now()
    paper.update_time = datetime.now()

    if wf:
        wf.status = "approved"
        wf.approver_id = current_user.user_id
        wf.opinion = (data.opinion or "").strip() or None
        wf.approve_time = datetime.now()

    db.commit()

    try:
        from .admin import record_operation
        record_operation(db, current_user, "APPROVE", "试卷审批",
                         f"审批通过试卷 {paper.paper_name}(ID:{paper_id})")
    except Exception as e:  # 操作日志为尽力而为，不影响主流程
        logger.warning(f"记录审批操作日志失败: {e}")

    return {"success": True, "message": "审批通过，已自动发布"}


@router.post("/papers/{paper_id}/reject", summary="审批驳回")
async def reject_paper(
    paper_id: int,
    data: PaperRejectRequest,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """驳回：paper_type → DRAFT（退回教师修改），理由写入最新 pending 工作流"""
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    if paper.paper_type != "PENDING":
        raise HTTPException(status_code=409, detail="试卷当前状态不可审批（仅待审批可操作）")

    opinion = (data.opinion or "").strip()
    if not opinion:
        raise HTTPException(status_code=400, detail="驳回理由不能为空")

    wf = _get_latest_pending_workflow(db, paper_id)

    paper.paper_type = "DRAFT"
    paper.update_time = datetime.now()

    if wf:
        wf.status = "rejected"
        wf.approver_id = current_user.user_id
        wf.opinion = opinion
        wf.approve_time = datetime.now()

    db.commit()

    try:
        from .admin import record_operation
        record_operation(db, current_user, "REJECT", "试卷审批",
                         f"驳回试卷 {paper.paper_name}(ID:{paper_id}): {opinion}")
    except Exception as e:
        logger.warning(f"记录审批操作日志失败: {e}")

    return {"success": True, "message": "已驳回，退回教师修改"}


@router.get("/papers/{paper_id}/logs", summary="审批日志")
async def get_approval_logs(
    paper_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """该试卷的审批历史（append-only 工作流记录，按时间倒序）"""
    wfs = (
        db.query(PaperApprovalWorkflow)
        .filter(PaperApprovalWorkflow.paper_id == paper_id)
        .order_by(desc(PaperApprovalWorkflow.workflow_id))
        .all()
    )

    logs = []
    for wf in wfs:
        logs.append({
            "workflow_id": wf.workflow_id,
            "step": wf.step,
            "status": wf.status,
            "opinion": wf.opinion or "",
            "submitter_name": wf.submitter.username if wf.submitter else "",
            "approver_name": wf.approver.username if wf.approver else "",
            "submit_time": wf.submit_time.isoformat() if wf.submit_time else None,
            "approve_time": wf.approve_time.isoformat() if wf.approve_time else None,
        })

    return {"success": True, "items": logs}


@router.get("/papers/{paper_id}/issues", summary="不合格检测")
async def get_paper_issues(
    paper_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """运行时对试卷题目做静态质量检测（不落库）"""
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    rels = (
        db.query(PaperQuestionRelation)
        .filter(PaperQuestionRelation.paper_id == paper_id)
        .order_by(PaperQuestionRelation.question_order)
        .all()
    )

    questions = []
    for rel in rels:
        q = rel.question
        if not q:
            continue
        questions.append({
            "question_id": q.question_id,
            "question_no": rel.question_order,
            "type_name": q.type.type_name if q.type else "",
            "question_content": q.question_content,
            "options": q.options,
            "answer": q.answer,
            "score": float(rel.question_score) if rel.question_score else 0,
        })

    issues = detect_paper_issues(questions)
    return {"success": True, "items": issues, "error_count": sum(1 for i in issues if i["severity"] == "error"),
            "warn_count": sum(1 for i in issues if i["severity"] == "warn")}
