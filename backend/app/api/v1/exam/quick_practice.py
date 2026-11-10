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
from sqlalchemy import and_, func, or_

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    QuestionSubject, SubCategory, KnowledgePoint, QuestionBank,
    QuestionKnowledge, PracticeRecord, SysUser,
    QuestionDetailCategory, QuestionType, QuestionImage
)
from ....services.option_utils import (
    is_subjective_question, normalize_options, render_image_placeholder
)
from ....services.image_service import sanitize_content_images, sanitize_options_images, verify_image_exists
from ....services.paper_group_selector import expand_question_groups
from ....services.practice_grading import submit_answers
from ....services.question_stats import QuestionStatsService
from ....services.question_material import get_question_group

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


def _is_canonical_other(point) -> bool:
    """taxonomy 中每个 L2 下的 canonical「其他」L3。

    它是 T-03/T-08b 的正式叶子，不是脏数据；前端不应把它当普通考点逐条
    下钻，而应聚合成一个「其他（未细分）」直练入口。
    """
    return (
        int(getattr(point, "level", 0) or 0) == 3
        and str(getattr(point, "point_name", "") or "").strip() == "其他"
    )


def _scope_payload(scope_type: str, *, scope_id=0, name="", subject_id=None,
                   sub_category_id=None, l2_id=None) -> dict:
    """统一的练习作用域描述，前端原样回传，提交时写入记录快照。"""
    return {
        "type": scope_type,
        "id": int(scope_id or 0),
        "name": name or "",
        "subject_id": subject_id,
        "sub_category_id": sub_category_id,
        "l2_id": l2_id,
    }


def _build_display_node(point, level: int, question_ids, answer_map: dict, *,
                        key: str, scope: dict, children=None,
                        is_direct: bool = False, is_other: bool = False,
                        other_count: int = 0, parent_id: int = 0) -> dict:
    """在旧 point 节点上叠加 display_points 语义，旧字段保持不变。"""
    node = _build_point_node(point, level, question_ids, answer_map, children)
    node.update({
        "key": key,
        "parent_id": int(parent_id or 0),
        "scope": scope,
        "is_direct": bool(is_direct),
        "is_other": bool(is_other),
        "other_count": int(other_count or 0),
    })
    return node


