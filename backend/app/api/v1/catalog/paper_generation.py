"""
智能组卷模块路由 - 增强版
支持智能组卷、手动组卷、模板组卷三种模式
"""
import uuid
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ....core.database import get_db
from ....models.models import (
    ExamPaper,
    PaperQuestionRelation,
    QuestionBank,
    SysUser,
    QuestionSubject,
    QuestionType,
    KnowledgePoint
)
from ....schemas.schemas import (
    AutoGeneratePaperRequest,
    ManualGeneratePaperRequest,
    GeneratePaperResponse,
    PaperDetailResponse,
    PaperListResponse,
    SuccessResponse,
    PaperUpdate
)
from ....core.security import get_current_user, require_teacher_or_admin
from .papers import apply_weakpoint_recommendation
from ....services.event_consumer import (
    outbox_mode_enabled,
    publish_paper_published_legacy,
)
from ....foundation.outbox import emit as outbox_emit
from ....core.events import EV_PAPER_PUBLISHED

router = APIRouter(prefix="/api/papers", tags=["试卷管理"])
logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================

def generate_paper_code() -> str:
    """生成唯一试卷编号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = str(uuid.uuid4())[:8].upper()
    return f"PAPER-{timestamp}-{random_str}"


def calculate_difficulty(questions: List[QuestionBank]) -> int:
    """根据题目计算试卷平均难度"""
    if not questions:
        return 3
    avg_difficulty = sum(q.difficulty for q in questions) / len(questions)
    return round(avg_difficulty)


def validate_question_availability(
        db: Session,
        subject_id: int,
        type_id: int,
        difficulty: Optional[int] = None,
        point_ids: Optional[List[int]] = None,
        exclude_ids: Optional[List[int]] = None,
        required_count: int = 0
) -> Dict[str, any]:
    """
    验证题目可用性

    Returns:
        {
            "available": bool,
            "count": int,
            "message": str
        }
    """
    query = db.query(QuestionBank).filter(
        QuestionBank.status == 1,
        QuestionBank.audit_status == 1,
        QuestionBank.subject_id == subject_id,
        QuestionBank.type_id == type_id
    )

    if difficulty:
        query = query.filter(QuestionBank.difficulty == difficulty)

    if point_ids:
        query = query.filter(QuestionBank.point_id.in_(point_ids))

    if exclude_ids:
        query = query.filter(~QuestionBank.question_id.in_(exclude_ids))

    available_count = query.count()

    return {
        "available": available_count >= required_count,
        "count": available_count,
        "message": f"可用题目{available_count}道，需要{required_count}道"
    }


# ==================== 智能组卷 ====================

@router.post("/auto-generate", response_model=GeneratePaperResponse, summary="智能自动组卷")
async def auto_generate_paper(
        request: AutoGeneratePaperRequest,
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    智能自动组卷

    根据配置的题型、难度、知识点等条件自动抽取题目组成试卷

    **使用场景：**
    - 模拟考试快速出题
    - 练习题库随机生成
    - 按知识点分布组卷
    """
    # 1. 验证科目
    subject = db.query(QuestionSubject).filter(
        QuestionSubject.subject_id == request.subject_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 2. 验证题型配置
    total_questions = sum(config.count for config in request.question_configs)
    if total_questions == 0:
        raise HTTPException(status_code=400, detail="题目配置不能为空")

    # 3. 预检查：验证每种题型的题目是否充足
    selected_question_ids = set()
    validation_errors = []

    for idx, config in enumerate(request.question_configs):
        # 验证题型是否存在
        qtype = db.query(QuestionType).filter(
            QuestionType.type_id == config.type_id
        ).first()
        if not qtype:
            validation_errors.append(f"题型ID {config.type_id} 不存在")
            continue

        # 检查题目可用性
        result = validate_question_availability(
            db=db,
            subject_id=request.subject_id,
            type_id=config.type_id,
            difficulty=(config.difficulty.value if hasattr(config.difficulty,
                                                           'value') else config.difficulty) if config.difficulty else None,
            point_ids=config.points,
            exclude_ids=list(selected_question_ids),
            required_count=config.count
        )

        if not result["available"]:
            validation_errors.append(
                f"题型'{qtype.type_name}': {result['message']}"
            )

    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail=f"题目不足：{'；'.join(validation_errors)}"
        )

    # 4. 创建试卷主记录
    paper_code = generate_paper_code()
    difficulty_value = (
        request.difficulty.value
        if hasattr(request.difficulty, 'value')
        else request.difficulty
    )

    new_paper = ExamPaper(
        paper_name=request.paper_name,
        paper_code=paper_code,
        subject_id=request.subject_id,
        composition_method="AUTO",
        creator_id=current_user.user_id,
        duration=request.duration,
        total_score=request.total_score,
        difficulty=difficulty_value,
        question_count=total_questions,
        exam_type=request.exam_type,
        paper_type="DRAFT",
        shuffle_questions=request.shuffle_questions,
        shuffle_options=request.shuffle_options,
        description=f"自动生成试卷 - {subject.subject_name}",
        knowledge_range=json.dumps({
            "configs": [c.dict() for c in request.question_configs]
        })
    )

    db.add(new_paper)
    db.flush()

    # 5. 按配置抽取题目并建立关联
    total_score_calculated = 0
    question_order = 0

    for config in request.question_configs:
        # 构建查询条件
        query = db.query(QuestionBank).filter(
            QuestionBank.status == 1,
            QuestionBank.audit_status == 1,
            QuestionBank.subject_id == request.subject_id,
            QuestionBank.type_id == config.type_id,
            ~QuestionBank.question_id.in_(selected_question_ids) if selected_question_ids else True
        )

        # 难度筛选
        if config.difficulty:
            diff_value = (
                config.difficulty.value
                if hasattr(config.difficulty, 'value')
                else config.difficulty
            )
            query = query.filter(QuestionBank.difficulty == diff_value)

        # 知识点筛选
        if config.points:
            query = query.filter(QuestionBank.point_id.in_(config.points))

        # 随机抽取指定数量的题目
        questions = query.order_by(func.rand()).limit(config.count).all()

        # 计算每题平均分
        avg_score = request.total_score / total_questions if total_questions > 0 else 0

        # 添加题目关联
        for question in questions:
            question_order += 1
            score = question.score if question.score else avg_score

            relation = PaperQuestionRelation(
                paper_id=new_paper.paper_id,
                question_id=question.question_id,
                question_order=question_order,
                question_score=score
            )
            db.add(relation)

            selected_question_ids.add(question.question_id)
            total_score_calculated += score

    # 6. 更新试卷总分并提交
    new_paper.total_score = total_score_calculated
    db.commit()
    db.refresh(new_paper)

    logger.info(
        f"用户 {current_user.username} 智能组卷成功: {paper_code}, "
        f"题目数: {total_questions}, 总分: {total_score_calculated}"
    )

    return GeneratePaperResponse(
        paper_id=new_paper.paper_id,
        paper_code=paper_code,
        paper_name=request.paper_name,
        question_count=total_questions,
        total_score=total_score_calculated,
        message="智能组卷成功"
    )


