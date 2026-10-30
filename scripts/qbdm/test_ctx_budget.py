# -*- coding: utf-8 -*-
"""ctx_budget 的回归测试：解析、禁入拦截、预算判定。

为什么只测这三件事：
    脚本的其余部分是 IO 与打印，真正会静默出错的是"切片解析错了"和"超预算却放行"，
    这两类错误会让 Z4 指标失去意义。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ctx_budget  # noqa: E402


def test_parse_item_with_range():
  path, start, end = ctx_budget._parse_item('backend/app/main.py:600-643')
  assert path == 'backend/app/main.py'
  assert (start, end) == (600, 643)


def test_parse_item_windows_abs_path_without_range():
  raw = 'D:\\砺安题库\\砺安题库\\AGENTS.md'
  path, start, end = ctx_budget._parse_item(raw)
  assert path == raw
  assert start is None and end is None


def test_forbidden_prefix_blocked():
  item = ctx_budget.inspect('题库/', os.getcwd())
  assert item.kind == 'forbidden'
  assert item.tokens == 0


def test_over_budget_fails(tmp_path):
  target = tmp_path / 'big.py'
  target.write_text('x = 1\n' * 40000, encoding='utf-8')
  log = tmp_path / 'ledger.md'
  code = ctx_budget.main(['--tier', 'T0', '--log', str(log), str(target)])
  assert code == 1
  assert 'FAIL' in log.read_text(encoding='utf-8')


def test_slice_pass(tmp_path):
  target = tmp_path / 'small.py'
  target.write_text('a = 1\nb = 2\nc = 3\n', encoding='utf-8')
  code = ctx_budget.main(['--tier', 'T2', f'{target}:1-2'])
  assert code == 0
