#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据库清单审计（终态架构 §16 / L7-10）。

为什么需要它：历史上出现过 0 字节库、worktree 复制库与备份库混放。
手工 `ls` 无法区分「在用 / 备份 / 空壳」，误删一次就是 R8 事故。
本脚本只读：扫描、分类、估算体积、输出报告，永不删除或修改任何库文件。

分类口径（优先级从上到下）：
  active     当前 SQLITE_PATH 指向的库（唯一在用）
  protected  备份 / 守卫快照 / audit 目录下的库（R8）
  empty      0 字节
  no_tables  有字节但 0 张表
  orphan     其余未被引用的库

用法：
  python backend/scripts/audit/db_inventory.py                  # 报告 + 汇总
  python backend/scripts/audit/db_inventory.py --sizes          # 附 top10 体积估算
  python backend/scripts/audit/db_inventory.py --check          # 违规退出码 1
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'backend'
DEFAULT_DB = BACKEND_DIR / 'data' / 'question_bank.db'
REPORT_PATH = BACKEND_DIR / 'data' / 'reports' / 'db_inventory.json'
DB_SUFFIXES = ('.db', '.sqlite', '.sqlite3')
SKIP_DIRS = {'.git', 'node_modules', 'dist', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pytest_cache'}
# 目录名命中即视为备份/快照资产（R8：只报告不删）
PROTECTED_DIR_NAMES = {'backups', 'snapshots', 'audit'}


def active_db_path() -> Path:
  """与 app.foundation.config.sqlite_path() 同口径：相对路径按 backend/ 解析。"""
  raw = os.environ.get('SQLITE_PATH') or str(DEFAULT_DB)
  path = Path(raw)
  if not path.is_absolute():
    path = BACKEND_DIR / path
  return path.resolve()


def iter_db_files(root: Path) -> list[Path]:
  """递归找库文件；跳过依赖与构建目录，避免扫进 node_modules。"""
  found: list[Path] = []
  for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for name in filenames:
      if name.endswith(DB_SUFFIXES):
        found.append(Path(dirpath) / name)
  return sorted(found)


def is_protected(path: Path) -> bool:
  """备份、快照、守卫副本均受 R8 保护；目录名或文件名命中即算。"""
  resolved = path.resolve()
  if any(p.name.lower() in PROTECTED_DIR_NAMES
         or p.name.lower().startswith(('backup', 'snapshot', 'pre_'))
         for p in resolved.parents):
    return True
  name = path.name.lower()
  if name.startswith(('backup', 'pre_')) or '.bak' in name:
    return True
  return 'guard_snapshot' in name or 'snapshot' in name


def _connect_ro(path: Path) -> sqlite3.Connection:
  return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)


def inspect_db(path: Path) -> dict:
  """只读打开；坏库不抛出，返回 error 供报告如实记录。"""
  info = {'bytes': path.stat().st_size, 'tables': None, 'rows': None, 'error': None}
  try:
    con = _connect_ro(path)
    try:
      info['tables'] = con.execute(
        "select count(*) from sqlite_master where type='table' and name not like 'sqlite_%'"
      ).fetchone()[0]
      if info['tables']:
        names = [r[0] for r in con.execute(
          "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
        )]
        total = 0
        for name in names:
          total += con.execute(f'select count(*) from "{name}"').fetchone()[0]
        info['rows'] = total
    finally:
      con.close()
  except sqlite3.Error as exc:
    info['error'] = f'{type(exc).__name__}: {exc}'
  return info


def classify(path: Path, active: Path, info: dict) -> str:
  if path.resolve() == active:
    return 'active'
  if is_protected(path):
    return 'protected'
  if info['bytes'] == 0:
    return 'empty'
  if info['tables'] == 0:
    return 'no_tables'
  return 'orphan'


