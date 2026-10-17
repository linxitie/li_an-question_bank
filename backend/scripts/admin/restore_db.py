#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SQLite 恢复 / 回滚 —— 覆盖主库并清理 -wal / -shm。

为什么必须连 -wal / -shm 一起处理（R10 红线）
----------------------------------------------
备份文件是 `sqlite3.backup()` 产出的**完整自洽**快照，其内容已经包含了
备份时刻所有已提交的 WAL 数据。恢复后若把旧的 -wal / -shm 留在原处，
SQLite 会把它们当作"尚待重放的增量"套到新主库上：

  - 旧 -wal 的页号与新主库的页布局不匹配 → 库损坏或读到错乱数据
  - 旧 -shm 是共享内存索引，与任一侧都不匹配 → 更直接的损坏来源

所以正确顺序是：**先删 -wal/-shm，再放主库**，而不是先放主库再删侧车。

安全设计
--------
恢复是破坏性操作，因此本脚本自带三道闸：
  1. 覆盖前先校验备份文件可打开且 integrity_check = ok
  2. 覆盖前**自动再备份一次当前状态**，使恢复本身可回退
  3. 需显式 --yes 或交互确认，避免误操作

用法：
    python scripts/admin/restore_db.py --backup <备份.db>
    python scripts/admin/restore_db.py --backup <备份.db> --yes      # 跳过交互确认
    python scripts/admin/restore_db.py --backup <备份.db> --dry-run # 只校验不落盘
    python scripts/admin/restore_db.py --list                       # 列出可用备份
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
DEFAULT_DB = os.path.join(_BACKEND, "data", "question_bank.db")
DEFAULT_BAK_DIR = os.path.join(_BACKEND, "data", "backups")


def _fmt_size(n: int) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if v < 1024 or unit == "GB":
            return f"{n} B" if unit == "B" else f"{v:.2f} {unit}"
        v /= 1024.0
    return str(n)


def _verify(path: str) -> tuple[bool, str]:
    if not os.path.exists(path):
        return False, f"文件不存在: {path}"
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        return False, f"无法作为 SQLite 打开: {e}"
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


