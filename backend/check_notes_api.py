"""模拟 /api/notes/question API 逻辑，检查是否会抛异常"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.models import QuestionNote, QuestionBank, QuestionSubject
from sqlalchemy import desc

db = SessionLocal()

USER_ID = 2  # 202516001

print("=== 1. 查询 QuestionNote ===")
base_query = db.query(QuestionNote).filter(QuestionNote.user_id == USER_ID)
total = base_query.count()
print(f"total: {total}")

notes = base_query.order_by(desc(QuestionNote.update_time)).offset(0).limit(20).all()
print(f"notes 数量: {len(notes)}")
print()

print("=== 2. 遍历 notes 构建 items ===")
items = []
for note in notes:
    print(f"\n处理 note_id={note.note_id}, question_id={note.question_id}")
    print(f"  note.create_time type: {type(note.create_time)}, value: {note.create_time}")
    print(f"  note.update_time type: {type(note.update_time)}, value: {note.update_time}")

    try:
        q = db.query(QuestionBank).filter(QuestionBank.question_id == note.question_id).first()
        print(f"  QuestionBank found: {q is not None}")
        if q:
            print(f"  q.question_content type: {type(q.question_content)}")
            print(f"  q.subject_id: {q.subject_id}")
            subj = db.query(QuestionSubject).filter(QuestionSubject.subject_id == q.subject_id).first()
            print(f"  Subject found: {subj is not None}, name: {subj.subject_name if subj else None}")

        # 模拟 _get_subcategory
        from app.api.v1.notes import _get_subcategory
        subcategory = _get_subcategory(q)
        print(f"  subcategory: {subcategory}")

        # 尝试构建 item（与 notes.py 第 301-310 行一致）
        item = {
            'note_id': note.note_id,
            'note_text': note.note_text,
            'question_id': note.question_id,
            'question_content': (q.question_content[:200] + '...' if q and q.question_content and len(q.question_content) > 200 else (q.question_content if q else '题目已删除')),
            'subject_name': subj.subject_name if subj else '',
            'subcategory': subcategory,
            'create_time': note.create_time.isoformat() if note.create_time else '',
            'update_time': note.update_time.isoformat() if note.update_time else '',
        }
        items.append(item)
        print(f"  ✓ item 构建成功")
        print(f"  item: {item}")
    except Exception as e:
        print(f"  ✗ 异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

print()
print(f"=== 3. 最终 items 数量: {len(items)} ===")
print(f"items: {items}")

db.close()
