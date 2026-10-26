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

from ..models.models import ExamPaper, PaperQuestionRelation


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
