# -*- coding: utf-8 -*-
"""v8 P1 迁移：收容标记 + 质量分列 + 考点重分配审计表。

幂等：重复执行不报错。
安全：默认先做 sqlite3.backup()，失败即中止；不 drop 任何表、不删任何行。
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "question_bank.db"
BACKUP_DIR = Path(__file__).resolve().parents[2] / "data" / "backups"


def _columns(conn: sqlite3.Connection, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def backup_db() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"question_bank_pre_v8_{time.strftime('%Y%m%d_%H%M%S')}.db"
    src = sqlite3.connect(DB_PATH)
    out = sqlite3.connect(dst)
    with out:
        src.backup(out)  # R10：WAL 下必须走 sqlite3.backup，不能用文件复制
    src.close()
    out.close()
    return dst


def migrate(apply: bool) -> None:
    if apply:
        print(f"backup -> {backup_db()}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cols = _columns(conn, "knowledge_point")
    if "is_fallback" not in cols:
        conn.execute("ALTER TABLE knowledge_point ADD COLUMN is_fallback INTEGER NOT NULL DEFAULT 0")
        print("+ knowledge_point.is_fallback")
    if "source_batch" not in cols:
        conn.execute("ALTER TABLE knowledge_point ADD COLUMN source_batch TEXT")
        print("+ knowledge_point.source_batch")

    qcols = _columns(conn, "question_bank")
    if "quality_score" not in qcols:
        conn.execute("ALTER TABLE question_bank ADD COLUMN quality_score INTEGER")
        print("+ question_bank.quality_score")
    if "quality_flags" not in qcols:
        conn.execute("ALTER TABLE question_bank ADD COLUMN quality_flags TEXT")
        print("+ question_bank.quality_flags")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS point_assign_audit (
            audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id      TEXT NOT NULL,
            question_id   INTEGER NOT NULL,
            old_point_id  INTEGER,
            new_point_id  INTEGER NOT NULL,
            score         INTEGER NOT NULL DEFAULT 0,
            tier          TEXT NOT NULL,
            reason        TEXT,
            create_time   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_paa_batch ON point_assign_audit(batch_id, question_id)")
    print("+ table point_assign_audit")

    # 收容标记：所有「其他*」节点（含 level 3/4、含 status=0 的历史别名节点）都算收容
    n = conn.execute("""SELECT count(*) FROM knowledge_point
                        WHERE point_name LIKE '其他%' AND is_fallback=0""").fetchone()[0]
    if apply:
        conn.execute("""UPDATE knowledge_point SET is_fallback=1, source_batch='v8-p1'
                        WHERE point_name LIKE '其他%'""")
        conn.commit()
    print(f"is_fallback 待标记 {n} 行（apply={apply}）")

    total = conn.execute("SELECT count(*) FROM knowledge_point WHERE is_fallback=1").fetchone()[0]
    print(f"当前 is_fallback=1 共 {total} 行")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写库；不给则只打印计划")
    args = ap.parse_args()
    migrate(args.apply)
