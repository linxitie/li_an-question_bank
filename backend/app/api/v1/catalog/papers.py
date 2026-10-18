"""
试卷管理模块路由
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....models.models import (
    ExamPaper, PaperQuestionRelation, QuestionBank, SysUser,
    PaperApproval, ExamRecord, ExamAnswerDetail
)
from ....schemas.schemas import PaperCreate, PaperUpdate, PaperDetailResponse, SuccessResponse
from ....core.security import get_current_user, require_admin
from ....core.cache import set_cache, get_cache, delete_cache, PAPER_CACHE_PREFIX
from ....services import weakpoint_reader

router = APIRouter(prefix="/api/papers", tags=["试卷管理"])


def apply_weakpoint_recommendation(query, db: Session, user_id: int):
    """E13：按用户薄弱考点的题型筛选试卷；无薄弱点时原样返回全量查询。"""
    type_ids = weakpoint_reader.get_weakpoint_type_ids(db, user_id)
    if not type_ids:
        return query

    paper_ids = (
        db.query(PaperQuestionRelation.paper_id)
        .join(QuestionBank, PaperQuestionRelation.question_id == QuestionBank.question_id)
        .filter(QuestionBank.type_id.in_(type_ids))
        .subquery()
    )
    return query.filter(ExamPaper.paper_id.in_(select(paper_ids.c.paper_id)))


def _require_staff(current_user: SysUser) -> None:
    """组卷属于教师/管理员职责，学生不得建卷或改卷。"""
    if current_user.user_type not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="仅教师或管理员可以管理试卷")


def _require_admin_role(current_user: SysUser) -> None:
    """审批与发布只能由管理员执行（role_level>=2 的教师不算管理员）。"""
    if current_user.user_type != "admin" or current_user.role_level < 2:
        raise HTTPException(status_code=403, detail="仅管理员可以审批或发布试卷")


def _reject_transition(paper: ExamPaper, action: str, allowed: str) -> None:
    """非法状态流转统一返回 409，并在 detail 中附当前状态与允许的前置状态。"""
    raise HTTPException(
        status_code=409,
        detail=(
            f"当前试卷状态为 {paper.paper_type}，不允许{action}；"
            f"仅 {allowed} 状态可以{action}"
        ),
    )


@router.post("/", response_model=PaperDetailResponse, summary="创建试卷")
async def create_paper(
    paper_data: PaperCreate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建试卷

    教师建卷固定落为 DRAFT（草稿），必须经「提交审批」进入 PENDING 后，
    由管理员审批（APPROVED / 退回 DRAFT），再发布为 PUBLISHED。
    """
    _require_staff(current_user)

    # 检查试卷编号是否已存在
    existing = db.query(ExamPaper).filter(ExamPaper.paper_code == paper_data.paper_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="试卷编号已存在")
    
    paper = ExamPaper(
        **paper_data.dict(),
        creator_id=current_user.user_id,
        paper_type="DRAFT"  # 建卷一律草稿，禁止直接落审批/发布态
    )
    
    db.add(paper)
    db.commit()
    db.refresh(paper)
    
    # 清除相关缓存
    delete_cache(f"{PAPER_CACHE_PREFIX}*")
    
    return paper

