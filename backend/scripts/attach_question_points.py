# 给已导入题目自动挂知识点（模块7 图谱挂题的前置）
#
# 策略：保守匹配 —— 只有题干里**完整出现**某个知识点名（长度 >= 4）才挂，
# 命中多个时取最长的那个。宁可少挂，不要挂错（挂错会导致薄弱点定位失真）。
#
# 用法：
#   python backend/scripts/attach_question_points.py            # 预演
#   python backend/scripts/attach_question_points.py --commit   # 写库（先备份）
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "question_bank.db"
MIN_LEN = 4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    points = [
        (pid, name)
        for pid, name in cur.execute("SELECT point_id, point_name FROM knowledge_point WHERE status=1")
        if name and len(name) >= MIN_LEN
    ]
    points.sort(key=lambda x: -len(x[1]))
    print(f"[INFO] 可用知识点 {len(points)} 个（长度 >= {MIN_LEN}）")

    sql = "SELECT question_id, question_content FROM question_bank WHERE point_id IS NULL"
    if args.limit:
        sql += f" LIMIT {args.limit}"
    rows = cur.execute(sql).fetchall()
    print(f"[INFO] 待挂题 {len(rows)} 道")

    plan = []
    for qid, content in rows:
        text = content or ""
        hit = None
        for pid, name in points:
            if name in text:
                hit = (pid, name)
                break
        if hit:
            plan.append((qid, hit[0], hit[1]))

    print(f"[PLAN] 可挂 {len(plan)} 道（覆盖率 {len(plan)/max(len(rows),1)*100:.1f}%）")
    for qid, pid, name in plan[:5]:
        print(f"   · 题{qid} → 考点「{name}」")

    if not args.commit:
        print("[DRY-RUN] 未写库。确认后加 --commit")
        conn.close()
        return 0

    backup = DB.with_suffix(f".db.bak_attach_{datetime.now():%Y%m%d_%H%M%S}")
    dst = sqlite3.connect(str(backup))
    with dst:
        conn.backup(dst)
    dst.close()
    print(f"[BACKUP] {backup}")

    cur.executemany("UPDATE question_bank SET point_id=? WHERE question_id=?", [(pid, qid) for qid, pid, _ in plan])
    conn.commit()
    left = cur.execute("SELECT COUNT(*) FROM question_bank WHERE point_id IS NULL").fetchone()[0]
    print(f"[DONE] 挂点 {len(plan)} 道，仍无考点 {left} 道")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
