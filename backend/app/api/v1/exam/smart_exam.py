"""
智能组卷 API 模块
面向学生角色，提供智能组卷全流程：
参数配置 → 预览微调 → 确认生成 → 答题卡 → 自动同步成绩分析

POST  /api/smart-exam/generate              — 智能组卷生成
POST  /api/smart-exam/{paper_id}/replace/{qid} — 替换题目
GET   /api/smart-exam/{paper_id}/preview    — 试卷预览
POST  /api/smart-exam/{paper_id}/confirm    — 确认试卷
POST  /api/smart-exam/{paper_id}/start      — 开始答题
POST  /api/smart-exam/{paper_id}/save-progress — 保存进度
POST  /api/smart-exam/{paper_id}/submit     — 提交+评分+同步自测
GET   /api/smart-exam/records               — 记录列表
GET   /api/smart-exam/records/{id}          — 记录详情
DELETE /api/smart-exam/records/{id}         — 删除记录
"""
import json
import logging
import uuid
from datetime import datetime, date
from typing import Optional, Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    ExamPaper,
    PaperQuestionRelation,
    SmartExamRecord,
    ExamRecord,
    ExamAnswerDetail,
    QuestionBank,
    QuestionSubject,
    QuestionType,
    SysUser,
    PracticeRecord,
    WrongQuestionPersonal,
)
from ....core.trigger_types import TRIGGER_PAPER_COMPLETED
from ....services.event_consumer import record_user_action
from ....services.option_utils import is_subjective_question
from ....services.paper_group_selector import (
    select_questions_with_groups,
    summarize_group_selection,
)
from ....schemas.schemas import (
    SmartExamGenerateRequest,
    SmartExamGenerateResponse,
    SmartExamSubmitRequest,
    SmartExamRecordItem,
    SmartExamRecordListResponse,
    SmartExamRecordDetailResponse,
    ReplaceQuestionRequest,
    QuestionPreviewItem,
    SuccessResponse,
)

router = APIRouter(prefix="/api/smart-exam", tags=["智能组卷"])
logger = logging.getLogger(__name__)


# ==================== 工具函数 ====================

def _get_user_smart_count(user_id: int, db: Session) -> int:
    """查询用户已生成的智能组卷数量，用于自动命名"""
    count = db.query(SmartExamRecord).filter(
        SmartExamRecord.user_id == user_id
    ).count()
    return count