def _build_display_points_for_subcat(*, sc, l2_points, l3_by_parent,
                                     question_ids_by_point, sub_question_ids,
                                     answer_map) -> tuple:
    """构造子科目的展示树，返回 (display_points, returned_ids, other_count)。

    规则（设计 D2）：
    - L2 有具体 L3：children = 具体 L3 + 末尾一个合成「其他（未细分）」；
    - L2 只有「其他」/直挂题：children = []，节点本身 is_direct，点击即练；
    - 子科目剩余未归属题（point_id 为空/孤立点）追加一个「其他（未归类）」。
    """
    subject_id = sc.subject_id
    display_points = []
    returned_ids = set()

    for l2 in l2_points:
        if l2.sub_category_id != sc.id:
            continue

        raw_children = [
            child for child in l3_by_parent.get(l2.point_id, [])
            if child.sub_category_id == sc.id
        ]
        specific_children = []
        other_ids = set()
        for l3 in _dedupe_children_by_name(raw_children):
            l3_ids = question_ids_by_point.get(l3.point_id, set()) & sub_question_ids
            if not l3_ids:
                continue
            if _is_canonical_other(l3):
                other_ids |= l3_ids
            else:
                specific_children.append((l3, l3_ids))

        direct_ids = (
            question_ids_by_point.get(l2.point_id, set()) & sub_question_ids
        )
        other_ids |= direct_ids
        l2_all_ids = direct_ids | other_ids
        for _, ids in specific_children:
            l2_all_ids |= ids

        if not l2_all_ids:
            continue

        if specific_children:
            children = []
            for l3, l3_ids in specific_children:
                children.append(_build_display_node(
                    l3, 3, l3_ids, answer_map,
                    key="l3:%s" % l3.point_id,
                    scope=_scope_payload(
                        "l3", scope_id=l3.point_id, name=l3.point_name,
                        subject_id=subject_id, sub_category_id=sc.id,
                        l2_id=l2.point_id,
                    ),
                    is_direct=True,
                    parent_id=l2.point_id,
                ))
            if other_ids:
                other_node = _build_display_node(
                    l2, 3, other_ids, answer_map,
                    key="other:%s:%s" % (sc.id, l2.point_id),
                    scope=_scope_payload(
                        "other", scope_id=l2.point_id,
                        name="%s·其他（未细分）" % l2.point_name,
                        subject_id=subject_id, sub_category_id=sc.id,
                        l2_id=l2.point_id,
                    ),
                    is_direct=True, is_other=True,
                    other_count=len(other_ids),
                    parent_id=l2.point_id,
                )
                # 合成节点没有物理 point_id，避免与真实考点混淆。
                other_node["point_id"] = 0
                other_node["point_name"] = "其他（未细分）"
                children.append(other_node)

            l2_node = _build_display_node(
                l2, 2, l2_all_ids, answer_map,
                key="l2:%s" % l2.point_id,
                scope=_scope_payload(
                    "l2", scope_id=l2.point_id, name=l2.point_name,
                    subject_id=subject_id, sub_category_id=sc.id,
                    l2_id=l2.point_id,
                ),
                children=children,
                other_count=len(other_ids),
            )
        else:
            l2_node = _build_display_node(
                l2, 2, l2_all_ids, answer_map,
                key="l2:%s" % l2.point_id,
                scope=_scope_payload(
                    "l2", scope_id=l2.point_id, name=l2.point_name,
                    subject_id=subject_id, sub_category_id=sc.id,
                    l2_id=l2.point_id,
                ),
                is_direct=True, is_other=True,
                other_count=len(other_ids),
            )

        display_points.append(l2_node)
        returned_ids |= l2_all_ids

    other_ids = sub_question_ids - returned_ids
    if other_ids:
        display_points.append(_build_synthetic_other(
            ids=other_ids,
            answer_map=answer_map,
            key="other:sub:%s" % sc.id,
            name="其他（未归类）",
            scope=_scope_payload(
                "other", scope_id=sc.id,
                name="%s·其他（未归类）" % sc.name,
                subject_id=subject_id, sub_category_id=sc.id, l2_id=None,
            ),
        ))

    return display_points, returned_ids, len(other_ids)


def _filters_for(*, ids, meta: dict, type_name_map: dict) -> dict:
    """返回子科目/未分类卡片可用的年份、题型、难度筛选项（只含真实有题的项）。"""
    years = set()
    type_counts = {}
    difficulty_counts = {}
    for qid in ids:
        item = meta.get(qid) or {}
        if item.get("year"):
            years.add(int(item["year"]))
        type_id = item.get("type_id")
        if type_id:
            type_counts[int(type_id)] = type_counts.get(int(type_id), 0) + 1
        difficulty = item.get("difficulty")
        if difficulty:
            difficulty_counts[int(difficulty)] = (
                difficulty_counts.get(int(difficulty), 0) + 1
            )
    return {
        "years": sorted(years, reverse=True),
        "types": [
            {
                "type_id": type_id,
                "type_name": type_name_map.get(type_id, "未知题型"),
                "count": count,
            }
            for type_id, count in sorted(type_counts.items())
        ],
        "difficulties": [
            {"difficulty": level, "count": count}
            for level, count in sorted(difficulty_counts.items())
        ],
    }


def _build_synthetic_other(*, ids, answer_map: dict, key: str, name: str,
                           scope: dict, parent_id: int = 0) -> dict:
    """合成「其他」节点：没有物理 point_id，只承载一组题。"""
    done, correct = _practice_stats(answer_map, ids)
    return {
        "point_id": 0,
        "point_name": name,
        "level": 2,
        "total_questions": len(ids),
        "done_count": done,
        "correct_count": correct,
        "accuracy": _accuracy(correct, done),
        "children": [],
        "key": key,
        "parent_id": int(parent_id or 0),
        "scope": scope,
        "is_direct": True,
        "is_other": True,
        "other_count": len(ids),
    }


