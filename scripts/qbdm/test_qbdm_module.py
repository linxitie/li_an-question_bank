# -*- coding: utf-8 -*-
"""QBDM 模块层（台账 + CLI）的回归测试。

守四件事：
  1) 台账里的模块与 `api_surface.json` 对得上（25 模块 = 343 端点，且一个 API 文件只归一个模块）；
  2) `module` 命令能按 id / 编号 / 名称定位到同一模块，未知模块必须非 0 退出；
  3) 门禁命令里出现的脚本必须真实存在（防止文档写了不存在的门禁）；
  4) 台账生成器可重复运行且结果稳定（去掉生成时间后可比）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_module_ledger as gen  # noqa: E402
import qbdm  # noqa: E402


def _ledger():
  return json.loads(qbdm.LEDGER.read_text(encoding='utf-8'))


def test_ledger_matches_api_surface():
  ledger = gen.build()
  assert ledger['totals']['modules'] == 25
  assert ledger['totals']['endpoints'] == 343
  assert ledger['totals']['api_files_unassigned'] == []


def test_api_file_belongs_to_one_module_only():
  seen = {}
  for module in gen.MODULES:
    for name in module['files']:
      assert name not in seen, f'{name} 同时归属 {seen[name]} 与 {module["id"]}'
      seen[name] = module['id']


def test_module_lookup_by_id_no_and_name(capsys):
  ledger = _ledger()
  by_id = qbdm._find_module(ledger, 'wrongbook')
  by_no = qbdm._find_module(ledger, '⑥')
  by_name = qbdm._find_module(ledger, '错题集')
  assert by_id and by_id['id'] == by_no['id'] == by_name['id'] == 'wrongbook'
  assert qbdm.main(['module', 'wrongbook']) == 0
  out = capsys.readouterr().out
  assert '[模块] ⑥ 错题集' in out
  assert 'D1' in out and 'O1' in out and 'T1' in out


def test_unknown_module_fails():
  assert qbdm.main(['module', 'no-such-module']) == 1


def test_modules_lists_all(capsys):
  assert qbdm.main(['modules']) == 0
  out = capsys.readouterr().out
  assert '25 个模块' in out
  assert '题目导入' in out


def test_module_json_is_machine_readable(capsys):
  assert qbdm.main(['module', 'practice', '--json']) == 0
  data = json.loads(capsys.readouterr().out)
  assert data['id'] == 'practice'
  assert data['endpoint_count'] > 0


def test_gate_scripts_exist():
  repo = qbdm.REPO_ROOT
  for module in gen.MODULES:
    names = {'id': module['id'], 'endpoint_count': 1, 'pages': ['x'], 'test_command': ''}
    for cmd in qbdm._module_gates(names):
      for part in cmd.split():
        if part.endswith('.py'):
          assert (repo / part).exists(), f'门禁脚本不存在：{part}'


def test_build_is_reproducible():
  first = gen._normalize(gen.build())
  second = gen._normalize(gen.build())
  assert first == second
