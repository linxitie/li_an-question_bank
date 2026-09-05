"""
历史题目题型回填迁移脚本
用法: python -m scripts.migrate_question_types [--dry-run]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionDetailCategory
from sqlalchemy import and_
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def detect_type_from_answer_and_content(q):
    """根据答案和内容推断题型"""
    answer = str(q.answer or '').strip()
    content = (q.question_content or '').lower()

    # 多选题判断
    if len(answer) > 1 and all(c in 'ABCD' for c in answer):
        return '多选题'
    # 关键词判断
    multi_keywords = ['多选', '不定项', '至少.*个', '两项', '哪些', '属于.*有', '正确的有', '错误的有']
    import re
    if any(re.search(kw, content) for kw in multi_keywords):
        return '多选题'
    if any(kw in content for kw in ['判断', '对错', '正确', '错误']) and len(content) < 300:
        return '单选题'
    if any(kw in content for kw in ['填空', '______', '___']):
        return '论述题'
    if any(kw in content for kw in ['简答', '简述']):
        return '简答题'
    if any(kw in content for kw in ['论述', '论证']):
        return '论述题'
    return '单选题'


def migrate(dry_run=False):
    db = SessionLocal()
    try:
        questions = db.query(QuestionBank).outerjoin(
            QuestionDetailCategory,
            QuestionBank.question_id == QuestionDetailCategory.question_id
        ).filter(
            QuestionDetailCategory.category_id == None
        ).all()

        logger.info(f"找到 {len(questions)} 条待回填题目")

        count = 0
        for q in questions:
            qtype = detect_type_from_answer_and_content(q)
            if not dry_run:
                db.add(QuestionDetailCategory(
                    question_id=q.question_id,
                    question_type_detail=qtype,
                    xingce_subcategory='无',
                    shenlun_subcategory='无',
                    gongzhuan_subcategory='无'
                ))
                count += 1

        if not dry_run:
            db.commit()
        logger.info(f"{'[DRY-RUN] 将' if dry_run else '已'}回填 {count} 条题目")

    finally:
        db.close()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    migrate(dry_run)