@router.get("/{paper_id}", response_model=PaperDetailResponse, summary="获取试卷详情")
async def get_paper(
    paper_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取试卷详情

    学生（role_level < 2）只能读取 PUBLISHED 试卷；草稿/待审批试卷一律按不存在处理，
    避免通过详情端点探测未公开试卷。教师/管理员按原有权限读取。
    """
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    if current_user.role_level < 2 and paper.paper_type != "PUBLISHED":
        raise HTTPException(status_code=404, detail="试卷不存在")

    cache_key = f"{PAPER_CACHE_PREFIX}{paper_id}"
    # 只缓存已发布试卷，避免草稿内容经缓存泄漏给学生
    if paper.paper_type == "PUBLISHED":
        cached = get_cache(cache_key)
        if cached:
            return cached

    if paper.paper_type == "PUBLISHED":
        set_cache(cache_key, paper.__dict__)

    return paper

@router.put("/{paper_id}", response_model=PaperDetailResponse, summary="更新试卷")
async def update_paper(
    paper_id: int,
    paper_data: PaperUpdate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新试卷
    """
    _require_staff(current_user)

    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    # 只有管理员或创建者可以更新
    if current_user.user_type != "admin" and paper.creator_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权修改此试卷")

    if paper.paper_type != "DRAFT":
        _reject_transition(paper, "编辑", "DRAFT")
    
    for key, value in paper_data.dict(exclude_unset=True).items():
        setattr(paper, key, value)
    
    db.commit()
    db.refresh(paper)
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")
    
    return paper

@router.delete("/{paper_id}", response_model=SuccessResponse, summary="删除试卷")
async def delete_paper(
    paper_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除试卷（已发布试卷也可删除，需确认）
    """
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    # 权限检查：教师只能删自己的，管理员删所有
    if current_user.user_type == "teacher" and paper.creator_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权删除此试卷")
    
    # 删除关联题目关系
    db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).delete()
    
    # 删除审批记录
    db.query(PaperApproval).filter(PaperApproval.paper_id == paper_id).delete()
    
    # 记录操作日志
    from ....models.models import OperationLog
    log = OperationLog(
        user_id=current_user.user_id,
        action="delete_paper",
        target_type="paper",
        target_id=paper_id,
        details=f"删除试卷: {paper.paper_name}"
    )
    db.add(log)
    
    # 删除试卷
    db.delete(paper)
    db.commit()
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")
    
    return SuccessResponse(message="删除成功")


@router.get("/{paper_id}/preview", response_model=dict, summary="预览试卷（不含答案）")
async def preview_paper(
    paper_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    学生端预览试卷 - 仅显示题目，不含答案和解析
    """
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    if current_user.role_level < 2 and paper.paper_type != "PUBLISHED":
        raise HTTPException(status_code=404, detail="试卷不存在")

    from ....services.exam_service import ExamService
    try:
        preview_data = ExamService.get_exam_preview(db, paper_id)
        return preview_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats", response_model=dict, summary="获取题目统计")
async def get_paper_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取试卷/题目统计信息（按角色差异化）
    """
    from ....services.question_stats import QuestionStatsService
    stats = QuestionStatsService.get_stats(db, current_user)
    stats["paper_stats"] = QuestionStatsService.get_paper_stats(db, current_user)
    return stats

@router.post("/{paper_id}/questions", response_model=SuccessResponse, summary="添加题目到试卷")
async def add_questions_to_paper(
    paper_id: int,
    question_ids: List[int],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    添加题目到试卷
    """
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="只有草稿状态的试卷才能添加题目")
    
    order = paper.question_count
    
    for question_id in question_ids:
        # 检查题目是否已存在
        existing = db.query(PaperQuestionRelation).filter(
            PaperQuestionRelation.paper_id == paper_id,
            PaperQuestionRelation.question_id == question_id
        ).first()
        
        if existing:
            continue
        
        question = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
        if not question:
            continue
        
        relation = PaperQuestionRelation(
            paper_id=paper_id,
            question_id=question_id,
            question_order=order + 1,
            question_score=question.score
        )
        db.add(relation)
        order += 1
    
    paper.question_count = order
    db.commit()
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")
    
    return SuccessResponse(message=f"成功添加 {order - paper.question_count} 道题目")

@router.delete("/{paper_id}/questions/{question_id}", response_model=SuccessResponse, summary="从试卷移除题目")
async def remove_question_from_paper(
    paper_id: int,
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    从试卷移除题目
    """
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="只有草稿状态的试卷才能移除题目")
    
    relation = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id,
        PaperQuestionRelation.question_id == question_id
    ).first()
    
    if not relation:
        raise HTTPException(status_code=404, detail="题目不在该试卷中")
    
    db.delete(relation)
    paper.question_count -= 1
    db.commit()
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")
    
    return SuccessResponse(message="移除成功")

@router.post("/{paper_id}/submit", response_model=SuccessResponse, summary="提交审批")
async def submit_for_approval(
    paper_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    提交试卷审批
    """
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    if current_user.user_type != "admin" and paper.creator_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="只有创建者可以提交审批")
    
    if paper.paper_type != "DRAFT":
        _reject_transition(paper, "提交审批", "DRAFT")
    
    if paper.question_count == 0:
        raise HTTPException(status_code=400, detail="试卷不能为空")
    
    paper.paper_type = "PENDING"
    db.commit()
    
    # 创建审批记录
    approval = PaperApproval(
        paper_id=paper_id,
        approver_id=current_user.user_id,
        approval_result="PENDING"
    )
    db.add(approval)
    db.commit()
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")
    
    return SuccessResponse(message="已提交审批")

@router.post("/{paper_id}/approve", response_model=SuccessResponse, summary="审批试卷")
async def approve_paper(
    paper_id: int,
    approval_result: str,
    opinion: Optional[str] = None,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    审批试卷
    - **approval_result**: APPROVED/REJECTED
    """
    _require_admin_role(current_user)

    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    if paper.paper_type != "PENDING":
        _reject_transition(paper, "审批", "PENDING")
    
    if approval_result == "APPROVED":
        paper.paper_type = "APPROVED"
    elif approval_result == "REJECTED":
        paper.paper_type = "DRAFT"
    else:
        raise HTTPException(status_code=400, detail="无效的审批结果")
    
    # 更新审批记录
    approval = db.query(PaperApproval).filter(PaperApproval.paper_id == paper_id).first()
    if approval:
        approval.approver_id = current_user.user_id
        approval.approval_result = approval_result
        approval.approval_opinion = opinion
        approval.approval_time = datetime.now()
    
    db.commit()
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")
    
    message = "审批通过" if approval_result == "APPROVED" else "审批驳回"
    return SuccessResponse(message=message)

@router.post("/{paper_id}/publish", response_model=SuccessResponse, summary="发布试卷")
async def publish_paper(
    paper_id: int,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    发布试卷
    """
    _require_admin_role(current_user)

    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    if paper.paper_type != "APPROVED":
        _reject_transition(paper, "发布", "APPROVED")
    
    paper.paper_type = "PUBLISHED"
    paper.publish_time = datetime.now()
    paper.approver_id = current_user.user_id
    db.commit()
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")

    # 纵向通信走事件总线（catalog 域不跨域 import platform）：
    # EV_PAPER_PUBLISHED → 消费者推送 data-changed 到在线端。
    from ....core import events
    await events.publish(events.Event(
        name=events.EV_PAPER_PUBLISHED,
        payload={"paper_id": paper_id},
        aggregate_id=f"p-{paper_id}",
        source="catalog.papers",
    ))
    
    return SuccessResponse(message="发布成功")