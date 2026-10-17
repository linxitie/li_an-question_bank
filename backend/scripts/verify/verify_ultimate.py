# -*- coding: utf-8 -*-
"""最终验证脚本"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..','..',  '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('='*60)
print('最终验证报告')
print('='*60)

# 1. 题型定义
print('\n【1. 题型定义表】')
cursor.execute("SELECT type_id, type_name, type_code FROM question_type ORDER BY type_id")
type_map = {}
for row in cursor.fetchall():
    type_map[row[0]] = row[1]
    print(f'  type_id={row[0]:2d}  名称="{row[1]}"  代码="{row[2]}"')

# 2. 题目分布
print('\n【2. 题目类型分布】')
cursor.execute("""
    SELECT qb.type_id, qt.type_name, COUNT(*) as cnt
    FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id = qt.type_id
    GROUP BY qb.type_id, qt.type_name
    ORDER BY qb.type_id
""")
total = 0
for row in cursor.fetchall():
    print(f'  type_id={row[0]:2d} ({row[1]}): {row[2]:5d}道')
    total += row[2]
print(f'  {"总计":20s}{total:5d}道')

# 3. 异常检查
print('\n【3. 异常检查】')

# 单选题答案多字母
single_ids = [t for t, n in type_map.items() if '单选' in n]
placeholders = ','.join(['?' for _ in single_ids])
cursor.execute(f"""
    SELECT COUNT(*) FROM question_bank
    WHERE type_id IN ({placeholders}) AND LENGTH(answer) > 1
    AND answer GLOB '[A-Z][A-Z]*'
""", single_ids)
bad_single = cursor.fetchone()[0]
print(f'  单选题答案多字母: {bad_single}道 {"OK" if bad_single == 0 else "FAIL"}')

# 多选题答案单字母
multi_ids = [t for t, n in type_map.items() if '多选' in n]
placeholders = ','.join(['?' for _ in multi_ids])
cursor.execute(f"""
    SELECT COUNT(*) FROM question_bank
    WHERE type_id IN ({placeholders}) AND LENGTH(answer) = 1
""", multi_ids)
bad_multi = cursor.fetchone()[0]
print(f'  多选题答案单字母: {bad_multi}道 {"OK" if bad_multi == 0 else "FAIL"}')

# 判断题
judge_ids = [t for t, n in type_map.items() if '判断' in n]
if judge_ids:
    placeholders = ','.join(['?' for _ in judge_ids])
    cursor.execute(f"SELECT COUNT(*) FROM question_bank WHERE type_id IN ({placeholders})", judge_ids)
    judge_cnt = cursor.fetchone()[0]
    print(f'  判断题数量: {judge_cnt}道')
else:
    print(f'  判断题: 无定义')

# 4. 抽样验证
print('\n【4. 抽样验证（每类随机2道）】')
for tid, tname in type_map.items():
    cursor.execute("""
        SELECT question_id, SUBSTR(question_content, 1, 40), answer
        FROM question_bank WHERE type_id = ? ORDER BY RANDOM() LIMIT 2
    """, (tid,))
    rows = cursor.fetchall()
    for r in rows:
        print(f'  [{tname}] ID={r[0]}: {r[1]}... 答案="{r[2]}"')

conn.close()
print('\n' + '='*60)
print('验证完成 OK')
print('='*60)
