# -*- coding: utf-8 -*-
"""给 `exam_record` 补齐评分口径 A 的 4 个字段（2026-11-09 立，2026-11-16 修订）。

背景：`is_scored` 统一为「分数已完全确定」后，同时补三个只读派生字段
`manual_pending_count` / `answered_count` / `question_total`，
供结果页、成绩单与学情使用。详见
`docs/plans/考试评分口径_is_scored统一_方案_v1.md` §4 P-A。

2026-11-16 修订（D5）：本脚本原先只登记 3 个派生字段，**漏了主字段 `is_scored`**。
漏的后果是可复现的：在缺列的库上跑 `--dry-run`，`_report()` 的
`SELECT record_id, is_completed, is_scored` 会直接抛
`OperationalError: no such column: is_scored`，脚本自身先崩，
执行者却会以为「迁移已完成」。同时 `app/main.py` 的 lifespan 自愈块只覆盖
`sys_user` / `achievement` / `exam_paper` / `study_material` / `forum_*` 等表，
**没有 exam_record 分支**，所以这 4 列在存量库上唯一的补列途径就是本脚本。两处一起补：
  1. 增加 `is_scored`；
  2. `_report()` 改为只 SELECT 真实存在的列，dry-run 不再崩。

2026-11-16 追加（D5-b）：上面第 3 段的"唯一途径"已不再成立 —— 应用启动时也会自愈
`exam_record`（`app/main.py::_ensure_exam_record_scoring_columns`，补列后还会按口径 A
从明细回填 4 个字段）。本脚本因此变成**离线/显式补列**入口：不启动应用也能补，
行为与启动自愈一致（同样的 4 列、同样的 `DEFAULT 0`）；在已自愈的库上运行会输出
`[OK] 无需迁移`。注意：本脚本只补列**不回填**——回填逻辑在
`app/services/exam_scoring.backfill_stale_records`，随启动执行一次。

同批新增的其余列不需要本脚本（D5 口径核对结论）：
  · `exam_paper.exam_open/exam_open_at/exam_close_at`（main.py:330-340 启动自愈）
  · `study_material.paper_code/paper_meta/doc_meta/list_time/placement`
    （main.py:490-546 启动自愈，含 idx_material_paper_code / idx_material_list_time /
     idx_material_placement 三个索引与 list_time、placement 的回填）
  · `exam_paper.paper_code` 是 main 已有列，不属于本批新增。
DDL 存档见 `backend/migrations/20261116_001_exam_record_scoring_fields.sql`。

SQLite 支持 `ALTER TABLE ... ADD COLUMN`，因此不需要重建表；
但每条 ALTER 只能加一列，且必须带默认值（存量行补 0）。

本脚本刻意只用 ASCII 标记（[OK]/[ADD]/[i]/[BAK]/[FAIL]）：Windows 控制台默认 GBK，
打印 emoji（如 U+2139、U+2705）会抛 UnicodeEncodeError 并被误判为失败
（与 `backend/scripts/gates/gate_all.py` 里 PYTHONIOENCODING 的坑同源）。

用法：
  python backend/scripts/migrate/migrate_add_exam_scoring_fields.py            # dry-run
  python backend/scripts/migrate/migrate_add_exam_scoring_fields.py --apply
  python backend/scripts/migrate/migrate_add_exam_scoring_fields.py --db <path> --apply
  python backend/scripts/migrate/migrate_add_exam_scoring_fields.py --db <path> \
      --backup-dir <dir> --apply          # 测试/离线库：不写进 backend/data/backups

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
# 顺序与 models.ExamRecord 一致，便于对照。
NEW_COLUMNS = {
    "is_scored": "ALTER TABLE exam_record ADD COLUMN is_scored INTEGER DEFAULT 0",
    "manual_pending_count": "ALTER TABLE exam_record ADD COLUMN manual_pending_count INTEGER DEFAULT 0",
    "answered_count": "ALTER TABLE exam_record ADD COLUMN answered_count INTEGER DEFAULT 0",
    "question_total": "ALTER TABLE exam_record ADD COLUMN question_total INTEGER DEFAULT 0",
}

# `_report()` 想看的列；缺哪列就跳过哪列（dry-run 阶段列本来就还不存在）
REPORT_COLUMNS = ("record_id", "is_completed", "is_scored")


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _backup(db_path: Path, backup_dir: Path = BACKUP_DIR) -> Path:
    """用 sqlite3.backup() 做一致性备份（R10：WAL 下禁止 copy2）。"""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = backup_dir / f"before_exam_scoring_fields_{stamp}.db"
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
    usable = [c for c in REPORT_COLUMNS if c in cols]
    if len(usable) != len(REPORT_COLUMNS):
        print(f"  [{label}] 暂缺列: {[c for c in REPORT_COLUMNS if c not in cols]}")
    if not usable:
        print(f"  [{label}] 无法统计记录数（缺少 {list(REPORT_COLUMNS)}）")
        return
    rows = list(conn.execute(
        f"SELECT {', '.join(usable)} FROM exam_record ORDER BY record_id"
    ))
    print(f"  [{label}] 记录 {len(rows)} 行" + (f"，示例 {rows[:3]}" if rows else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="exam_record 补齐评分口径 A 的 4 个字段")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="数据库路径")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    parser.add_argument("--backup-dir", default=str(BACKUP_DIR),
                        help="备份目录（默认 backend/data/backups）")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[FAIL] 数据库不存在: {db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    try:
        if "exam_record" not in [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]:
            print(f"[FAIL] 库里没有 exam_record 表: {db_path}")
            return 2

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

        backup = _backup(db_path, Path(args.backup_dir))
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
        print("[OK] 迁移完成（is_scored 的取值由业务写点/回填脚本决定，本脚本只补列）")
        return 0 if ok == "ok" else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
