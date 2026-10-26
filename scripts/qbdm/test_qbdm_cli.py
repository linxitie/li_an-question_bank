# -*- coding: utf-8 -*-
"""qbdm CLI 的回归测试。

重点守两件事：角色->门禁的映射不能指到不存在的命令；未知角色必须非 0 退出。
（"子进程编码误判"已由 --run 的实跑手工验证，这里只测纯逻辑部分。）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import qbdm  # noqa: E402
from qbdm import GATES, ROLES, main  # noqa: E402


def test_every_role_gate_exists():
  for code, role in ROLES.items():
    for name in role['gates']:
      assert name in GATES, f'{code} 引用了未定义门禁 {name}'


def test_role_prints_known_role(capsys):
  assert main(['role', 'BE']) == 0
  out = capsys.readouterr().out
  assert '后端建模师' in out
  assert 'api_contract' in out


def test_unknown_role_fails():
  assert main(['role', 'NOPE']) == 1


def test_process_role_has_no_gate():
  assert main(['gate', '--role', 'PM']) == 0


def test_gate_listing_does_not_run(capsys):
  assert main(['gate', '--role', 'SEC']) == 0
  out = capsys.readouterr().out
  assert 'check_secrets.py' in out
  assert 'PASS' not in out  # 未加 --run 时不得执行
