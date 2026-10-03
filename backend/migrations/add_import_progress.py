"""为 question_import_record 表补齐解析进度字段（幂等）。

背景
----
题目导入的异步解析（`_process_import_async`）需要向上报真实进度，
但 `question_import_record` 表原先没有承载进度的列，导致前端只能定时器伪造。

本脚本做两件事
--------------
1. 先备份数据库（可用 ``--no-backup`` 跳过，但不建议）
2. 幂等地补齐两列：
   - ``progress_percent INTEGER DEFAULT 0``  解析进度 0-100
   - ``current_phase  VARCHAR(50)``          当前阶段标识

幂等保证
--------
执行前用 ``PRAGMA table_info`` 查列是否已存在，存在则跳过该列。
因此本脚本可重复执行任意次而不报错。

用法
----
    python backend/migrations/add_import_progress.py
    python backend/migrations/add_import_progress.py --no-backup
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
import sys
from datetime import datetime

TABLE = 'question_import_record'
# (列名, SQLite 列定义)
COLUMNS = [
    ('progress_percent', 'INTEGER DEFAULT 0'),
    ('current_phase', 'VARCHAR(50)'),
]


def default_db_path() -> str:
    """定位 question_bank.db（backend/data/question_bank.db）"""
    here = os.path.dirname(os.path.abspath(__file__))          # backend/migrations
    backend_dir = os.path.dirname(here)                        # backend
    return os.path.join(backend_dir, 'data', 'question_bank.db')


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def backup(db_path: str) -> str:
    """备份数据库并返回备份路径。备份同样要过 integrity_check 才可信。"""
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak_dir = os.path.join(os.path.dirname(db_path), 'backups', f'pre_import_progress_{stamp}')
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, os.path.basename(db_path))
    shutil.copy2(db_path, bak)

    con = sqlite3.connect(bak)
    try:
        state = con.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        con.close()
    if state != 'ok':
        raise RuntimeError(f'备份完整性校验失败: {state}（已中止迁移）')
    return bak


def existing_columns(con: sqlite3.Connection) -> set:
    return {r[1] for r in con.execute(f'PRAGMA table_info({TABLE})')}


def main() -> int:
    ap = argparse.ArgumentParser(description='补齐 question_import_record 进度字段（幂等）')
    ap.add_argument('--db', default=None, help='数据库路径，默认 backend/data/question_bank.db')
    ap.add_argument('--no-backup', action='store_true', help='跳过备份（不推荐）')
    args = ap.parse_args()

    db_path = args.db or default_db_path()
    if not os.path.exists(db_path):
        print(f'错误：数据库不存在 {db_path}', file=sys.stderr)
        return 2

    if not args.no_backup:
        bak = backup(db_path)
        print(f'[1/3] 已备份 -> {bak}')
        print(f'      SHA256 = {sha256(bak)}')
    else:
        print('[1/3] 跳过备份（--no-backup）')

    con = sqlite3.connect(db_path)
    added, skipped = [], []
    try:
        before = existing_columns(con)
        rows_before = con.execute('SELECT COUNT(*) FROM question_bank').fetchone()[0]

        for name, ddl in COLUMNS:
            if name in before:
                skipped.append(name)
                continue
            con.execute(f'ALTER TABLE {TABLE} ADD COLUMN {name} {ddl}')
            added.append(name)
        con.commit()

        after = existing_columns(con)
        missing = [n for n, _ in COLUMNS if n not in after]
        if missing:
            raise RuntimeError(f'迁移后仍缺列: {missing}')

        rows_after = con.execute('SELECT COUNT(*) FROM question_bank').fetchone()[0]
        state = con.execute('PRAGMA integrity_check').fetchone()[0]
    except Exception as e:
        con.rollback()
        con.close()
        print(f'迁移失败并已回滚: {type(e).__name__}: {e}', file=sys.stderr)
        return 1
    finally:
        try:
            con.close()
        except Exception:
            pass

    print(f'[2/3] 新增列: {added or "无"}')
    print(f'      已存在跳过: {skipped or "无"}')
    print(f'[3/3] question_bank 行数 {rows_before} -> {rows_after} '
          f'({"一致 PASS" if rows_before == rows_after else "不一致 FAIL"})')
    print(f'      integrity_check = {state} {"(PASS)" if state == "ok" else "(FAIL)"}')

    ok = (state == 'ok') and (rows_before == rows_after) and not missing
    print('结果:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
