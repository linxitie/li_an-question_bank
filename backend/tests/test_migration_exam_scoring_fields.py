# -*- coding: utf-8 -*-
"""D5（2026-11-16）：`exam_record` 评分口径 A 补列脚本的自测。

为什么要有这组用例：`migrate_add_exam_scoring_fields.py` 原先只登记 3 个派生字段、
**漏了主字段 `is_scored`**，而且在缺列的库上跑 `--dry-run` 时 `_report()` 里那句
`SELECT record_id, is_completed, is_scored` 会直接抛 `no such column: is_scored`，
脚本自身先崩 —— 手工执行时极容易被当成「已迁移」。所以用例不复用真实库，
而是**现场造一个没有这 4 列的老库**，跑真子进程，验证：

1. dry-run 不再崩，且明确列出 4 个待加列；
2. --apply 后 4 列俱在、存量行取默认值 0、备份文件落在 --backup-dir；
3. 重复 --apply 幂等（[OK] 无需迁移，不再产生备份）。

真实库 / 其它环境执行姿势见脚本 docstring；本文件只证明脚本行为正确。
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_DIR / "scripts" / "migrate" / "migrate_add_exam_scoring_fields.py"

FOUR = ("is_scored", "manual_pending_count", "answered_count", "question_total")


def _old_db(path: Path) -> None:
    """造一个「本批之前的」exam_record：只有 4 个老列 + 1 行存量数据。"""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """CREATE TABLE exam_record (
                   record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER,
                   paper_id INTEGER,
                   is_completed INTEGER DEFAULT 0
               )"""
        )
        conn.execute("INSERT INTO exam_record(user_id, paper_id, is_completed) "
                     "VALUES (1, 9, 1)")
        conn.commit()
    finally:
        conn.close()


def _cols(path: Path, table: str = "exam_record") -> list[str]:
    conn = sqlite3.connect(str(path))
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def _run(db: Path, backups: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # 子进程 stdout 是管道：强制 UTF-8，避免 Windows CP936 解码把中文断言搞成乱码
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--db", str(db), "--backup-dir", str(backups), *args],
        cwd=str(BACKEND_DIR), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=120,
    )


def test_dry_run_on_old_db_lists_four_columns_without_crash(tmp_path):
    db = tmp_path / "old.db"
    backups = tmp_path / "backups"
    _old_db(db)

    cp = _run(db, backups)
    out = cp.stdout + cp.stderr
    assert cp.returncode == 0, out
    assert "[i] dry-run" in out, out
    listed = next(line for line in out.splitlines() if line.startswith("待加列:"))
    for col in FOUR:
        assert col in listed, out
    # dry-run 不改库
    assert not [c for c in FOUR if c in _cols(db)]
    assert not backups.exists() or not list(backups.glob("*.db"))


def test_apply_adds_all_four_columns_and_backs_up(tmp_path):
    db = tmp_path / "old.db"
    backups = tmp_path / "backups"
    _old_db(db)

    cp = _run(db, backups, "--apply")
    out = cp.stdout + cp.stderr
    assert cp.returncode == 0, out
    assert "[OK] 迁移完成" in out, out
    assert "integrity_check = ok" in out, out

    cols = _cols(db)
    missing = [c for c in FOUR if c not in cols]
    assert not missing, f"仍缺列: {missing}；现有列: {cols}"

    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT is_scored, manual_pending_count, answered_count, question_total "
            "FROM exam_record WHERE record_id = 1"
        ).fetchone()
    finally:
        conn.close()
    assert row == (0, 0, 0, 0), f"存量行默认值不对: {row}"

    made = list(backups.glob("before_exam_scoring_fields_*.db"))
    assert len(made) == 1, f"备份文件数: {made}"


def test_second_apply_is_noop_and_makes_no_backup(tmp_path):
    db = tmp_path / "old.db"
    backups = tmp_path / "backups"
    _old_db(db)
    assert _run(db, backups, "--apply").returncode == 0
    first = sorted(backups.glob("before_exam_scoring_fields_*.db"))
    assert len(first) == 1

    cp = _run(db, backups, "--apply")
    out = cp.stdout + cp.stderr
    assert cp.returncode == 0, out
    assert "[OK] 无需迁移" in out, out
    assert sorted(backups.glob("before_exam_scoring_fields_*.db")) == first, "重复执行不应再备份"
