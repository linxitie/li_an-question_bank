# -*- coding: utf-8 -*-
"""检查152道多选题（答案单字母）的选项格式"""
import sqlite3
import os
import json

db_path = os.path.join(os.path.dirname(__file__), '..','..',  '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('=== 检查152道多选题的选项格式 ===\n')

# 抽样10道题，查看完整选项
cursor.execute("""
    SELECT question_id, question_content, options, answer
    FROM question_bank
    WHERE type_id = 3 AND LENGTH(answer) = 1
    LIMIT 10
""")
rows = cursor.fetchall()
for row in rows:
    qid = row[0]
    content = row[1][:60] if row[1] else 'None'
    options_raw = row[2]
    answer = row[3]
    
    print(f'ID={qid}: 答案="{answer}"')
    print(f'  内容: {content}...')
    
    # 解析选项
    try:
        if options_raw:
            opts = json.loads(options_raw)
            if isinstance(opts, list):
                print(f'  选项数量: {len(opts)}')
                for opt in opts:
                    if isinstance(opt, dict):
                        key = opt.get('key', '?')
                        val = str(opt.get('value', ''))[:30]
                        print(f'    {key}: {val}...')
            elif isinstance(opts, dict):
                print(f'  选项格式: dict, keys={list(opts.keys())[:5]}')
            else:
                print(f'  选项格式: {type(opts).__name__}')
        else:
            print(f'  选项: 空')
    except Exception as e:
        print(f'  选项解析失败: {e}')
        print(f'  原始选项前100字符: {str(options_raw)[:100]}')
    print()

# 统计选项格式分布
print('\n=== 选项格式分布 ===')
cursor.execute("""
    SELECT 
        CASE 
            WHEN options IS NULL OR options = '' THEN '空'
            WHEN options LIKE '[{"key"%' THEN 'JSON数组'
            WHEN options LIKE '{"key"%' THEN 'JSON对象'
            WHEN options LIKE 'A.%' OR options LIKE 'A、%' THEN '文本格式'
            ELSE '其他格式'
        END as format_type,
        COUNT(*) as cnt
    FROM question_bank
    WHERE type_id = 3 AND LENGTH(answer) = 1
    GROUP BY format_type
""")
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}道')

# 检查真正的多选题应该长什么样
print('\n=== 真正的多选题样本（答案>=2字母） ===')
cursor.execute("""
    SELECT question_id, options, answer
    FROM question_bank
    WHERE type_id = 3 AND LENGTH(answer) >= 2
    LIMIT 3
""")
for row in cursor.fetchall():
    qid = row[0]
    answer = row[2]
    try:
        opts = json.loads(row[1]) if row[1] else []
        opt_count = len(opts) if isinstance(opts, list) else 0
        print(f'ID={qid}: 答案="{answer}" 选项数={opt_count}')
    except:
        print(f'ID={qid}: 答案="{answer}" 选项解析失败')

conn.close()