def _generate_paper_code() -> str:
    """生成唯一试卷编号"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = str(uuid.uuid4())[:8].upper()
    return f"SMART-{timestamp}-{random_str}"


def _get_year_range_filter(year_range: str, year_start: Optional[int], year_end: Optional[int]):
    """
    根据年份范围参数返回过滤条件
    返回 (min_year, max_year) 元组
    """
    current_year = datetime.now().year
    if year_range == "3":
        return (current_year - 3, current_year)
    elif year_range == "5":
        return (current_year - 5, current_year)
    elif year_range == "10":
        return (current_year - 10, current_year)
    elif year_range == "custom" and year_start and year_end:
        return (year_start, year_end)
    else:
        return (None, None)  # 不限年份


def _difficulty_number(d: int) -> int:
    """
    将 1-5 难度映射到 简/中/难：
    1-2 → 简单, 3 → 中等, 4-5 → 困难
    """
    if d <= 2:
        return 1  # 简单
    elif d == 3:
        return 2  # 中等
    else:
        return 3  # 困难


def _auto_record_wrong(user_id: int, question_id: int, subject_id: int, db: Session):
    """自动将错题收录到个人错题集"""
    try:
        if not subject_id:
            q = db.query(QuestionBank).filter(
                QuestionBank.question_id == question_id
            ).first()
            if q:
                subject_id = q.subject_id
            else:
                return

        existing = db.query(WrongQuestionPersonal).filter(
            WrongQuestionPersonal.user_id == user_id,
            WrongQuestionPersonal.question_id == question_id,
            WrongQuestionPersonal.collection_type == "WRONG"
        ).first()

        if existing:
            existing.error_count = (existing.error_count or 0) + 1
            existing.last_review_time = datetime.now()
            existing.review_count = (existing.review_count or 0) + 1
        else:
            db.add(WrongQuestionPersonal(
                user_id=user_id,
                question_id=question_id,
                subject_id=subject_id,
                collection_type="WRONG",
                error_count=1,
                accuracy_rate=0.0,
                add_time=datetime.now(),
                last_review_time=datetime.now(),
                review_count=1,
            ))
    except Exception as e:
        logger.warning(f"自动收录错题失败(qid={question_id}): {e}")


# ==================== 1. 智能组卷生成 ====================

@router.post("/generate", response_model=SmartExamGenerateResponse, summary="智能组卷—生成试卷")
async def smart_generate_paper(
    request: SmartExamGenerateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    智能组卷—生成试卷

    根据科目模式、年份范围、难度分布和题型配置，智能抽取题目组成试卷。
    支持四种科目模式：行测(xingce)、申论(shenlun)、公专(gongzhuan)、混合(mixed)。

    **生成逻辑：**
    1. 按科目+题型+子科目配置分别抽取
    2. 按年份范围过滤题目
    3. 按难度比例分配（简单/中等/困难）
    4. 知识点去重（避免同一知识点过多重复）
    5. 混合模式合并行测+公专的题目
    """
    # 1. 自动生成试卷名称
    if request.paper_name:
        paper_name = request.paper_name
    else:
        seq = _get_user_smart_count(current_user.user_id, db) + 1
        # 中文数字映射
        cn_num = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}
        seq_str = cn_num.get(seq, str(seq))
        mode_label = {"xingce": "行测", "shenlun": "申论", "gongzhuan": "公专", "mixed": "混合"}
        paper_name = f"智能组卷第{seq_str}套"

    # 2. 验证配置
    total_questions = sum(config.count for config in request.question_configs)
    if total_questions == 0:
        raise HTTPException(status_code=400, detail="题目配置不能为空")

    # 难度比例验证
    if request.difficulty_easy_pct + request.difficulty_medium_pct + request.difficulty_hard_pct != 100:
        raise HTTPException(status_code=400, detail="难度比例之和必须为100%")

    # 3. 确定科目ID列表
    subject_ids = []
    if request.subject_mode == "xingce":
        subject_ids = [1]
    elif request.subject_mode == "shenlun":
        subject_ids = [2]
    elif request.subject_mode == "gongzhuan":
        subject_ids = [3]
    elif request.subject_mode == "mixed":
        subject_ids = [1, 3]  # 行测 + 公专
    else:
        raise HTTPException(status_code=400, detail=f"不支持的科目模式: {request.subject_mode}")

    # 4. 获取年份范围
    min_year, max_year = _get_year_range_filter(
        request.year_range, request.year_start, request.year_end
    )

    # 5. 按配置抽取题目
    selected_question_ids = set()
    selected_questions = []
    difficulty_stats = {"easy": 0, "medium": 0, "hard": 0}
    subject_stats = {}

    for config in request.question_configs:
        # 验证题型
        qtype = db.query(QuestionType).filter(
            QuestionType.type_id == config.type_id
        ).first()
        if not qtype:
            raise HTTPException(status_code=400, detail=f"题型ID {config.type_id} 不存在")

        # 计算该配置的难度分布
        easy_count = max(1, round(config.count * request.difficulty_easy_pct / 100))
        medium_count = max(1, round(config.count * request.difficulty_medium_pct / 100))
        hard_count = config.count - easy_count - medium_count
        if hard_count < 1:
            medium_count = config.count - easy_count
            hard_count = 0 if medium_count > 0 else 1
            if medium_count < 0:
                easy_count = config.count
                medium_count = 0

        difficulty_buckets = [
            (1, easy_count),    # 简单: difficulty 1-2
            (2, medium_count),  # 中等: difficulty 3
            (3, hard_count),    # 困难: difficulty 4-5
        ]

        for diff_bucket, need_count in difficulty_buckets:
            if need_count <= 0:
                continue

            # 构建查询
            query = db.query(QuestionBank).filter(
                QuestionBank.status == 1,
                QuestionBank.audit_status == 1,
                QuestionBank.subject_id == config.subject_id,
                QuestionBank.type_id == config.type_id,
                ~QuestionBank.question_id.in_(selected_question_ids) if selected_question_ids else True
            )

            # 年份过滤
            if min_year is not None and max_year is not None:
                query = query.filter(QuestionBank.year >= min_year, QuestionBank.year <= max_year)

            # 子科目过滤
            if config.subcategory:
                subcat = config.subcategory
                if config.subject_id == 1:
                    query = query.filter(QuestionBank.xingce_subcategory == subcat)
                elif config.subject_id == 2:
                    query = query.filter(QuestionBank.shenlun_subcategory == subcat)
                elif config.subject_id == 3:
                    query = query.filter(QuestionBank.gongzhuan_subcategory == subcat)

            # 难度过滤
            if diff_bucket == 1:
                query = query.filter(QuestionBank.difficulty.in_([1, 2]))
            elif diff_bucket == 2:
                query = query.filter(QuestionBank.difficulty == 3)
            else:
                query = query.filter(QuestionBank.difficulty.in_([4, 5]))

            # 随机抽取（题组感知：命中复合题整组展开，材料与子题不拆散）
            questions, selected_question_ids = select_questions_with_groups(
                db=db,
                query=query,
                count=need_count,
                selected_ids=selected_question_ids,
            )

            for q in questions:
                selected_questions.append({
                    "question": q,
                    "config": config,
                })

                # 统计
                d = q.difficulty
                if d <= 2:
                    difficulty_stats["easy"] += 1
                elif d == 3:
                    difficulty_stats["medium"] += 1
                else:
                    difficulty_stats["hard"] += 1

                subj_name = db.query(QuestionSubject).filter(
                    QuestionSubject.subject_id == q.subject_id
                ).first()
                subj_label = subj_name.subject_name if subj_name else f"科目{q.subject_id}"
                if subj_label not in subject_stats:
                    subject_stats[subj_label] = 0
                subject_stats[subj_label] += 1

    # 6. 检查是否有足够的题目
    if len(selected_questions) < total_questions:
        logger.warning(
            f"智能组卷题目不足: 需要{total_questions}道, 实际抽到{len(selected_questions)}道"
        )

    # 7. 创建试卷
    duration = request.duration or 120  # 默认120分钟
    paper_code = _generate_paper_code()
    avg_difficulty = round(
        sum(item["question"].difficulty for item in selected_questions) / max(len(selected_questions), 1)
    ) if selected_questions else 3

    new_paper = ExamPaper(
        paper_name=paper_name,
        paper_code=paper_code,
        subject_id=subject_ids[0],  # 主科目
        composition_method="SMART",
        creator_id=current_user.user_id,
        duration=duration,
        total_score=sum(config.count * config.score_per_question for config in request.question_configs),
        difficulty=avg_difficulty,
        question_count=len(selected_questions),
        exam_type="PRACTICE",
        paper_type="DRAFT",  # 私有草稿，不发布
        description=f"智能组卷 - {paper_name}",
        knowledge_range=json.dumps({
            "subject_mode": request.subject_mode,
            "year_range": request.year_range,
            "configs": [c.model_dump() for c in request.question_configs],
        }, ensure_ascii=False),
    )

    db.add(new_paper)
    db.flush()

    # 8. 创建题目关联
    total_score_calculated = 0.0
    for idx, item in enumerate(selected_questions):
        q = item["question"]
        cfg = item["config"]
        score = cfg.score_per_question

        relation = PaperQuestionRelation(
            paper_id=new_paper.paper_id,
            question_id=q.question_id,
            question_order=idx + 1,
            question_score=score,
        )
        db.add(relation)
        total_score_calculated += score

    new_paper.total_score = total_score_calculated
    db.commit()
    db.refresh(new_paper)

    # 9. 构建预览题目列表
    question_previews = []
    for item in selected_questions:
        q = item["question"]
        cfg = item["config"]

        # 获取题型名称
        qtype = db.query(QuestionType).filter(QuestionType.type_id == q.type_id).first()
        type_name = qtype.type_name if qtype else "未知"
        is_subjective = is_subjective_question(q, qtype)

        # 获取子科目
        subcat = cfg.get("subcategory") or ""
        if not subcat:
            if q.subject_id == 1:
                subcat = q.xingce_subcategory or ""
            elif q.subject_id == 2:
                subcat = q.shenlun_subcategory or ""
            elif q.subject_id == 3:
                subcat = q.gongzhuan_subcategory or ""

        question_previews.append(QuestionPreviewItem(
            question_id=q.question_id,
            question_content=q.question_content[:200] + "..." if q.question_content and len(q.question_content) > 200 else (q.question_content or ""),
            question_type=qtype.type_code if qtype else "",
            type_name=type_name,
            difficulty=q.difficulty,
            options=[] if is_subjective else q.options,
            answer=None,  # 预览不显示答案（客户端可点击展开查看）
            answer_analysis=None,
            subcategory=subcat,
            year=q.year,
            score=cfg.score_per_question,
        ))

    logger.info(
        f"用户 {current_user.username} 智能组卷成功: {paper_code}, "
        f"题目数: {len(selected_questions)}, 总分: {total_score_calculated}"
    )

    quota = summarize_group_selection(total_questions, len(selected_questions))
    message = "智能组卷生成成功"
    if quota["over_quota"]:
        message += f"；{quota['over_quota_reason']}，请核对后再发布"

    return SmartExamGenerateResponse(
        paper_id=new_paper.paper_id,
        paper_name=paper_name,
        paper_code=paper_code,
        questions=question_previews,
        total_score=total_score_calculated,
        question_count=len(selected_questions),
        difficulty_distribution=difficulty_stats,
        subject_breakdown=subject_stats,
        duration=duration,
        message=message,
        **quota,
    )


