"""验证剩余4题通用选择题 + 答案截断检查"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionDetailCategory

db = SessionLocal()
try:
    # 1. 检查4题通用"选择题"
    generic = db.query(
        QuestionBank.question_id,
        QuestionBank.answer,
        QuestionBank.question_content,
        QuestionDetailCategory.question_type_detail
    ).outerjoin(
        QuestionDetailCategory,
        QuestionBank.question_id == QuestionDetailCategory.question_id
    ).filter(
        QuestionBank.subject_id == 3,
        QuestionBank.status == 1,
        QuestionDetailCategory.question_type_detail == '选择题'
    ).all()

    print(f"=== 通用'选择题'({len(generic)}题) ===")
    for qid, ans, content, qt in generic:
        letters = re.sub(r'[^A-D]', '', str(ans or '').upper())
        new_type = '多选题' if len(letters) >= 2 else '单选题'
        print(f"  Q{qid}: ans={ans}, 建议类型={new_type}, preview={(content or '')[:80]}")

    # 2. 答案截断检查：答案字段只有一个字母但内容中有"ABCD"等完整答案
    truncated = []
    rows = db.query(
        QuestionBank.question_id,
        QuestionBank.answer,
        QuestionBank.question_content
    ).filter(
        QuestionBank.subject_id == 3,
        QuestionBank.status == 1
    ).all()

    for qid, ans, content in rows:
        if not ans or not content:
            continue
        ans_str = str(ans).strip().upper()
        # 单字母答案
        if len(re.sub(r'[^A-D]', '', ans_str)) == 1:
            # 检查内容中是否有嵌入式多字母答案
            embedded = re.findall(r'(?:故本题答案|故正确答案|本题答案|正确答案)(?:为|是|选)\s*[:：]?\s*([A-D]{2,4})', content)
            if embedded:
                truncated.append((qid, ans, embedded[0], content[:80]))

    print(f"\n=== 答案截断检查(单字母但内容含多字母)({len(truncated)}题) ===")
    for qid, ans, full, preview in truncated[:15]:
        print(f"  Q{qid}: 当前答案={ans}, 内容中多字母={full}, preview={preview}")

    # 3. 写作题检查
    writing = db.query(QuestionBank.question_id, QuestionBank.question_content).filter(
        QuestionBank.subject_id == 3,
        QuestionBank.status == 1,
        QuestionBank.question_content.like('%写作%')
    ).limit(5).all()
    print(f"\n=== 含'写作'关键词题目({len(writing)}题) ===")
    for qid, content in writing:
        print(f"  Q{qid}: {(content or '')[:80]}")

finally:
    db.close()
