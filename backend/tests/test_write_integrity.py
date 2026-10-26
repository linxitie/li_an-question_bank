# -*- coding: utf-8 -*-
"""CI-1..CI-6 行为测试：能抓新增缺陷，又不会把已登记存量当失败。"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

AUDIT_DIR = Path(__file__).resolve().parents[1] / 'scripts' / 'audit'
if str(AUDIT_DIR) not in sys.path:
  sys.path.insert(0, str(AUDIT_DIR))

import content_integrity as ci  # noqa: E402


SCHEMA = """
create table question_bank (
  question_id integer primary key, type_id integer not null default 1,
  question_content text, answer text, answer_analysis text, options text,
  group_id integer not null default 0, sort_order integer, question_level integer,
  question_number text);
create table question_groups (
  id integer primary key, group_type text, subject text, shared_content text,
  shared_content_images text);
create table question_image (
  image_id integer primary key, question_id integer, image_path text,
  image_type text, image_order integer);
create table question_knowledge (
  id integer primary key, question_id integer, knowledge_point_id integer);
"""


@pytest.fixture()
def con():
  conn = sqlite3.connect(':memory:')
  conn.executescript(SCHEMA)
  conn.execute("insert into question_groups values (1, 'material', '公专', '材料A', '[]')")
  conn.execute("insert into question_bank (question_id, group_id, question_content) values (1, 1, '题1')")
  yield conn
  conn.close()


def test_ci1_known_orphan_warns_but_new_one_fails(con):
  con.execute("insert into question_bank (question_id, group_id) values (99, 42)")
  result = ci.check_group_refs(con)
  assert result['status'] == 'FAIL'
  assert any('99' in line for line in result['failures'])
  assert any('不存在' in line for line in result['failures'])

  con2 = sqlite3.connect(':memory:')
  con2.executescript(SCHEMA)
  con2.execute("insert into question_groups (id, subject, shared_content) values (11, '公专', '材料')")
  known = ci.check_group_refs(con2)
  con2.close()
  assert known['status'] == 'WARN'
  assert known['orphan_groups'] == [11]


def test_ci2_empty_group_is_failure(con):
  con.execute("insert into question_groups (id, subject, shared_content, shared_content_images) "
              "values (7, '公专', '', '[]')")
  result = ci.check_group_content(con)
  assert result['status'] == 'FAIL'
  assert any('7' in line for line in result['failures'])


def test_ci3_missing_image_is_tolerated_until_baseline(con):
  for image_id in range(1, 14):
    con.execute("insert into question_image (image_id, question_id, image_path) "
                "values (?, 1, '/static/questions/definitely-missing.png')", (image_id,))
  assert ci.check_images(con)['status'] == 'WARN'

  con.execute("insert into question_image (image_id, question_id, image_path) "
              "values (14, 1, '/static/questions/definitely-missing.png')")
  assert ci.check_images(con)['status'] == 'FAIL'


def test_ci4_unresolved_tokens_above_baseline_fail(con):
  con.execute("update question_groups set shared_content = '[IMAGE:ghost_1]' where id = 1")
  assert ci.check_tokens(con)['status'] == 'WARN'

  tokens = ' '.join(f'[IMAGE:ghost_{i}]' for i in range(2, 13))
  con.execute("update question_groups set shared_content = ? where id = 1", (tokens,))
  assert ci.check_tokens(con)['status'] == 'FAIL'


def test_ci5_essay_on_non_essay_group_fails(con):
  con.execute("insert into question_bank (question_id, type_id, group_id) values (2, 14, 1)")
  result = ci.check_essay_groups(con)
  assert result['status'] == 'FAIL'
  assert any('非申论组' in line for line in result['failures'])


def test_ci6_detects_content_drift(con):
  baseline = {'fingerprints': {t: ci.gc_previews.fingerprint(con, t)
                               for t in ci.gc_previews.FINGERPRINT_TABLES}}
  assert ci.check_fingerprint(con, baseline)['status'] == 'PASS'

  con.execute("update question_bank set question_content = '题1改' where question_id = 1")
  drifted = ci.check_fingerprint(con, baseline)
  assert drifted['status'] == 'FAIL'
  assert any('question_bank' in line for line in drifted['failures'])
