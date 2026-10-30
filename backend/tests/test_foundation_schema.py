"""F1 Step 1：7 表幂等建表与结构校验。"""
import sqlite3

from app.foundation import schema as fs


def test_ensure_schema_is_idempotent(tmp_path):
    db = tmp_path / "f1.db"
    conn = sqlite3.connect(db)
    try:
        first = fs.ensure_schema(conn)
        assert sorted(first) == sorted(fs.FOUNDATION_TABLES)
        assert fs.verify_schema(conn) == []

        second = fs.ensure_schema(conn)
        assert second == [], "第二次执行不得重复建表"
        assert fs.verify_schema(conn) == []
    finally:
        conn.close()


def test_ensure_schema_does_not_touch_existing_tables(tmp_path):
    db = tmp_path / "f1.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE question_bank (question_id INTEGER PRIMARY KEY, x TEXT)")
        conn.execute("INSERT INTO question_bank (x) VALUES ('keep')")
        conn.execute("CREATE TABLE question_bank__twin (question_id INTEGER PRIMARY KEY, x TEXT)")
        conn.execute("INSERT INTO question_bank__twin (x) VALUES ('keep')")
        conn.commit()
        before = sorted(conn.execute("SELECT name, sql FROM sqlite_master").fetchall())

        fs.ensure_schema(conn)

        after = sorted(conn.execute("SELECT name, sql FROM sqlite_master").fetchall())
        kept = [row for row in after if row in before]
        assert kept == before, "既有表定义不得被修改"
        assert conn.execute("SELECT x FROM question_bank").fetchone() == ("keep",)
    finally:
        conn.close()


def test_verify_reports_missing_table(tmp_path):
    conn = sqlite3.connect(tmp_path / "f1.db")
    try:
        diffs = fs.verify_schema(conn)
        assert len(diffs) >= len(fs.FOUNDATION_TABLES)
        assert any("foundation_outbox" in d for d in diffs)
    finally:
        conn.close()


def test_verify_detects_column_mismatch(tmp_path):
    db = tmp_path / "f1.db"
    conn = sqlite3.connect(db)
    try:
        fs.ensure_schema(conn)
        conn.execute("ALTER TABLE foundation_inbox RENAME TO foundation_inbox_old")
        conn.execute("CREATE TABLE foundation_inbox (consumer TEXT PRIMARY KEY)")
        conn.commit()
        diffs = fs.verify_schema(conn)
        assert any("foundation_inbox" in d for d in diffs)
    finally:
        conn.close()
