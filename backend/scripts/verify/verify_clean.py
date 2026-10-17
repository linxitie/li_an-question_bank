# -*- coding: utf-8 -*-
"""最终精确验证 - 使用type_id直接判断"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..','..',  '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('='*60)
print('最终精确验证报告')
print('='*60)

# 1. 题型定义
print('\n[1] 题型定义表')
cursor.execute("SELECT type_id, type_name, type_code FROM question_type ORDER BY type_id")
type_map = {}
for row in cursor.fetchall():
    type_map[row[0]] = row[1]
    print(f'  type_id={row[0]:2d}  name="{row[1]}"  code="{row[2]}"')

# 2. 题目分布
print('\n[2] 题目类型分布')
cursor.execute("""
    SELECT qb.type_id, qt.type_name, COUNT(*) as cnt
    FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id = qt.type_id
    GROUP BY qb.type_id, qt.type_name
    ORDER BY qb.type_id
""")
total = 0
for row in cursor.fetchall():
    print(f'  type_id={row[0]:2d} ({row[1]}): {row[2]:5d}d')
    total += row[2]
print(f'  {"total":20s}{total:5d}d')

# 3. 精确异常检查（直接用type_id=1检查单选题）
print('\n[3] 异常检查（直接用type_id）')

# type_id=1 是单选题
cursor.execute("""
    SELECT COUNT(*) FROM question_bank
    WHERE type_id = 1 AND LENGTH(answer) > 1
    AND answer GLOB '[A-Z][A-Z]*'
""")
bad_single = cursor.fetchone()[0]
print(f'  type_id=1(单选题) 答案多字母: {bad_single}d  {"OK" if bad_single == 0 else "FAIL"}')

# type_id=3 是多选题
cursor.execute("""
    SELECT COUNT(*) FROM question_bank
    WHERE type_id = 3 AND LENGTH(answer) = 1
""")
bad_multi = cursor.fetchone()[0]
print(f'  type_id=3(多选题) 答案单字母: {bad_multi}d  {"OK" if bad_multi == 0 else "FAIL"}')

# type_id=2 简答题
cursor.execute("SELECT COUNT(*) FROM question_bank WHERE type_id = 2")
short_cnt = cursor.fetchone()[0]
print(f'  type_id=2(简答题): {short_cnt}d')

# type_id=4 不应有题目
cursor.execute("SELECT COUNT(*) FROM question_bank WHERE type_id = 4")
type4_cnt = cursor.fetchone()[0]
print(f'  type_id=4(空): {type4_cnt}d  {"OK" if type4_cnt == 0 else "FAIL"}')

# 4. detail_category 一致性
print('\n[4] question_detail_category 一致性')
cursor.execute("""
    SELECT qdc.question_type_detail, COUNT(*) as cnt
    FROM question_detail_category qdc
    GROUP BY qdc.question_type_detail
""")
for row in cursor.fetchall():
    print(f'  "{row[0]}": {row[1]}d')

# 5. 抽样验证
print('\n[5] 抽样验证')
for tid, tname in type_map.items():
    cursor.execute("""
        SELECT question_id, SUBSTR(question_content, 1, 40), answer
        FROM question_bank WHERE type_id = ? ORDER BY RANDOM() LIMIT 2
    """, (tid,))
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(f'  [{tname}] ID={r[0]}: {r[1]}... answer="{r[2]}"')
    else:
        print(f'  [{tname}] (no questions)')

conn.close()
print('\n' + '='*60)
print('DONE')
print('='*60)