# ==================== 2. 替换题目 ====================

@router.post("/{paper_id}/replace/{question_id}", summary="替换单道题目")
async def replace_question(
    paper_id: int,
    question_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    替换试卷中的一道题目

    在同类型、同难度、同知识点的候选题中随机选取一道替换。
    候选题排除试卷中已有的题目。
    """
    # 验证试卷归属
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id,
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")

    # 获取当前题目
    current_question = db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id
    ).first()
    if not current_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 获取试卷已有题目ID
    existing_relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).all()
    existing_ids = {r.question_id for r in existing_relations}

    # 查找候选题
    query = db.query(QuestionBank).filter(
        QuestionBank.status == 1,
        QuestionBank.audit_status == 1,
        QuestionBank.subject_id == current_question.subject_id,
        QuestionBank.type_id == current_question.type_id,
        QuestionBank.difficulty == current_question.difficulty,
        ~QuestionBank.question_id.in_(existing_ids),
    )

    # 同知识点优先
    if current_question.point_id:
        query = query.filter(QuestionBank.point_id == current_question.point_id)

    alternatives = query.order_by(func.random()).limit(5).all()

    if not alternatives:
        # 放宽知识点限制
        alternatives = db.query(QuestionBank).filter(
            QuestionBank.status == 1,
            QuestionBank.audit_status == 1,
            QuestionBank.subject_id == current_question.subject_id,
            QuestionBank.type_id == current_question.type_id,
            QuestionBank.difficulty == current_question.difficulty,
            ~QuestionBank.question_id.in_(existing_ids),
        ).order_by(func.random()).limit(5).all()

    if not alternatives:
        raise HTTPException(status_code=400, detail="没有可替换的候选题")

    # 随机选一道替换
    import random
    new_question = random.choice(alternatives)

    # 更新关联
    relation = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id,
        PaperQuestionRelation.question_id == question_id,
    ).first()
    if not relation:
        raise HTTPException(status_code=404, detail="题目不在试卷中")

    old_order = relation.question_order
    old_score = float(relation.question_score)

    # 删除旧关联，创建新关联
    db.delete(relation)
    db.flush()

    new_relation = PaperQuestionRelation(
        paper_id=paper_id,
        question_id=new_question.question_id,
        question_order=old_order,
        question_score=old_score,
    )
    db.add(new_relation)
    db.commit()

    # 获取题型名称
    qtype = db.query(QuestionType).filter(QuestionType.type_id == new_question.type_id).first()

    logger.info(f"用户 {current_user.username} 替换题目: paper={paper_id}, {question_id}→{new_question.question_id}")

    return {
        "message": "题目替换成功",
        "old_question_id": question_id,
        "new_question_id": new_question.question_id,
        "new_question": {
            "question_id": new_question.question_id,
            "question_content": new_question.question_content[:200] + "..." if new_question.question_content and len(new_question.question_content) > 200 else (new_question.question_content or ""),
            "difficulty": new_question.difficulty,
            "type_name": qtype.type_name if qtype else "",
            "year": new_question.year,
        }
    }


# ==================== 3. 试卷预览 ====================

@router.get("/{paper_id}/preview", summary="获取试卷预览")
async def preview_paper(
    paper_id: int,
    show_answer: bool = Query(False, description="是否显示答案"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取试卷完整预览（含所有题目详情）
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 权限检查：只能看自己的智能组卷或已发布的试卷
    if paper.creator_id != current_user.user_id and paper.paper_type != "PUBLISHED":
        raise HTTPException(status_code=403, detail="无权查看此试卷")

    # 获取题目
    relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).order_by(PaperQuestionRelation.question_order).all()

    question_ids = [r.question_id for r in relations]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all() if question_ids else []
    question_map = {q.question_id: q for q in questions}

    questions_list = []
    for r in relations:
        q = question_map.get(r.question_id)
        if not q:
            continue

        qtype = db.query(QuestionType).filter(QuestionType.type_id == q.type_id).first()
        is_subjective = is_subjective_question(q, qtype)

        questions_list.append({
            "question_id": q.question_id,
            "question_order": r.question_order,
            "question_content": q.question_content,
            "question_type": qtype.type_code if qtype else "",
            "type_name": qtype.type_name if qtype else "",
            "difficulty": q.difficulty,
            "options": [] if is_subjective else q.options,
            "is_subjective": is_subjective,
            "answer": q.answer if show_answer else None,
            "answer_analysis": q.answer_analysis if show_answer else None,
            "score": float(r.question_score),
            "year": q.year,
        })

    return {
        "paper_id": paper.paper_id,
        "paper_name": paper.paper_name,
        "paper_code": paper.paper_code,
        "subject_id": paper.subject_id,
        "duration": paper.duration,
        "total_score": float(paper.total_score),
        "difficulty": paper.difficulty,
        "question_count": len(questions_list),
        "questions": questions_list,
    }


# ==================== 4. 确认试卷 ====================

@router.post("/{paper_id}/confirm", summary="确认试卷")
async def confirm_paper(
    paper_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    确认试卷生成完成，准备开始答题

    将试卷状态从 DRAFT 更新为 APPROVED（私有状态，不公开发布）。
    """
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
        ExamPaper.creator_id == current_user.user_id,
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在或无权操作")

    if paper.paper_type != "DRAFT":
        raise HTTPException(status_code=400, detail="试卷已确认，无需重复操作")

    # 检查题目数量
    question_count = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).count()
    if question_count == 0:
        raise HTTPException(status_code=400, detail="试卷不能为空")

    paper.paper_type = "APPROVED"
    paper.publish_time = datetime.now()
    db.commit()

    logger.info(f"用户 {current_user.username} 确认智能组卷: {paper.paper_id}")

    return {
        "message": "试卷已确认",
        "paper_id": paper.paper_id,
        "paper_name": paper.paper_name,
        "question_count": question_count,
        "total_score": float(paper.total_score),
        "duration": paper.duration,
    }


