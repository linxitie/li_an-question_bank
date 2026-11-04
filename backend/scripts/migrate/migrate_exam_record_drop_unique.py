"""重建 exam_record，移除历史库遗留的 uk_paper_user 唯一约束。

背景：模型 models.py 的 ExamRecord 已在 B4 修复中移除 (paper_id, user_id)
唯一约束并改为普通索引，但既有 SQLite 库仍是旧表结构。结果是同一学生
第二次开始同一张试卷时 INSERT 触发 UNIQUE constraint failed，接口 500。

SQLite 不支持 DROP CONSTRAINT，这里按官方 12 步用新表重建：
  备份 -> 建新表 -> 拷数据 -> 删旧表 -> 改名 -> 重建索引 -> 外键检查

用法：
  python backend/scripts/migrate/migrate_exam_record_drop_unique.py            # dry-run
  python backend/scripts/migrate/migrate_exam_record_drop_unique.py --apply
  python backend/scripts/migrate/migrate_exam_record_drop_unique.py --db <path> --apply
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "question_bank.db"
BACKUP_DIR = Path(__file__).resolve().parents[2] / "data" / "backups"

CREATE_TABLE_SQL = """
CREATE TABLE exam_record_new (
    record_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    paper_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    exam_type VARCHAR(10) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    duration_used INTEGER,
    total_score DECIMAL(10, 2),
    is_completed INTEGER,
    is_scored INTEGER,
    submit_time DATETIME,
    is_late INTEGER,
    attempt_count INTEGER,
    create_time DATETIME,
    FOREIGN KEY(paper_id) REFERENCES exam_paper (paper_id),
    FOREIGN KEY(user_id) REFERENCES sys_user (user_id)
)
"""

INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_paper_id_examrecord ON exam_record (paper_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_id_examrecord ON exam_record (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_paper_user_examrecord ON exam_record (paper_id, user_id)",
    "CREATE INDEX IF NOT EXISTS idx_start_time ON exam_record (start_time)",
    "CREATE INDEX IF NOT EXISTS idx_is_completed_examrecord ON exam_record (is_completed)",
)


def has_unique_constraint(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='exam_record'"
    ).fetchone()
    if not row or not row[0]:
        return False
    return "UK_PAPER_USER" in row[0].upper()


def backup(conn: sqlite3.Connection, db: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_path = BACKUP_DIR / f"question_bank_pre_exam_record_unique_{stamp}.db"
    dst = sqlite3.connect(str(dst_path))
    try:
        conn.backup(dst)
    finally:
        dst.close()
    return dst_path


def migrate(conn: sqlite3.Connection) -> int:
    """执行重建，返回迁移的记录数。"""
    count = conn.execute("SELECT COUNT(*) FROM exam_record").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS exam_record_new")
        conn.executescript(CREATE_TABLE_SQL)
        columns = (
            "record_id, paper_id, user_id, exam_type, start_time, end_time, "
            "duration_used, total_score, is_completed, is_scored, submit_time, "
            "is_late, attempt_count, create_time"
        )
        conn.execute(
            f"INSERT INTO exam_record_new ({columns}) SELECT {columns} FROM exam_record"
        )
        conn.execute("DROP TABLE exam_record")
        conn.execute("ALTER TABLE exam_record_new RENAME TO exam_record")
        for sql in INDEX_SQL:
            conn.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="移除 exam_record 历史唯一约束")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    args = parser.parse_args()

    db = Path(args.db).resolve()
    if not db.exists():
        raise SystemExit(f"数据库不存在：{db}")

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        if not has_unique_constraint(conn):
            print("exam_record 已无 uk_paper_user；无需迁移")
            return 0
        print(f"检测到 uk_paper_user 唯一约束：{db}")
        if not args.apply:
            print("dry-run：未修改数据库（加 --apply 执行）")
            return 0
        # 先记录迁移前的既有外键问题：历史库存在 user_task_progress -> sys_user
        # 的孤儿行，与本次迁移无关，不能据此判定迁移失败
        fk_before = set(conn.execute("PRAGMA foreign_key_check").fetchall())
        backup_path = backup(conn, db)
        print(f"备份完成：{backup_path}")
        count = migrate(conn)
        fk_after = set(conn.execute("PRAGMA foreign_key_check").fetchall())
        new_errors = sorted(fk_after - fk_before)
        if new_errors:
            raise SystemExit(f"迁移引入了新的外键错误：{new_errors[:5]}")
        if fk_after:
            print(f"迁移完成，保留 {count} 条记录；既有外键问题 {len(fk_after)} 条未变化")
        else:
            print(f"迁移完成：重建 exam_record，保留 {count} 条记录，唯一约束已移除")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
