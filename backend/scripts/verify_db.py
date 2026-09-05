import sqlite3
import os

# 使用修复脚本使用的同一个数据库
db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'question_bank.db')
print(f"数据库路径: {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print(f"错误: 数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('\n=== 数据库中的表 ===')
for t in tables:
    print(f'  {t[0]}')

# 查看 question_type 表
print('\n=== question_type 表内容 ===')
try:
    cursor.execute("SELECT * FROM question_type")
    rows = cursor.fetchall()
    for row in rows:
        print(f'  {row}')
except Exception as e:
    print(f'  查询失败: {e}')

# 查看题目类型分布
print('\n=== 修复后题目类型分布 ===')
try:
    # 尝试不同的表名组合
    for qb_table in ['question_bank', 'questions']:
        for qt_table in ['question_type', 'types']:
            try:
                cursor.execute(f"""
                    SELECT qt.name as type_name, COUNT(*) as count
                    FROM {qb_table} qb
                    LEFT JOIN {qt_table} qt ON qb.type_id = qt.id
                    GROUP BY qt.name
                """)
                rows = cursor.fetchall()
                if rows:
                    print(f'  使用表: {qb_table} + {qt_table}')
                    for row in rows:
                        print(f'    {row[0]}: {row[1]}道')
                    break
            except:
                continue
except Exception as e:
    print(f'  查询失败: {e}')

# 直接查看 question_bank 表结构
print('\n=== question_bank 表结构 ===')
try:
    cursor.execute("PRAGMA table_info(question_bank)")
    cols = cursor.fetchall()
    for c in cols:
        print(f'  {c[1]} ({c[2]})')
except Exception as e:
    print(f'  查询失败: {e}')

conn.close()
