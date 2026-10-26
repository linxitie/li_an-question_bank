#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QBDM 模式入口 —— 一个命令把"我现在是谁、该跑什么门禁"说清楚。

为什么要有它：
    QBDM 的九角色与门禁矩阵写在文档里，但人不会每次都翻文档。
    本 CLI 把矩阵变成可执行清单：print 模式看"该跑什么"，--run 模式真跑并回退出码。
    v2 增加模块层：`modules` / `module <id>` 从台账读出该模块的端点/页面/测试，
    并打印"设计 D / 优化 O / 测试 T"三段式清单（与 题库设计模式_v2.md 同源）。

用法：
    python scripts/qbdm/qbdm.py role BE          # 看某角色能改什么、被什么否决
    python scripts/qbdm/qbdm.py gate --role BE   # 看该角色该跑哪些门禁（不执行）
    python scripts/qbdm/qbdm.py gate --role QA --run   # 真跑
    python scripts/qbdm/qbdm.py modules          # 列出 25 个功能模块
    python scripts/qbdm/qbdm.py module wrongbook # 单模块作战清单
    python scripts/qbdm/qbdm.py status           # 检查模式资产是否齐全
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / 'docs/design/题库模块台账_v1.json'
DESIGN_MODE = REPO_ROOT / 'scripts/qbdm/design_mode.json'

# 角色卡：与 docs/superpowers/specs/题库设计模式_角色卡_v1.md 保持一致
ROLES: dict[str, dict] = {
    'ARCH': {'name': '系统架构师', 'can': '定边界/分层/依赖方向，出 ADR',
             'veto': '跨域直连、新建第 38 个 API 模块', 'gates': ['module_boundary']},
    'PM': {'name': '项目管理师', 'can': '拆任务/控范围/管分支',
           'veto': '无验收命令的任务行、一分支两件事', 'gates': []},
    'DATA': {'name': '数据建模师', 'can': '表/字段/索引/迁移/计数口径',
             'veto': '破坏 R10、无迁移加字段', 'gates': ['field_fingerprint', 'db_guard']},
    'BE': {'name': '后端建模师', 'can': '端点 + ORM',
           'veto': '裸 SQL、跨域 import api 层', 'gates': ['api_contract', 'module_boundary']},
    'API': {'name': '接口建模师', 'can': '保 343 端点契约',
            'veto': '未批准的端点增删改', 'gates': ['api_contract']},
    'FE': {'name': '前端建模师', 'can': '只改 <script>，走 VTJ 工具',
           'veto': '直改 <template>、raw 页同步', 'gates': ['frontend_contract']},
    'SEC': {'name': '网络安全检测与保障员', 'can': '凭据/越权/注入/脱敏',
            'veto': '密钥入 .md/源码/提交信息', 'gates': ['secrets']},
    'QA': {'name': '系统测试与问题反馈员', 'can': '用命令证明能/不能用',
           'veto': '无证据的"完成"声明', 'gates': ['quick', 'sweep']},
    'DOC': {'name': '归档与索引官', 'can': '落盘/双写/更新索引',
            'veto': '只展示不落盘', 'gates': []},
}

