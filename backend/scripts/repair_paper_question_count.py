#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repair_paper_question_count.py — 修正 exam_paper.question_count 漂移（P1-3 数据修复）。

`question_count` 是冗余字段，唯一事实来源是 paper_question_relation 的行数。
旧导入路径按 +1 累加（且 linked 只加一次），导致「110 题的试卷显示 1 题」。

先用本脚本盘点/修复存量数据；代码侧已改为每次写关联后按行数重算，
新导入不会再漂移。

用法:
  python backend/scripts/repair_paper_question_count.py            # 只盘点，有漂移则退出码 1
  python backend/scripts/repair_paper_question_count.py --apply    # 先快照再修正
  python backend/scripts/repair_paper_question_count.py --db <path> [--apply]

约束（与 AGENTS.md R10 一致）:
  - 写库前 MUST 用 sqlite3.Connection.backup() 生成整库快照，禁止 shutil.copy2。
  - WAL 模式下快照同理走 backup API，保证 -wal 内容一并落入快照。
"""

import argparse
import datetime
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "backend" / "data" / "question_bank.db"

MISMATCH_SQL = """
SELECT p.paper_id,
       p.paper_name,
       COALESCE(p.question_count, 0) AS recorded,
       (SELECT COUNT(*) FROM paper_question_relation r WHERE r.paper_id = p.paper_id) AS actual
FROM exam_paper p
WHERE COALESCE(p.question_count, 0)
      != (SELECT COUNT(*) FROM paper_question_relation r WHERE r.paper_id = p.paper_id)
ORDER BY p.paper_id
"""


def take_snapshot(con: sqlite3.Connection, db_path: Path) -> Path:
    """用 backup API 生成整库快照（R10：不得 shutil.copy2）。"""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot = db_path.with_name(f"{db_path.stem}.precount_repair_{stamp}{db_path.suffix}")
    dst = sqlite3.connect(str(snapshot))
    try:
        con.backup(dst)
    finally:
        dst.close()
    return snapshot


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="修正 exam_paper.question_count 漂移")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite 路径（默认 {DEFAULT_DB}）")
    parser.add_argument("--apply", action="store_true", help="实际写库（默认只盘点）")
    args = parser.parse_args(argv)

    db_path = args.db.resolve()
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 2

    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(MISMATCH_SQL).fetchall()
        if not rows:
            print(f"OK: {db_path} 无 question_count 漂移")
            return 0

        print(f"{db_path}\n漂移试卷 {len(rows)} 张：")
        print(f"  {'paper_id':>8}  {'recorded':>8}  {'actual':>6}  纸卷名")
        for paper_id, name, recorded, actual in rows:
            print(f"  {paper_id:>8}  {recorded:>8}  {actual:>6}  {name}")

        if not args.apply:
            print("\n仅盘点，未写库；确认后加 --apply。")
            return 1

        snapshot = take_snapshot(con, db_path)
        print(f"\n已生成快照: {snapshot}")
        with con:
            con.executemany(
                """UPDATE exam_paper
                   SET question_count = (
                       SELECT COUNT(*) FROM paper_question_relation r
                       WHERE r.paper_id = exam_paper.paper_id
                   )
                   WHERE paper_id = ?""",
                [(row[0],) for row in rows],
            )
        print(f"已修正 {len(rows)} 张试卷的 question_count")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
