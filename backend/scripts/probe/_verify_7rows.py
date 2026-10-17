# -*- coding: utf-8 -*-
"""临时验证：7条论述误判行经过当前 _detect_question_type 的判定结果"""
import sys
import json
import sqlite3
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from app.services.text_parser import _detect_question_type, canonical_answer

con = sqlite3.connect('data/question_bank.db')
con.row_factory = sqlite3.Row
rows = con.execute("""
    SELECT qb.question_id, qb.question_content, qb.options, qb.answer
    FROM question_bank qb WHERE qb.type_id = 2
""").fetchall()
con.close()

for r in rows:
    opts = r['options']
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except Exception:
            opts = []
    detected, conf = _detect_question_type(r['question_content'], opts or [], r['answer'] or '')
    norm = canonical_answer(r['answer'] or '')
    mark = '← 需修复' if detected != '论述题' else ''
    print(f"qid={r['question_id']:<5} answer={r['answer']!r:<8} norm={norm!r:<8} "
          f"engine→{detected} conf={conf:.2f} {mark}")
