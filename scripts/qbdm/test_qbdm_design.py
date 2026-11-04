# -*- coding: utf-8 -*-
"""「题库设计」模式（v5）绑定与 CLI 的回归测试。

守六件事：
  1) 绑定文件里的角色与技能都真实可加载（`.agents/skills` ∪ `.opencode/skills` ∪ 插件/内置）；
  2) 三个状态（设计/测试/优化）都有步骤，且每步角色都在九角色内；
  3) MCP 工具名与 vtj-mcp-server 的 19 个工具对得上；
  4) `design` 命令按状态/模块输出，未知模块必须非 0 退出；
  5) v5 新命令 `branch` / `handoff` / `token` 可运行且输出关键段；
  6) 模式绑定版本必须是 v5（防止 design_mode.json 停在旧版）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import qbdm  # noqa: E402

# 由插件（Superpowers）/内置工具提供、正文不在本仓的技能；以及浏览器类内置技能。
PLUGIN_SKILLS = {
    'brainstorming', 'writing-plans', 'executing-plans', 'tdd',
    'test-driven-development', 'systematic-debugging',
    'verification-before-completion', 'using-superpowers',
    'dispatching-parallel-agents', 'subagent-driven-development',
    'requesting-code-review', 'receiving-code-review',
    'using-git-worktrees', 'finishing-a-development-branch', 'writing-skills',
    'browser',
}


def _mode():
    return json.loads(qbdm.DESIGN_MODE.read_text(encoding='utf-8'))


def _skill_roots():
    repo = qbdm.REPO_ROOT
    return [repo / '.agents/skills', repo / '.opencode/skills']


def test_mode_version_is_v5():
    assert _mode()['version'] == 'v5'


def test_mode_has_three_states_and_steps():
    mode = _mode()
    assert mode['mode'] == '题库设计'
    assert set(mode['states']) == {'design', 'test', 'optimize'}
    for key, state in mode['states'].items():
        assert state['steps'], f'{key} 没有步骤'
        for step in state['steps']:
            assert set(step['roles']) <= set(mode['roles']), f'{step["id"]} 角色越界'


def test_skills_are_resolvable():
    """技能名必须能在仓库技能目录或插件/内置清单里找到来源（A34 的可执行口径）。"""
    mode = _mode()
    used = {s for state in mode['states'].values() for step in state['steps']
            for s in step['skills']}
    used |= {s for role in mode['roles'].values() for s in role['skills']}
    roots = _skill_roots()
    for name in sorted(used):
        if name in PLUGIN_SKILLS:
            continue
        found = any((root / name).is_dir() for root in roots)
        assert found, f'技能无来源（仓库与插件都没有）：{name}'


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
    """项目技能不入 Git：缺失时跳过（按技能重建手册 v2 重建），存在则必须完整。"""
    if not (qbdm.REPO_ROOT / '.opencode/skills').is_dir():
        import pytest
        pytest.skip('本机无 .opencode/skills（不入 Git），按技能重建手册 v2 重建')
    card = qbdm.REPO_ROOT / '.opencode/skills/qbdm-design-mode/SKILL.md'
    assert card.exists(), '「题库设计」模式技能缺失，自动触发会失效'


# ---------- v5 新命令 ----------

def _has_git() -> bool:
    return qbdm._rev_parse('HEAD') is not None


def test_branch_cli(capsys):
    import pytest
    if not _has_git():
        pytest.skip('非 git 工作区')
    assert qbdm.main(['branch']) == 0
    out = capsys.readouterr().out
    assert '[分支]' in out
    assert '[拓扑]' in out
    assert '模块' in out


def test_handoff_cli(capsys):
    assert qbdm.main(['handoff']) == 0
    out = capsys.readouterr().out
    assert '[接管]' in out
    assert '学习计划' in out and '联考小智' in out
    assert '父域' in out
    assert '子分支命名' in out


def test_token_cli(capsys):
    assert qbdm.main(['token']) == 0
    out = capsys.readouterr().out
    assert '五零指标' in out
    assert 'T2' in out
    assert '[TOKEN]' in out