def _snapshot_current(db: str) -> str | None:
    """覆盖前给当前主库留一份可回退的快照（同样走 sqlite3.backup()）。"""
    if not os.path.exists(db):
        return None
    out_dir = os.path.join(os.path.dirname(db), "backups")
    os.makedirs(out_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(out_dir, f"{os.path.splitext(os.path.basename(db))[0]}"
                                f"_pre_restore_{stamp}.db")
    src = sqlite3.connect(db, timeout=30.0)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    except sqlite3.Error as e:
        print(f"[restore] ⚠️  覆盖前快照失败({e})，仍继续恢复。", file=sys.stderr)
        return None
    finally:
        src.close()
    return dest


def _probe_lock(path: str) -> str | None:
    """探测文件是否被占用。Windows 下被其他进程打开的文件无法改名/删除，
    此时恢复必然失败，应在动手之前就给出可操作的提示。

    做法是改到临时名再改回来 —— 非破坏性，且比 open() 更可靠：
    Python 的 open() 默认允许多进程共享，探测不出占用。
    返回错误描述，未被占用则返回 None。
    """
    if not os.path.exists(path):
        return None
    probe = path + ".lockprobe"
    try:
        os.rename(path, probe)
    except OSError as e:
        return f"{os.path.basename(path)} 被其他进程占用（{e}）"
    try:
        os.rename(probe, path)
    except OSError as e:
        return f"{os.path.basename(path)} 探测后改名回失败（{e}）"
    return None


def restore(db: str, backup: str, yes: bool, dry_run: bool) -> int:
    db = os.path.abspath(db)
    backup = os.path.abspath(backup)

    print(f"[restore] 备份源 : {backup}")
    if os.path.exists(backup):
        print(f"[restore]          {_fmt_size(os.path.getsize(backup))}")
    print(f"[restore] 目标库 : {db}")

    # ── 闸 1：备份文件必须自身完好 ──────────────────────────
    ok, msg = _verify(backup)
    print(f"[restore] 备份校验: {msg}")
    if not ok:
        print("[restore] 拒绝恢复：备份文件不可用", file=sys.stderr)
        return 2
    if os.path.abspath(backup) == db:
        print("[restore] 拒绝恢复：备份与目标库是同一文件", file=sys.stderr)
        return 2

    for side in ("-wal", "-shm"):
        p = db + side
        if os.path.exists(p):
            print(f"[restore] 将清理 {os.path.basename(p)}"
                  f"（{_fmt_size(os.path.getsize(p))}）")

    if dry_run:
        print("[restore] --dry-run：校验通过，未做任何改动")
        return 0

    # ── 闸 3：显式确认 ──────────────────────────────────────
    if not yes:
        print("\n即将覆盖主库并清理 WAL。此操作不可撤销（但当前状态会被自动快照）。")
        ans = input("确认恢复？输入 yes 继续: ").strip().lower()
        if ans != "yes":
            print("[restore] 已取消")
            return 1

    # ── 闸 4：占用预检 ───────────────────────────────────────
    # 必须在建快照之前做。Windows 下被其他进程打开的文件无法删除，
    # 与其先建一份注定用不上的快照再失败，不如当场说清原因。
    blocked = [m for m in (_probe_lock(db), _probe_lock(db + "-wal"),
                           _probe_lock(db + "-shm")) if m]
    if blocked:
        print("[restore] 拒绝恢复：目标库正被占用", file=sys.stderr)
        for m in blocked:
            print(f"[restore]   - {m}", file=sys.stderr)
        print("[restore] 请先停止正在运行的应用 / 爬虫进程，再执行恢复。", file=sys.stderr)
        print("[restore] 不停进程直接恢复会破坏 SQLite 的锁语义。", file=sys.stderr)
        return 3

    # ── 闸 2：覆盖前自动快照当前状态 ────────────────────────
    pre = _snapshot_current(db)
    if pre:
        print(f"[restore] 覆盖前快照: {pre}")

    # ── 顺序要紧：先删侧车，再落主库 ────────────────────────
    # 反过来做，旧 -wal 会被 SQLite 当作增量重放到新主库，导致损坏。
    removed = []
    for side in ("-wal", "-shm"):
        p = db + side
        if os.path.exists(p):
            try:
                os.remove(p)
                removed.append(os.path.basename(p))
            except OSError as e:
                print(f"[restore] 删除 {p} 失败（可能刚被其他进程占用）: {e}",
                      file=sys.stderr)
                print(f"[restore] 主库尚未被覆盖，数据安全。"
                      f"请停止应用后重试。", file=sys.stderr)
                return 1
    if removed:
        print(f"[restore] 已删除: {', '.join(removed)}")
    else:
        print("[restore] 侧车: 快照阶段已由 SQLite 自动 checkpoint 清除，"
              "无需额外删除")

    try:
        shutil.copyfile(backup, db)
    except OSError as e:
        print(f"[restore] 覆盖主库失败: {e}", file=sys.stderr)
        if pre:
            print(f"[restore] 可用覆盖前快照回退: {pre}", file=sys.stderr)
        return 1

    ok, msg = _verify(db)
    print(f"[restore] 恢复后校验: {msg}")
    if not ok:
        print("[restore] ❌ 恢复后库未通过完整性校验", file=sys.stderr)
        if pre:
            print(f"[restore] 请立即用覆盖前快照回退: {pre}", file=sys.stderr)
        return 1

    print(f"[restore] ✅ 恢复完成  {_fmt_size(os.path.getsize(db))}")
    if pre:
        print(f"[restore] 回退本次恢复: python scripts/admin/restore_db.py --backup \"{pre}\" --yes")
    return 0


def list_backups(d: str) -> int:
    if not os.path.isdir(d):
        print(f"[restore] 目录不存在: {d}", file=sys.stderr)
        return 2
    files = sorted((f for f in os.listdir(d)
                    if f.endswith(".db") and not f.endswith(".log")),
                   reverse=True)
    if not files:
        print(f"[restore] {d} 下没有 .db 备份")
        return 0
    print(f"{'文件':<58} {'体积':>12}")
    for f in files:
        p = os.path.join(d, f)
        print(f"{f:<58} {_fmt_size(os.path.getsize(p)):>12}")
    print(f"\n共 {len(files)} 份。data/*.bak* 的 41 份历史备份不在此目录内，"
          f"本脚本不会触碰它们。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="SQLite 恢复 / 回滚")
    ap.add_argument("--backup", help="备份文件路径")
    ap.add_argument("--db", default=DEFAULT_DB, help="目标主库路径")
    ap.add_argument("--yes", action="store_true", help="跳过交互确认")
    ap.add_argument("--dry-run", action="store_true", help="只校验不落盘")
    ap.add_argument("--list", action="store_true", help="列出可用备份")
    ap.add_argument("--bak-dir", default=DEFAULT_BAK_DIR, help="备份目录")
    a = ap.parse_args()

    if a.list:
        return list_backups(a.bak_dir)
    if not a.backup:
        ap.error("需要 --backup <文件>，或用 --list 查看可用备份")
    return restore(a.db, a.backup, a.yes, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())