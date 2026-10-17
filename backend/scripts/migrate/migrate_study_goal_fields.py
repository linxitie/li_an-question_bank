# -*- coding: utf-8 -*-
"""
study_goal 表结构增量迁移（幂等）

新增两列以支撑首页/金币购统一的 4 字段目标：
  - subject_mode     今日学习科目：0=混科，>0=单科 subject_id
  - expected_minutes 单日预期学习时长（分钟）

用法：
  python scripts/migrate_study_goal_fields.py --dry-run   # 预览
  python scripts/migrate_study_goal_fields.py --apply     # 执行（幂等，可重复）

设计要点：
  1. 幂等：先查 sqlite_master/PRAGMA table_info，已存在则跳过
  2. 零数据丢失：仅 ADD COLUMN，不改动任何既有列与数据
  3. 默认值兼容：DEFAULT 0，旧记录读取时自动为「混科 / 未设时长」
  4. 使用 SQLite 原生 ALTER TABLE ADD COLUMN，不重建表、不建临时表
"""
import argparse
import os
import sqlite3
import sys

# 与 app/core/config.py 的 SQLite 路径保持一致：相对 backend/ 目录
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "question_bank.db")

# (列名, DDL 类型与默认值, 用途说明)
NEW_COLUMNS = [
    ("subject_mode", "INTEGER DEFAULT 0", "今日学习科目：0=混科，>0=单科 subject_id"),
    ("expected_minutes", "INTEGER DEFAULT 0", "单日预期学习时长（分钟），0=未设置"),
]


def existing_columns(conn: sqlite3.Connection, table: str) -> set:
    cur = conn.execute("PRAGMA table_info(%s)" % table)
    return {row[1] for row in cur.fetchall()}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="study_goal 表增量迁移（幂等）")
    parser.add_argument("--apply", action="store_true", help="实际执行；缺省为 dry-run 预览")
    parser.add_argument("--db", default=DB_PATH, help="数据库路径（默认 backend/data/question_bank.db）")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print("[错误] 数据库不存在: %s" % db_path)
        return 1

    apply = args.apply
    mode = "执行" if apply else "预览(dry-run)"
    print("=" * 68)
    print("study_goal 增量迁移 · %s" % mode)
    print("数据库: %s" % db_path)
    print("=" * 68)

    conn = sqlite3.connect(db_path)
    try:
        if not table_exists(conn, "study_goal"):
            print("[错误] 表 study_goal 不存在，请先确认数据库版本")
            return 1

        before = existing_columns(conn, "study_goal")
        row_count = conn.execute("SELECT COUNT(*) FROM study_goal").fetchone()[0]
        print("当前 study_goal 记录数: %d" % row_count)
        print("迁移前列: %s" % ", ".join(sorted(before)))
        print("-" * 68)

        added, skipped = [], []
        for col, ddl, comment in NEW_COLUMNS:
            if col in before:
                skipped.append(col)
                print("  [跳过] %-18s 已存在 —— %s" % (col, comment))
                continue
            added.append(col)
            sql = "ALTER TABLE study_goal ADD COLUMN %s %s" % (col, ddl)
            print("  [新增] %s" % sql)
            print("         用途: %s" % comment)
            if apply:
                conn.execute(sql)
                print("         已执行")
            else:
                print("         (dry-run 未执行)")

        if apply and added:
            conn.commit()
            after = existing_columns(conn, "study_goal")
            print("-" * 68)
            print("迁移后列: %s" % ", ".join(sorted(after)))
            # 校验：新列应全部存在，且旧记录可读、默认值为 0
            miss = [c for c, _, _ in NEW_COLUMNS if c not in after]
            if miss:
                print("[失败] 迁移后仍缺列: %s" % miss)
                return 1
            sample = conn.execute(
                "SELECT goal_id, subject_mode, expected_minutes FROM study_goal ORDER BY goal_id LIMIT 3"
            ).fetchall()
            print("校验通过，抽样(gid, subject_mode, expected_minutes): %s" % sample)
            print("新增列数: %d" % len(added))
            print("=" * 68)
            print("[完成] 迁移成功")
        else:
            print("-" * 68)
            print("待新增列: %s" % (added or "无"))
            if not apply:
                print("=" * 68)
                print("[预览完成] 未做任何改动。确认无误后加 --apply 执行。")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())