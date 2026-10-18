"""
快速练习 API
GET  /api/quick-practice/subjects                  — 获取所有科目
GET  /api/quick-practice/sub-categories?subjectId=  — 获取子科目+考点+题目统计
GET  /api/quick-practice/knowledge-points?subCategoryId= — 获取考点列表
GET  /api/quick-practice/questions?kpIds=&limit=    — 按考点筛选题目
POST /api/quick-practice/submit                     — 提交练习结果
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, text

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    QuestionSubject, SubCategory, KnowledgePoint, QuestionBank,
    QuestionKnowledge, PracticeRecord, SysUser,
    QuestionDetailCategory, QuestionType, QuestionImage
)
from ....services.option_utils import normalize_options, render_image_placeholder
from ....services.image_service import sanitize_content_images, sanitize_options_images, verify_image_exists
from ....services.practice_grading import submit_answers

router = APIRouter(prefix="/api/quick-practice", tags=["快速练习"])
logger = logging.getLogger(__name__)


# ============================================================
# 辅助函数
# ============================================================

def _get_user_done_counts(db: Session, user_id: int, question_ids: List[int]) -> int:
    """统计用户在指定题目列表中的去重做题数"""
    if not question_ids:
        return 0
    return db.query(func.count(distinct(PracticeRecord.question_id))).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.question_id.in_(question_ids)
    ).scalar() or 0


def _get_user_correct_counts(db: Session, user_id: int, question_ids: List[int]) -> int:
    """统计用户在指定题目列表中做对过的去重题数（is_correct=1）"""
    if not question_ids:
        return 0
    return db.query(func.count(distinct(PracticeRecord.question_id))).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.question_id.in_(question_ids),
        PracticeRecord.is_correct == 1,
    ).scalar() or 0


def _count_questions_by_kp(db: Session, kp_id: int) -> int:
    """统计某考点下的题目总数"""
    return db.query(func.count(QuestionKnowledge.id)).filter(
        QuestionKnowledge.knowledge_point_id == kp_id
    ).scalar() or 0


# ============================================================
# API 端点
# ============================================================

@router.get("/subjects", summary="获取所有科目")
async def get_subjects(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回3个科目（行测/申论/公专），含子科目数量"""
    subjects = db.query(QuestionSubject).filter(
        QuestionSubject.status == 1
    ).order_by(QuestionSubject.sort_order).all()

    items = []
    for s in subjects:
        sub_count = db.query(func.count(SubCategory.id)).filter(
            SubCategory.subject_id == s.subject_id,
            SubCategory.status == 1
        ).scalar() or 0
        items.append({
            "subject_id": s.subject_id,
            "subject_name": s.subject_name,
            "subject_code": s.subject_code,
            "description": s.description,
            "sub_category_count": sub_count,
        })

    return {"total": len(items), "items": items}


