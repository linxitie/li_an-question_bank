# 迁移：给 wrong_question_personal 补遗忘曲线排程字段（模块4 P4）
# 用法: python backend/scripts/migrate_review_schedule.py
# 规范（R10）: 备份走 sqlite3.backup()，不用 shutil.copy2
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "question_bank.db"
COLS = [
    ("next_review_at", "DATETIME"),
    ("review_ease", "FLOAT DEFAULT 2.5"),
    ("review_interval_days", "INTEGER DEFAULT 1"),
    ("review_reps", "INTEGER DEFAULT 0"),
]


def main() -> int:
    if not DB.exists():
        print(f"[SKIP] 数据库不存在: {DB}")
        return 0

    backup = DB.with_suffix(".db.bak_review_20261114")
    src = sqlite3.connect(str(DB))
    dst = sqlite3.connect(str(backup))
    with dst:
        src.backup(dst)
    dst.close()
    print(f"[BACKUP] {backup}")

    cur = src.cursor()
    cur.execute("PRAGMA table_info(wrong_question_personal)")
    existing = {row[1] for row in cur.fetchall()}
    if not existing:
        print("[SKIP] 表 wrong_question_personal 不存在")
        src.close()
        return 0

    added = []
    for name, ddl in COLS:
        if name in existing:
            print(f"[OK] 已存在 {name}")
            continue
        cur.execute(f"ALTER TABLE wrong_question_personal ADD COLUMN {name} {ddl}")
        added.append(name)
        print(f"[ADD] {name} {ddl}")

    src.commit()
    cur.execute("SELECT COUNT(*) FROM wrong_question_personal")
    print(f"[DONE] 新增 {len(added)} 列，现有错题 {cur.fetchone()[0]} 条")
    src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
