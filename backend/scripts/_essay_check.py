# -*- coding: utf-8 -*-
import sys
import sqlite3
sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect('data/question_bank.db')
n_essay = con.execute(
    "SELECT COUNT(*) FROM question_bank WHERE type_id=2").fetchone()[0]
detail_essay = con.execute(
    "SELECT COUNT(*) FROM question_detail_category WHERE question_type_detail='论述题'").fetchone()[0]
print('type_id=2(论述题) 题数:', n_essay)
print('detail=论述题 题数:', detail_essay)
for r in con.execute("""SELECT qb.question_id, qt.type_name, qdc.question_type_detail
    FROM question_bank qb LEFT JOIN question_type qt ON qb.type_id=qt.type_id
    LEFT JOIN question_detail_category qdc ON qdc.question_id=qb.question_id
    WHERE qb.question_id IN (83,609,709,865,929,934,1095)"""):
    print(' ', tuple(r))
con.close()
