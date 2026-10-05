# -*- coding: utf-8 -*-
"""
为 practice_record 增加复合索引 (user_id, practice_date, subject_id)。

背景
----
目标进度（goal_progress）与全时段学习统计都按「用户 + 日期区间 + 科目」
聚合。原有四个单列索引无法同时命中这三个条件，查询会退化为「按 user_id
扫全表 + 逐行过滤日期与科目」。刷题记录是增长最快的表，这个代价会随数据量
线性放大。

安全约定
--------
1. **默认 dry-run**：不加 --apply 只做检查并打印计划，不写库。
2. 写库前强制用 sqlite3 的 `backup()` API 做快照 —— 本项目是 SQLite WAL 模式，
   `shutil.copy2` 只拷主库会丢失已提交但未 checkpoint 的事务（README 明确禁止）。
3. 索引名先查后建，已存在则跳过，脚本可重复执行。
4. 不使用 `CREATE INDEX CONCURRENTLY`（那是 PostgreSQL 语法，SQLite 不支持）。

用法
----
    python scripts/migrate_add_practice_composite_index.py            # dry-run
    python scripts/migrate_add_practice_composite_index.py --apply    # 实际执行
"""
import argparse
import datetime
import os
import sqlite3
import sys

DB_REL = os.path.join("data", "question_bank.db")
INDEX_NAME = "idx_user_date_subject_practicerecord"
INDEX_COLS = ["user_id", "practice_date", "subject_id"]


def _backup(db_path: str) -> str:
    """用 sqlite3 backup API 做一致性快照（WAL 模式下唯一安全的方式）。"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst_path = f"{db_path}.bak_index_{ts}"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dst_path)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dst_path


def main() -> int:
    parser = argparse.ArgumentParser(description="practice_record 复合索引迁移")
    parser.add_argument("--apply", action="store_true", help="真正写库（默认 dry-run）")
    parser.add_argument("--db", default=DB_REL, help="数据库路径")
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print(f"[迁移] 数据库不存在：{db_path}")
        return 1

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()

        exists = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (INDEX_NAME,),
        ).fetchone()
        if exists:
            print(f"[迁移] 索引 {INDEX_NAME} 已存在，跳过。")
            return 0

        cols = [r[1] for r in cur.execute("PRAGMA table_info(practice_record)")]
        missing = [c for c in INDEX_COLS if c not in cols]
        if missing:
            print(f"[迁移] practice_record 缺少列 {missing}，无法建索引。请先确认表结构。")
            return 1

        row_count = cur.execute("SELECT COUNT(*) FROM practice_record").fetchone()[0]
        print(f"[迁移] 目标表 practice_record 现有 {row_count} 行")
        print(f"[迁移] 计划创建索引 {INDEX_NAME} ({', '.join(INDEX_COLS)})")
        # SQLite 建索引是全表排序，耗时随行数增长，故明确告知规模
        print(f"[迁移] 预估耗时：约 {max(1, row_count // 100000)}~{max(2, row_count // 50000)} 秒")

        if not args.apply:
            print("[迁移] DRY-RUN 结束，未写库。确认无误后加 --apply 执行。")
            return 0

        backup_path = _backup(db_path)
        print(f"[迁移] 已备份数据库 -> {backup_path}")

        # 单条语句建索引；SQLite 不支持 CONCURRENTLY，构建期间会持有写锁
        cur.execute(
            f'CREATE INDEX "{INDEX_NAME}" ON practice_record '
            f'({", ".join(INDEX_COLS)})'
        )
        con.commit()

        after = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (INDEX_NAME,),
        ).fetchone()
        if after:
            print(f"[迁移] 索引 {INDEX_NAME} 创建成功。")
            print(f"[迁移] 如需回滚：先 DROP INDEX {INDEX_NAME}; 再还原 {backup_path}（连同 -wal/-shm）。")
            return 0
        print("[迁移] 创建后校验失败，请检查。")
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
