# -*- coding: utf-8 -*-
"""T11 全量验收：与基线对比输出最终指标"""
import sys
import sqlite3
import os
sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect('data/question_bank.db')
cur = con.cursor()

total = cur.execute('SELECT COUNT(*) FROM question_bank').fetchone()[0]
active = cur.execute('SELECT COUNT(*) FROM question_bank WHERE status=1').fetchone()[0]
utb = cur.execute("SELECT COUNT(*) FROM question_bank WHERE question_content LIKE '%UTB%' OR question_content LIKE '%测试要点%'").fetchone()[0]
essay = cur.execute("SELECT COUNT(*) FROM question_bank WHERE status=1 AND type_id=2").fetchone()[0]
empty_analysis = cur.execute("SELECT COUNT(*) FROM question_bank WHERE status=1 AND (answer_analysis IS NULL OR TRIM(answer_analysis)='' OR answer_analysis='[OCR导入，待补充答案解析]')").fetchone()[0]
empty_answer = cur.execute("SELECT COUNT(*) FROM question_bank WHERE status=1 AND (answer='' OR answer='待补充')").fetchone()[0]
conflict = cur.execute("""
    SELECT COUNT(*) FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id=qt.type_id
    LEFT JOIN question_detail_category qdc ON qdc.question_id=qb.question_id
    WHERE qb.status=1 AND ((qt.type_name IN ('单选题','多选题') AND qdc.question_type_detail IN ('论述题','简答题','案例分析题','写作题'))
       OR (qt.type_name='论述题' AND qdc.question_type_detail IN ('单选题','多选题','选择题')))""").fetchone()[0]

sq = os.path.join('app', 'static', 'questions')
entries = os.listdir(sq) if os.path.exists(sq) else []
dir_list = [d for d in entries if os.path.isdir(os.path.join(sq, d))]
loose_files = [d for d in entries if not os.path.isdir(os.path.join(sq, d))]
empty_dirs = sum(1 for d in dir_list if not os.listdir(os.path.join(sq, d)))
img_files = sum(len([f for f in os.listdir(os.path.join(sq, d)) if f.lower().endswith(('.png','.jpg','.jpeg'))]) for d in dir_list)

print('====== 验收指标（基线 → 现状）======')
print(f'总题数(含软删)     : 930 → {total}')
print(f'活跃题数           : 930 → {active}')
print(f'UTB/测试要点污染   : 10 → {utb}')
print(f'污染试卷           : 2 → {cur.execute("SELECT COUNT(*) FROM exam_paper WHERE paper_name LIKE \'%UTB%\'").fetchone()[0]}')
print(f'论述题误判(活跃)   : 7 → {essay}')
print(f'双源题型冲突       : 0 → {conflict}')
print(f'空解析(活跃)       : 314 → {empty_analysis}')
print(f'空答案(活跃)       : 103 → {empty_answer}')
print(f'图片目录总数       : 383 → {len(dir_list)}')
print(f'空目录             : 298 → {empty_dirs}')
print(f'散落扁平图片文件   : 0 → {len(loose_files)}')
print(f'图片文件           : 370 → {img_files}')
con.close()
