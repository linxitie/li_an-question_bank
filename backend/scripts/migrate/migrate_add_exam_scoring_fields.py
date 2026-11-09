# -*- coding: utf-8 -*-
"""给 `exam_record` 加 3 个评分派生字段（口径 A，2026-11-09）。

背景：`is_scored` 统一为「分数已完全确定」后，同时补三个只读派生字段
`manual_pending_count` / `answered_count` / `question_total`，
供结果页、成绩单与学情使用。详见
`docs/plans/考试评分口径_is_scored统一_方案_v1.md` §4 P-A。

SQLite 支持 `ALTER TABLE ... ADD COLUMN`，因此不需要重建表；
但每条 ALTER 只能加一列，且必须带默认值（存量行补 0）。

本脚本刻意只用 ASCII 标记（[OK]/[ADD]/[i]）：Windows 控制台默认 GBK，
打印 emoji（如 U+2139、U+2705）会抛 UnicodeEncodeError 并被误判为失败
（与 `backend/scripts/gates/gate_all.py` 里 PYTHONIOENCODING 的坑同源）。

用法：
  python backend/scripts/migrate/migrate_add_exam_scoring_fields.py            # dry-run
  python backend/scripts/migrate/migrate_add_exam_scoring_fields.py --apply
  python backend/scripts/migrate/migrate_add_exam_scoring_fields.py --db <path> --apply

回滚：`sqlite3.backup()` 生成的备份文件可直接顶回（同时删除 -wal/-shm）。
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = BACKEND_DIR / "data" / "question_bank.db"
BACKUP_DIR = BACKEND_DIR / "data" / "backups"

# 列名 -> ALTER 语句（只允许加列，绝不改/删已有列）
NEW_COLUMNS = {
    "manual_pending_count": "ALTER TABLE exam_record ADD COLUMN manual_pending_count INTEGER DEFAULT 0",
    "answered_count": "ALTER TABLE exam_record ADD COLUMN answered_count INTEGER DEFAULT 0",
    "question_total": "ALTER TABLE exam_record ADD COLUMN question_total INTEGER DEFAULT 0",
}


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _backup(db_path: Path) -> Path:
    """用 sqlite3.backup() 做一致性备份（R10：WAL 下禁止 copy2）。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"before_exam_scoring_fields_{stamp}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(out))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return out


def _report(conn: sqlite3.Connection, label: str) -> None:
    cols = _columns(conn, "exam_record")
    print(f"  [{label}] exam_record 列({len(cols)}): {', '.join(cols)}")
    rows = list(conn.execute(
        "SELECT record_id, is_completed, is_scored FROM exam_record ORDER BY record_id"
    ))
    print(f"  [{label}] 记录 {len(rows)} 行" + (f"，示例 {rows[:3]}" if rows else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="exam_record 加评分派生字段")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="数据库路径")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[FAIL] 数据库不存在: {db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    try:
        existing = _columns(conn, "exam_record")
        missing = [c for c in NEW_COLUMNS if c not in existing]
        print(f"数据库: {db_path}")
        print(f"待加列: {missing or '无（已是最新）'}")
        if not missing:
            _report(conn, "现状")
            print("[OK] 无需迁移")
            return 0

        if not args.apply:
            _report(conn, "迁移前")
            print("[i] dry-run：未改动。加 --apply 执行（会自动备份）")
            return 0

        backup = _backup(db_path)
        print(f"[BAK] 备份: {backup}")

        for col in missing:
            conn.execute(NEW_COLUMNS[col])
            print(f"  [ADD] 加列 {col}")
        conn.commit()

        after = _columns(conn, "exam_record")
        still = [c for c in NEW_COLUMNS if c not in after]
        if still:
            print(f"[FAIL] 迁移后仍缺列: {still}")
            return 1
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        _report(conn, "迁移后")
        print(f"  integrity_check = {ok}")
        print("[OK] 迁移完成（字段值由 backfill 脚本回填）")
        return 0 if ok == "ok" else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
