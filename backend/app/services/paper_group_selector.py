"""复合题（题组）感知的抽题工具。

背景：行测资料分析、申论材料题、公专情境题都以 question_groups 组织，
子题必须和同一 group 的兄弟题一起出现，材料才完整。原来的智能组卷按
QuestionBank 扁平随机抽 count 道，可能只抽到组内 1 题，学生端就看不到材料，
也无法回答整组问题。

本模块提供唯一入口：给定候选查询，先随机抽，命中 group_id>0 的题时把整组
成员按 sort_order 一起加入；组内成员即使不满足题型/难度筛选也一并带入，
因为"完整"优先于"精确匹配筛选条件"。
"""
from typing import Iterable, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from app.models.models import QuestionBank


def _group_members(db: Session, group_id: int) -> Sequence[QuestionBank]:
    """取组内全部可用子题，按题组内顺序返回。"""
    return (
        db.query(QuestionBank)
        .filter(
            QuestionBank.group_id == group_id,
            QuestionBank.status == 1,
            QuestionBank.audit_status == 1,
        )
        .order_by(QuestionBank.sort_order.asc(), QuestionBank.question_id.asc())
        .all()
    )


def select_questions_with_groups(
    db: Session,
    query,
    count: int,
    selected_ids: Optional[Iterable[int]] = None,
    candidate_multiplier: int = 8,
) -> Tuple[list, Set[int]]:
    """从 query 中抽 count 道题；命中题组时整组展开。

    返回 (按抽取顺序排列的题目列表, 已占用 question_id 集合)。
    组内成员会连续排列，保证学生端材料块只出现一次且覆盖整组。
    """
    if count <= 0:
        return [], set(selected_ids or [])

    used: Set[int] = set(selected_ids or [])
    picked: list = []
    picked_groups: Set[int] = set()

    # 多取一些候选：随机序列里同一题组的成员可能重复命中，需要余量
    limit = max(count * candidate_multiplier, count + 20)
    candidates = query.order_by(func_random()).limit(limit).all()

    def push(q: QuestionBank) -> None:
        if q.question_id in used:
            return
        used.add(q.question_id)
        picked.append(q)

    for q in candidates:
        if len(picked) >= count:
            break
        gid = int(q.group_id or 0)
        if gid <= 0:
            push(q)
            continue
        if gid in picked_groups:
            continue

        members = _group_members(db, gid)
        if not members:
            # 组头已失效：宁可跳过，也不把半组题塞进试卷
            continue
        if any(m.question_id in used for m in members):
            # 组内已有成员被别的题型的配置选走，整组跳过避免拆组
            continue

        for m in members:
            push(m)
        picked_groups.add(gid)

    return picked, used


def summarize_group_selection(requested_count: int, actual_count: int) -> dict:
    """把"请求题量 vs 实际题量"整理成可直接塞进 API 响应的字段。

    整组展开是设计行为：命中题组时组内成员全部带入，因此实际题数可能
    超过请求数。前端必须显式提示，否则教师会以为系统抽多了题。
    """
    requested = max(int(requested_count or 0), 0)
    actual = max(int(actual_count or 0), 0)
    over = actual > requested and requested > 0
    return {
        "requested_count": requested,
        "actual_count": actual,
        "over_quota": over,
        "over_quota_reason": (
            f"命中复合题组后整组展开，实际 {actual} 题（配置 {requested} 题）"
            if over else ""
        ),
    }


def func_random():
    """兼容 SQLite 与 MySQL 的随机排序。"""
    from sqlalchemy import func

    return func.random()