def _parse_int_csv(value: Optional[str]) -> List[int]:
    if not value:
        return []
    parsed = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parsed.append(int(part))
        except ValueError:
            continue
    return sorted(set(parsed))


def _point_children(db: Session, *, subject_id: int, l2_id: int) -> tuple:
    """返回 L2 下的 (具体 L3 ids, canonical 其他 L3 ids)。"""
    rows = db.query(KnowledgePoint).filter(
        KnowledgePoint.subject_id == subject_id,
        KnowledgePoint.status == 1,
        KnowledgePoint.level == 3,
        KnowledgePoint.parent_id == l2_id,
    ).all()
    specific, other = [], []
    for row in rows:
        if _is_canonical_other(row):
            other.append(row.point_id)
        else:
            specific.append(row.point_id)
    return specific, other


def _resolve_scope_query(db: Session, *, scope: str, scope_id: int = 0,
                         subject_id: Optional[int] = None,
                         sub_category_id: Optional[int] = None,
                         l2_id: Optional[int] = None,
                         point_id: Optional[int] = None,
                         include_descendants: bool = True,
                         include_other: bool = False):
    """按 scope 构造可见题查询（设计 D3）。

    旧路径未传 scope 时不进入本函数；这里只负责新语义，保证默认参数与旧
    调用完全隔离。
    """
    base = QuestionStatsService.visible_query(db)
    scope = (scope or "").strip().lower()
    target_id = int(scope_id or point_id or l2_id or 0)

    if scope == "subject":
        sid = int(subject_id or target_id or 0)
        if not sid:
            raise HTTPException(status_code=400, detail="scope=subject 需要 subject_id")
        return base.filter(QuestionBank.subject_id == sid)

    if scope == "subcategory":
        sid = int(sub_category_id if sub_category_id is not None else target_id)
        if sid == 0:
            return base.filter(QuestionBank.sub_category_id.is_(None))
        return base.filter(QuestionBank.sub_category_id == sid)

    if scope in ("l3", "knowledge_point"):
        pid = int(point_id or target_id or 0)
        if not pid:
            raise HTTPException(status_code=400, detail="scope=l3 需要 point_id")
        point = db.query(KnowledgePoint).filter(
            KnowledgePoint.point_id == pid,
            KnowledgePoint.status == 1,
        ).first()
        if point is None:
            return base.filter(False)
        if int(point.level or 0) == 2:
            scope, l2_id = "l2", pid
        else:
            return base.filter(QuestionBank.point_id == pid)

    if scope == "l2":
        lid = int(l2_id or point_id or target_id or 0)
        if not lid:
            raise HTTPException(status_code=400, detail="scope=l2 需要 l2_id")
        point = db.query(KnowledgePoint).filter(
            KnowledgePoint.point_id == lid,
            KnowledgePoint.status == 1,
            KnowledgePoint.level == 2,
        ).first()
        if point is None:
            return base.filter(False)
        sid = int(point.subject_id)
        specific, other = _point_children(db, subject_id=sid, l2_id=lid)
        ids = [lid]
        if include_descendants:
            ids.extend(specific)
        if include_other:
            ids.extend(other)
        return base.filter(QuestionBank.point_id.in_(ids))

    if scope == "other":
        sid = int(subject_id or 0)
        if not sid and sub_category_id is not None:
            sc = db.query(SubCategory).filter(SubCategory.id == sub_category_id).first()
            sid = int(sc.subject_id) if sc else 0
        if not sid and l2_id:
            l2 = db.query(KnowledgePoint).filter(
                KnowledgePoint.point_id == l2_id
            ).first()
            sid = int(l2.subject_id) if l2 else 0
        if not sid:
            raise HTTPException(status_code=400, detail="scope=other 需要 subject_id")

        # 子科目级「其他（未归类）」= 该子科目全部可见题（供超集过滤），
        # 再按 point_id 收窄到 空/失效/其他 L3/L2 直挂。绝不能用
        # sub_category_id == sc 当作 other 条件，否则整科题都会被算进其他。
        if sub_category_id is not None:
            if int(sub_category_id) == 0:
                return base.filter(QuestionBank.sub_category_id.is_(None))
            base = base.filter(QuestionBank.sub_category_id == int(sub_category_id))

        all_point_rows = db.query(KnowledgePoint.point_id).filter(
            KnowledgePoint.subject_id == sid,
            KnowledgePoint.status == 1,
        ).all()
        valid_point_ids = [int(row[0]) for row in all_point_rows]

        if l2_id:
            _specific, other = _point_children(db, subject_id=sid, l2_id=int(l2_id))
            ids = [int(l2_id)] + other
        else:
            l2_rows = db.query(KnowledgePoint.point_id).filter(
                KnowledgePoint.subject_id == sid,
                KnowledgePoint.status == 1,
                KnowledgePoint.level == 2,
            ).all()
            l2_ids = [int(row[0]) for row in l2_rows]
            other_rows = db.query(KnowledgePoint.point_id).filter(
                KnowledgePoint.subject_id == sid,
                KnowledgePoint.status == 1,
                KnowledgePoint.level == 3,
                KnowledgePoint.point_name == "其他",
            ).all()
            ids = l2_ids + [int(row[0]) for row in other_rows]

        conditions = [QuestionBank.point_id.is_(None)]
        if ids:
            conditions.append(QuestionBank.point_id.in_(ids))
        if valid_point_ids:
            # 指向失效/被删知识点的题也归「其他」，与 display_points 的
            # 「其他（未归类）」口径一致。
            conditions.append(and_(
                QuestionBank.point_id.isnot(None),
                ~QuestionBank.point_id.in_(valid_point_ids),
            ))
        return base.filter(or_(*conditions))

    raise HTTPException(status_code=400, detail="不支持的 scope：%s" % scope)


