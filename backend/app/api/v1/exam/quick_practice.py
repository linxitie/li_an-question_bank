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
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    QuestionSubject, SubCategory, KnowledgePoint, QuestionBank,
    PracticeRecord, SysUser,
    QuestionDetailCategory, QuestionType, QuestionImage
)
from ....services.option_utils import (
    is_subjective_question, normalize_options, render_image_placeholder
)
from ....services.image_service import sanitize_content_images, sanitize_options_images, verify_image_exists
from ....services.practice_grading import submit_answers
from ....services.question_stats import QuestionStatsService
from ....services.question_material import get_question_group

router = APIRouter(prefix="/api/quick-practice", tags=["快速练习"])
logger = logging.getLogger(__name__)

# 「其他」收容叶子的统一命名。治理脚本 `scripts/qbdm/fix_fallback_points.py` 会把
# 历史遗留的裸名「其他」重命名为这个带后缀的名字，前端据此识别"无细分"节点。
FALLBACK_POINT_NAME = "其他（未细分）"
_LEGACY_FALLBACK_NAMES = ("其他",)


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
    child_nodes = children or []
    return {
        "point_id": point.point_id,
        "point_name": point.point_name,
        "level": level,
        "total_questions": len(ids),
        "done_count": done,
        "correct_count": correct,
        "accuracy": _accuracy(correct, done),
        "children": child_nodes,
        # 规则 R2：只有"确实有可练子节点"才允许下钻。
        # 前端见到 drillable=false 只渲染「练习」按钮，杜绝"下钻进去只有其他"。
        "drillable": bool(child_nodes),
        "is_fallback": _is_fallback_name(point.point_name),
    }


def _is_fallback_name(name: Optional[str]) -> bool:
    """名称是否为「其他（未细分）」收容叶子（重命名前后都能命中）"""
    text = (name or "").strip()
    if not text:
        return False
    return text == FALLBACK_POINT_NAME or text in _LEGACY_FALLBACK_NAMES


def _is_fallback_point(point) -> bool:
    """是否为「其他（未细分）」收容叶子。

    判定只认名称，不新增列：knowledge_point.alias_of 是 raw SQL 写的历史列，
    ORM 模型里没有；硬加 is_fallback 列会引出迁移与多库兼容风险。
    """
    return _is_fallback_name(getattr(point, "point_name", None))


def _fallback_point_ids_by_subcat(db: Session, sub_category_id: int) -> List[int]:
    """取某子科目下所有收容叶子的 point_id"""
    rows = db.query(KnowledgePoint.point_id, KnowledgePoint.point_name).filter(
        KnowledgePoint.sub_category_id == sub_category_id,
        KnowledgePoint.status == 1,
        KnowledgePoint.level == 3,
    ).all()
    return [int(pid) for pid, name in rows if _is_fallback_name(name)]


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
                # 「其他（未细分）」不再作为 L2 的子考点展示：
                # 否则每个 L2 下都会出现一个同名的"其他"，即用户反馈的满屏「其他」。
                and not _is_fallback_point(child)
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

        # ---- 「其他（未细分）」收容块（子科目级，一个入口，可直接练） ----
        # 口径与 L2/L3 一致：主考点 point_id 就是收容叶子，或主考点为空（导入时确实无法归类）。
        fallback_point_ids = {
            p.point_id for p in points
            if _is_fallback_point(p) and p.sub_category_id == sc.id
        }
        fallback_question_ids = set()
        for pid in fallback_point_ids:
            fallback_question_ids |= question_ids_by_point.get(pid, set())
        fallback_question_ids &= sub_question_ids
        fallback_question_ids |= {
            qid for qid in sub_question_ids if qid not in question_point_ids
        }

        fallback_block = None
        if fallback_question_ids:
            fb_done, fb_correct = _practice_stats(answer_map, fallback_question_ids)
            fallback_block = {
                "id": 0,
                "name": FALLBACK_POINT_NAME,
                "is_fallback": True,
                "point_ids": sorted(fallback_point_ids),
                "total_questions": len(fallback_question_ids),
                "done_count": fb_done,
                "correct_count": fb_correct,
                "accuracy": _accuracy(fb_correct, fb_done),
                # 收容箱本身就是叶子：只能直接练，不参与下钻
                "drillable": False,
            }

        unclassified_count = len(
            sub_question_ids - returned_question_ids - fallback_question_ids
        )

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
            "fallback": fallback_block,
            "children": [],
            "is_unclassified": False,
            "unclassified_count": unclassified_count,
            # 子科目本身永远可进（进的是"考点列表"而非"再下一级"）
            "drillable": True,
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
            "fallback": None,
            "children": [],
            "is_unclassified": True,
            "drillable": True,
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
            "level": 3,
            # 收容叶子由前端渲染成"直接开练"，不再下钻到更细一层
            "is_fallback": _is_fallback_point(kp),
            # L3 是树的末端，永不下钻（规则 R2）
            "drillable": False,
            "total_questions": len(kp_question_ids),
            "done_count": kp_done,
            "correct_count": kp_correct,
            "accuracy": _accuracy(kp_correct, kp_done),
        })

    # 稳定排序：真实考点保持 sort_order 原序，「其他（未细分）」固定排最后
    items.sort(key=lambda item: 1 if item["is_fallback"] else 0)

    return {"sub_category_id": sub_category_id, "total": len(items), "items": items}


