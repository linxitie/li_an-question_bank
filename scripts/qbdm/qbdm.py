#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QBDM 模式入口 —— 一个命令把"我现在是谁、该跑什么门禁"说清楚。

为什么要有它：
    QBDM 的九角色与门禁矩阵写在文档里，但人不会每次都翻文档。
    本 CLI 把矩阵变成可执行清单：print 模式看"该跑什么"，--run 模式真跑并回退出码。

用法：
    python scripts/qbdm/qbdm.py role BE          # 看某角色能改什么、被什么否决
    python scripts/qbdm/qbdm.py gate --role BE   # 看该角色该跑哪些门禁（不执行）
    python scripts/qbdm/qbdm.py gate --role QA --run   # 真跑
    python scripts/qbdm/qbdm.py status           # 检查模式资产是否齐全
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

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
    ('docs/superpowers/specs/题库设计模式_v1.md', '权威全文'),
    ('docs/superpowers/specs/题库设计模式_角色卡_v1.md', '热加载角色卡'),
    ('docs/design/题库领域词表_v1.md', '领域词表'),
    ('scripts/qbdm/ctx_budget.py', '装载预算闸'),
    ('scripts/qbdm/test_sweep.py', '逐文件测试扫描器'),
    ('.opencode/skills/qbdm-role-switch/SKILL.md', '项目技能（不入 Git）'),
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

    args = parser.parse_args(argv)

    if args.cmd == 'role':
        return _print_role(args.code)

    if args.cmd == 'status':
        missing = 0
        print('QBDM 资产自检：')
        for path, label in ARTIFACTS:
            ok = os.path.exists(os.path.join(args.repo if hasattr(args, 'repo') else '.', path))
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