# 模块三段式作战清单：与 docs/superpowers/specs/题库设计模式_v2.md §2 同源。
# 放这里是为了「不翻文档也能看到该检查什么」；两处不一致时以 v2 文档为准。
PLAYBOOK: dict[str, list[tuple[str, str]]] = {
    'design': [
        ('D1', '边界：本模块拥有哪些端点/页面/事件；跨模块只走契约与事件，不直接 import'),
        ('D2', '数据：表/字段/索引变更走迁移单；计数口径引用领域词表 D1–D6，不另写 WHERE'),
        ('D3', '契约：端点只增不改；请求/响应字段与前端调用点逐项对齐'),
        ('D4', '事件：只发本模块拥有的 trigger_type；add-only；定义幂等键'),
        ('D5', '权限：每个端点鉴权依赖 + 角色（student/teacher/admin）+ 设备端'),
        ('D6', '三端：PC/平板/手机入口与降级；平板复用手机页，不新建副本（R12）'),
        ('D7', '状态：空/加载/错误三态齐全；失败可重试，不留在半死状态'),
        ('D8', '失败与回滚：写操作的事务边界；失败不留半条数据'),
        ('D9', '可观测：审计字段/错误码可区分；日志不泄露敏感值'),
        ('D10', '不做什么：显式排除项，防范围蔓延'),
    ],
    'optimize': [
        ('O1', '性能：列表分页/索引/N+1；万级题量下的 P95 与首屏'),
        ('O2', '一致性：三端计数同源；与 test_three_end_counts.py 口径对齐'),
        ('O3', '体验：骨架屏、空态文案、错误可恢复；不做无声失败'),
        ('O4', '安全：IDOR、越权、上传/解析注入、输出脱敏'),
        ('O5', '事件幂等：重复提交/重放不重复发事件、不重复加金币'),
        ('O6', '冗余：合并重复校验与重复请求，删死代码（不顺手改无关模块）'),
        ('O7', '三端复用：不复制平板/手机页；共享页只由①域改'),
        ('O8', '可维护：单函数 ≤60 行、单文件 ≤800 行；常量不硬编码'),
    ],
    'test': [
        ('T1', '契约：gate_l4_api_contract 通过，端点数 343 或含已批准增量'),
        ('T2', '边界：check_module_boundary 通过，无跨域 import'),
        ('T3', '数据：db_tables.json 差异可解释，迁移有 dry-run'),
        ('T4', '域测：pytest 跑本模块候选测试，FAIL 不结案'),
        ('T5', '前端：store spec 覆盖空/错/成功；vitest 通过'),
        ('T6', '页面：gate_l5_frontend_contract 通过，VTJ 设计器可开'),
        ('T7', '三端手工：按域卡 §7 清单逐项，记录设备与结果'),
        ('T8', '回归：事件链 E1–E13 抽查 + 幂等重放；跨模块改动加一致性用例'),
    ],
}

# 个别模块的专属附加门禁：导入链是唯一有 L1/L1h/L3 三层解析门禁的模块。
EXTRA_GATES: dict[str, list[str]] = {
    'question-import': [
        'python backend/scripts/gates/gate_l1_parser.py',
        'python backend/scripts/gates/gate_l1h_composite_material.py',
        'python backend/scripts/gates/gate_l3_ingest.py',
    ],
}

GATES: dict[str, list[str]] = {
    'quick': ['python', 'backend/scripts/gates/gate_all.py', '--quick'],
    'l0': ['python', 'backend/scripts/gates/gate_l0_redlines.py'],
    'field_fingerprint': ['python', 'backend/scripts/gates/gate_l1g_field_fingerprint.py'],
    'parser': ['python', 'backend/scripts/gates/gate_l1_parser.py'],
    'composite_material': ['python', 'backend/scripts/gates/gate_l1h_composite_material.py'],
    'matching': ['python', 'backend/scripts/gates/gate_l2_matching.py'],
    'ingest': ['python', 'backend/scripts/gates/gate_l3_ingest.py'],
    'api_contract': ['python', 'backend/scripts/gates/gate_l4_api_contract.py'],
    'frontend_contract': ['python', 'backend/scripts/gates/gate_l5_frontend_contract.py'],
    'module_boundary': ['python', 'backend/scripts/gates/check_module_boundary.py'],
    'secrets': ['python', 'backend/scripts/gates/check_secrets.py'],
    'db_guard': ['python', '-m', 'pytest', 'backend/tests/test_db_guard.py', '-q'],
    'sweep': ['python', 'scripts/qbdm/test_sweep.py', '--suite', 'backend/tests'],
}

