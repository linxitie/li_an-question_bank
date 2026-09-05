"""验证题目类型映射正确性"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionDetailCategory

db = SessionLocal()
try:
    rows = db.query(
        QuestionBank.question_id,
        QuestionBank.answer,
        QuestionBank.question_content,
        QuestionDetailCategory.question_type_detail
    ).outerjoin(
        QuestionDetailCategory,
        QuestionBank.question_id == QuestionDetailCategory.question_id
    ).filter(
        QuestionBank.subject_id == 3,
        QuestionBank.status == 1
    ).all()

    total = len(rows)
    wrong = []
    type_dist = {}

    for qid, ans, content, qt in rows:
        key = qt or "无分类"
        type_dist[key] = type_dist.get(key, 0) + 1

        # 多字母答案但非多选题
        if ans:
            letters = re.sub(r'[^A-D]', '', str(ans).upper())
            if len(letters) >= 2 and qt and '多选' not in qt:
                wrong.append((qid, ans, qt, (content or '')[:60]))

    print(f"总计: {total} 题")
    print(f"题型分布: {type_dist}")
    print(f"多字母答案但非多选题: {len(wrong)} 题")
    for qid, ans, qt, preview in wrong[:15]:
        print(f"  Q{qid}: ans={ans}, type={qt}, preview={preview}")

    # 检查有选项但类型为论述题的情况
    has_options_but_discuss = []
    for qid, ans, content, qt in rows:
        if qt and '论述' in qt and content:
            # 检查内容是否包含选项模式 (A. B. C. D.)
            if re.search(r'[A-D][.、．]\s*\S', content):
                has_options_but_discuss.append((qid, qt, content[:80]))

    print(f"\n有选项但类型为论述题: {len(has_options_but_discuss)} 题")
    for qid, qt, preview in has_options_but_discuss[:10]:
        print(f"  Q{qid}: type={qt}, preview={preview}")

finally:
    db.close()
