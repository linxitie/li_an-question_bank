"""启动期数据库守卫。

背景（2026-10-25 事故）：`backend/.env` 缺失时，`SQLITE_PATH` 回落到默认值。
若默认值指向一个旧/空库，SQLAlchemy 会照常启动并在该库上 `create_all`，
于是「题目、账号突然消失」——故障表现为业务数据丢失，实际是连错库，
且日志里没有任何提示。本模块把这一沉默故障变成启动时的一条明确记录：

1. 打印真实解析后的库路径（相对路径按 backend/ 解析，不依赖进程 cwd）；
2. 库文件不存在时 ERROR 告警（默认不阻断，方便 CI/全新环境建库）；
3. 建表后校验关键表/列，缺列（如 `question_bank.sub_category_id`）直接 ERROR；
4. 打印关键表行数，空库（题目 0 / 用户 0）ERROR。

需要「连错库即拒绝启动」的场景，设 `DB_GUARD_STRICT=1`。
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import inspect, text

# app/core/db_guard.py -> app/core -> app -> backend
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# 关键表及其必须存在的列：缺失即说明连到了旧schema库
CRITICAL_SCHEMA = {
    "question_bank": (
        "question_id",
        "subject_id",
        "sub_category_id",
        "group_id",
        "status",
        "audit_status",
    ),
    "sys_user": ("user_id", "user_no", "password"),
}

# 行数为 0 时需要告警的表（这些表在正常业务库里不可能为空）
NON_EMPTY_TABLES = ("question_bank", "sys_user")


def resolve_sqlite_path(sqlite_path: str) -> Path:
    """把 SQLITE_PATH 解析成绝对路径。

    相对路径一律相对 backend/ 解析：uvicorn 的 cwd 可能是仓库根，若按 cwd
    解析会得到 backend/backend/data/... 这种不存在的路径，进而静默新建空库。
    """
    path = Path(sqlite_path)
    return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()


def is_strict() -> bool:
    return os.environ.get("DB_GUARD_STRICT", "").strip().lower() in ("1", "true", "yes", "on")


def preflight(logger, db_type: str, sqlite_path: str) -> Path | None:
    """建表之前调用：确认库文件位置，文件不存在时明确告警。"""
    if db_type != "sqlite":
        logger.info(f"[db-guard] 使用非 SQLite 数据库: {db_type}")
        return None

    path = resolve_sqlite_path(sqlite_path)
    exists = path.exists()
    logger.info(f"[db-guard] SQLite 实际路径: {path} (exists={exists}, size={path.stat().st_size if exists else 0})")
    if not exists:
        logger.error(
            "[db-guard] 目标库文件不存在，本次启动将新建空库——题目与账号都会是空的！"
            f" 期望路径: {path}；请检查 backend/.env 的 SQLITE_PATH 或恢复数据文件。"
        )
        if is_strict():
            raise RuntimeError(f"SQLite 库文件不存在: {path}")
    return path


def verify(engine, logger) -> dict:
    """建表之后调用：校验 schema 与行数，返回可断言/可落盘的检查结果。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    missing_tables = [t for t in CRITICAL_SCHEMA if t not in tables]
    missing_columns: dict[str, list[str]] = {}
    for table, columns in CRITICAL_SCHEMA.items():
        if table not in tables:
            continue
        actual = {c["name"] for c in inspector.get_columns(table)}
        lack = [c for c in columns if c not in actual]
        if lack:
            missing_columns[table] = lack

    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for table in NON_EMPTY_TABLES:
            if table in tables:
                counts[table] = int(conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)

    result = {
        "tables": len(tables),
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "counts": counts,
    }

    if missing_tables or missing_columns:
        logger.error(f"[db-guard] schema 不完整，业务查询会直接 500: {result}")
        if is_strict():
            raise RuntimeError(f"数据库 schema 不完整: {result}")
    else:
        logger.info(f"[db-guard] schema 校验通过，行数={counts}")

    empty = [t for t in NON_EMPTY_TABLES if counts.get(t) == 0]
    if empty:
        logger.error(f"[db-guard] 以下表为空，疑似连到空库/新库: {empty}（若为首次初始化请忽略）")

    return result
