"""T-07 tests for the partial unique index on visible sibling knowledge points.

The index is partial (``WHERE status = 1``) because hidden legacy aliases may
intentionally share a name with a visible canonical node.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "20261024_004_taxonomy_v2_unique_sibling.sql"
)
SOURCE_DB = Path(r"C:\Users\21499\AppData\Local\Temp\opencode\taxonomy_t06.db")
TARGET_DB = Path(r"C:\Users\21499\AppData\Local\Temp\opencode\taxonomy_t07.db")

INDEX_NAME = "uq_knowledge_point_sibling_visible"


def _migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _index_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (INDEX_NAME,),
    ).fetchone()
    return row is not None


def _index_list(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'knowledge_point'"
        )
    }


def _new_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE knowledge_point (
            point_id INTEGER PRIMARY KEY,
            point_name TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            sub_category_id INTEGER NOT NULL,
            parent_id INTEGER NOT NULL,
            status INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    conn.executescript(_migration_sql())
    return conn


def _insert(
    conn: sqlite3.Connection,
    point_id: int,
    name: str = "其他",
    *,
    subject_id: int = 1,
    sub_category_id: int = 10,
    parent_id: int = 100,
    status: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO knowledge_point "
        "(point_id, point_name, subject_id, sub_category_id, parent_id, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (point_id, name, subject_id, sub_category_id, parent_id, status),
    )


# ---------------------------------------------------------------------------
# In-memory schema tests
# ---------------------------------------------------------------------------


def test_index_exists_after_migration():
    conn = _new_conn()
    try:
        assert _index_exists(conn)
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (INDEX_NAME,),
        ).fetchone()[0]
        assert "WHERE status = 1" in sql.replace("WHERE status=1", "WHERE status = 1")
    finally:
        conn.close()


def test_duplicate_visible_sibling_is_rejected():
    conn = _new_conn()
    try:
        _insert(conn, 1, "其他", status=1)
        with pytest.raises(sqlite3.IntegrityError):
            _insert(conn, 2, "其他", status=1)
        conn.rollback()
    finally:
        conn.close()


def test_hidden_duplicate_sharing_visible_name_is_allowed():
    conn = _new_conn()
    try:
        _insert(conn, 1, "其他", status=1)
        _insert(conn, 2, "其他", status=0)
        conn.commit()

        assert (
            conn.execute("SELECT COUNT(*) FROM knowledge_point").fetchone()[0] == 2
        )
    finally:
        conn.close()


def test_same_name_different_parent_is_allowed():
    conn = _new_conn()
    try:
        _insert(conn, 1, "其他", parent_id=100)
        _insert(conn, 2, "其他", parent_id=200)
        conn.commit()

        assert (
            conn.execute("SELECT COUNT(*) FROM knowledge_point").fetchone()[0] == 2
        )
    finally:
        conn.close()


def test_same_name_different_subject_is_allowed():
    conn = _new_conn()
    try:
        _insert(conn, 1, "其他", subject_id=1)
        _insert(conn, 2, "其他", subject_id=2)
        conn.commit()

        assert (
            conn.execute("SELECT COUNT(*) FROM knowledge_point").fetchone()[0] == 2
        )
    finally:
        conn.close()


def test_reapplying_migration_is_idempotent():
    conn = _new_conn()
    try:
        conn.executescript(_migration_sql())
        conn.executescript(_migration_sql())

        assert _index_exists(conn)
        names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name = ?",
                (INDEX_NAME,),
            )
        ]
        assert names == [INDEX_NAME]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Temp taxonomy DB apply test (t06 -> t07 copy via sqlite3 backup API)
# ---------------------------------------------------------------------------


def _copy_with_backup_api(src_path: Path, dst_path: Path) -> None:
    if dst_path.exists():
        dst_path.unlink()

    src = sqlite3.connect("file:" + src_path.as_posix() + "?mode=ro", uri=True)
    dst = sqlite3.connect(str(dst_path))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def _visible_duplicate_groups(conn: sqlite3.Connection) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT 1
            FROM knowledge_point
            WHERE status = 1
            GROUP BY subject_id, sub_category_id, parent_id, point_name
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]


@pytest.mark.skipif(not SOURCE_DB.exists(), reason="taxonomy_t06.db not available")
def test_apply_index_to_taxonomy_t06_copy():
    _copy_with_backup_api(SOURCE_DB, TARGET_DB)

    conn = sqlite3.connect(str(TARGET_DB))
    try:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(knowledge_point)")
        }
        assert "status" in columns
        assert _visible_duplicate_groups(conn) == 0
        assert INDEX_NAME not in _index_list(conn)

        conn.executescript(_migration_sql())
        assert _index_exists(conn)
        assert _visible_duplicate_groups(conn) == 0
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

        row = conn.execute(
            """
            SELECT subject_id, sub_category_id, parent_id, point_name
            FROM knowledge_point
            WHERE status = 1
            ORDER BY point_id
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        subject_id, sub_category_id, parent_id, point_name = row
        next_id = conn.execute(
            "SELECT COALESCE(MAX(point_id), 0) + 1 FROM knowledge_point"
        ).fetchone()[0]

        visible_insert = (
            "INSERT INTO knowledge_point "
            "(point_id, point_name, subject_id, sub_category_id, parent_id, status) "
            "VALUES (?, ?, ?, ?, ?, 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                visible_insert,
                (next_id, point_name, subject_id, sub_category_id, parent_id),
            )
        conn.rollback()

        hidden_insert = (
            "INSERT INTO knowledge_point "
            "(point_id, point_name, subject_id, sub_category_id, parent_id, status) "
            "VALUES (?, ?, ?, ?, ?, 0)"
        )
        conn.execute(
            hidden_insert,
            (next_id, point_name, subject_id, sub_category_id, parent_id),
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM knowledge_point WHERE point_id = ?", (next_id,)
            ).fetchone()[0]
            == 1
        )
        conn.rollback()

        # Re-applying the migration must not fail on the existing index.
        conn.executescript(_migration_sql())
        assert _index_exists(conn)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()
