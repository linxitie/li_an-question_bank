"""试卷与题目关联的派生统计。

`ExamPaper.question_count` 是冗余字段：唯一事实来源是 `PaperQuestionRelation` 的行数。
导入、手工加题、删题、清空等多条写路径都曾各自做 +1/-1 累加，
一旦任一环节的初值或增量出错（实测：导入 110 题的试卷 question_count=1），
字段就永久漂移，前端「题目数」与实际组卷不一致。

约定：**任何修改试卷-题目关联的路径，结束后都调用 recount_paper_questions()**，
不要再用增量算术。
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import ExamPaper, PaperQuestionRelation, QuestionBank


def recount_paper_questions(db: Session, paper: ExamPaper) -> int:
    """以关联行实际数量重算 paper.question_count 并返回该数量。

    调用前无需手动 flush：本函数会先 flush，确保当前事务里 add 的关系行被计入。
    """
    db.flush()
    actual = (
        db.query(func.count(PaperQuestionRelation.question_id))
        .filter(PaperQuestionRelation.paper_id == paper.paper_id)
        .scalar()
        or 0
    )
    paper.question_count = int(actual)
    return int(actual)


def next_question_order(db: Session, paper_id: int) -> int:
    """返回该试卷下一个可用的题序（max(question_order)+1），从 1 开始。

    题序同样以关联行为准：question_count 漂移时按它续号会产生重复题序。
    """
    db.flush()
    current_max = (
        db.query(func.max(PaperQuestionRelation.question_order))
        .filter(PaperQuestionRelation.paper_id == paper_id)
        .scalar()
        or 0
    )
    return int(current_max) + 1


def normalize_question_orders(db: Session, paper_id: int, *, apply: bool = True) -> dict:
    """按**题号**把卷内题序对齐（D8，2026-11-15）。不满足前提就一条不改。

    为什么需要它：导入路径是"追加模型"（`next_question_order` = max+1），
    只要一张卷**分批补录**，后补的题就会排到卷尾 —— 2024 国考卷 #4 实测 100 条里 60 条错位，
    当时只能靠 `backend/scripts/seed_2024_gk/fix_relation_order.py` 事后修。
    这里把那条规则（`question_order = question_number`）搬进服务层，导入完自动对齐。

    前提（与修复脚本同口径，**宁可不改也不误伤**）：
      · 该卷所有关联题都有**纯数字题号**；
      · 题号**互不重复**。

    Returns:
        {"total": int, "changed": int, "skipped_reason": str|None}
        `skipped_reason`: empty / non-numeric / duplicate
    """
    db.flush()
    rels = (db.query(PaperQuestionRelation)
              .filter(PaperQuestionRelation.paper_id == paper_id).all())
    total = len(rels)
    if not total:
        return {"total": 0, "changed": 0, "skipped_reason": "empty"}

    qids = [r.question_id for r in rels]
    nums = dict(db.query(QuestionBank.question_id, QuestionBank.question_number)
                  .filter(QuestionBank.question_id.in_(qids)).all())
    want: dict = {}
    for qid in qids:
        raw = str(nums.get(qid) or "").strip()
        if not raw.isdigit() or len(raw) > 4:
            return {"total": total, "changed": 0, "skipped_reason": "non-numeric"}
        want[qid] = int(raw)
    if len(set(want.values())) != len(want):
        return {"total": total, "changed": 0, "skipped_reason": "duplicate"}

    changed = 0
    for rel in rels:
        target = want[rel.question_id]
        if int(rel.question_order or 0) != target:
            changed += 1
            if apply:
                rel.question_order = target
    if apply and changed:
        db.flush()
    return {"total": total, "changed": changed, "skipped_reason": None}
