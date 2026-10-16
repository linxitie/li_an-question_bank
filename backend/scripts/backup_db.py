#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SQLite 在线备份 —— 必须使用 sqlite3.backup() API。

为什么不能用 shutil.copy2（R10 红线）
------------------------------------
本库运行在 WAL 模式。当前实测：主库 292.31 MB，-wal 4.60 MB，-shm 0.03 MB。
WAL 模式下已提交的数据可能仍只存在于 -wal 中，此时 shutil.copy2 拷到的
主库是一份**缺少最近提交的不一致快照**，且它无法察觉这一点 —— 备份"成功"
但内容是错的。只有 sqlite3.backup() 会走 SQLite 自己的读事务，
在一致的时间点取快照。

红线 R8：data/ 下已有 41 份 .bak* 是全系统唯一存世的行测题副本
（含 bak_pre_wipe_20261004_102517，10171 道题），本脚本只新增文件，
绝不删除、覆盖或清理任何既有备份。

用法：
    python scripts/backup_db.py                     # 备份到 data/backups/
    python scripts/backup_db.py --db <路径>          # 指定库
    python scripts/backup_db.py --out-dir <目录>      # 指定输出目录
    python scripts/backup_db.py --label 导入前留档    # 追加标签，便于回溯
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
DEFAULT_DB = os.path.join(_BACKEND, "data", "question_bank.db")
DEFAULT_OUT = os.path.join(_BACKEND, "data", "backups")

# 备份后抽样核对的表：覆盖题库主干，用于人工确认内容而非仅文件大小
_SAMPLE_TABLES = ("sys_user", "question_bank", "exam_paper",
                  "paper_question_relation", "study_material")


def _resolve(p: str) -> str:
    return os.path.abspath(p)


def _fmt_size(n: int) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if v < 1024 or unit == "GB":
            return f"{n} B" if unit == "B" else f"{v:.2f} {unit}"
        v /= 1024.0
    return str(n)


def _sidecar_size(db: str, suffix: str) -> int:
    p = db + suffix
    return os.path.getsize(p) if os.path.exists(p) else 0


def _describe(db: str) -> str:
    """取库的状态摘要。用于打印与写进备份日志。"""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        page_count = con.execute("PRAGMA page_count").fetchone()[0]
        page_size = con.execute("PRAGMA page_size").fetchone()[0]
        lines = [
            f"  journal_mode : {mode}",
            f"  integrity    : {integrity}",
            f"  page_count   : {page_count} × {page_size} bytes"
            f" = {page_count * page_size / 1024 / 1024:.2f} MB",
        ]
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in _SAMPLE_TABLES:
            if t in tables:
                n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                lines.append(f"  {t:<26}: {n} 行")
        return "\n".join(lines)
    finally:
        con.close()


def _verify(backup: str) -> tuple[bool, str]:
    """独立打开备份文件做完整性校验。备份文件写完但打不开，等于没备份。"""
    try:
        con = sqlite3.connect(f"file:{backup}?mode=ro", uri=True)
    except sqlite3.Error as e:
        return False, f"无法打开备份: {e}"
    try:
        res = con.execute("PRAGMA integrity_check").fetchone()[0]
        if res != "ok":
            return False, f"integrity_check = {res}"
        n = con.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
        return True, f"ok（{n} 个对象）"
    except sqlite3.Error as e:
        return False, f"校验出错: {e}"
    finally:
        con.close()


def backup(db: str, out_dir: str, label: str | None = None) -> int:
    db, out_dir = _resolve(db), _resolve(out_dir)

    if not os.path.exists(db):
        print(f"[backup] 错误：主库不存在 {db}", file=sys.stderr)
        return 2

    os.makedirs(out_dir, exist_ok=True)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{os.path.splitext(os.path.basename(db))[0]}_{stamp}"
    if label:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        name += "_" + safe
    dest = os.path.join(out_dir, name + ".db")

    if os.path.exists(dest):
        print(f"[backup] 错误：目标已存在，拒绝覆盖 {dest}", file=sys.stderr)
        return 2

    print(f"[backup] 源库   : {db}")
    print(f"[backup] 源库附带: -wal {_fmt_size(_sidecar_size(db, '-wal'))}"
          f" / -shm {_fmt_size(_sidecar_size(db, '-shm'))}")
    print("[backup] 源库状态:")
    print(_describe(db))
    print(f"[backup] 目标   : {dest}")

    src = sqlite3.connect(db, timeout=30.0)
    try:
        # progress=1 每 16 页回显一次进度；备份 292 MB 约需数秒。
        # SQLite 会在备份期间自动重放 WAL，因此产物是包含最近提交的一致快照。
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst, pages=2048, progress=lambda st, tot, cur: None)
            dst.commit()
        finally:
            dst.close()
    except sqlite3.Error as e:
        # 失败时不要留下半成品，否则会被误当成可用的备份
        if os.path.exists(dest):
            try:
                os.remove(dest)
                print("[backup] 已删除不完整的备份文件", file=sys.stderr)
            except OSError:
                pass
        print(f"[backup] 备份失败: {e}", file=sys.stderr)
        return 1
    finally:
        src.close()

    size = os.path.getsize(dest)
    print(f"[backup] 完成   : {_fmt_size(size)}")

    ok, msg = _verify(dest)
    print(f"[backup] 校验   : {msg}")
    if not ok:
        print("[backup] 备份不可用，请勿依赖此文件", file=sys.stderr)
        return 1

    log = dest + ".log"
    with open(log, "w", encoding="utf-8") as fh:
        fh.write(f"备份时间 : {_dt.datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"源库     : {db}\n")
        fh.write(f"备份文件 : {dest}\n")
        fh.write(f"体积     : {_fmt_size(size)}\n")
        fh.write(f"校验     : {msg}\n\n")
        fh.write("=== 源库状态 ===\n")
        fh.write(_describe(db) + "\n")

    print(f"[backup] 日志   : {log}")
    print(f"[backup] 恢复命令: python scripts/restore_db.py --backup \"{dest}\"")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="SQLite 在线备份（sqlite3.backup()）")
    ap.add_argument("--db", default=DEFAULT_DB, help="主库路径")
    ap.add_argument("--out-dir", default=DEFAULT_OUT, help="备份输出目录")
    ap.add_argument("--label", default=None, help="文件名标签，如 导入前留档")
    a = ap.parse_args()
    return backup(a.db, a.out_dir, a.label)


if __name__ == "__main__":
    sys.exit(main())