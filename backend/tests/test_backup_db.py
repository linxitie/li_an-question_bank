"""R0 备份工具测试。"""
import sqlite3
from pathlib import Path

import pytest

from scripts.content_hub.backup_db import backup_database


def test_backup_creates_integrity_checked_copy(tmp_path: Path):
    src = tmp_path / "q.db"
    con = sqlite3.connect(src)
    con.execute("CREATE TABLE t (x INTEGER)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()

    dst = backup_database(src, tmp_path / "bak")

    assert dst.exists()
    copied = sqlite3.connect(dst)
    try:
        assert copied.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert copied.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    finally:
        copied.close()


def test_missing_source_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        backup_database(tmp_path / "missing.db", tmp_path / "bak")
