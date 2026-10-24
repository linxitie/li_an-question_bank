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
from sqlalchemy import func

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    QuestionSubject, SubCategory, KnowledgePoint, QuestionBank,
    QuestionKnowledge, PracticeRecord, SysUser,
    QuestionDetailCategory, QuestionType, QuestionImage, QuestionGroup
)
from ....services.option_utils import (
    is_subjective_question, normalize_options, render_image_placeholder
)
from ....services.image_service import sanitize_content_images, sanitize_options_images, verify_image_exists
from ....services.practice_grading import submit_answers
from ....services.question_stats import QuestionStatsService

router = APIRouter(prefix="/api/quick-practice", tags=["快速练习"])
logger = logging.getLogger(__name__)


# ============================================================
# 辅助函数
# ============================================================

def _practice_answer_map(db: Session, user_id: int, question_ids) -> dict:
    """一次聚合查询：question_id -> 是否做对过（0/1）。

    同一题可能有多条记录，取 max(is_correct)，保证去重且「做对过」口径一致。
    """
    ids = {int(qid) for qid in question_ids if qid is not None}
    if not ids:
        return {}
    rows = db.query(
        PracticeRecord.question_id,
        func.max(PracticeRecord.is_correct),
    ).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.question_id.in_(ids),
    ).group_by(PracticeRecord.question_id).all()
    return {int(question_id): int(best or 0) for question_id, best in rows}


def _practice_stats(answer_map: dict, question_ids) -> tuple:
    """基于聚合结果统计去重已完成数 / 做对过数"""
    done = 0
    correct = 0
    for question_id in {int(qid) for qid in question_ids if qid is not None}:
        if question_id in answer_map:
            done += 1
            if answer_map[question_id] == 1:
                correct += 1
    return done, correct


def _accuracy(correct: int, done: int):
    """正确率：百分比，保留一位小数；未做题为 0"""
    return round(correct * 100 / done, 1) if done else 0


def _visible_question_ids_by_point(db: Session, point_ids) -> dict:
    """按「主考点」收集可见题目ID（统一走 QuestionStatsService.visible_query）

    以 question_bank.point_id 为准（T-06/T-08b 的单一主 canonical 考点），
    不使用 question_knowledge 关系表——一道题挂多个 L2/L3 时关系表会重复计数，
    破坏「ΣL2 + 未分类 = 子科目总数」的精确性。
    """
    ids = {int(pid) for pid in point_ids if pid is not None}
    if not ids:
        return {}
    rows = QuestionStatsService.visible_query(db).with_entities(
        QuestionBank.point_id, QuestionBank.question_id
    ).filter(
        QuestionBank.point_id.in_(ids)
    ).all()
    grouped = {}
    for point_id, question_id in rows:
        grouped.setdefault(int(point_id), set()).add(int(question_id))
    return grouped


def _build_point_node(point, level: int, question_ids, answer_map: dict,
                      children=None) -> dict:
    """构造 L2/L3 节点：题量为可见题去重数，children 仅 L2 非空"""
    ids = {int(qid) for qid in question_ids if qid is not None}
    done, correct = _practice_stats(answer_map, ids)
    return {
        "point_id": point.point_id,
        "point_name": point.point_name,
        "level": level,
        "total_questions": len(ids),
        "done_count": done,
        "correct_count": correct,
        "accuracy": _accuracy(correct, done),
        "children": children or [],
    }