# ==================== 5. 开始答题 ====================

@router.post("/{paper_id}/start", summary="开始答题")
async def start_smart_exam(
    paper_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    开始智能组卷答题

    创建 SmartExamRecord 记录，支持断点续答。
    如果已有未完成的记录，直接返回继续做题。
    """
    # 验证试卷
    paper = db.query(ExamPaper).filter(
        ExamPaper.paper_id == paper_id,
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    # 检查是否有未完成的记录
    existing = db.query(SmartExamRecord).filter(
        SmartExamRecord.user_id == current_user.user_id,
        SmartExamRecord.paper_id == paper_id,
        SmartExamRecord.status == "incomplete",
    ).first()

    if existing:
        # 返回已有记录，继续做题
        return {
            "message": "继续未完成的答题",
            "record_id": existing.id,
            "paper_id": existing.paper_id,
            "paper_name": existing.paper_name,
            "current_index": existing.current_index,
            "answers_json": existing.answers_json,
            "marked_questions": existing.marked_questions,
            "time_spent": existing.time_spent,
            "total_questions": existing.total_questions,
            "completed_count": existing.completed_count,
            "is_resume": True,
        }

    # 获取题目列表
    relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).order_by(PaperQuestionRelation.question_order).all()

    question_ids = [r.question_id for r in relations]
    if not question_ids:
        raise HTTPException(status_code=400, detail="试卷没有题目")

    # 创建新的智能组卷记录
    smart_record = SmartExamRecord(
        user_id=current_user.user_id,
        paper_id=paper_id,
        paper_name=paper.paper_name,
        subject_mode="xingce",  # 从 paper 的 knowledge_range 中解析
        total_questions=len(question_ids),
        completed_count=0,
        total_score=float(paper.total_score),
        status="incomplete",
        current_index=0,
        answers_json="{}",
        marked_questions="[]",
        time_spent=0,
        start_time=datetime.now(),
    )
    db.add(smart_record)
    db.commit()
    db.refresh(smart_record)

    logger.info(f"用户 {current_user.username} 开始智能组卷答题: record={smart_record.id}")

    return {
        "message": "开始答题",
        "record_id": smart_record.id,
        "paper_id": paper_id,
        "paper_name": paper.paper_name,
        "current_index": 0,
        "answers_json": "{}",
        "marked_questions": "[]",
        "time_spent": 0,
        "total_questions": len(question_ids),
        "completed_count": 0,
        "is_resume": False,
    }


# ==================== 6. 保存进度 ====================

@router.post("/{paper_id}/save-progress", summary="保存答题进度")
async def save_progress(
    paper_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    payload: Dict[str, Any] = None,
):
    """
    保存答题进度（断点续答）

    请求体示例:
    {
        "answers_json": "{\"1\": \"A\", \"2\": \"B,C\"}",
        "current_index": 15,
        "completed_count": 12,
        "marked_questions": "[1, 5, 10]",
        "time_spent": 600
    }
    """
    smart_record = db.query(SmartExamRecord).filter(
        SmartExamRecord.user_id == current_user.user_id,
        SmartExamRecord.paper_id == paper_id,
        SmartExamRecord.status == "incomplete",
    ).first()

    if not smart_record:
        raise HTTPException(status_code=404, detail="未找到进行中的答题记录")

    if payload:
        if "answers_json" in payload:
            smart_record.answers_json = payload["answers_json"] if isinstance(payload["answers_json"], str) else json.dumps(payload["answers_json"], ensure_ascii=False)
        if "current_index" in payload:
            smart_record.current_index = payload["current_index"]
        if "completed_count" in payload:
            smart_record.completed_count = payload["completed_count"]
        if "marked_questions" in payload:
            smart_record.marked_questions = payload["marked_questions"] if isinstance(payload["marked_questions"], str) else json.dumps(payload["marked_questions"])
        if "time_spent" in payload:
            smart_record.time_spent = payload["time_spent"]

    smart_record.update_time = datetime.now()
    db.commit()

    return {"message": "进度已保存", "record_id": smart_record.id}


# ==================== 7. 提交试卷（核心） ====================

@router.post("/{paper_id}/submit", summary="提交试卷+自动评分+同步自测")
async def submit_smart_exam(
    paper_id: int,
    request: SmartExamSubmitRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    提交智能组卷答案

    **核心流程：**
    1. 自动评分客观题
    2. 创建 ExamRecord (exam_type=SELF_TEST) → 自动同步到「成绩分析图→自测」
    3. 批量创建 ExamAnswerDetail（每题答题明细）
    4. 更新 SmartExamRecord 状态为 completed
    5. 自动收录错题到 WrongQuestionPersonal
    6. 批量记录 PracticeRecord
    7. 触发自动签到
    8. 返回成绩摘要
    """
    # 1. 获取智能组卷记录
    smart_record = db.query(SmartExamRecord).filter(
        SmartExamRecord.user_id == current_user.user_id,
        SmartExamRecord.paper_id == paper_id,
    ).first()

    if not smart_record:
        # 容忍：没有 start 记录时自动创建
        paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="试卷不存在")
        smart_record = SmartExamRecord(
            user_id=current_user.user_id,
            paper_id=paper_id,
            paper_name=paper.paper_name,
            total_questions=paper.question_count or len(request.answers),
            total_score=float(paper.total_score),
            status="incomplete",
            start_time=datetime.now(),
        )
        db.add(smart_record)
        db.flush()

    if smart_record.status == "completed":
        return {
            "message": "该试卷已提交，本次重复回调已忽略",
            "record_id": smart_record.id,
            "exam_record_id": smart_record.exam_record_id,
            "paper_id": paper_id,
            "paper_name": smart_record.paper_name,
            "earned_score": float(smart_record.earned_score or 0),
            "duplicate": True,
            "synced_to_analysis": True,
        }

    # 2. 获取试卷和题目
    paper = db.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")

    relations = db.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id
    ).order_by(PaperQuestionRelation.question_order).all()

    question_ids = [r.question_id for r in relations]
    questions = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(question_ids)
    ).all() if question_ids else []
    question_map = {q.question_id: q for q in questions}
    relation_map = {r.question_id: r for r in relations}

    # 3. 自动评分
    now = datetime.now()
    total_score = 0.0
    scored_count = 0
    correct_count = 0
    wrong_count = 0

    for question_id, student_answer in request.answers.items():
        qid = int(question_id)
        question = question_map.get(qid)
        if not question:
            continue

        is_correct = None
        score_obtained = 0.0

        # 获取题型判断是否客观题
        qtype = db.query(QuestionType).filter(QuestionType.type_id == question.type_id).first()
        is_objective = qtype.is_objective if qtype and hasattr(qtype, 'is_objective') and qtype.is_objective is not None else True

        if is_objective:
            correct_answer = (question.answer or "").strip()
            student_ans = student_answer.strip() if student_answer else ""

            # 多选题乱序判断
            if "," in correct_answer:
                correct_set = set(correct_answer.replace("，", ",").split(","))
                student_set = set(student_ans.replace("，", ",").split(","))
                is_correct = correct_set == student_set
            else:
                is_correct = correct_answer.upper() == student_ans.upper()

            if is_correct:
                relation = relation_map.get(qid)
                score_obtained = float(relation.question_score) if relation else (float(paper.total_score) / max(len(question_ids), 1))
                total_score += score_obtained
                correct_count += 1
            else:
                wrong_count += 1
        else:
            # 主观题暂不自动评分
            pass

        scored_count += 1

        # 创建答题详情
        answer_detail = ExamAnswerDetail(
            record_id=0,  # 先占位，创建 ExamRecord 后更新
            question_id=qid,
            student_answer=student_answer,
            is_correct=1 if is_correct else (0 if is_correct is not None else None),
            score_obtained=score_obtained,
            difficulty=question.difficulty,
            correct_answer=question.answer,
            answer_analysis=question.answer_analysis,
            knowledge_point=str(question.point_id) if question.point_id else None,
            create_time=now,
        )
        db.add(answer_detail)
        db.flush()  # 获取 detail_id

    # 4. 创建 ExamRecord (SELF_TEST → 同步到成绩分析→自测)
    time_spent = smart_record.time_spent or 0

    exam_record = ExamRecord(
        paper_id=paper_id,
        user_id=current_user.user_id,
        exam_type="SELF_TEST",
        start_time=smart_record.start_time or now,
        end_time=now,
        duration_used=time_spent,
        total_score=total_score,
        is_completed=1,
        is_scored=1,
        submit_time=now,
        attempt_count=1,
    )
    db.add(exam_record)
    db.flush()

    # 更新答题详情的 record_id
    for detail in db.query(ExamAnswerDetail).filter(
        ExamAnswerDetail.record_id == 0
    ).all():
        detail.record_id = exam_record.record_id

    # 5. 更新智能组卷记录
    smart_record.status = "completed"
    smart_record.end_time = now
    smart_record.earned_score = total_score
    smart_record.time_spent = time_spent
    smart_record.completed_count = scored_count
    smart_record.answers_json = json.dumps(request.answers, ensure_ascii=False)
    smart_record.exam_record_id = exam_record.record_id

    # 6. 自动收录错题 + 批量记录 PracticeRecord
    today = date.today()
    for question_id, student_answer in request.answers.items():
        qid = int(question_id)
        question = question_map.get(qid)
        if not question:
            continue

        # 判断对错
        correct_answer = (question.answer or "").strip()
        student_ans = student_answer.strip() if student_answer else ""
        if "," in correct_answer:
            correct_set = set(correct_answer.replace("，", ",").split(","))
            student_set = set(student_ans.replace("，", ",").split(","))
            is_q_correct = correct_set == student_set
        else:
            is_q_correct = correct_answer.upper() == student_ans.upper()

        # PracticeRecord
        practice = PracticeRecord(
            user_id=current_user.user_id,
            question_id=qid,
            subject_id=question.subject_id,
            type_id=question.type_id,
            answer=student_answer,
            is_correct=1 if is_q_correct else 0,
            practice_time=now,
            practice_date=today,
            time_spent=0,
            source_type="智能组卷",
        )
        db.add(practice)

        # 错题收录
        if not is_q_correct:
            _auto_record_wrong(current_user.user_id, qid, question.subject_id, db)

    # 7. 自动签到
    try:
        from ....api.v1.exam.stats import ensure_daily_checkin
        ensure_daily_checkin(current_user.user_id, db)
    except Exception as e:
        logger.warning(f"自动签到失败: {e}")

    # F2b：整卷记录、练习明细与完成事件同一事务提交。
    db.flush()
    await record_user_action(
        db,
        current_user.user_id,
        TRIGGER_PAPER_COMPLETED,
        session={
            "paper_id": paper_id,
            "record_id": smart_record.id,
            "exam_record_id": exam_record.record_id,
            "total_score": total_score,
            "max_score": float(paper.total_score or 0),
        },
    )
    db.commit()

    # 计算正确率
    accuracy = round(correct_count / max(scored_count, 1) * 100, 1)

    logger.info(
        f"用户 {current_user.username} 提交智能组卷: record={smart_record.id}, "
        f"exam_record={exam_record.record_id}, 得分={total_score}/{float(paper.total_score)}, "
        f"正确率={accuracy}%"
    )

    return {
        "message": "提交成功！成绩已同步到成绩分析",
        "record_id": smart_record.id,
        "exam_record_id": exam_record.record_id,
        "paper_id": paper_id,
        "paper_name": paper.paper_name,
        "total_score": total_score,
        "max_score": float(paper.total_score),
        "accuracy": accuracy,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "scored_count": scored_count,
        "time_spent": time_spent,
        "synced_to_analysis": True,
    }


