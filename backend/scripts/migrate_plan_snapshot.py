# 迁移：创建 study_plan_snapshot 表（模块4 · 7-4 方案版本快照）
# 用法: python backend/scripts/migrate_plan_snapshot.py
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "question_bank.db"

DDL = """
CREATE TABLE IF NOT EXISTS study_plan_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL,
    plan_id INTEGER,
    version INTEGER DEFAULT 1,
    payload TEXT,
    task_count INTEGER DEFAULT 0,
    created_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES sys_user (user_id)
)
"""


def main() -> int:
    if not DB.exists():
        print(f"[SKIP] 数据库不存在: {DB}")
        return 0
    backup = DB.with_suffix(".db.bak_snapshot_20261116")
    src = sqlite3.connect(str(DB))
    dst = sqlite3.connect(str(backup))
    with dst:
        src.backup(dst)
    dst.close()
    print(f"[BACKUP] {backup}")

    cur = src.cursor()
    cur.executescript(DDL)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_user_plan ON study_plan_snapshot (user_id, plan_id, version)")
    src.commit()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(study_plan_snapshot)")]
    print(f"[OK] study_plan_snapshot 列={cols}")
    src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
