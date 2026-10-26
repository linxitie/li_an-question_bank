from sqlalchemy.orm import Session

from ..models.models import QuestionGroup


def get_question_group(db: Session, group_id: int):
    """只读题组材料；返回 QuestionGroup 或 None。"""
    if not group_id:
        return None
    return db.query(QuestionGroup).filter(QuestionGroup.id == group_id).first()
