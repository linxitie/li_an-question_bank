# -*- coding: utf-8 -*-
"""数据库清单：分类、worktree 降级、体积口径都可复现。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parents[1] / 'scripts' / 'audit'
if str(AUDIT_DIR) not in sys.path:
  sys.path.insert(0, str(AUDIT_DIR))

import db_inventory  # noqa: E402


def _make_db(path: Path, tables: int = 1) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  con = sqlite3.connect(path)
  for i in range(tables):
    con.execute(f'create table t{i} (id integer primary key, payload text)')
    con.execute(f"insert into t{i} (payload) values ('x')")
  con.commit()
  con.close()


def _report(root: Path) -> dict:
  return db_inventory.collect(root)


def test_classification_and_worktree_warning(tmp_path):
  active = tmp_path / 'backend' / 'data' / 'question_bank.db'
  _make_db(active)
  _make_db(tmp_path / 'backend' / 'data' / 'backups' / 'pre_x.db')
  _make_db(tmp_path / 'backend' / 'data' / 'snapshots' / 'snap.db')
  _make_db(tmp_path / 'backend' / 'data' / 'stray.db')
  empty = tmp_path / '.worktrees' / 'wt' / 'backend' / 'empty.db'
  empty.parent.mkdir(parents=True, exist_ok=True)
  empty.write_bytes(b'')

  old = db_inventory.active_db_path
  db_inventory.active_db_path = lambda: active.resolve()
  try:
    report = _report(tmp_path)
    categories = {item['relative']: item['category'] for item in report['items']}
    failures, warnings = db_inventory.check(report)
  finally:
    db_inventory.active_db_path = old

  assert categories['backend\\data\\question_bank.db'] == 'active'
  assert categories['backend\\data\\backups\\pre_x.db'] == 'protected'
  assert categories['backend\\data\\snapshots\\snap.db'] == 'protected'
  assert categories['backend\\data\\stray.db'] == 'orphan'
  assert any('stray.db' in line for line in failures)
  assert not any('empty.db' in line for line in failures)
  assert any('empty.db' in line for line in warnings)


def test_sizes_use_content_bytes(tmp_path):
  db = tmp_path / 'q.db'
  db.parent.mkdir(parents=True, exist_ok=True)
  con = sqlite3.connect(db)
  con.execute('create table big (id integer primary key, payload text)')
  con.execute('create table small (id integer primary key)')
  con.execute("insert into big (payload) values (?)", ('x' * 5000,))
  con.commit()
  con.close()

  sizes = db_inventory.table_sizes(db)
  assert sizes['method'] == 'content-bytes'
  assert sizes['top'][0]['table'] == 'big'
  assert sizes['top'][0]['bytes'] >= 5000
  assert sizes['total_bytes'] >= 5000
