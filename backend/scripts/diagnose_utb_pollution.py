# -*- coding: utf-8 -*-
"""diagnose_utb_pollution.py — 检查UTB测试数据的全链路污染（只读）"""
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect('data/question_bank.db')
cur = con.cursor()

print('=== UTB 污染题目 ID ===')
ids = [r[0] for r in cur.execute(
    "SELECT question_id FROM question_bank WHERE question_content LIKE '%UTB%' OR question_content LIKE '%测试要点%'")]
print(ids)

print()
print('=== 关联试卷（双轨入库污染）===')
for r in cur.execute("SELECT paper_id, paper_name, paper_type, question_count, creator_id FROM exam_paper WHERE paper_name LIKE '%UTB%' OR paper_name LIKE '%直测%'"):
    print(r)

print()
print('=== 导入记录污染 ===')
for r in cur.execute("SELECT * FROM question_import_record WHERE original_filename LIKE '%UTB%' OR original_filename LIKE '%直测%'"):
    print(r)

print()
print('=== 试卷-题目关联污染 ===')
if ids:
    rows = cur.execute(
        'SELECT paper_id, question_id FROM paper_question_relation WHERE question_id IN (%s)' % ','.join(map(str, ids))
    ).fetchall()
    print(f'{len(rows)} 条关联: {rows[:12]}')

print()
print('=== 重复题目检测（同题干前50字多行）===')
for r in cur.execute(
    "SELECT substr(question_content,1,50), COUNT(*) c FROM question_bank WHERE status=1 GROUP BY substr(question_content,1,50) HAVING c>1 ORDER BY c DESC LIMIT 8"):
    print(r)

print()
print('=== 空目录统计（static/questions）===')
import os
sq = 'app/static/questions'
if os.path.exists(sq):
    dirs = [d for d in os.listdir(sq) if os.path.isdir(os.path.join(sq, d))]
    empty = [d for d in dirs if not os.listdir(os.path.join(sq, d))]
    print(f'目录总数: {len(dirs)}, 空目录: {len(empty)}')
    # 引用检查：内容引用了不存在文件的题
    print()
    print('=== 内容引用图片但文件缺失的题（前10）===')
    import re
    missing = 0
    for qid, content in cur.execute("SELECT question_id, question_content FROM question_bank WHERE question_content LIKE '%<img%'"):
        for m in re.findall(r'src="(/static/questions/[^"]+)"', content or ''):
            rel = m.lstrip('/').replace('static/questions', 'app/static/questions', 1)
            if not os.path.exists(rel.replace('/', os.sep)):
                print(f'qid={qid} 缺失: {m}')
                missing += 1
                if missing >= 10:
                    break
        if missing >= 10:
            break
    if missing == 0:
        print('无缺失')

con.close()