# ==================== 手动组卷 ====================

@router.post("/manual-generate", response_model=GeneratePaperResponse, summary="手动组卷")
async def manual_generate_paper(
        request: ManualGeneratePaperRequest,
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    手动组卷

    根据指定的题目ID列表创建试卷，适合精确控制题目内容

    **使用场景：**
    - 精选真题组卷
    - 教师精心挑选题目
    - 特定考点强化训练
    """
    # 1. 验证科目
    subject = db.query(QuestionSubject).filter(
        QuestionSubject.subject_id == request.subject_id
    ).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 2. 验证题目ID列表
    if not request.question_ids:
        raise HTTPException(status_code=400, detail="题目列表不能为空")

    # 3. 批量查询题目并验证
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(request.question_ids),
        QuestionBank.subject_id == request.subject_id,
        QuestionBank.status == 1,
        QuestionBank.audit_status == 1
    ).all()

    if len(questions) != len(request.question_ids):
        found_ids = {q.question_id for q in questions}
        missing_ids = set(request.question_ids) - found_ids
        raise HTTPException(
            status_code=400,
            detail=f"以下题目不存在或不可用: {', '.join(map(str, missing_ids))}"
        )

    # 4. 计算总分
    total_score = 0
    if request.question_scores:
        # 使用自定义分值
        for qid, score in request.question_scores.items():
            total_score += score
    else:
        # 使用题目默认分值
        total_score = sum(q.score for q in questions if q.score)
        if total_score <= 0:
            total_score = len(questions) * 1.0  # 默认每题1分

    # 5. 计算平均难度
    avg_difficulty = calculate_difficulty(questions)

    # 6. 创建试卷
    paper_code = generate_paper_code()
    new_paper = ExamPaper(
        paper_name=request.paper_name,
        paper_code=paper_code,
        subject_id=request.subject_id,
        composition_method="MANUAL",
        creator_id=current_user.user_id,
        duration=request.duration,
        total_score=total_score,
        difficulty=avg_difficulty,
        question_count=len(questions),
        exam_type=request.exam_type if hasattr(request, 'exam_type') else "PRACTICE",
        paper_type="DRAFT",
        description=f"手动组卷 - {subject.subject_name}"
    )

    db.add(new_paper)
    db.flush()

    # 7. 添加题目关联（保持指定顺序）
    for idx, question_id in enumerate(request.question_ids):
        question = next((q for q in questions if q.question_id == question_id), None)
        if not question:
            continue

        score = (
            request.question_scores.get(question_id, question.score)
            if request.question_scores
            else question.score or 1.0
        )

        relation = PaperQuestionRelation(
            paper_id=new_paper.paper_id,
            question_id=question_id,
            question_order=idx + 1,
            question_score=score
        )
        db.add(relation)

    db.commit()
    db.refresh(new_paper)

    logger.info(
        f"用户 {current_user.username} 手动组卷成功: {paper_code}, "
        f"题目数: {len(questions)}, 总分: {total_score}"
    )

    return GeneratePaperResponse(
        paper_id=new_paper.paper_id,
        paper_code=paper_code,
        paper_name=request.paper_name,
        question_count=len(questions),
        total_score=total_score,
        message="手动组卷成功"
    )


# ==================== 模板组卷 ====================

@router.post("/template-generate", response_model=GeneratePaperResponse, summary="模板组卷")
async def template_generate_paper(
        template_id: int,
        paper_name: Optional[str] = None,
        exam_type: str = Query("SIMULATION", description="考试类型"),
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    基于试卷模板快速组卷

    从已有试卷复制结构和题目，快速生成新试卷

    **使用场景：**
    - 历年试卷复用
    - A/B卷生成
    - 多班级统一考试
    """
    # 1. 获取模板试卷
    template_paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == template_id
    ).first()

    if not template_paper:
        raise HTTPException(status_code=404, detail="模板试卷不存在")

    # 2. 获取模板试卷的题目
    template_relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == template_id
    ).order_by(PaperQuestionRelation.question_order).all()

    if not template_relations:
        raise HTTPException(status_code=400, detail="模板试卷没有题目")

    # 3. 验证题目是否仍然可用
    template_question_ids = [r.question_id for r in template_relations]
    available_questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(template_question_ids),
        QuestionBank.status == 1,
        QuestionBank.audit_status == 1
    ).all()

    available_ids = {q.question_id for q in available_questions}
    unavailable_ids = set(template_question_ids) - available_ids

    if unavailable_ids:
        logger.warning(f"模板中有{len(unavailable_ids)}道题目已不可用")

    # 4. 创建新试卷
    paper_code = generate_paper_code()
    new_paper_name = paper_name or f"{template_paper.paper_name}-副本"

    new_paper = ExamPaper(
        paper_name=new_paper_name,
        paper_code=paper_code,
        subject_id=template_paper.subject_id,
        composition_method="TEMPLATE",
        creator_id=current_user.user_id,
        duration=template_paper.duration,
        total_score=template_paper.total_score,
        difficulty=template_paper.difficulty,
        question_count=len(available_questions),
        exam_type=exam_type,
        paper_type="DRAFT",
        shuffle_questions=template_paper.shuffle_questions,
        shuffle_options=template_paper.shuffle_options,
        description=f"基于模板#{template_id}生成 - {template_paper.paper_name}"
    )

    db.add(new_paper)
    db.flush()

    # 5. 复制题目关联
    question_order = 0
    total_score = 0

    for relation in template_relations:
        if relation.question_id not in available_ids:
            continue

        question_order += 1
        new_relation = PaperQuestionRelation(
            paper_id=new_paper.paper_id,
            question_id=relation.question_id,
            question_order=question_order,
            question_score=relation.question_score
        )
        db.add(new_relation)
        total_score += relation.question_score

    # 6. 更新总分并提交
    new_paper.total_score = total_score
    new_paper.question_count = question_order
    db.commit()
    db.refresh(new_paper)

    logger.info(
        f"用户 {current_user.username} 模板组卷成功: {paper_code}, "
        f"基于模板#{template_id}"
    )

    return GeneratePaperResponse(
        paper_id=new_paper.paper_id,
        paper_code=paper_code,
        paper_name=new_paper_name,
        question_count=question_order,
        total_score=total_score,
        message="模板组卷成功"
    )


