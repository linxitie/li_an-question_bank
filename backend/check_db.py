import sqlite3

# 连接数据库
conn = sqlite3.connect('data/question_bank.db')
cursor = conn.cursor()

# 执行查询
sql = "select source, count(*) from news_article where status=0 group by source order by source"
cursor.execute(sql)

# 打印结果
results = cursor.fetchall()
print("=== 待审新闻统计 ===")
for row in results:
    print(f"来源: {row[0]}, 数量: {row[1]}")

conn.close()