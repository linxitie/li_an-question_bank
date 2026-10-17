# -*- coding: utf-8 -*-
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..','..',  '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('='*60)
print('题目类型修复验证报告')
print('='*60)

# 1. 题型定义表
print('\n【1. 题型定义表 question_type】')
cursor.execute("SELECT type_id, type_name, type_code, subject_id FROM question_type ORDER BY type_id")
type_map = {}
for row in cursor.fetchall():
    type_map[row[0]] = row[1]
    print(f'  type_id={row[0]:2d}  名称="{row[1]}"  代码="{row[2]}"  subject_id={row[3]}')

# 2. 题目类型分布
print('\n【2. 题目类型分布统计】')
cursor.execute("""
    SELECT qb.type_id, COUNT(*) as cnt
    FROM question_bank qb
    GROUP BY qb.type_id
    ORDER BY qb.type_id
""")
total = 0
for row in cursor.fetchall():
    name = type_map.get(row[0], '未知')
    print(f'  type_id={row[0]:2d} ({name}): {row[1]:5d}道')
    total += row[1]
print(f'  {"":40s}------')
print(f'  {"总计":40s}{total:5d}道')

# 3. 检查单选题是否有异常答案（多个字母）
import re
print('\n【3. 单选题异常检查（答案含多个字母）】')
single_type_ids = [t for t, n in type_map.items() if '单选' in n]
if single_type_ids:
    placeholders = ','.join(['?' for _ in single_type_ids])
    cursor.execute(f"""
        SELECT qb.question_id, SUBSTR(qb.question_content, 1, 40), qb.answer
        FROM question_bank qb
        WHERE qb.type_id IN ({placeholders})
    """, single_type_ids)
    rows = cursor.fetchall()
    bad = [(r[0], r[1], r[2]) for r in rows if r[2] and len(r[2]) > 1 and re.match(r'^[A-Za-z]{2,}$', r[2].strip())]
    print(f'  单选题type_id: {single_type_ids}')
    print(f'  单选题总数: {len(rows)}')
    print(f'  答案含2个以上字母的异常题目数: {len(bad)}')
    for r in bad[:5]:
        print(f'    ID={r[0]}: {r[1]}... 答案="{r[2]}"')
else:
    print('  未找到单选题类型')

# 4. 检查多选题是否有异常答案（只有一个字母）
print('\n【4. 多选题异常检查（答案仅一个字母）】')
multi_type_ids = [t for t, n in type_map.items() if '多选' in n]
if multi_type_ids:
    placeholders = ','.join(['?' for _ in multi_type_ids])
    cursor.execute(f"""
        SELECT qb.question_id, SUBSTR(qb.question_content, 1, 40), qb.answer
        FROM question_bank qb
        WHERE qb.type_id IN ({placeholders})
    """, multi_type_ids)
    rows = cursor.fetchall()
    bad = [(r[0], r[1], r[2]) for r in rows if r[2] and len(r[2].strip()) == 1]
    print(f'  多选题type_id: {multi_type_ids}')
    print(f'  多选题总数: {len(rows)}')
    print(f'  答案仅1个字母的异常题目数: {len(bad)}')
    for r in bad[:10]:
        print(f'    ID={r[0]}: {r[1]}... 答案="{r[2]}"')
else:
    print('  未找到多选题类型')

# 5. 检查判断题是否有异常
print('\n【5. 判断题异常检查】')
judge_type_ids = [t for t, n in type_map.items() if '判断' in n]
if judge_type_ids:
    placeholders = ','.join(['?' for _ in judge_type_ids])
    cursor.execute(f"""
        SELECT COUNT(*) FROM question_bank qb
        WHERE qb.type_id IN ({placeholders})
    """, judge_type_ids)
    cnt = cursor.fetchone()[0]
    print(f'  判断题type_id: {judge_type_ids}')
    print(f'  判断题总数: {cnt}')
    cursor.execute(f"""
        SELECT qb.question_id, SUBSTR(qb.question_content, 1, 30), qb.answer
        FROM question_bank qb
        WHERE qb.type_id IN ({placeholders})
        AND qb.answer NOT IN ('对', '错', '正确', '错误', '√', '×', '1', '0', 'True', 'False', 'true', 'false', 'A', 'B')
        LIMIT 10
    """, judge_type_ids)
    rows = cursor.fetchall()
    if rows:
        print(f'  答案格式异常的判断题（前10道）:')
        for r in rows:
            print(f'    ID={r[0]}: {r[1]}... 答案="{r[2]}"')
    else:
        print(f'  所有判断题答案格式正常')
else:
    print('  未找到判断题类型')

# 6. 检查 detail_category 一致性
print('\n【6. question_detail_category 一致性检查】')
try:
    cursor.execute("""
        SELECT qb.type_id, qdc.type_name, COUNT(*) as cnt
        FROM question_bank qb
        LEFT JOIN question_detail_category qdc ON qb.question_id = qdc.question_id
        GROUP BY qb.type_id, qdc.type_name
        ORDER BY qb.type_id
    """)
    for r in cursor.fetchall():
        bank_type = type_map.get(r[0], '未知')
        match = '✓' if r[1] == bank_type else '✗'
        print(f'  bank={bank_type}(id={r[0]}) vs detail={r[1]}: {r[2]}道 {match}')
except Exception as e:
    print(f'  查询失败: {e}')

conn.close()
print('\n' + '='*60)
print('验证完成')
print('='*60)
