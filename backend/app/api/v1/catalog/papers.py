"""
试卷管理模块路由
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....models.models import (
    ExamPaper, PaperQuestionRelation, QuestionBank, SysUser,
    PaperApproval, ExamRecord, ExamAnswerDetail
)
from ....schemas.schemas import PaperCreate, PaperUpdate, PaperDetailResponse, SuccessResponse
from ....core.security import get_current_user, require_admin
from ....cache import set_cache, get_cache, delete_cache, PAPER_CACHE_PREFIX

router = APIRouter(prefix="/api/papers", tags=["试卷管理"])

@router.post("/", response_model=PaperDetailResponse, summary="创建试卷")
async def create_paper(
    paper_data: PaperCreate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建试卷
    """
    # 检查试卷编号是否已存在
    existing = db.query(ExamPaper).filter(ExamPaper.paper_code == paper_data.paper_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="试卷编号已存在")
    
    paper = ExamPaper(
        **paper_data.dict(),
        creator_id=current_user.user_id
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
    db: Session = Depends(get_db)
):
    """
    获取试卷详情
    """
    cache_key = f"{PAPER_CACHE_PREFIX}{paper_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
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
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    # 只有管理员或创建者可以更新
    if current_user.role_level < 2 and paper.creator_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权修改此试卷")
    
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
    
    if paper.creator_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="只有创建者可以提交审批")
    
    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="只能提交草稿状态的试卷")
    
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
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    if paper.paper_type != "PENDING":
        raise HTTPException(status_code=400, detail="试卷状态不是待审批")
    
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
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    
    if paper.paper_type != "APPROVED":
        raise HTTPException(status_code=400, detail="只有已审批通过的试卷才能发布")
    
    paper.paper_type = "PUBLISHED"
    paper.publish_time = datetime.now()
    db.commit()
    
    delete_cache(f"{PAPER_CACHE_PREFIX}{paper_id}")
    
    return SuccessResponse(message="发布成功")