# 模式资产清单：缺一项，模式就不完整
ARTIFACTS = [
    ('docs/superpowers/specs/题库设计模式_v1.md', '权威全文（角色/流程/门禁）'),
    ('docs/superpowers/specs/题库设计模式_角色卡_v1.md', '热加载角色卡'),
    ('docs/superpowers/specs/题库设计模式_v2.md', '模块层全文（设计/优化/测试）'),
    ('docs/superpowers/specs/题库设计模式_模块作战卡_v1.md', '热加载模块卡'),
    ('docs/superpowers/specs/题库设计模式_v3.md', '「题库设计」模式（会话执行版）'),
    ('scripts/qbdm/design_mode.json', '模式绑定（角色/技能/MCP/门禁）'),
    ('docs/design/题库模块台账_v1.md', '模块台账（人读）'),
    ('docs/design/题库模块台账_v1.json', '模块台账（机读）'),
    ('docs/design/题库领域词表_v1.md', '领域词表'),
    ('scripts/qbdm/ctx_budget.py', '装载预算闸'),
    ('scripts/qbdm/test_sweep.py', '逐文件测试扫描器'),
    ('scripts/qbdm/gen_module_ledger.py', '台账生成器'),
    ('.opencode/skills/qbdm-role-switch/SKILL.md', '项目技能（不入 Git）'),
    ('.opencode/skills/qbdm-design-mode/SKILL.md', '「题库设计」模式技能（不入 Git）'),
]


def _print_role(code: str) -> int:
    role = ROLES.get(code.upper())
    if not role:
        print(f'未知角色 {code}。可选：{", ".join(ROLES)}')
        return 1
    print(f'[ROLE] {code.upper()} {role["name"]}')
    print(f'  能做：{role["can"]}')
    print(f'  否决：{role["veto"]}')
    print(f'  门禁：{" / ".join(role["gates"]) or "无（流程类角色）"}')
    return 0


def _gate_commands(code: str) -> tuple[list[str], int]:
    role = ROLES.get(code.upper())
    if not role:
        print(f'未知角色 {code}。可选：{", ".join(ROLES)}')
        return [], 1
    return [g for g in role['gates']], 0


def _load_ledger() -> dict | None:
    if not LEDGER.exists():
        print(f'缺台账：{LEDGER}（先运行 python scripts/qbdm/gen_module_ledger.py）')
        return None
    return json.loads(LEDGER.read_text(encoding='utf-8'))


def _find_module(ledger: dict, key: str) -> dict | None:
    k = key.strip().lower()
    for m in ledger['modules']:
        if k in {m['id'].lower(), m['no'], m['name'].lower()}:
            return m
    for m in ledger['modules']:
        if k in m['id'].lower() or k in m['name'].lower():
            return m
    return None


def _module_gates(module: dict) -> list[str]:
    cmds = ['python backend/scripts/gates/gate_all.py --quick']
    if module['endpoint_count']:
        cmds.append('python backend/scripts/gates/gate_l4_api_contract.py')
        cmds.append('python backend/scripts/gates/check_module_boundary.py')
    cmds += EXTRA_GATES.get(module['id'], [])
    if module['pages']:
        cmds.append('python backend/scripts/gates/gate_l5_frontend_contract.py')
    if module['test_command']:
        cmds.append(module['test_command'])
    return cmds


def _print_modules(ledger: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(ledger, ensure_ascii=False, indent=2))
        return 0
    t = ledger['totals']
    print(f'QBDM 模块台账 v1｜{t["modules"]} 个模块｜{t["endpoints"]} 端点｜'
          f'生成于 {ledger["generated_at"]}')
    for m in ledger['modules']:
        tests = f'{len(m["tests_registered"])}/{len(m["tests_candidates"])}'
        print(f'  {m["no"]} {m["name"]}（{m["id"]}）｜{m["scope"]}｜端点 {m["endpoint_count"]}'
              f'｜页面 {len(m["pages"])}｜测试 {tests}｜{m["status"]}')
    if t['card_gaps']:
        print(f'  ! 已实现但域卡空表：{"、".join(t["card_gaps"])}（先补域卡再开工）')
    if t['modules_without_tests']:
        print(f'  ! 已实现但无测试线索：{"、".join(t["modules_without_tests"])}')
    print('用法：python scripts/qbdm/qbdm.py module <id> 查看单模块作战清单')
    return 0


