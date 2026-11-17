# -*- coding: utf-8 -*-
"""v8b 迁移：给 point_assign_audit 补复核字段（P3 复核队列需要）。

新增列：review_status / reviewer_id / review_time / review_note。
幂等：已存在的列会跳过。执行前自动用 sqlite3.backup 备份（红线 R10）。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "data" / "question_bank.db"
BACKUP_DIR = BACKEND_DIR / "data" / "backups"

COLS = [
    ("review_status", "TEXT DEFAULT 'pending'"),
    ("reviewer_id", "INTEGER"),
    ("review_time", "TEXT"),
    ("review_note", "TEXT"),
]


def backup(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"question_bank_pre_v8b_{datetime.now():%Y%m%d_%H%M%S}.db"
    src = sqlite3.connect(str(db_path))
    out = sqlite3.connect(str(dst))
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    return dst


def main() -> int:
    dst = backup(DB_PATH)
    print(f"备份：{dst}")
    conn = sqlite3.connect(str(DB_PATH))
    try:
        existing = {r[1] for r in conn.execute("PRAGMA table_info(point_assign_audit)")}
        for name, ddl in COLS:
            if name in existing:
                print(f"跳过（已存在）：{name}")
                continue
            conn.execute(f"ALTER TABLE point_assign_audit ADD COLUMN {name} {ddl}")
            print(f"新增列：{name}")
        conn.execute(
            "UPDATE point_assign_audit SET review_status = 'pending' WHERE review_status IS NULL"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_paa_status ON point_assign_audit(review_status)")
        conn.commit()
    finally:
        conn.close()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())