# ==================== 8. 记录列表 ====================

@router.get("/records", response_model=SmartExamRecordListResponse, summary="我的智能组卷记录")
async def get_smart_exam_records(
    status: Optional[str] = Query(None, description="筛选状态: incomplete/completed"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户的智能组卷记录列表

    - 未完成记录（红色状态标签）：可点击继续答题
    - 已完成记录（绿色状态标签）：可查看成绩详情
    """
    query = db.query(SmartExamRecord).filter(
        SmartExamRecord.user_id == current_user.user_id
    )

    if status:
        query = query.filter(SmartExamRecord.status == status)

    total = query.count()
    records = query.order_by(desc(SmartExamRecord.create_time)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = []
    for r in records:
        items.append(SmartExamRecordItem(
            id=r.id,
            record_id=r.id,
            paper_id=r.paper_id,
            paper_name=r.paper_name or "未命名试卷",
            subject_mode=r.subject_mode or "",
            total_questions=r.total_questions or 0,
            completed_count=r.completed_count or 0,
            total_score=float(r.total_score) if r.total_score else 0,
            earned_score=float(r.earned_score) if r.earned_score else None,
            status=r.status or "incomplete",
            time_spent=r.time_spent or 0,
            start_time=r.start_time.strftime("%Y-%m-%d %H:%M:%S") if r.start_time else None,
            end_time=r.end_time.strftime("%Y-%m-%d %H:%M:%S") if r.end_time else None,
            create_time=r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
        ))

    return SmartExamRecordListResponse(total=total, items=items)


# ==================== 9. 记录详情 ====================

@router.get("/records/{record_id}", summary="获取智能组卷记录详情")
async def get_smart_exam_record_detail(
    record_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取单次智能组卷记录的详细信息

    包含答题进度、答案快照、关联的考试成绩等。
    """
    smart_record = db.query(SmartExamRecord).filter(
        SmartExamRecord.id == record_id,
        SmartExamRecord.user_id == current_user.user_id,
    ).first()

    if not smart_record:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 获取关联的考试成绩
    exam_data = None
    if smart_record.exam_record_id:
        exam_record = db.query(ExamRecord).filter(
            ExamRecord.record_id == smart_record.exam_record_id
        ).first()
        if exam_record:
            # 获取答题详情
            details = db.query(ExamAnswerDetail).filter(
                ExamAnswerDetail.record_id == exam_record.record_id
            ).all()

            exam_data = {
                "record_id": exam_record.record_id,
                "total_score": float(exam_record.total_score),
                "duration_used": exam_record.duration_used,
                "is_completed": bool(exam_record.is_completed),
                "submit_time": exam_record.submit_time.strftime("%Y-%m-%d %H:%M:%S") if exam_record.submit_time else None,
                "details_count": len(details),
            }

    return {
        "id": smart_record.id,
        "paper_id": smart_record.paper_id,
        "paper_name": smart_record.paper_name,
        "subject_mode": smart_record.subject_mode,
        "total_questions": smart_record.total_questions,
        "completed_count": smart_record.completed_count,
        "total_score": float(smart_record.total_score) if smart_record.total_score else 0,
        "earned_score": float(smart_record.earned_score) if smart_record.earned_score else None,
        "status": smart_record.status,
        "time_spent": smart_record.time_spent,
        "answers_json": smart_record.answers_json,
        "marked_questions": smart_record.marked_questions,
        "current_index": smart_record.current_index,
        "start_time": smart_record.start_time.strftime("%Y-%m-%d %H:%M:%S") if smart_record.start_time else None,
        "end_time": smart_record.end_time.strftime("%Y-%m-%d %H:%M:%S") if smart_record.end_time else None,
        "create_time": smart_record.create_time.strftime("%Y-%m-%d %H:%M:%S") if smart_record.create_time else None,
        "exam_record": exam_data,
    }


# ==================== 10. 删除记录 ====================

@router.delete("/records/{record_id}", summary="删除智能组卷记录")
async def delete_smart_exam_record(
    record_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除智能组卷记录（仅未完成的记录可删除）
    """
    smart_record = db.query(SmartExamRecord).filter(
        SmartExamRecord.id == record_id,
        SmartExamRecord.user_id == current_user.user_id,
    ).first()

    if not smart_record:
        raise HTTPException(status_code=404, detail="记录不存在")

    if smart_record.status == "completed":
        raise HTTPException(status_code=400, detail="已完成的记录不可删除")

    db.delete(smart_record)
    db.commit()

    return SuccessResponse(message="记录已删除")
