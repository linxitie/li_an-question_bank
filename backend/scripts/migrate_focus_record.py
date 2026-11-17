# 迁移：创建 focus_record 表（模块4 · 专注力热力图数据源）
# 用法: python backend/scripts/migrate_focus_record.py
# 规范（R10）: 备份走 sqlite3.backup()，不用 shutil.copy2
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "question_bank.db"

DDL = """
CREATE TABLE IF NOT EXISTS focus_record (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME NOT NULL,
    minutes INTEGER DEFAULT 0,
    mode VARCHAR(10) DEFAULT 'focus',
    source VARCHAR(20) DEFAULT 'widget',
    created_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES sys_user (user_id)
)
"""


def main() -> int:
    if not DB.exists():
        print(f"[SKIP] 数据库不存在: {DB}")
        return 0

    backup = DB.with_suffix(".db.bak_focus_20261116")
    src = sqlite3.connect(str(DB))
    dst = sqlite3.connect(str(backup))
    with dst:
        src.backup(dst)
    dst.close()
    print(f"[BACKUP] {backup}")

    cur = src.cursor()
    cur.executescript(DDL)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_focus_user_time ON focus_record (user_id, started_at)")
    src.commit()

    cols = [r[1] for r in cur.execute("PRAGMA table_info(focus_record)")]
    n = cur.execute("SELECT COUNT(*) FROM focus_record").fetchone()[0]
    print(f"[OK] focus_record 列={cols} 现有记录={n}")
    src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
