import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'question_bank.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 先查看 question_type 表结构
print('=== question_type 表结构 ===')
cursor.execute("PRAGMA table_info(question_type)")
cols = cursor.fetchall()
col_names = [c[1] for c in cols]
print(f'  列名: {col_names}')

# 2. 查看 question_type 表内容
print('\n=== question_type 表内容 ===')
cursor.execute("SELECT * FROM question_type")
for row in cursor.fetchall():
    print(f'  {row}')

# 2. 统计各 type_id 的题目数量
print('\n=== 按 type_id 统计题目数量 ===')
cursor.execute("""
    SELECT qb.type_id, COUNT(*) as count
    FROM question_bank qb
    GROUP BY qb.type_id
    ORDER BY qb.type_id
""")
for row in cursor.fetchall():
    # 获取对应的类型名称（列名是 type_name 不是 name）
    cursor.execute("SELECT type_name FROM question_type WHERE type_id = ?", (row[0],))
    type_name = cursor.fetchone()
    name_str = type_name[0] if type_name else "未知"
    print(f'  type_id={row[0]} ({name_str}): {row[1]}道')

# 3. 查找可能的错误分类（单选题答案含多个字母）
print('\n=== 检查可能错误的单选题（答案含多个字母） ===')
cursor.execute("""
    SELECT qb.question_id, qb.question_content, qb.answer, qt.type_name, qt.type_id
    FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id = qt.type_id
    WHERE qt.type_name LIKE '%单选%' AND LENGTH(qb.answer) > 2
    LIMIT 10
""")
rows = cursor.fetchall()
print(f'  发现 {len(rows)} 道可能错误的单选题（显示前10道）')
for row in rows:
    content = row[1][:40] if row[1] else ''
    print(f'  ID={row[0]}: {content}... 答案="{row[2]}" 类型={row[3]}(id={row[4]})')

# 4. 查找可能的错误分类（多选题答案只有一个字母）
print('\n=== 检查可能错误的多选题（答案只有一个字母） ===')
cursor.execute("""
    SELECT qb.question_id, qb.question_content, qb.answer, qt.type_name, qt.type_id
    FROM question_bank qb
    LEFT JOIN question_type qt ON qb.type_id = qt.type_id
    WHERE qt.type_name LIKE '%多选%' AND LENGTH(qb.answer) <= 2
    LIMIT 10
""")
rows = cursor.fetchall()
print(f'  发现 {len(rows)} 道可能错误的多选题（显示前10道）')
for row in rows:
    content = row[1][:40] if row[1] else ''
    print(f'  ID={row[0]}: {content}... 答案="{row[2]}" 类型={row[3]}(id={row[4]})')

# 5. 总计
print('\n=== 题目总数 ===')
cursor.execute("SELECT COUNT(*) FROM question_bank")
total = cursor.fetchone()[0]
print(f'  总计: {total}道')

conn.close()
