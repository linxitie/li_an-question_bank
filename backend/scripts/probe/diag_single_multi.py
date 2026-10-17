# -*- coding: utf-8 -*-
"""诊断340道单选题答案多字母的问题"""
import sqlite3
import os
import re

db_path = os.path.join(os.path.dirname(__file__), '..','..',  '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 确认单选题type_id
print('=== 确认单选题type_id ===')
cursor.execute("SELECT type_id, type_name FROM question_type ORDER BY type_id")
types = cursor.fetchall()
single_ids = []
for tid, tname in types:
    print(f'  type_id={tid} name="{tname}"')
    if '单选' in tname:
        single_ids.append(tid)
print(f'单选题type_id列表: {single_ids}')

# 2. 检查单选题答案长度分布
print('\n=== 单选题答案长度分布 ===')
if single_ids:
    ph = ','.join(['?' for _ in single_ids])
    cursor.execute(f"""
        SELECT LENGTH(answer) as ans_len, COUNT(*) as cnt
        FROM question_bank
        WHERE type_id IN ({ph})
        GROUP BY ans_len ORDER BY ans_len
    """, single_ids)
    for row in cursor.fetchall():
        print(f'  答案长度={row[0]}: {row[1]}道')

# 3. 检查答案是否包含中文或其他字符
print('\n=== 单选题答案异常样本（长度>1） ===')
if single_ids:
    ph = ','.join(['?' for _ in single_ids])
    cursor.execute(f"""
        SELECT question_id, answer, SUBSTR(question_content, 1, 40)
        FROM question_bank
        WHERE type_id IN ({ph}) AND LENGTH(answer) > 1
        LIMIT 20
    """, single_ids)
    rows = cursor.fetchall()
    for r in rows:
        has_alpha = bool(re.match(r'^[A-Za-z]+$', r[1]))
        print(f'  ID={r[0]} 答案="{r[1]}" 纯字母={has_alpha} | {r[2]}...')

# 4. 检查答案含逗号/分号的情况（多答案用标点分隔）
print('\n=== 答案含标点分隔的统计 ===')
if single_ids:
    ph = ','.join(['?' for _ in single_ids])
    cursor.execute(f"""
        SELECT COUNT(*) FROM question_bank
        WHERE type_id IN ({ph}) AND LENGTH(answer) > 1
        AND (answer LIKE '%,%' OR answer LIKE '%;%' OR answer LIKE '%，%' OR answer LIKE '%、%')
    """, single_ids)
    print(f'  含标点分隔: {cursor.fetchone()[0]}道')

    cursor.execute(f"""
        SELECT COUNT(*) FROM question_bank
        WHERE type_id IN ({ph}) AND LENGTH(answer) > 1
        AND answer GLOB '[A-Z][A-Z]*'
    """, single_ids)
    print(f'  纯多字母(如ABC): {cursor.fetchone()[0]}道')

    cursor.execute(f"""
        SELECT COUNT(*) FROM question_bank
        WHERE type_id IN ({ph}) AND LENGTH(answer) > 1
        AND answer NOT GLOB '[A-Z][A-Z]*'
        AND answer NOT LIKE '%,%'
        AND answer NOT LIKE '%;%'
        AND answer NOT LIKE '%，%'
        AND answer NOT LIKE '%、%'
    """, single_ids)
    print(f'  其他格式: {cursor.fetchone()[0]}道')

conn.close()