def _dedupe_children_by_name(children) -> list:
    """同级 L3 按名称去重，保留 point_id 最小者，再按排序展示"""
    kept = {}
    for child in sorted(children, key=lambda item: item.point_id):
        kept.setdefault(child.point_name, child)
    return sorted(kept.values(), key=lambda item: (item.sort_order or 0, item.point_id))


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
    返回指定科目下所有子科目，每个子科目包含 canonical L2 考点及其 L3 子节点。
    计数口径：统一走 QuestionStatsService.visible_query；0 题 L2/L3 不返回。
    """
    sub_cats = db.query(SubCategory).filter(
        SubCategory.subject_id == subject_id,
        SubCategory.status == 1
    ).order_by(SubCategory.sort_order).all()

    visible_rows = QuestionStatsService.visible_query(db).with_entities(
        QuestionBank.question_id,
        QuestionBank.sub_category_id,
        QuestionBank.point_id,
    ).filter(
        QuestionBank.subject_id == subject_id
    ).all()

    question_ids_by_subcat = {}
    global_unclassified_ids = set()
    question_point_ids = {}
    all_visible_ids = []
    for question_id, sc_id, point_id in visible_rows:
        qid = int(question_id)
        all_visible_ids.append(qid)
        if point_id is not None:
            question_point_ids[qid] = int(point_id)
        if sc_id is None:
            global_unclassified_ids.add(qid)
        else:
            question_ids_by_subcat.setdefault(int(sc_id), set()).add(qid)

    answer_map = _practice_answer_map(db, current_user.user_id, all_visible_ids)

    points = db.query(KnowledgePoint).filter(
        KnowledgePoint.subject_id == subject_id,
        KnowledgePoint.status == 1,
        KnowledgePoint.level.in_((2, 3)),
    ).order_by(KnowledgePoint.sort_order, KnowledgePoint.point_id).all()

    # 按 point_id 去重；L2 分组，L3 挂到 parent
    seen_point_ids = set()
    l2_points = []
    l3_by_parent = {}
    for point in points:
        if point.point_id in seen_point_ids:
            continue
        seen_point_ids.add(point.point_id)
        if point.level == 2:
            l2_points.append(point)
        elif point.level == 3:
            l3_by_parent.setdefault(point.parent_id, []).append(point)

    # 按「主考点」分组：question_bank.point_id 决定唯一归属，关系表不参与计数
    question_ids_by_point = {}
    for qid, pid in question_point_ids.items():
        if pid in seen_point_ids:
            question_ids_by_point.setdefault(pid, set()).add(qid)

    result = []
    for sc in sub_cats:
        sub_question_ids = set(question_ids_by_subcat.get(sc.id, set()))
        sub_done, sub_correct = _practice_stats(answer_map, sub_question_ids)

        returned_question_ids = set()
        point_items = []
        for l2 in l2_points:
            if l2.sub_category_id != sc.id:
                continue

            children = []
            child_question_ids = set()
            raw_children = [
                child for child in l3_by_parent.get(l2.point_id, [])
                if child.sub_category_id == sc.id
            ]
            for l3 in _dedupe_children_by_name(raw_children):
                l3_question_ids = question_ids_by_point.get(l3.point_id, set()) & sub_question_ids
                if not l3_question_ids:
                    continue  # 0 题 L3（含 0 题的「其他」）不返回
                children.append(
                    _build_point_node(l3, 3, l3_question_ids, answer_map)
                )
                child_question_ids |= l3_question_ids

            # L2 = 直挂 L2 题（primary point_id == L2）+ 其 L3 子节点题
            l2_question_ids = (
                question_ids_by_point.get(l2.point_id, set()) & sub_question_ids
            ) | child_question_ids
            if not l2_question_ids:
                continue  # 0 题 L2 不返回

            point_items.append(
                _build_point_node(l2, 2, l2_question_ids, answer_map, children)
            )
            returned_question_ids |= l2_question_ids

        unclassified_count = len(sub_question_ids - returned_question_ids)

        result.append({
            "id": sc.id,
            "name": sc.name,
            "description": sc.description,
            "sort_order": sc.sort_order,
            "total_questions": len(sub_question_ids),
            "done_count": sub_done,
            "correct_count": sub_correct,
            "accuracy": _accuracy(sub_correct, sub_done),
            "knowledge_points": point_items,
            "children": [],
            "is_unclassified": False,
            "unclassified_count": unclassified_count,
        })

    # 仅当存在 sub_category_id IS NULL 的可见题时追加合成「未分类」项
    if global_unclassified_ids:
        unc_done, unc_correct = _practice_stats(answer_map, global_unclassified_ids)
        result.append({
            "id": 0,
            "name": "未分类",
            "description": "未归入任何子科目的题目",
            "sort_order": 999,
            "total_questions": len(global_unclassified_ids),
            "done_count": unc_done,
            "correct_count": unc_correct,
            "accuracy": _accuracy(unc_correct, unc_done),
            "knowledge_points": [],
            "children": [],
            "is_unclassified": True,
            "unclassified_count": len(global_unclassified_ids),
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
    """返回指定子科目下的 L3 叶子考点，含可见题统计；0 题考点不返回"""
    kps = db.query(KnowledgePoint).filter(
        KnowledgePoint.sub_category_id == sub_category_id,
        KnowledgePoint.status == 1,
        KnowledgePoint.level == 3,
    ).order_by(KnowledgePoint.sort_order, KnowledgePoint.point_id).all()

    point_question_ids = _visible_question_ids_by_point(
        db, [kp.point_id for kp in kps]
    )
    answer_map = _practice_answer_map(
        db, current_user.user_id,
        {qid for ids in point_question_ids.values() for qid in ids},
    )

    items = []
    for kp in kps:
        kp_question_ids = point_question_ids.get(kp.point_id, set())
        if not kp_question_ids:
            continue
        kp_done, kp_correct = _practice_stats(answer_map, kp_question_ids)
        items.append({
            "point_id": kp.point_id,
            "point_name": kp.point_name,
            "description": kp.description,
            "total_questions": len(kp_question_ids),
            "done_count": kp_done,
            "correct_count": kp_correct,
            "accuracy": _accuracy(kp_correct, kp_done),
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

    from sqlalchemy import func as sql_func

    if by_sub_category:
        # P1-3 直查：按 question_bank.sub_category_id 取可见题，不依赖
        # question_knowledge，未挂知识点的题也能练。
        sc_id = raw_ids[0]
        visible_query = QuestionStatsService.visible_query(db).filter(
            QuestionBank.sub_category_id == sc_id
        )
        if visible_query.count() == 0:
            return {"total": 0, "items": [], "message": "该子科目下暂无题目"}

        # 按题干内容去重（保留 question_id 最小的）
        sub = visible_query.with_entities(
            sql_func.min(QuestionBank.question_id).label('min_id')
        ).group_by(QuestionBank.question_content).subquery()
    else:
        # P1-8 待处理：旧路径仍走 考点 -> question_knowledge 反查
        kp_ids = raw_ids
        qid_rows = db.query(QuestionKnowledge.question_id).filter(
            QuestionKnowledge.knowledge_point_id.in_(kp_ids)
        ).distinct().all()
        question_ids = [r[0] for r in qid_rows]

        if not question_ids:
            return {"total": 0, "items": [], "message": "该考点下暂无题目"}

        # 构建题目查询 - 按题干内容去重（保留 question_id 最小的）
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
    type_cache = {}
    group_cache = {}
    for q in questions:
        qtype = None
        if q.type_id:
            if q.type_id not in type_cache:
                type_cache[q.type_id] = db.query(QuestionType).filter(
                    QuestionType.type_id == q.type_id
                ).first()
            qtype = type_cache[q.type_id]

        # 获取题型详情
        qtype_name = '选择题'
        detail_row = db.query(QuestionDetailCategory).filter(
            QuestionDetailCategory.question_id == q.question_id
        ).first()
        if detail_row and detail_row.question_type_detail:
            qtype_name = str(detail_row.question_type_detail)
        elif qtype:
            qtype_name = qtype.type_name or '选择题'

        group = None
        if q.group_id:
            if q.group_id not in group_cache:
                group_cache[q.group_id] = db.query(QuestionGroup).filter(
                    QuestionGroup.id == q.group_id
                ).first()
            group = group_cache[q.group_id]

        # 统一规范化options（自动处理双编码JSON、补全、排序、IMAGE转换）
        # 主观题以 question_type.is_objective=0 为准：不补全、不渲染占位选项
        is_subjective = is_subjective_question(q, qtype)
        if is_subjective:
            cleaned_options = []
        else:
            normalized_opts = normalize_options(q.options, q.question_content or '')
            cleaned_options = sanitize_options_images(normalized_opts, q.question_id, db)

        # 图片预检+恢复（先转换 IMAGE 占位符为 img 标签，再 sanitize 预检）
        cleaned_content = sanitize_content_images(
            render_image_placeholder(q.question_content or ''), q.question_id, db
        )
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
            "score": float(q.score or 0),
            "group_id": q.group_id or 0,
            "shared_content": (group.shared_content or '') if group else '',
            "shared_content_images": group.shared_content_images if group else None,
            "is_subjective": bool(qtype is not None and qtype.is_objective == 0),
            "question_type_name": (
                qtype.type_name if qtype and qtype.type_name else qtype_name
            ),
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
