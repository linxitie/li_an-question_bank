# -*- coding: utf-8 -*-
"""「题库设计」模式（v3）绑定与 CLI 的回归测试。

守四件事：
  1) 绑定文件里的角色与技能都真实存在，防止写了调不动的技能名；
  2) 三个状态（设计/测试/优化）都有步骤，且每步角色都在九角色内；
  3) MCP 工具名与 vtj-mcp-server 的 19 个工具对得上；
  4) `design` 命令按状态/模块输出，未知模块必须非 0 退出。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import qbdm  # noqa: E402

# 由插件（Superpowers 等）提供、正文不在本仓 .opencode/skills 的技能。
PLUGIN_SKILLS = {
    'brainstorming', 'codebase-design', 'tdd', 'writing-plans',
    'systematic-debugging', 'agent-browser', 'domain-modeling',
}


def _mode():
    return json.loads(qbdm.DESIGN_MODE.read_text(encoding='utf-8'))


def test_mode_has_three_states_and_steps():
    mode = _mode()
    assert mode['mode'] == '题库设计'
    assert set(mode['states']) == {'design', 'test', 'optimize'}
    for key, state in mode['states'].items():
        assert state['steps'], f'{key} 没有步骤'
        for step in state['steps']:
            assert set(step['roles']) <= set(mode['roles']), f'{step["id"]} 角色越界'


def test_skills_are_resolvable():
    repo = qbdm.REPO_ROOT
    mode = _mode()
    used = {s for state in mode['states'].values() for step in state['steps']
            for s in step['skills']}
    used |= {s for role in mode['roles'].values() for s in role['skills']}
    for name in used:
        if name in PLUGIN_SKILLS:
            continue
        card = repo / '.opencode/skills' / name / 'SKILL.md'
        assert card.exists(), f'技能不存在：{name}'


def test_mcp_tools_match_server():
    mode = _mode()
    tools = mode['mcp']['tools']
    assert len(tools) == 19
    assert len(set(tools)) == 19
    for step in mode['states']['design']['steps']:
        for tool in step['mcp']:
            assert tool in tools, f'未登记的 MCP 工具：{tool}'


def test_design_cli_prints_pipeline(capsys):
    assert qbdm.main(['design', 'wrongbook', '--state', 'design']) == 0
    out = capsys.readouterr().out
    assert '[模式] 题库设计' in out
    assert '错题集' in out
    assert 'D0' in out and 'D6' in out


def test_design_cli_states(capsys):
    for state in ('design', 'test', 'optimize'):
        assert qbdm.main(['design', 'practice', '--state', state]) == 0
        out = capsys.readouterr().out
        assert '状态' in out


def test_design_cli_json(capsys):
    assert qbdm.main(['design', 'wrongbook', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['module']['id'] == 'wrongbook'
    assert data['state'] == 'design'


def test_design_unknown_module_fails():
    assert qbdm.main(['design', 'no-such-module']) == 1


def test_design_without_module(capsys):
    assert qbdm.main(['design', '--state', 'optimize']) == 0
    out = capsys.readouterr().out
    assert '未指定' in out


def test_entry_skill_exists():
    card = qbdm.REPO_ROOT / '.opencode/skills/qbdm-design-mode/SKILL.md'
    assert card.exists(), '「题库设计」模式技能缺失，自动触发会失效'