@router.get("/sub-categories", summary="获取子科目及考点统计")
async def get_sub_categories(
    subject_id: int = Query(..., ge=1, le=3, alias="subjectId", description="科目ID: 1=行测 2=申论 3=公专"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    返回指定科目下所有子科目，每个子科目包含其考点列表。
    对每个考点统计：总题目数 + 当前用户已做题数。
    对每个子科目统计：总题目数 + 当前用户已做题数。
    """
    sub_cats = db.query(SubCategory).filter(
        SubCategory.subject_id == subject_id,
        SubCategory.status == 1
    ).order_by(SubCategory.sort_order).all()

    result = []
    for sc in sub_cats:
        # 获取该子科目下的所有考点
        kps = db.query(KnowledgePoint).filter(
            KnowledgePoint.sub_category_id == sc.id,
        ).order_by(KnowledgePoint.sort_order).all()

        # 收集该子科目下所有题目ID（按 question_bank 子科目列统计，与 /exercise/questions 同口径）
        subcat_col = {
            1: QuestionBank.xingce_subcategory,
            2: QuestionBank.shenlun_subcategory,
            3: QuestionBank.gongzhuan_subcategory,
        }.get(subject_id)
        sub_question_ids = []
        if subcat_col is not None:
            sub_rows = db.query(QuestionBank.question_id).filter(
                QuestionBank.status == 1,
                QuestionBank.subject_id == subject_id,
                subcat_col == sc.name
            ).all()
            sub_question_ids = [r[0] for r in sub_rows]

        sub_total = len(sub_question_ids)
        sub_done = _get_user_done_counts(db, current_user.user_id, sub_question_ids)
        sub_correct = _get_user_correct_counts(db, current_user.user_id, sub_question_ids)
        sub_accuracy = round(sub_correct * 100 / max(sub_done, 1), 1) if sub_done else 0

        # 构建考点列表
        point_items = []
        for kp in kps:
            kp_question_ids = [
                r[0] for r in db.query(QuestionKnowledge.question_id).filter(
                    QuestionKnowledge.knowledge_point_id == kp.point_id
                ).all()
            ]
            kp_total = len(kp_question_ids)
            kp_done = _get_user_done_counts(db, current_user.user_id, kp_question_ids)
            kp_correct = _get_user_correct_counts(db, current_user.user_id, kp_question_ids)
            kp_accuracy = round(kp_correct * 100 / max(kp_done, 1), 1) if kp_done else 0

            point_items.append({
                "point_id": kp.point_id,
                "point_name": kp.point_name,
                "total_questions": kp_total,
                "done_count": kp_done,
                "correct_count": kp_correct,
                "accuracy": kp_accuracy,
            })

        result.append({
            "id": sc.id,
            "name": sc.name,
            "description": sc.description,
            "sort_order": sc.sort_order,
            "total_questions": sub_total,
            "done_count": sub_done,
            "correct_count": sub_correct,
            "accuracy": sub_accuracy,
            "knowledge_points": point_items,
        })

    return {
        "subject_id": subject_id,
        "total": len(result),
        "items": result,
    }


@router.get("/knowledge-points", summary="获取考点列表")
async def get_knowledge_points(
    sub_category_id: int = Query(..., ge=1, alias="subCategoryId", description="子科目ID"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回指定子科目下的所有考点，含题目统计"""
    kps = db.query(KnowledgePoint).filter(
        KnowledgePoint.sub_category_id == sub_category_id,
    ).order_by(KnowledgePoint.sort_order).all()

    items = []
    for kp in kps:
        kp_question_ids = [
            r[0] for r in db.query(QuestionKnowledge.question_id).filter(
                QuestionKnowledge.knowledge_point_id == kp.point_id
            ).all()
        ]
        kp_total = len(kp_question_ids)
        kp_done = _get_user_done_counts(db, current_user.user_id, kp_question_ids)

        items.append({
            "point_id": kp.point_id,
            "point_name": kp.point_name,
            "description": kp.description,
            "total_questions": kp_total,
            "done_count": kp_done,
        })

    return {"sub_category_id": sub_category_id, "total": len(items), "items": items}


@router.get("/questions", summary="获取练习题目")
async def get_practice_questions(
    knowledge_point_ids: str = Query(..., description="考点ID列表，逗号分隔；当 bySubCategory=true 时为子科目ID"),
    limit: int = Query(20, ge=1, le=100, description="题目数量上限"),
    year: Optional[int] = Query(None, description="题目年份筛选（近N年）"),
    by_sub_category: bool = Query(False, alias="bySubCategory", description="是否按子科目ID查询"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    根据考点ID列表获取题目。
    支持年份筛选（如只取近3年/近5年/不限）。
    当 bySubCategory=true 时，knowledge_point_ids 参数为子科目ID，
    系统自动查找该子科目下所有考点再获取题目。
    返回去重后的题目列表。
    """
    try:
        raw_ids = [int(x.strip()) for x in knowledge_point_ids.split(",") if x.strip()]
    except ValueError:
        return {"error": "考点ID格式错误，请使用逗号分隔的整数", "items": [], "total": 0}

    if not raw_ids:
        return {"error": "请至少选择一个考点或子科目", "items": [], "total": 0}

    # 如果是按子科目查询，先查出该子科目下所有考点
    if by_sub_category:
        sc_id = raw_ids[0]
        kp_rows = db.query(KnowledgePoint.point_id).filter(
            KnowledgePoint.sub_category_id == sc_id
        ).all()
        kp_ids = [r[0] for r in kp_rows]
        if not kp_ids:
            return {"total": 0, "items": [], "message": "该子科目下暂无考点"}
    else:
        kp_ids = raw_ids

    # 通过 question_knowledge 关联表获取题目ID
    qid_rows = db.query(QuestionKnowledge.question_id).filter(
        QuestionKnowledge.knowledge_point_id.in_(kp_ids)
    ).distinct().all()
    question_ids = [r[0] for r in qid_rows]

    if not question_ids:
        return {"total": 0, "items": [], "message": "该考点下暂无题目"}

    # 构建题目查询 - 按题干内容去重（保留 question_id 最小的）
    from sqlalchemy import func as sql_func
    sub = db.query(
        sql_func.min(QuestionBank.question_id).label('min_id')
    ).filter(
        QuestionBank.question_id.in_(question_ids),
        QuestionBank.status == 1
    ).group_by(QuestionBank.question_content).subquery()

    query = db.query(QuestionBank).filter(
        QuestionBank.question_id.in_(db.query(sub.c.min_id))
    )

    # 年份筛选
    if year and year > 0:
        import datetime as dt
        current_year = dt.date.today().year
        min_year = current_year - year
        query = query.filter(QuestionBank.year >= min_year)

    total = query.count()
    questions = query.order_by(func.random()).limit(limit).all()

    items = []
    for q in questions:
        # 获取题型详情
        qtype_name = '选择题'
        detail_row = db.query(QuestionDetailCategory).filter(
            QuestionDetailCategory.question_id == q.question_id
        ).first()
        if detail_row and detail_row.question_type_detail:
            qtype_name = str(detail_row.question_type_detail)
        elif q.type_id:
            qt = db.query(QuestionType).filter(QuestionType.type_id == q.type_id).first()
            if qt:
                qtype_name = qt.type_name or '选择题'

        # 统一规范化options（自动处理双编码JSON、补全、排序、IMAGE转换）
        normalized_opts = normalize_options(q.options, q.question_content or '')

        # 图片预检+恢复（先转换 IMAGE 占位符为 img 标签，再 sanitize 预检）
        cleaned_content = sanitize_content_images(
            render_image_placeholder(q.question_content or ''), q.question_id, db
        )
        cleaned_options = sanitize_options_images(normalized_opts, q.question_id, db)
        cleaned_analysis = sanitize_content_images(
            render_image_placeholder(q.answer_analysis or ''), q.question_id, db
        )

        # 查询 QuestionImage 表，只返回存在的图片
        img_list = db.query(QuestionImage).filter(
            QuestionImage.question_id == q.question_id
        ).order_by(QuestionImage.image_order).all()
        valid_images = [{
            "image_path": i.image_path,
            "image_type": i.image_type,
            "image_order": i.image_order
        } for i in img_list if verify_image_exists(i.image_path)]

        items.append({
            "question_id": q.question_id,
            "subject_id": q.subject_id,
            "type_id": q.type_id,
            "question_content": cleaned_content,
            "question_type_detail": qtype_name,
            "options": cleaned_options,
            "answer": q.answer,
            "answer_analysis": cleaned_analysis,
            "difficulty": q.difficulty,
            "year": q.year,
            "source": q.source,
            "tags": q.tags,
            "requirements": q.requirements or '',
            "images": valid_images,
        })

    return {"total": total, "limit": limit, "items": items}


@router.post("/submit", summary="提交练习结果")
async def submit_practice(
    payload: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    提交练习结果。支持批量提交。
    请求体格式:
    {
        "subject_id": 1,
        "records": [
            {
                "question_id": 123,
                "user_answer": "A",
                "is_correct": true,
                "time_spent": 45
            },
            ...
        ]
    }
    """
    records_data = payload.get("records", [])
    if not records_data:
        return {"status": "ok", "count": 0}

    subject_id = payload.get("subject_id")
    normalized = [{
        "question_id": item.get("question_id"),
        "subject_id": item.get("subject_id"),
        "user_answer": item.get("user_answer", ""),
        "is_correct": item.get("is_correct", False),
        "time_spent": item.get("time_spent", 0),
        "source": "快速练习",
    } for item in records_data]

    try:
        result = await submit_answers(
            db, current_user.user_id, normalized,
            source_type="快速练习",
            subject_id=subject_id,
            session_id=payload.get("session_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "ok",
        "count": result["count"],
        "correct": result["correct"],
        "total": result["total"],
        "accuracy": result["accuracy"],
        "wrong_question_stats": result["wrong_question_stats"],
    }