# ==================== 试卷管理 ====================

@router.get("/list", response_model=PaperListResponse, summary="试卷列表查询")
async def get_paper_list(
        subject_id: Optional[int] = Query(None, description="科目ID"),
        paper_type: Optional[str] = Query(None, description="试卷状态"),
        exam_type: Optional[str] = Query(None, description="考试类型"),
        composition_method: Optional[str] = Query(None, description="组卷方式"),
        keyword: Optional[str] = Query(None, max_length=100, description="搜索关键词"),
        recommend: bool = Query(False, description="推荐位：按用户薄弱考点筛选，无薄弱点时返回全量"),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    分页查询试卷列表

    **权限说明：**
    - 普通用户：只能看到已发布的试卷
    - 教师/管理员：可以看到自己创建的所有试卷
    - 超级管理员：可以看到所有试卷
    """
    query = db.query(ExamPaper)

    # 权限过滤
    if current_user.role_level < 2:
        # 普通用户只看发布的试卷
        query = query.filter(ExamPaper.paper_type == "PUBLISHED")
    elif current_user.role_level < 3:
        # 教师看自己创建的或发布的
        query = query.filter(
            or_(
                ExamPaper.creator_id == current_user.user_id,
                ExamPaper.paper_type == "PUBLISHED"
            )
        )
    # 管理员可以看到所有

    # 条件过滤
    if subject_id:
        query = query.filter(ExamPaper.subject_id == subject_id)
    if paper_type:
        query = query.filter(ExamPaper.paper_type == paper_type)
    if exam_type:
        query = query.filter(ExamPaper.exam_type == exam_type)
    if composition_method:
        query = query.filter(ExamPaper.composition_method == composition_method)
    if keyword:
        query = query.filter(
            or_(
                ExamPaper.paper_name.like(f"%{keyword}%"),
                ExamPaper.paper_code.like(f"%{keyword}%")
            )
        )

    # E13：推荐位复用成绩分析域的薄弱点服务（只读），无薄弱点或参数为空时退化为全量
    if recommend:
        query = apply_weakpoint_recommendation(query, db, current_user.user_id)

    # 统计总数
    total = query.count()

    # 分页查询
    papers = query.order_by(
        ExamPaper.create_time.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    return PaperListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=papers
    )

@router.get("/{paper_id}", response_model=PaperDetailResponse, summary="获取试卷详情")
async def get_paper_detail(
        paper_id: int,
        mode: str = Query("preview", description="模式: preview/exam/analysis"),
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    获取试卷详细信息

    **参数说明：**
    - **mode=preview**: 预览模式，显示答案和解析（教师用）
    - **mode=exam**: 考试模式，隐藏答案（学生用）
    - **mode=analysis**: 分析模式，显示完整信息包括统计
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id
    ).first()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 权限检查
    if paper.paper_type != "PUBLISHED" and paper.creator_id != current_user.user_id:
        if current_user.role_level < 2:
            raise HTTPException(status_code=403, detail="无权查看此试卷")

    # 获取试卷题目（按顺序）
    relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).order_by(PaperQuestionRelation.question_order).all()

    question_ids = [r.question_id for r in relations]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all()

    # 构建题目字典
    question_dict = {q.question_id: q for q in questions}
    relation_dict = {r.question_id: r for r in relations}

    # 按顺序组装题目列表
    paper_questions = []
    for relation in relations:
        if relation.question_id not in question_dict:
            continue

        q = question_dict[relation.question_id]
        q_data = q.__dict__.copy()

        # 根据不同模式处理敏感信息
        if mode == "exam" and paper.paper_type == "PUBLISHED":
            # 考试模式：隐藏答案和解析
            q_data.pop('answer', None)
            q_data.pop('answer_analysis', None)
        elif mode == "preview":
            # 预览模式：保留所有信息，添加题目顺序和分值
            pass

        # 添加额外信息
        q_data['question_order'] = relation.question_order
        q_data['question_score'] = float(relation.question_score)

        paper_questions.append(q_data)

    result = paper.__dict__.copy()
    result['questions'] = paper_questions
    result['mode'] = mode

    return PaperDetailResponse(**result)


@router.put("/{paper_id}", response_model=SuccessResponse, summary="更新试卷信息")
async def update_paper_info(
        paper_id: int,
        paper_data: PaperUpdate,
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    更新试卷基本信息（不改变题目组成）
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id
    ).first()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 权限检查
    if paper.creator_id != current_user.user_id and current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="无权修改此试卷")

    # 只有草稿状态的试卷可以修改
    if paper.paper_type not in ["DRAFT"]:
        raise HTTPException(status_code=400, detail="只有草稿状态的试卷可以修改")

    # 更新字段
    update_data = paper_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(paper, key, value)

    db.commit()
    db.refresh(paper)

    logger.info(f"用户 {current_user.username} 更新试卷 ID: {paper_id}")

    return SuccessResponse(message="试卷更新成功")




@router.post("/{paper_id}/publish", response_model=SuccessResponse, summary="发布试卷")
async def publish_paper(
        paper_id: int,
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    发布试卷（使对学生可见）
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id
    ).first()

    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    if current_user.user_type != "admin" or current_user.role_level < 2:
        raise HTTPException(status_code=403, detail="仅管理员可以发布试卷")

    # 状态检查：仅已审批通过的试卷可发布（封堵教师绕过审批直发草稿）
    if paper.paper_type != "APPROVED":
        raise HTTPException(
            status_code=409,
            detail=(
                f"当前试卷状态为 {paper.paper_type}，不允许发布；"
                f"仅 APPROVED 状态可以发布"
            ),
        )

    # 检查是否有题目
    question_count = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).count()

    if question_count == 0:
        raise HTTPException(status_code=400, detail="试卷不能为空")

    # 发布
    paper.paper_type = "PUBLISHED"
    paper.publish_time = datetime.now()
    paper.approver_id = current_user.user_id

    # 纵向通信走事件总线（catalog 域不跨域 import platform）：
    # EV_PAPER_PUBLISHED → 消费者推送 data-changed 到在线端。
    # F2b：开启 Outbox 时状态与事件同一事务；关闭时保留旧的 commit 后直发。
    if outbox_mode_enabled():
        outbox_emit(
            db,
            event_name=EV_PAPER_PUBLISHED,
            aggregate_type="paper",
            aggregate_id=f"p-{paper_id}",
            payload={"paper_id": paper_id},
            producer="catalog.paper_generation",
        )
        db.commit()
    else:
        db.commit()
        await publish_paper_published_legacy(
            paper_id, "catalog.paper_generation"
        )

    logger.info(f"用户 {current_user.username} 发布试卷 ID: {paper_id}")

    return SuccessResponse(message="试卷发布成功")


@router.post("/{paper_id}/duplicate", response_model=GeneratePaperResponse, summary="复制试卷")
async def duplicate_paper(
        paper_id: int,
        current_user: SysUser = Depends(require_teacher_or_admin),
        db: Session = Depends(get_db)
):
    """
    快速复制试卷（用于A/B卷或年度复用）
    """
    # 调用模板组卷逻辑
    return await template_generate_paper(
        template_id=paper_id,
        paper_name=None,
        exam_type="SIMULATION",
        current_user=current_user,
        db=db
    )
