"""按文件名顺序执行 backend/migrations/*.sql（SQLite）。

用法：
  python backend/scripts/migrate/apply.py            # 默认 dry-run
  python backend/scripts/migrate/apply.py --apply
  python backend/scripts/migrate/apply.py --verify
  python backend/scripts/migrate/apply.py --db <path> # 指定库（默认 SQLITE_PATH）

幂等：DDL 全部 IF NOT EXISTS，重复执行 changed=0。--verify 校验 F1 7 表 + F3 media_assets + F5 图投影表。
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.foundation import graph_schema as gs  # noqa: E402
from app.foundation import media_schema as ms  # noqa: E402
from app.foundation import schema as fs  # noqa: E402
from app.foundation.config import MIGRATIONS_DIR, sqlite_path  # noqa: E402


def _connect(db: Path) -> sqlite3.Connection:
    if not db.exists():
        raise SystemExit(f"数据库不存在：{db}（先确认 SQLITE_PATH）")
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


# 只登记 SQLite 可执行的迁移。历史 001-004 是 MySQL 语法（USE/COMMENT/AFTER），
# 由 apply.py 明确跳过，避免在 SQLite 上误执行半截。
SQLITE_MIGRATIONS: tuple[str, ...] = (
    "20261027_001_foundation_core.sql",
    "20261027_002_media_assets.sql",
    "20261027_003_graph_projection.sql",
)


def _migration_files() -> list[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    legacy = [p.name for p in files if p.name not in SQLITE_MIGRATIONS]
    if legacy:
        print(f"skip (non-sqlite): {', '.join(legacy)}")
    return [p for p in files if p.name in SQLITE_MIGRATIONS]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="砺安题库迁移执行器（SQLite）")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    mode.add_argument("--verify", action="store_true", help="只校验 F1 7 表 + F3 media_assets 结构")
    parser.add_argument("--db", default=None, help="覆盖数据库路径")
    args = parser.parse_args(argv)

    db = Path(args.db).resolve() if args.db else sqlite_path()
    conn = _connect(db)
    try:
        if args.verify:
            diffs = fs.verify_schema(conn)
            diffs += ms.verify_media_schema(conn)
            diffs += gs.verify_graph_schema(conn)
            for d in diffs:
                print(f"DIFF {d}")
            print("verify: " + ("OK" if not diffs else f"{len(diffs)} 处差异"))
            return 0 if not diffs else 1

        files = _migration_files()
        before = set(fs._table_names(conn))
        print(f"db={db}")
        for path in files:
            print(f"  {path.name} sha256={_digest(path)} {'APPLIED' if args.apply else 'PENDING(dry-run)'}")
        missing = [t for t in fs.FOUNDATION_TABLES if t not in before]
        print(f"foundation tables missing: {missing or 'none'}")
        media_missing = [t for t in ms.MEDIA_TABLES if t not in before]
        print(f"media tables missing: {media_missing or 'none'}")
        graph_missing = [t for t in gs.GRAPH_TABLES if t not in before]
        print(f"graph tables missing: {graph_missing or 'none'}")

        if not args.apply:
            print("dry-run：未修改数据库（加 --apply 执行）")
            return 0

        for path in files:
            conn.executescript(path.read_text(encoding="utf-8"))
        conn.commit()
        after = set(fs._table_names(conn))
        created = sorted(after - before)
        diffs = fs.verify_schema(conn) + ms.verify_media_schema(conn) + gs.verify_graph_schema(conn)
        print(f"apply: created={created or 'none'} changed={len(created)}")
        if diffs:
            for d in diffs:
                print(f"DIFF {d}")
            return 1
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
