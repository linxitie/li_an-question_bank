# 生成知识图谱结构边（模块7 · P6）
# 从 knowledge_point 的父子关系生成 kg_edge.contains 结构边，幂等
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "question_bank.db"

c = sqlite3.connect(str(DB))
cur = c.cursor()
rows = cur.execute(
    "SELECT point_id, parent_id FROM knowledge_point WHERE parent_id IS NOT NULL AND parent_id > 0"
).fetchall()
print(f"[SRC] 有父节点的知识点 {len(rows)} 个")

inserted = 0
for child, parent in rows:
    exists = cur.execute(
        "SELECT 1 FROM kg_edge WHERE src_type='knowledge_point' AND src_id=? AND dst_type='knowledge_point' AND dst_id=? AND relation='contains'",
        (parent, child),
    ).fetchone()
    if exists:
        continue
    cur.execute(
        "INSERT INTO kg_edge (src_type, src_id, dst_type, dst_id, relation, weight, confidence, origin, created_at) "
        "VALUES ('knowledge_point', ?, 'knowledge_point', ?, 'contains', 1.0, 1.0, 'builtin', datetime('now'))",
        (parent, child),
    )
    inserted += 1
c.commit()
total = cur.execute("SELECT COUNT(*) FROM kg_edge").fetchone()[0]
print(f"[DONE] 新增结构边 {inserted} 条，kg_edge 合计 {total}")
c.close()
