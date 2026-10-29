#!/usr/bin/env python3
"""SQLite 备份工具（R0 前置）。

用 sqlite3.backup() 做一致性备份，避免 WAL 模式下只拷主库导致备份不完整。
用法（在 backend 目录执行）：
    python -m scripts.content_hub.backup_db
    python -m scripts.content_hub.backup_db --db data/question_bank.db --out data/backups
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = BACKEND_ROOT / "data" / "question_bank.db"
DEFAULT_OUT = BACKEND_ROOT / "data" / "backups"


def backup_database(src: Path, out_dir: Path) -> Path:
    """备份 SQLite 库并校验完整性，返回备份文件路径。"""
    src = Path(src).resolve()
    out_dir = Path(out_dir)
    if not src.is_file():
        raise FileNotFoundError(f"database not found: {src}")

    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}_{datetime.now():%Y%m%d_%H%M%S}.db"

    src_conn = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    try:
        dst_conn = sqlite3.connect(dst)
        try:
            src_conn.backup(dst_conn)
            check = dst_conn.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise RuntimeError(f"integrity_check failed: {check}")
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return dst


def table_counts(db: Path) -> dict[str, int]:
    """返回库内各业务表行数（跳过 sqlite_ 内部表）。"""
    conn = sqlite3.connect(db)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite 一致性备份")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    try:
        dst = backup_database(args.db, args.out)
    except Exception as exc:  # noqa: BLE001 - CLI 顶层统一报错
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    counts = table_counts(dst)
    print(f"backup={dst}")
    print("integrity=ok")
    for name, value in counts.items():
        print(f"{name}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
