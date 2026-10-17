#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史做题记录清理脚本 — 保留指定日期之后的记录（运维工具）

用法:
    python scripts/cleanup_old_records.py --dry-run
    python scripts/cleanup_old_records.py --apply [--keep-since 2026-08-01]

说明:
    - 目标库: backend/.env 的 SQLITE_PATH（默认 ./data/question_bank.db）
    - 删除顺序(先子后父):
        score_analysis -> year_paper -> smart_exam_record -> exam_answer_detail
        -> exam_record -> practice_record
    - 不动错题集 wrong_question_personal 等学习资产表
    - --apply 执行前自动备份数据库文件到 backend/data/backups/pre_cleanup_<时间戳>/
    - 幂等：可重复执行
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings  # noqa: E402


def resolve_db_path():
    p = settings.SQLITE_PATH or "./data/question_bank.db"
    if not os.path.isabs(p):
        p = os.path.join(BACKEND_DIR, p)
    return os.path.normpath(p)


def main():
    ap = argparse.ArgumentParser(description="Cleanup old practice/exam records")
    ap.add_argument("--dry-run", action="store_true", help="Preview counts only (no writes)")
    ap.add_argument("--apply", action="store_true", help="Execute deletion (auto-backup first)")
    ap.add_argument("--keep-since", default="2026-08-01",
                    help="Keep records on/after this date, YYYY-MM-DD (default: 2026-08-01)")
    args = ap.parse_args()

    if args.dry_run == args.apply:
        print("[x] Please specify exactly one of --dry-run / --apply")
        sys.exit(2)

    db_path = resolve_db_path()
    print("[i] DB path :", db_path)
    print("[i] exists  :", os.path.exists(db_path))
    if not os.path.exists(db_path):
        sys.exit(1)

    cutoff_date = args.keep_since
    cutoff_dt = cutoff_date + " 00:00:00"
    print("[i] keep-since:", cutoff_date)

    conn = sqlite3.connect(db_path, timeout=30)
    cur = conn.cursor()

    # ---- 统计口径定义（dry-run 与 apply 使用完全相同的谓词）----
    OLD_IDS = "(SELECT record_id FROM exam_record WHERE start_time < :dt)"

    statements = [
        # (label, delete_sql, count_sql)
        ("score_analysis",
         "DELETE FROM score_analysis WHERE record_id IN " + OLD_IDS,
         "SELECT COUNT(*) FROM score_analysis WHERE record_id IN " + OLD_IDS),
        ("year_paper",
         "DELETE FROM year_paper WHERE record_id IN " + OLD_IDS,
         "SELECT COUNT(*) FROM year_paper WHERE record_id IN " + OLD_IDS),
        ("smart_exam_record.detach-link",
         "UPDATE smart_exam_record SET exam_record_id = NULL "
         "WHERE exam_record_id IN " + OLD_IDS,
         "SELECT COUNT(*) FROM smart_exam_record WHERE exam_record_id IN " + OLD_IDS),
        ("smart_exam_record",
         "DELETE FROM smart_exam_record "
         "WHERE COALESCE(start_time, create_time) < :dtfull",
         "SELECT COUNT(*) FROM smart_exam_record "
         "WHERE COALESCE(start_time, create_time) < :dtfull"),
        ("exam_answer_detail",
         "DELETE FROM exam_answer_detail WHERE record_id IN " + OLD_IDS,
         "SELECT COUNT(*) FROM exam_answer_detail WHERE record_id IN " + OLD_IDS),
        ("exam_record",
         "DELETE FROM exam_record WHERE start_time < :dtfull",
         "SELECT COUNT(*) FROM exam_record WHERE start_time < :dtfull"),
        ("practice_record",
         "DELETE FROM practice_record "
         "WHERE COALESCE(practice_date, DATE(practice_time)) < :donly",
         "SELECT COUNT(*) FROM practice_record "
         "WHERE COALESCE(practice_date, DATE(practice_time)) < :donly"),
    ]

    params_map = {
        "score_analysis": {"dt": cutoff_dt},
        "year_paper": {"dt": cutoff_dt},
        "smart_exam_record.detach-link": {"dt": cutoff_dt},
        "smart_exam_record": {"dtfull": cutoff_dt},
        "exam_answer_detail": {"dt": cutoff_dt},
        "exam_record": {"dtfull": cutoff_dt},
        "practice_record": {"donly": cutoff_date},
    }

    def preview_counts():
        rows = []
        for label, _sql, cnt_sql in statements:
            cur.execute(cnt_sql, params_map[label])
            rows.append((label, cur.fetchone()[0]))
        return rows

    counts = preview_counts()
    total = sum(c for _, c in counts)
    print("[i] --- will delete (rows) ---")
    for label, c in counts:
        print("      %-28s %d" % (label, c))
    print("[i] TOTAL:", total)

    if args.dry_run:
        conn.close()
        print("[ok] dry-run finished (no writes)")
        return

    # ---- apply: 先备份 ----
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = os.path.join(BACKEND_DIR, "data", "backups", "pre_cleanup_" + ts)
    os.makedirs(bdir, exist_ok=True)
    try:
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except Exception as e:
        print("[w] wal_checkpoint skipped:", e)
    for suffix in ["", "-wal", "-shm"]:
        src = db_path + suffix
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(bdir, os.path.basename(src) or ("db" + suffix)))
    print("[i] backup ->", bdir)

    # ---- 事务执行删除 ----
    try:
        affected = {}
        for label, sql, _ in statements:
            cur.execute(sql, params_map[label])
            affected[label] = cur.rowcount
        conn.commit()
        print("[ok] APPLY COMMITTED")
        for label, sql, _ in statements:
            print("      %-28s deleted=%s" % (label, affected.get(label)))
    except Exception as e:
        conn.rollback()
        print("[x] FAILED, rolled back:", e)
        sys.exit(1)

    # ---- 剩余量复核 ----
    remain = []
    cur.execute("SELECT COUNT(*) FROM exam_record")
    remain.append(("exam_record", cur.fetchone()[0]))
    cur.execute("SELECT COUNT(*) FROM practice_record")
    remain.append(("practice_record", cur.fetchone()[0]))
    cur.execute(
        "SELECT COUNT(*) FROM practice_record "
        "WHERE COALESCE(practice_date, DATE(practice_time)) >= ?",
        (cutoff_date,),
    )
    remain.append(("practice_record kept(>=cutoff)", cur.fetchone()[0]))
    cur.execute("SELECT MIN(practice_date) FROM practice_record")
    remain.append(("earliest practice_date", cur.fetchone()[0]))
    cur.execute("SELECT MIN(start_time) FROM exam_record")
    remain.append(("earliest exam start_time", cur.fetchone()[0]))
    print("[i] --- remaining after cleanup ---")
    for k, v in remain:
        print("      %-32s %s" % (k, v))

    conn.close()
    print("[done]")


if __name__ == "__main__":
    main()
