"""数据库守卫单测：覆盖「连错库/旧库」导致数据看起来消失的三类信号。"""
import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.db_guard import (
    BACKEND_ROOT,
    is_strict,
    preflight,
    resolve_sqlite_path,
    verify,
)

logger = logging.getLogger("test.db_guard")


def test_relative_path_resolves_against_backend_root():
    p = resolve_sqlite_path("./data/question_bank.db")
    assert p.is_absolute()
    assert p == (BACKEND_ROOT / "data" / "question_bank.db").resolve()
    # 关键回归：不能按进程 cwd 解析，否则会得到 backend/backend/data/...
    assert "backend\\backend" not in str(p).lower()


def test_absolute_path_kept():
    raw = str(BACKEND_ROOT / "data" / "x.db")
    assert str(resolve_sqlite_path(raw)) == raw


def test_preflight_warns_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("DB_GUARD_STRICT", raising=False)
    missing = tmp_path / "not_exists.db"
    # 不抛异常：CI / 全新环境允许建库
    assert preflight(logger, "sqlite", str(missing)) == missing


def test_preflight_strict_raises_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_GUARD_STRICT", "1")
    assert is_strict() is True
    with pytest.raises(RuntimeError):
        preflight(logger, "sqlite", str(tmp_path / "not_exists.db"))


def test_verify_flags_missing_column_and_reports_counts(tmp_path):
    db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        # 模拟旧 schema：question_bank 没有 sub_category_id，且题目为 0
        conn.execute(text(
            "CREATE TABLE question_bank (question_id INTEGER PRIMARY KEY, subject_id INTEGER,"
            " group_id INTEGER, status INTEGER, audit_status INTEGER)"
        ))
        conn.execute(text("CREATE TABLE sys_user (user_id INTEGER PRIMARY KEY, user_no TEXT, password TEXT)"))
        conn.execute(text("INSERT INTO sys_user (user_no, password) VALUES ('u1', 'x')"))
        conn.execute(text("INSERT INTO question_bank (subject_id, status, audit_status) VALUES (1, 1, 1)"))

    result = verify(engine, logger)

    assert result["missing_tables"] == []
    assert result["missing_columns"]["question_bank"] == ["sub_category_id"]
    assert result["counts"]["question_bank"] == 1
    assert result["counts"]["sys_user"] == 1
    engine.dispose()


def test_verify_strict_raises_on_missing_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_GUARD_STRICT", "1")
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE question_bank (question_id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError):
        verify(engine, logger)
    engine.dispose()