def table_sizes(path: Path, top: int = 10) -> dict:
  """按「列数据字节」统计表体积（本机 sqlite 未编译 DBSTAT，无法读页归属）。

  为什么不用 rootpage 间隔：大字段的溢出页会落在别的对象区间里，
  实测会把 5 MB 表报成 43 MB。这里逐表对每列 CAST AS BLOB 后求和，
  得到可复现、可比较的内容字节（不含索引与页开销），用于识别体量主因。
  """
  con = _connect_ro(path)
  try:
    names = [r[0] for r in con.execute(
      "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
    )]
    sizes: dict[str, int] = {}
    for name in names:
      cols = [r[1] for r in con.execute(f'pragma table_info("{name}")')]
      if not cols:
        continue
      expr = ' + '.join(f'coalesce(length(cast("{c}" as blob)), 0)' for c in cols)
      total = con.execute(f'select coalesce(sum({expr}), 0) from "{name}"').fetchone()[0]
      sizes[name] = int(total or 0)
  finally:
    con.close()
  ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:top]
  return {'method': 'content-bytes', 'total_bytes': sum(sizes.values()),
          'top': [{'table': t, 'bytes': b} for t, b in ranked]}


def collect(root: Path, with_sizes: bool = False) -> dict:
  active = active_db_path()
  items = []
  for path in iter_db_files(root):
    info = inspect_db(path)
    category = classify(path, active, info)
    item = {
      'path': str(path),
      'relative': str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
      'category': category,
      'in_worktree': '.worktrees' in path.parts,
      **info,
    }
    if with_sizes and category == 'active' and info['tables']:
      item['sizes'] = table_sizes(path)
    items.append(item)
  counts: dict[str, int] = {}
  for item in items:
    counts[item['category']] = counts.get(item['category'], 0) + 1
  return {
    'scanned_at': datetime.now().strftime('%Y%m%d_%H%M%S'),
    'root': str(root), 'active': str(active),
    'total': len(items), 'counts': counts, 'items': items,
  }


def check(report: dict) -> tuple[list[str], list[str]]:
  """返回 (failures, warnings)。worktree 只提示，主树 0 字节/孤儿判失败。"""
  failures, warnings = [], []
  for item in report['items']:
    if item['bytes'] == 0:
      (warnings if item['in_worktree'] else failures).append(f"0 字节库：{item['relative']}")
    if item['category'] == 'orphan':
      (warnings if item['in_worktree'] else failures).append(f"未被引用的库：{item['relative']}")
  if not report['items']:
    failures.append('未扫描到任何库文件')
  return failures, warnings


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description='数据库清单审计（只读）')
  parser.add_argument('--root', default=str(REPO_ROOT))
  parser.add_argument('--sizes', action='store_true', help='估算在用/备份库的 top10 表体积')
  parser.add_argument('--check', action='store_true', help='违规时退出码 1')
  parser.add_argument('--report', default=str(REPORT_PATH))
  args = parser.parse_args(argv)

  report = collect(Path(args.root).resolve(), with_sizes=args.sizes)
  failures, warnings = check(report)
  report['check'] = {'ok': not failures, 'failures': failures, 'warnings': warnings}
  out = Path(args.report)
  out.parent.mkdir(parents=True, exist_ok=True)
  out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

  print(f"库文件 {report['total']} 个：{report['counts']}")
  for name in ('active', 'protected', 'empty', 'no_tables', 'orphan'):
    for item in report['items']:
      if item['category'] != name:
        continue
      mb = item['bytes'] / 1024 / 1024
      print(f"  [{name}] {item['relative']} {mb:.2f} MB tables={item['tables']}")
  if args.sizes:
    for item in report['items']:
      if 'sizes' not in item:
        continue
      print(f"\n{item['relative']} top10（数据字节，方法 {item['sizes']['method']}）：")
      for row in item['sizes']['top']:
        print(f"  {row['table']:<32} {row['bytes'] / 1024 / 1024:>8.2f} MB")
  print(f"报告：{out}")
  for line in failures:
    print(f"FAIL {line}", file=sys.stderr)
  for line in warnings:
    print(f"WARN {line}")
  if args.check and failures:
    return 1
  print('检查通过' if args.check else '完成')
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
