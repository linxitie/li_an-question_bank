# -*- coding: utf-8 -*-
"""管理员端用户与权限合并：增量迁移（幂等）。

新增：
  - sys_user: is_deleted / deleted_at / deleted_by / delete_reason
  - user_permission_override
  - permission_change_batch

用法：
  python scripts/migrate/migrate_admin_user_permissions.py --dry-run
  python scripts/migrate/migrate_admin_user_permissions.py --apply

设计：
  1. 默认 dry-run，只打印将执行的 DDL；
  2. --apply 前先用 sqlite3.backup() 生成完整备份（WAL 模式下不能只拷主库）；
  3. 全部 DDL 幂等，可重复执行；
  4. 只 ADD COLUMN / CREATE TABLE，不重建表、不删数据。
"""
import argparse
import datetime
import os
import sqlite3
import sys


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(BACKEND_DIR, "data", "question_bank.db")
BACKUP_DIR = os.path.join(BACKEND_DIR, "data", "backups")

NEW_COLUMNS = [
    ("is_deleted", "INTEGER DEFAULT 0", "0正常/1回收站/2已注销"),
    ("deleted_at", "DATETIME", "删除时间"),
    ("deleted_by", "BIGINT", "删除操作人"),
    ("delete_reason", "VARCHAR(255)", "删除原因"),
]

CREATE_SQL = [
    """
    CREATE TABLE IF NOT EXISTS user_permission_override (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT NOT NULL,
        permission_code VARCHAR(64) NOT NULL,
        effect VARCHAR(8) NOT NULL,
        scope_type VARCHAR(16) NOT NULL DEFAULT 'global',
        scope_id BIGINT NOT NULL DEFAULT 0,
        scope_key VARCHAR(64) NOT NULL DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'active',
        reason VARCHAR(255) NOT NULL DEFAULT '',
        granted_by BIGINT,
        granted_at DATETIME,
        expires_at DATETIME,
        revoked_by BIGINT,
        revoked_at DATETIME,
        batch_id VARCHAR(36),
        updated_at DATETIME,
        FOREIGN KEY(user_id) REFERENCES sys_user(user_id),
        FOREIGN KEY(granted_by) REFERENCES sys_user(user_id),
        FOREIGN KEY(revoked_by) REFERENCES sys_user(user_id),
        CONSTRAINT uk_user_permission_override
            UNIQUE (user_id, permission_code, scope_type, scope_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_permission_override_user_status ON user_permission_override(user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_permission_override_code_status ON user_permission_override(permission_code, status)",
    "CREATE INDEX IF NOT EXISTS idx_permission_override_batch ON user_permission_override(batch_id)",
    """
    CREATE TABLE IF NOT EXISTS permission_change_batch (
        batch_id VARCHAR(36) PRIMARY KEY,
        operator_id BIGINT NOT NULL,
        action VARCHAR(32) NOT NULL,
        target_count INTEGER DEFAULT 0,
        reason VARCHAR(255) NOT NULL DEFAULT '',
        before_json TEXT,
        after_json TEXT,
        undo_deadline DATETIME,
        undone_at DATETIME,
        undone_by BIGINT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(operator_id) REFERENCES sys_user(user_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_permission_batch_operator ON permission_change_batch(operator_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_permission_batch_created ON permission_change_batch(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_is_deleted ON sys_user(is_deleted)",
]


def table_exists(conn, table):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def existing_columns(conn, table):
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table).fetchall()}


def backup(db_path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = os.path.join(BACKUP_DIR, "question_bank_pre_admin_merge_%s.db" % stamp)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def main():
    parser = argparse.ArgumentParser(description="管理员端用户与权限合并迁移（幂等）")
    parser.add_argument("--apply", action="store_true", help="实际执行；缺省 dry-run")
    parser.add_argument("--dry-run", dest="apply", action="store_false", help="显式预览（默认行为）")
    parser.add_argument("--db", default=DB_PATH, help="数据库路径")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print("[错误] 数据库不存在: %s" % db_path)
        return 1

    mode = "执行" if args.apply else "预览(dry-run)"
    print("=" * 70)
    print("管理员端用户与权限合并迁移 · %s" % mode)
    print("数据库: %s" % db_path)
    print("=" * 70)

    if args.apply:
        target = backup(db_path)
        print("[备份] %s" % target)

    conn = sqlite3.connect(db_path)
    try:
        if not table_exists(conn, "sys_user"):
            print("[错误] sys_user 不存在，拒绝迁移")
            return 1

        cols = existing_columns(conn, "sys_user")
        pending_cols = [(c, d, n) for c, d, n in NEW_COLUMNS if c not in cols]
        print("sys_user 现有列数: %d；待新增: %s" % (len(cols), [c for c, _, _ in pending_cols] or "无"))

        statements = []
        for col, ddl, note in pending_cols:
            statements.append(("ALTER TABLE sys_user ADD COLUMN %s %s" % (col, ddl), note))
        for sql in CREATE_SQL:
            statements.append((sql, "建表/索引（幂等）"))

        for sql, note in statements:
            print("-" * 70)
            print("[%s] %s" % ("执行" if args.apply else "预览", sql.strip().splitlines()[0][:100]))
            print("        用途: %s" % note)
            if args.apply:
                conn.execute(sql)

        if args.apply:
            conn.commit()
            after_cols = existing_columns(conn, "sys_user")
            missing = [c for c, _, _ in NEW_COLUMNS if c not in after_cols]
            if missing:
                print("[失败] 迁移后仍缺列: %s" % missing)
                return 1
            tables = [t for t in ("user_permission_override", "permission_change_batch") if table_exists(conn, t)]
            print("-" * 70)
            print("[完成] 新增列 %d，表 %s" % (len(pending_cols), tables))
            print("[提示] 回滚：停服后恢复上方备份，并删除 -wal/-shm；不要只拷主库。")
        else:
            print("-" * 70)
            print("[预览完成] 未做任何改动。确认无误后加 --apply。")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