def _serialize_practice_questions(db: Session, questions, *, total: int, limit: int,
                                    requested_limit: int = 0,
                                    group_expanded: bool = False,
                                    scope: Optional[str] = None,
                                    extra_count: int = 0) -> dict:
    """统一序列化练习题，含题型、选项、图片与题组材料。"""
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

        is_subjective = is_subjective_question(q, qtype)
        if is_subjective:
            cleaned_options = []
        else:
            normalized_opts = normalize_options(q.options, q.question_content or '')
            cleaned_options = sanitize_options_images(
                normalized_opts, q.question_id, db
            )

        cleaned_content = sanitize_content_images(
            render_image_placeholder(q.question_content or ''), q.question_id, db
        )
        cleaned_analysis = sanitize_content_images(
            render_image_placeholder(q.answer_analysis or ''), q.question_id, db
        )

        img_list = db.query(QuestionImage).filter(
            QuestionImage.question_id == q.question_id
        ).order_by(QuestionImage.image_order).all()
        valid_images = [{
            "image_path": i.image_path,
            "image_type": i.image_type,
            "image_order": i.image_order,
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

    return {
        "total": total,
        "limit": limit,
        "requested_limit": int(requested_limit or limit),
        "actual_count": len(items),
        "group_expanded": bool(group_expanded),
        "extra_count": int(extra_count or 0),
        "scope": scope,
        "items": items,
    }


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
        QuestionBank.year,
        QuestionBank.type_id,
        QuestionBank.difficulty,
    ).filter(
        QuestionBank.subject_id == subject_id
    ).all()

    question_ids_by_subcat = {}
    global_unclassified_ids = set()
    question_point_ids = {}
    question_meta = {}
    all_visible_ids = []
    for question_id, sc_id, point_id, year, type_id, difficulty in visible_rows:
        qid = int(question_id)
        all_visible_ids.append(qid)
        question_meta[qid] = {
            "year": int(year) if year else None,
            "type_id": int(type_id) if type_id else None,
            "difficulty": int(difficulty) if difficulty else None,
        }
        if point_id is not None:
            question_point_ids[qid] = int(point_id)
        if sc_id is None:
            global_unclassified_ids.add(qid)
        else:
            question_ids_by_subcat.setdefault(int(sc_id), set()).add(qid)

    type_name_map = {
        int(type_id): type_name
        for type_id, type_name in db.query(
            QuestionType.type_id, QuestionType.type_name
        ).all()
    }

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

        display_points, _display_returned, orphan_count = _build_display_points_for_subcat(
            sc=sc,
            l2_points=l2_points,
            l3_by_parent=l3_by_parent,
            question_ids_by_point=question_ids_by_point,
            sub_question_ids=sub_question_ids,
            answer_map=answer_map,
        )
        unclassified_count = len(sub_question_ids - returned_question_ids)
        # display 分支覆盖全部题；以它为准确认没有题被展示树漏掉。
        unclassified_count = max(unclassified_count, orphan_count)
        other_question_count = 0
        for node in display_points:
            if node.get("is_other"):
                other_question_count += int(node.get("total_questions") or 0)
            for child in node.get("children") or []:
                if child.get("is_other"):
                    other_question_count += int(child.get("total_questions") or 0)

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
            "display_points": display_points,
            "has_specific_points": any(
                bool(node.get("children")) for node in display_points
            ),
            "other_count": other_question_count,
            "other_question_count": other_question_count,
            "filters": _filters_for(
                ids=sub_question_ids,
                meta=question_meta,
                type_name_map=type_name_map,
            ),
            "children": [],
            "is_unclassified": False,
            "unclassified_count": unclassified_count,
        })

    # 仅当存在 sub_category_id IS NULL 的可见题时追加合成「未分类」项
    if global_unclassified_ids:
        unc_done, unc_correct = _practice_stats(answer_map, global_unclassified_ids)
        unc_scope = _scope_payload(
            "other", scope_id=0, name="未分类",
            subject_id=subject_id, sub_category_id=None, l2_id=None,
        )
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
            "display_points": [
                _build_synthetic_other(
                    ids=global_unclassified_ids,
                    answer_map=answer_map,
                    key="other:global",
                    name="未分类",
                    scope=unc_scope,
                )
            ],
            "has_specific_points": False,
            "other_count": len(global_unclassified_ids),
            "other_question_count": len(global_unclassified_ids),
            "filters": _filters_for(
                ids=global_unclassified_ids,
                meta=question_meta,
                type_name_map=type_name_map,
            ),
            "children": [],
            "is_unclassified": True,
            "unclassified_count": len(global_unclassified_ids),
        })

    return {
        "subject_id": subject_id,
        "total": len(result),
        "filters": _filters_for(
            ids=all_visible_ids,
            meta=question_meta,
            type_name_map=type_name_map,
        ),
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
    knowledge_point_ids: str = Query("", description="考点ID列表，逗号分隔；当 bySubCategory=true 时为子科目ID"),
    limit: int = Query(20, ge=1, le=100, description="题目数量上限"),
    year: Optional[int] = Query(None, description="题目年份筛选（近N年）"),
    by_sub_category: bool = Query(False, alias="bySubCategory", description="是否按子科目ID查询"),
    scope: Optional[str] = Query(None, description="subject/subcategory/l2/l3/other"),
    scope_id: int = Query(0, ge=0, alias="scopeId", description="scope 对应主键"),
    subject_id: Optional[int] = Query(
        None, ge=1, le=3, alias="subjectId",
        description="未分类（0号）范围必填：1=行测 2=申论 3=公专",
    ),
    sub_category_id: Optional[int] = Query(None, ge=0, alias="subCategoryId"),
    l2_id: Optional[int] = Query(None, ge=0, alias="l2Id"),
    point_id: Optional[int] = Query(None, ge=0, alias="pointId"),
    include_descendants: bool = Query(True, alias="includeDescendants"),
    include_other: bool = Query(False, alias="includeOther"),
    year_from: Optional[int] = Query(None, alias="yearFrom"),
    year_to: Optional[int] = Query(None, alias="yearTo"),
    type_ids: str = Query("", alias="typeIds", description="题型ID，逗号分隔"),
    difficulties: str = Query("", description="难度 1-5，逗号分隔"),
    order: str = Query("random", description="random/weak/unseen"),
    dedupe: bool = Query(True),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    根据考点ID列表或 scope 获取题目。
    旧参数（knowledge_point_ids/bySubCategory/year）保持原语义；新调用传
    scope 后走作用域查询，并支持年份区间、题型、难度、排序与题组展开。
    """
    from sqlalchemy import case
    from sqlalchemy import func as sql_func

    raw_ids = _parse_int_csv(knowledge_point_ids)
    if not scope and not raw_ids:
        return {"error": "请至少选择一个考点或子科目", "items": [], "total": 0}

    try:
        if scope:
            query = _resolve_scope_query(
                db,
                scope=scope,
                scope_id=scope_id,
                subject_id=subject_id,
                sub_category_id=sub_category_id,
                l2_id=l2_id,
                point_id=point_id,
                include_descendants=include_descendants,
                include_other=include_other,
            )
            if year_from:
                query = query.filter(QuestionBank.year >= year_from)
            if year_to:
                query = query.filter(QuestionBank.year <= year_to)
            parsed_types = _parse_int_csv(type_ids)
            if parsed_types:
                query = query.filter(QuestionBank.type_id.in_(parsed_types))
            parsed_difficulties = _parse_int_csv(difficulties)
            if parsed_difficulties:
                query = query.filter(
                    QuestionBank.difficulty.in_(parsed_difficulties)
                )
            if dedupe:
                sub = query.with_entities(
                    sql_func.min(QuestionBank.question_id).label("min_id")
                ).group_by(QuestionBank.question_content).subquery()
                query = db.query(QuestionBank).filter(
                    QuestionBank.question_id.in_(db.query(sub.c.min_id))
                )
            order_key = (order or "random").strip().lower()
            if order_key == "weak":
                stats = db.query(
                    PracticeRecord.question_id.label("question_id"),
                    sql_func.avg(PracticeRecord.is_correct).label("accuracy"),
                ).filter(
                    PracticeRecord.user_id == current_user.user_id
                ).group_by(PracticeRecord.question_id).subquery()
                query = query.outerjoin(
                    stats, stats.c.question_id == QuestionBank.question_id
                )
                order_clause = sql_func.coalesce(stats.c.accuracy, 0).asc()
            elif order_key == "unseen":
                seen = db.query(PracticeRecord.question_id.label("question_id")).filter(
                    PracticeRecord.user_id == current_user.user_id
                ).distinct().subquery()
                query = query.outerjoin(
                    seen, seen.c.question_id == QuestionBank.question_id
                )
                order_clause = case((seen.c.question_id.is_(None), 0), else_=1)
            else:
                order_clause = sql_func.random()

            total = query.count()
            questions = query.order_by(order_clause, sql_func.random()).limit(limit).all()
            questions, extra = expand_question_groups(db, questions)
            return _serialize_practice_questions(
                db, questions, total=total, limit=limit,
                requested_limit=limit, group_expanded=extra > 0,
                scope=scope, extra_count=extra,
            )
    except HTTPException:
        raise

    if by_sub_category:
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
    questions, extra = expand_question_groups(db, questions)
    return _serialize_practice_questions(
        db, questions, total=total, limit=limit,
        requested_limit=limit, group_expanded=extra > 0,
        extra_count=extra,
    )


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

    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else None
    try:
        result = await submit_answers(
            db, current_user.user_id, normalized,
            source_type="快速练习",
            subject_id=subject_id,
            session_id=payload.get("session_id"),
            scope=scope,
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
