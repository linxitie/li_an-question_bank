# -*- coding: utf-8 -*-
"""检查152道多选题（答案单字母）的具体情况"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..','..',  '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('=== 152道多选题（答案单字母）分析 ===\n')

# 先看答案分布
cursor.execute("""
    SELECT qb.answer, COUNT(*) as cnt
    FROM question_bank qb
    WHERE qb.type_id = 3 AND LENGTH(qb.answer) = 1
    GROUP BY qb.answer
    ORDER BY cnt DESC
""")
print('【答案分布】')
for row in cursor.fetchall():
    print(f'  答案 "{row[0]}": {row[1]}道')

# 查看这些题的选项数量
print('\n【选项数量分析（抽样20道）】')
cursor.execute("""
    SELECT qb.question_id, qb.answer, 
           CASE 
             WHEN qb.options LIKE '%"key":"A"%' AND qb.options LIKE '%"key":"B"%' 
                  AND qb.options LIKE '%"key":"C"%' AND qb.options LIKE '%"key":"D"%' THEN 4
             WHEN qb.options LIKE '%"key":"A"%' AND qb.options LIKE '%"key":"B"%' 
                  AND qb.options LIKE '%"key":"C"%' THEN 3
             WHEN qb.options LIKE '%"key":"A"%' AND qb.options LIKE '%"key":"B"%' THEN 2
             ELSE 1
           END as option_count,
           SUBSTR(qb.question_content, 1, 60) as content_preview
    FROM question_bank qb
    WHERE qb.type_id = 3 AND LENGTH(qb.answer) = 1
    LIMIT 20
""")
for row in cursor.fetchall():
    print(f'  ID={row[0]:5d} | 选项数={row[2]} | 答案="{row[1]}" | {row[3]}...')

# 分析：这些单字母答案的多选题，是否实际应该是单选题？
print('\n【判断：这些题是真正的多选题还是误分类的单选题？】')
cursor.execute("""
    SELECT 
        CASE 
            WHEN qb.options LIKE '%"key":"A"%' AND qb.options LIKE '%"key":"B"%' 
                 AND qb.options LIKE '%"key":"C"%' AND qb.options LIKE '%"key":"D"%' THEN '4选项'
            WHEN qb.options LIKE '%"key":"A"%' AND qb.options LIKE '%"key":"B"%' 
                 AND qb.options LIKE '%"key":"C"%' THEN '3选项'
            WHEN qb.options LIKE '%"key":"A"%' AND qb.options LIKE '%"key":"B"%' THEN '2选项'
            ELSE '1选项/无选项'
        END as option_count,
        COUNT(*) as cnt
    FROM question_bank qb
    WHERE qb.type_id = 3 AND LENGTH(qb.answer) = 1
    GROUP BY option_count
""")
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}道')

# 检查原始修复脚本的判断逻辑
print('\n【结论分析】')
print('  这152道题的共同特征：')
print('  - 当前type_id=3(多选题)')
print('  - 答案只有1个字母')
print('  - 需要检查选项数量来判断是否为真正的多选题')

conn.close()