def _print_module(module: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(module, ensure_ascii=False, indent=2))
        return 0
    print(f'[模块] {module["no"]} {module["name"]}（{module["id"]}）')
    print(f'[范围] {module["scope"]}｜状态：{module["status"]}')
    if module['card']:
        state = '已填' if module['card_filled'] else '空表，开工前先补页面/端点/测试'
        print(f'[域卡] {module["card"]}（{state}）')
    print(f'[端点] {module["endpoint_count"]} 个｜域 {", ".join(module["api_domains"]) or "无"}'
          f'｜前缀 {", ".join(module["endpoint_prefixes"]) or "无"}')
    print(f'[页面] {len(module["pages"])} 个')
    for page in module['pages']:
        print(f'  - {page}')
    print(f'[测试] 登记 {len(module["tests_registered"])}｜候选 {len(module["tests_candidates"])}'
          '（候选需人工确认）')
    for test in (module['tests_registered'] + module['tests_candidates'])[:8]:
        print(f'  - {test}')
    print('[门禁]')
    for cmd in _module_gates(module):
        print(f'  - {cmd}')
    for key, title in [('design', '设计 D1–D10'), ('optimize', '优化 O1–O8'),
                       ('test', '测试 T1–T8')]:
        print(f'[{title}]')
        for code, text in PLAYBOOK[key]:
            print(f'  {code} {text}')
    return 0


def _load_design_mode() -> dict | None:
    if not DESIGN_MODE.exists():
        print(f'缺模式绑定：{DESIGN_MODE}')
        return None
    return json.loads(DESIGN_MODE.read_text(encoding='utf-8'))


def _print_roles(mode: dict) -> None:
    print('[九角色 × dsh × 技能]')
    for code, role in mode['roles'].items():
        skills = ' / '.join(role['skills']) or '无'
        print(f'  {code:5} {role["name"]:<10} {role["dsh"]:<16} 技能：{skills}')


