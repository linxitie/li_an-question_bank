# -*- coding: utf-8 -*-
"""深度验证：检查特殊题型和异常题目"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('='*60)
print('深度验证报告')
print('='*60)

# 1. 检查单选题答案异常的2道题（ID=971, ID=981）
print('\n【1. 单选题异常题目详情】')
cursor.execute("""
    SELECT qb.question_id, qb.question_content, qb.options, qb.answer, qb.type_id, qt.type_name
    FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id = qt.type_id
    WHERE qb.question_id IN (971, 981)
""")
for row in cursor.fetchall():
    print(f'\n  题目ID: {row[0]}')
    print(f'  题型: {row[5]}(type_id={row[4]})')
    print(f'  内容: {row[1][:80] if row[1] else "无"}')
    print(f'  选项: {row[2][:100] if row[2] else "无"}')
    print(f'  答案: {row[3]}')

# 2. 检查type_id=4的多选题（比type_id=3多109道）
print('\n\n【2. type_id=4 vs type_id=3 多选题对比】')
for tid in [3, 4]:
    cursor.execute("""
        SELECT qt.type_name, qt.type_code, COUNT(*) as cnt
        FROM question_bank qb
        LEFT JOIN question_type qt ON qb.type_id = qt.type_id
        WHERE qb.type_id = ?
        GROUP BY qb.type_id
    """, (tid,))
    row = cursor.fetchone()
    if row:
        print(f'  type_id={tid}: 名称="{row[0]}" 代码="{row[1]}" 数量={row[2]}道')

# 3. 检查type_id=2(简答题)唯一的1道题
print('\n\n【3. 简答题(type_id=2)唯一题目】')
cursor.execute("""
    SELECT qb.question_id, qb.question_content, qb.answer, qb.type_id
    FROM question_bank qb
    WHERE qb.type_id = 2
""")
row = cursor.fetchone()
if row:
    print(f'  题目ID: {row[0]}')
    print(f'  内容: {row[1][:100] if row[1] else "无"}')
    print(f'  答案: {row[2][:100] if row[2] else "无"}')
else:
    print('  无简答题')

# 4. 检查所有题型的完整统计
print('\n\n【4. 全部题型详细统计】')
cursor.execute("""
    SELECT qb.type_id, qt.type_name, COUNT(*) as cnt,
           AVG(LENGTH(qb.answer)) as avg_answer_len
    FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id = qt.type_id
    GROUP BY qb.type_id, qt.type_name
    ORDER BY qb.type_id
""")
for row in cursor.fetchall():
    print(f'  type_id={row[0]:2d} | {row[1]:8s} | {row[2]:5d}道 | 平均答案长度={row[3]:.1f}')

# 5. 抽样检查几道修复后的多选题
print('\n\n【5. 修复后的多选题抽样检查】')
cursor.execute("""
    SELECT qb.question_id, SUBSTR(qb.question_content, 1, 50), qb.answer, qt.type_name
    FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id = qt.type_id
    WHERE qt.type_name LIKE '%多选%'
    AND LENGTH(qb.answer) >= 2
    ORDER BY RANDOM()
    LIMIT 5
""")
for row in cursor.fetchall():
    print(f'  ID={row[0]}: {row[1]}... 答案="{row[2]}" 类型={row[3]}')

conn.close()
print('\n' + '='*60)
print('深度验证完成')
print('='*60)