@router.get("/questions", summary="获取练习题目")
async def get_practice_questions(
    knowledge_point_ids: str = Query(..., description="考点ID列表，逗号分隔；当 bySubCategory=true 时为子科目ID"),
    limit: int = Query(20, ge=1, le=100, description="题目数量上限"),
    year: Optional[int] = Query(None, description="题目年份筛选（近N年）"),
    by_sub_category: bool = Query(False, alias="bySubCategory", description="是否按子科目ID查询"),
    fallback_only: bool = Query(
        False, alias="fallbackOnly",
        description="只取「其他（未细分）」收容题（配合 bySubCategory=true，knowledgePointIds 传子科目ID）",
    ),
    sub_category_ids: Optional[str] = Query(
        None, alias="subCategoryIds",
        description="子科目ID列表（逗号分隔）：多子科目联合练习，与 bySubCategory 互斥优先",
    ),
    types: Optional[str] = Query(
        None, description="题型ID列表（逗号分隔）：1=单选 4=多选 5=判断 …",
    ),
    difficulty: Optional[str] = Query(
        None, description="难度：easy=较易(<=2) / hard=较难(>=4) / 其它=不限",
    ),
    order: str = Query("random", description="顺序：random / year_desc / hard_first"),
    subject_id: Optional[int] = Query(
        None, ge=1, le=3, alias="subjectId",
        description="未分类（0号）范围必填：1=行测 2=申论 3=公专",
    ),
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

    sc_list: List[int] = []
    if sub_category_ids:
        try:
            sc_list = [int(x.strip()) for x in sub_category_ids.split(",") if x.strip()]
        except ValueError:
            return {"error": "子科目ID格式错误", "items": [], "total": 0}

    if sc_list:
        # 多子科目联合练习（自定义刷题蓝图用）：OR 拼接，仍走同一可见口径
        conditions = [QuestionBank.sub_category_id.in_([s for s in sc_list if s != 0])]
        if 0 in sc_list:
            conditions.append(QuestionBank.sub_category_id.is_(None))
        if fallback_only:
            for sid in sc_list:
                fb_ids = _fallback_point_ids_by_subcat(db, sid) if sid else []
                if fb_ids:
                    conditions.append(QuestionBank.point_id.in_(fb_ids))
        visible_query = QuestionStatsService.visible_query(db).filter(or_(*conditions))
        if subject_id is not None:
            visible_query = visible_query.filter(QuestionBank.subject_id == subject_id)
        if visible_query.count() == 0:
            return {"total": 0, "items": [], "message": "所选范围下暂无题目"}
        sub = visible_query.with_entities(
            sql_func.min(QuestionBank.question_id).label('min_id')
        ).group_by(QuestionBank.question_content).subquery()
    elif by_sub_category:
        # P1-3 直查：按 question_bank.sub_category_id 取可见题，不依赖
        # question_knowledge，未挂知识点的题也能练。
        sc_id = raw_ids[0]
        if sc_id == 0:
            # 0 是前端合成的「未分类」虚拟子科目，不是真实 sub_categories.id。
            # 未分类题必须限定科目，避免把三科混在一次练习里。
            if subject_id is None:
                return {
                    "total": 0,
                    "items": [],
                    "message": "未分类练习需指定科目（subjectId=1/2/3）",
                }
            visible_query = QuestionStatsService.visible_query(db).filter(
                QuestionBank.sub_category_id.is_(None),
                QuestionBank.subject_id == subject_id,
            )
        elif fallback_only:
            # 「其他（未细分）」直练：收容叶子主考点 + 主考点为空的题，二者合起来
            # 就是 sub-categories 里 fallback.total_questions 的口径。
            fb_ids = _fallback_point_ids_by_subcat(db, sc_id)
            condition = QuestionBank.sub_category_id == sc_id
            if fb_ids:
                condition = or_(condition, QuestionBank.point_id.in_(fb_ids))
            visible_query = QuestionStatsService.visible_query(db).filter(condition)
            if subject_id is not None:
                visible_query = visible_query.filter(
                    QuestionBank.subject_id == subject_id
                )
        else:
            visible_query = QuestionStatsService.visible_query(db).filter(
                QuestionBank.sub_category_id == sc_id
            )
            if subject_id is not None:
                visible_query = visible_query.filter(
                    QuestionBank.subject_id == subject_id
                )
        if visible_query.count() == 0:
            return {"total": 0, "items": [], "message": "该子科目下暂无题目"}

        # 按题干内容去重（保留 question_id 最小的）
        sub = visible_query.with_entities(
            sql_func.min(QuestionBank.question_id).label('min_id')
        ).group_by(QuestionBank.question_content).subquery()
    else:
        # 按考点直练：用 question_bank.point_id（唯一主考点）取题。
        # 旧实现走 question_knowledge 反查，与 sub-categories 的计数口径不一致，
        # 会出现"列表显示 706 题、点进去 0 题"的错位（P1-8 遗留，本次对齐）。
        visible_query = QuestionStatsService.visible_query(db).filter(
            QuestionBank.point_id.in_(raw_ids)
        )
        if visible_query.count() == 0:
            return {"total": 0, "items": [], "message": "该考点下暂无题目"}

        # 按题干内容去重（保留 question_id 最小的）
        sub = visible_query.with_entities(
            sql_func.min(QuestionBank.question_id).label('min_id')
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

    # 题型筛选（蓝图用；不给则不限）
    type_ids = []
    if types:
        try:
            type_ids = [int(x.strip()) for x in types.split(",") if x.strip()]
        except ValueError:
            type_ids = []
    if type_ids:
        query = query.filter(QuestionBank.type_id.in_(type_ids))

    # 难度筛选：库里 difficulty 以 3 为主（3541/3750），因此「较易/较难」是窄口径
    diff_key = (difficulty or "").strip().lower()
    if diff_key == "easy":
        query = query.filter(QuestionBank.difficulty.isnot(None), QuestionBank.difficulty <= 2)
    elif diff_key == "hard":
        query = query.filter(QuestionBank.difficulty.isnot(None), QuestionBank.difficulty >= 4)

    total = query.count()
    order_key = (order or "random").strip().lower()
    if order_key == "year_desc":
        questions = query.order_by(QuestionBank.year.desc(), QuestionBank.question_id).limit(limit).all()
    elif order_key == "hard_first":
        questions = query.order_by(QuestionBank.difficulty.desc(), QuestionBank.question_id).limit(limit).all()
    else:
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
                group_cache[q.group_id] = get_question_group(db, q.group_id)
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

    # 练习范围（考点/子科目/其他收容）由前端带上，用于「练习记录」按考点归类；
    # 不带时 practice_grading 会退化为按第一题的主考点解析，仍然不会落 NULL。
    scope = payload.get("scope") or {}
    try:
        result = await submit_answers(
            db, current_user.user_id, normalized,
            source_type="快速练习",
            subject_id=subject_id,
            session_id=payload.get("session_id"),
            scope={
                "type": scope.get("type"),
                "id": scope.get("id"),
                "name": scope.get("name"),
                "sub_category_id": scope.get("sub_category_id"),
            } if scope else None,
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


# ============================================================
# 练习蓝图（Practice Blueprint）— 先预览，后开练
# ============================================================

class BlueprintRequest(BaseModel):
    """练习蓝图：与前端 PracticeBlueprint 一一对应（方案 v6.0 §5.2）"""

    subject: Optional[str] = Field(None, description="xc=行测 sl=申论 ga=公专")
    subjectId: Optional[int] = Field(None, description="1/2/3；与 subject 二者其一")
    pointIds: List[int] = Field(default_factory=list, description="考点ID（叶节点）")
    subCategoryIds: List[int] = Field(default_factory=list, description="子科目ID")
    includeFallback: bool = Field(True, description="是否包含「其他（未细分）」收容题（默认包含：不包含时公专/申论范围会恒为空）")
    yearRange: str = Field("0", description="1/3/5/0=不限")
    types: List[int] = Field(default_factory=list, description="题型ID")
    difficulty: str = Field("mix", description="easy/mid/hard/mix")
    count: int = Field(20, ge=1, le=100)
    minutes: int = Field(0, ge=0, le=600, description="0=不限时")


_SUBJECT_ID_BY_CODE = {"xc": 1, "sl": 2, "ga": 3}

# 每题预计耗时（秒）：客观题 45s、主观题 240s。用于"开练前就知道要花多久"。
_SECONDS_PER_OBJECTIVE = 45
_SECONDS_PER_SUBJECTIVE = 240


def _blueprint_subject_id(bp: BlueprintRequest) -> Optional[int]:
    if bp.subjectId in (1, 2, 3):
        return bp.subjectId
    code = (bp.subject or "").strip().lower()
    return _SUBJECT_ID_BY_CODE.get(code)


def _blueprint_visible_query(db: Session, bp: BlueprintRequest):
    """把蓝图翻译成一个"可见题"查询（不取题，只用于计数与预览）。

    口径必须与 GET /questions 完全一致，否则会出现"预览 63 题、开练 0 题"。
    """
    subject_id = _blueprint_subject_id(bp)
    conditions = []

    sc_ids = [int(x) for x in bp.subCategoryIds if x is not None]
    if bp.pointIds:
        # 考点优先且互斥：用户点的是「某一考点」，就只算这个考点的题。
        # 若同时 OR 上子科目条件，预览会把整个子科目算进来（实测 635 预览 123、
        # 实际取题 31），与 GET /questions 的考点分支口径不一致。
        conditions.append(QuestionBank.point_id.in_([int(x) for x in bp.pointIds]))
    elif sc_ids:
        real = [x for x in sc_ids if x != 0]
        if real:
            conditions.append(QuestionBank.sub_category_id.in_(real))
        if 0 in sc_ids:
            conditions.append(QuestionBank.sub_category_id.is_(None))

    if not conditions:
        if subject_id is None:
            return None
        conditions.append(QuestionBank.subject_id == subject_id)

    base = QuestionStatsService.visible_query(db).filter(or_(*conditions))
    if subject_id is not None:
        base = base.filter(QuestionBank.subject_id == subject_id)

    if not bp.includeFallback:
        # 排除收容叶子：只要用户没勾"包含其他"，就不把未细分题塞进练习
        fallback_ids = [
            int(pid) for pid, name in db.query(
                KnowledgePoint.point_id, KnowledgePoint.point_name
            ).filter(KnowledgePoint.status == 1).all()
            if _is_fallback_name(name)
        ]
        if fallback_ids:
            base = base.filter(
                or_(QuestionBank.point_id.is_(None),
                    QuestionBank.point_id.notin_(fallback_ids))
            )
    return base


def _blueprint_apply_filters(query, bp: BlueprintRequest):
    if bp.yearRange and bp.yearRange not in ("0", "all", ""):
        try:
            years = int(bp.yearRange)
        except ValueError:
            years = 0
        if years > 0:
            import datetime as dt
            query = query.filter(QuestionBank.year >= dt.date.today().year - years)
    if bp.types:
        query = query.filter(QuestionBank.type_id.in_([int(x) for x in bp.types]))
    diff_key = (bp.difficulty or "mix").strip().lower()
    if diff_key == "easy":
        query = query.filter(QuestionBank.difficulty.isnot(None), QuestionBank.difficulty <= 2)
    elif diff_key == "hard":
        query = query.filter(QuestionBank.difficulty.isnot(None), QuestionBank.difficulty >= 4)
    return query


@router.post("/blueprint", summary="练习蓝图预览（开练前算清题量与时长）")
async def preview_blueprint(
    payload: BlueprintRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回 {available, picked, estimatedMinutes, distribution, note}。

    「先预览后开练」是本次重构的核心：用户点「开始练习」之前就知道会拿到多少题、
    花多久、由哪些子科目构成，避免"点完发现只有 3 题"的落差。
    """
    base = _blueprint_visible_query(db, payload)
    if base is None:
        return {
            "available": 0, "picked": 0, "estimatedMinutes": 0,
            "distribution": [], "note": "请先选择科目或考点范围",
        }

    dedup = base.with_entities(
        func.min(QuestionBank.question_id).label("min_id")
    ).group_by(QuestionBank.question_content).subquery()
    query = db.query(QuestionBank).filter(QuestionBank.question_id.in_(db.query(dedup.c.min_id)))
    query = _blueprint_apply_filters(query, payload)

    available = query.count()
    picked = min(available, payload.count)

    # 分布：按子科目名聚合（最多 6 项），让"这 20 题从哪来"一目了然
    rows = query.with_entities(
        QuestionBank.sub_category_id, func.count(QuestionBank.question_id)
    ).group_by(QuestionBank.sub_category_id).all()
    name_by_id = {
        int(sid): sname for sid, sname in db.query(SubCategory.id, SubCategory.name).all()
    }
    distribution = sorted(
        [
            {"sub_category_id": int(sid) if sid is not None else 0,
             "name": name_by_id.get(int(sid)) if sid is not None else "未分类",
             "count": int(cnt)}
            for sid, cnt in rows
        ],
        key=lambda item: -item["count"],
    )[:6]

    # 预计时长：客观题/主观题分开估；无题型筛选时按客观题估（题库 98% 为客观题）
    subjective_type_ids = {
        int(tid) for tid, obj in db.query(
            QuestionType.type_id, QuestionType.is_objective
        ).filter(QuestionType.is_objective == 0).all()
    }
    if payload.types:
        seconds = sum(
            _SECONDS_PER_SUBJECTIVE if int(t) in subjective_type_ids else _SECONDS_PER_OBJECTIVE
            for t in payload.types
        ) / max(len(payload.types), 1)
    else:
        seconds = _SECONDS_PER_OBJECTIVE
    estimated = int(round(picked * seconds / 60.0))

    note = ""
    if available == 0 and not payload.includeFallback:
        # 这是真实数据形态：公专/申论大量题目主考点就是收容叶子，
        # 不勾"包含其他"时范围就是空的——直接告诉用户怎么解决，而不是报"暂无题目"。
        note = "该范围的题目都在「其他（未细分）」里，请勾选「包含其他（未细分）」"
        probe = _blueprint_visible_query(
            db, payload.model_copy(update={"includeFallback": True})
        )
        if probe is not None:
            probe_count = probe.with_entities(
                func.count(func.distinct(QuestionBank.question_content))
            ).scalar() or 0
            if probe_count:
                note = f"不包含「其他（未细分）」时范围为空；勾选后可用 {probe_count} 题"
    elif available == 0:
        note = "该范围暂无题目，请放宽年份/题型/难度条件"
    elif available < payload.count:
        note = f"该范围仅 {available} 题，将按 {available} 题生成"

    return {
        "available": available,
        "picked": picked,
        "estimatedMinutes": estimated,
        "distribution": distribution,
        "note": note,
    }