def _print_design(mode: dict, state_key: str, module: dict | None, as_json: bool,
                  with_roles: bool) -> int:
    state = mode['states'][state_key]
    payload = {
        'mode': mode['mode'],
        'version': mode['version'],
        'state': state_key,
        'module': module,
        'steps': state['steps'],
        'mcp_redlines': mode['mcp']['redlines'],
        'notes': mode['notes'],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f'[模式] 题库设计 {mode["version"]}｜默认标准模式｜可升级：创造 / PTC')
    if module:
        print(f'[模块] {module["no"]} {module["name"]}（{module["id"]}）｜'
              f'端点 {module["endpoint_count"]}｜页面 {len(module["pages"])}｜'
              f'测试 {len(module["tests_registered"])}/{len(module["tests_candidates"])}')
    else:
        print('[模块] 未指定（加模块 id 可带出端点/页面/测试事实）')
    print(f'[状态] {state["name"]}：{state["goal"]}')
    print(f'[步骤 {len(state["steps"])}]')
    for step in state['steps']:
        print(f'  {step["id"]} {"+".join(step["roles"])}  {step["action"]}')
        if step['skills']:
            print(f'      技能：{" / ".join(step["skills"])}')
        if step['mcp']:
            print(f'      MCP ：{" / ".join(step["mcp"])}')
        print(f'      产出：{step["output"]}')
        print(f'      门禁：{step["gate"]}')
        print(f'      退出：{step["exit"]}')
    print('[MCP 红线]')
    for line in mode['mcp']['redlines']:
        print(f'  - {line}')
    print('[注意事项]')
    for line in mode['notes']:
        print(f'  - {line}')
    if with_roles:
        _print_roles(mode)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description='QBDM 模式入口（角色 / 门禁 / 资产自检）')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_role = sub.add_parser('role', help='查看某角色的权限与门禁')
    p_role.add_argument('code')

    p_gate = sub.add_parser('gate', help='列出（或执行）该角色应跑的门禁')
    p_gate.add_argument('--role', required=True)
    p_gate.add_argument('--run', action='store_true', help='真正执行；默认只打印')
    p_gate.add_argument('--repo', default='.')

    sub.add_parser('status', help='检查 QBDM 资产是否齐全')

    p_modules = sub.add_parser('modules', help='列出 25 个功能模块（读台账）')
    p_modules.add_argument('--json', action='store_true', help='输出台账 JSON')

    p_module = sub.add_parser('module', help='打印单模块作战清单（设计/优化/测试）')
    p_module.add_argument('id', help='模块 id / 编号 / 名称，如 wrongbook / ⑥ / 错题集')
    p_module.add_argument('--json', action='store_true', help='输出该模块的台账 JSON')

    p_design = sub.add_parser('design', help='「题库设计」模式：按状态打印多角色管线')
    p_design.add_argument('id', nargs='?', help='可选模块 id / 编号 / 名称')
    p_design.add_argument('--state', default='design',
                          choices=['design', 'test', 'optimize'],
                          help='design 设计态 / test 测试态 / optimize 优化态')
    p_design.add_argument('--roles', action='store_true', help='附九角色 × 技能对照')
    p_design.add_argument('--json', action='store_true', help='输出机器可读管线')

    args = parser.parse_args(argv)

    if args.cmd == 'role':
        return _print_role(args.code)

    if args.cmd == 'modules':
        ledger = _load_ledger()
        return _print_modules(ledger, args.json) if ledger else 1

    if args.cmd == 'module':
        ledger = _load_ledger()
        if not ledger:
            return 1
        module = _find_module(ledger, args.id)
        if not module:
            print(f'未知模块 {args.id}。可用：{", ".join(m["id"] for m in ledger["modules"])}')
            return 1
        return _print_module(module, args.json)

    if args.cmd == 'design':
        mode = _load_design_mode()
        if not mode:
            return 1
        module = None
        if args.id:
            ledger = _load_ledger()
            if not ledger:
                return 1
            module = _find_module(ledger, args.id)
            if not module:
                print(f'未知模块 {args.id}。可用：'
                      f'{", ".join(m["id"] for m in ledger["modules"])}')
                return 1
        return _print_design(mode, args.state, module, args.json, args.roles)

    if args.cmd == 'status':
        missing = 0
        print('QBDM 资产自检：')
        for path, label in ARTIFACTS:
            ok = os.path.exists(os.path.join(REPO_ROOT, path))
            missing += 0 if ok else 1
            print(f'  {"OK  " if ok else "MISS"} {path:52} {label}')
        print('结论：' + ('齐全' if not missing else f'缺 {missing} 项'))
        return 0 if not missing else 1

    names, code = _gate_commands(args.role)
    if code:
        return code
    if not names:
        print(f'{args.role.upper()} 为流程类角色，无机器门禁；请按角色卡的产出清单自检。')
        return 0

    print(f'{args.role.upper()} 的门禁（{len(names)} 项）：')
    failures = 0
    for name in names:
        cmd = GATES[name]
        printable = ' '.join(cmd)
        if not args.run:
            print(f'  - {name:20} {printable}')
            continue
        print(f'  > {printable}', flush=True)
        # 子进程必须带 UTF-8 输出编码：否则 Windows GBK 控制台下门禁脚本打印 ✅ 会抛
        # UnicodeEncodeError，被误判为 FAIL（本项目已知坑，AGENTS.md §7 已记录）
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        proc = subprocess.run(cmd, cwd=args.repo, env=env)
        print(f'    {"PASS" if proc.returncode == 0 else "FAIL"} (exit {proc.returncode})')
        failures += 0 if proc.returncode == 0 else 1
    if args.run:
        print(f'结论：{"全部通过" if not failures else f"{failures} 项失败"}')
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
