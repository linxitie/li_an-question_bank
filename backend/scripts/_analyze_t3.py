# -*- coding: utf-8 -*-
"""只读分析：分类 repair_question_types.py dry-run 的 102 条变更，甄别可疑项"""
import sys
import json
import sqlite3
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionDetailCategory
from app.services.text_parser import _detect_question_type, canonical_answer

db = SessionLocal()
questions = db.query(QuestionBank).filter(QuestionBank.status == 1).all()

cat = Counter()
suspicious = []
for q in questions:
    old_bank = q.type.type_name if q.type else ''
    detail = db.query(QuestionDetailCategory).filter(
        QuestionDetailCategory.question_id == q.question_id).first()
    old_detail = detail.question_type_detail if detail else ''
    detected, _conf = _detect_question_type(q.question_content or '', q.options or [], q.answer or '')
    norm = canonical_answer(q.answer or '')
    new_answer = norm if (detected in ('单选题', '多选题') and norm) else (q.answer or '')

    type_changed = detected != old_bank
    detail_changed = detected != old_detail
    answer_changed = new_answer != (q.answer or '')
    if not (type_changed or detail_changed or answer_changed):
        continue

    letters = len([c for c in (q.answer or '') if c.upper() in 'ABCD'])
    if '论述' in old_bank or '论述' in old_detail:
        key = f'论述→{detected}'
    elif type_changed and old_bank in ('单选题', '多选题') and detected in ('单选题', '多选题'):
        key = f'{old_bank}→{detected}(答案{letters}字母)'
    elif answer_changed and not type_changed:
        key = '仅答案归一化'
    else:
        key = f'其他:{old_bank}→{detected}'
    cat[key] += 1
    # 可疑：单字母答案却被改判多选，或多字母被判单选
    if (detected == '多选题' and letters <= 1) or (detected == '单选题' and letters >= 2):
        suspicious.append((q.question_id, old_bank, detected, q.answer, letters,
                           (q.question_content or '')[:40]))

print('=== 变更分类统计 ===')
for k, v in cat.most_common():
    print(f'  {k}: {v}')
print(f'  合计: {sum(cat.values())}')
print()
print('=== 可疑项（答案字母数与判定矛盾）===')
for s in suspicious[:15]:
    print(f'  qid={s[0]} {s[1]}→{s[2]} answer={s[3]!r} letters={s[4]} | {s[5]}')
print(f'  可疑合计: {len(suspicious)}')
db.close()
