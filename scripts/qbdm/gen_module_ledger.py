#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成《题库模块台账》——QBDM 模块层的唯一事实来源。

为什么要有它：
    QBDM v1 只定义了「角色 + 流程 + 门禁」，没有回答「这个功能模块由谁负责、
    动它要碰哪些端点/页面/测试/事件」。本脚本把散落在三处的模块事实合成一份台账：
      1) backend/data/refactor_baseline/api_surface.json —— 端点归属（权威基线）
      2) src/modules/<域>/README.md —— 域卡（页面/端点/测试/事件登记）
      3) 仓库实际文件 —— 页面与测试的现状（防止域卡过期）

设计取舍：
    - 端点以 api_surface.json 为准，域卡只作交叉核对；域卡漏填不影响台账正确性。
    - 页面与测试用「精确文件名 + 关键字候选」双口径：登记口径可信，候选口径标注
      「需人工确认」，不做无证据断言（QBDM Z2）。
    - 生成结果可复现；`--check` 用于发现台账与仓库漂移。

用法：
    python scripts/qbdm/gen_module_ledger.py            # 重新生成 JSON + Markdown
    python scripts/qbdm/gen_module_ledger.py --check    # 只校验是否漂移（退出码 0/1）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_SURFACE = REPO_ROOT / 'backend/data/refactor_baseline/api_surface.json'
OUT_JSON = REPO_ROOT / 'docs/design/题库模块台账_v1.json'
OUT_MD = REPO_ROOT / 'docs/design/题库模块台账_v1.md'

TZ = timezone(timedelta(hours=8))

# 25 个功能模块：20 个学生端域（权威来源 docs/plans/分支使用说明书_v1.md §3.1）
# + 5 个平台/跨端模块。编号只用于文档，不进入代码。
# page_names 为「精确页面名」，避免 profile 这类关键字把 teacher_profile 误算进来。
MODULES: list[dict] = [
    {
        'no': '①', 'id': 'identity', 'name': '认证 + 个人中心', 'scope': '学生端',
        'dir': 'identity', 'files': ['auth.py', 'auth_qrcode.py', 'devices.py', 'feedback.py'],
        'status': '已实现',
        'page_names': ['login', 'mobile_login', 'tablet_login', 'profile', 'mobile_profile',
                       'tablet_profile', 'home_page', 'mobile_home', 'tablet_home', 'help',
                       'mobile_help', 'feedback', 'mobile_feedback', 'mobile_notifications',
                       'mobile_scan'],
        'test_kw': 'identity|auth|device|feedback',
    },
    {
        'no': '②', 'id': 'catalog', 'name': '题库浏览', 'scope': '学生端',
        'dir': 'catalog', 'files': ['questions.py', 'question_actions.py'],
        'status': '已实现',
        'page_names': ['question_bank', 'mobile_question_bank', 'tablet_question_bank',
                       'question_preview_list'],
        'test_kw': 'catalog|question_visibility|question_stats',
    },
    {
        'no': '③', 'id': 'practice', 'name': '答题练习', 'scope': '学生端',
        'dir': 'practice', 'files': ['practice.py', 'quick_practice.py'],
        'status': '已实现',
        'page_names': ['answer_page', 'exercise', 'mobile_answer', 'mobile_practice',
                       'tablet_practice', 'solution'],
        'test_kw': 'practice|quick_practice|answer_doc',
    },
    {
        'no': '④', 'id': 'records', 'name': '练习记录', 'scope': '学生端',
        'dir': 'records', 'files': ['exam_records.py'],
        'status': '已实现',
        'page_names': ['mobile_history'],
        'test_kw': 'exam_records|history',
    },
    {
        'no': '⑤', 'id': 'papers', 'name': '智能组卷 + 历年试卷', 'scope': '学生端',
        'dir': 'papers', 'files': ['smart_exam.py', 'papers.py', 'paper_generation.py'],
        'status': '已实现',
        'page_names': ['smart_exam', 'smart_answer', 'student_papers',
                       'mobile_student_papers', 'smart_recommend'],
        'test_kw': 'paper|smart_exam',
    },
    {
        'no': '⑥', 'id': 'wrongbook', 'name': '错题集', 'scope': '学生端',
        'dir': 'wrongbook', 'files': ['wrong_questions.py'],
        'status': '已实现',
        'page_names': ['wrong_questions', 'mobile_wrong_questions', 'mobile_wrong_review'],
        'test_kw': 'wrong',
    },
    {
        'no': '⑦', 'id': 'notes', 'name': '笔记 + 收藏', 'scope': '学生端',
        'dir': 'notes', 'files': ['notes.py', 'collection.py'],
        'status': '已实现',
        'page_names': ['notes', 'mobile_notes', 'favorites', 'mobile_favorites'],
        'test_kw': 'notes|collection|favorite',
    },
    {
        'no': '⑧', 'id': 'analytics', 'name': '成绩分析', 'scope': '学生端',
        'dir': 'analytics', 'files': ['stats.py'],
        'status': '已实现',
        'page_names': ['score_analysis', 'mobile_score_analysis'],
        'test_kw': 'analytics|three_end_counts',
    },
    {
        'no': '⑨', 'id': 'community', 'name': '论坛社区', 'scope': '学生端',
        'dir': 'community', 'files': ['forum.py', 'quotes.py'],
        'status': '已实现',
        'page_names': ['forum', 'mobile_forum', 'tablet_forum', 'mobile_forum_create',
                       'mobile_forum_detail', 'daily_quote', 'quote_banner'],
        'test_kw': 'community|forum|quote',
    },
    {
        'no': '⑩', 'id': 'news', 'name': '每日新闻', 'scope': '学生端',
        'dir': 'news', 'files': ['news.py'],
        'status': '已实现',
        'page_names': ['daily_news', 'mobile_news'],
        'test_kw': 'news',
    },
    {
        'no': '⑪', 'id': 'calendar', 'name': '考试日历', 'scope': '学生端',
        'dir': 'calendar', 'files': ['calendar.py'],
        'status': '已实现',
        'page_names': ['exam_calendar', 'exam_calendar_block', 'mobile_calendar',
                       'countdown_block', 'countdown_timer'],
        'test_kw': 'calendar',
    },
    {
        'no': '⑫', 'id': 'recruitment', 'name': '招考信息', 'scope': '学生端',
        'dir': 'recruitment', 'files': ['recruitment.py'],
        'status': '已实现',
        'page_names': ['recruitment_info', 'mobile_recruitment'],
        'test_kw': 'recruitment',
    },
    {
        'no': '⑬', 'id': 'about', 'name': '关于砺安题库', 'scope': '学生端',
        'dir': 'about', 'files': [],
        'status': '已实现（页面接入待 P3）',
        'page_names': ['about'],
        'test_kw': 'about',
    },
    {
        'no': '⑭', 'id': 'library', 'name': '备考资料', 'scope': '学生端',
        'dir': 'library', 'files': ['materials.py', 'videos.py', 'media.py'],
        'status': '已实现',
        'page_names': ['materials_gongzhuan', 'materials_shenlun', 'materials_xingce',
                       'study_materials', 'mobile_materials'],
        'test_kw': 'library|material|gongzhuan',
    },
    {
        'no': '⑮', 'id': 'growth', 'name': '成就成长（枢纽）', 'scope': '学生端',
        'dir': 'growth', 'files': ['achievements.py', 'goals.py', 'tasks.py'],
        'status': '已实现',
        'page_names': ['achievements', 'mobile_achievements', 'goal_card', 'personal_goal'],
        'test_kw': 'achievement|goal|task',
    },
    {
        'no': '⑯', 'id': 'reward', 'name': '金币商城', 'scope': '学生端',
        'dir': 'reward', 'files': ['shop.py', 'coins.py'],
        'status': '已实现',
        'page_names': ['gold_purchase', 'mobile_gold_purchase', 'tablet_gold_purchase'],
        'test_kw': 'reward|coin|shop',
    },
    {
        'no': '⑰', 'id': 'checkin', 'name': '每日签到', 'scope': '学生端',
        'dir': 'checkin', 'files': [],
        'status': '未开发（复用 badge_task）',
        'page_names': ['signin_card', 'signin_status'],
        'test_kw': 'checkin|signin',
    },
    {
        'no': '⑱', 'id': 'ai-assistant', 'name': '联考小智', 'scope': '学生端',
        'dir': 'ai-assistant', 'files': ['llm.py'],
        'status': '未开发（端点已预留）',
        'page_names': [],
        'test_kw': 'llm|assistant',
    },
    {
        'no': '⑲', 'id': 'mock-exam', 'name': '模拟上机考试', 'scope': '学生端',
        'dir': 'mock-exam', 'files': [],
        'status': '未开发',
        'page_names': [],
        'test_kw': 'mock',
    },
    {
        'no': '⑳', 'id': 'mini-exam', 'name': '小模考', 'scope': '学生端',
        'dir': 'mini-exam', 'files': [],
        'status': '未开发（复用 /api/exams）',
        'page_names': [],
        'test_kw': 'mini',
    },
    {
        'no': '㉑', 'id': 'question-import', 'name': '题目导入', 'scope': '跨端',
        'dir': None, 'files': ['question_import.py'],
        'status': '已实现',
        'page_names': ['question_import', 'manual_match_dialog'],
        'test_kw': 'import|parser|recognizer|mineru|material|taxonomy|text_|rich_text|'
                   'subjective|similarity|matcher',
    },
    {
        'no': '㉒', 'id': 'teacher', 'name': '教师端', 'scope': '平台端',
        'dir': None, 'files': ['teacher.py'],
        'status': '已实现',
        'page_names': ['teacher_dashboard', 'teacher_questions', 'teacher_papers',
                       'teacher_scores', 'teacher_classes', 'teacher_messages',
                       'teacher_analytics', 'teacher_profile'],
        'test_kw': 'teacher|paper_publish|platform_question',
    },
    {
        'no': '㉓', 'id': 'admin', 'name': '管理端', 'scope': '平台端',
        'dir': None, 'files': ['admin.py', 'admin_approval.py', 'admin_shop.py'],
        'status': '已实现',
        'page_names': ['admin_dashboard', 'admin_questions', 'admin_users', 'admin_logs',
                       'admin_backup', 'admin_settings', 'admin_permissions', 'admin_materials',
                       'admin_shop', 'admin_help', 'admin_profile', 'paper_approval'],
        'test_kw': 'admin|approval|materials_admin',
    },
    {
        'no': '㉔', 'id': 'exams', 'name': '考试与答卷', 'scope': '跨端',
        'dir': None, 'files': ['exams.py'],
        'status': '已实现',
        'page_names': ['paper_answer', 'paper_result'],
        'test_kw': 'exam',
    },
    {
        'no': '㉕', 'id': 'realtime', 'name': '实时通知通道', 'scope': '平台端',
        'dir': None, 'files': ['websocket.py'],
        'status': '已实现',
        'page_names': [],
        'test_kw': 'websocket|monitoring|cross_domain',
    },
]

# 非页面/非模块文件：列入「未归属」时给出解释，避免被当成漏登记。
NON_MODULE_PAGES = {
    'navbar': '全局导航组件',
    'footer_info': '全局页脚组件',
    'app_navigation': '全局导航组件',
    'download_client': '下载引导页',
    'TeacherNavHeader': '教师端导航组件',
    'not-found': '系统 404 页',
    'unauthorized': '系统 403 页',
}


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _sections(text: str) -> dict[str, str]:
    """把域卡按 `## 1. xxx` 切成编号 -> 正文，供后续按节提取。"""
    parts = re.split(r'^## (\d+)\. .*$', text, flags=re.M)
    out: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        out[parts[i]] = parts[i + 1]
    return out


def _spans(text: str) -> list[str]:
    return re.findall(r'`([^`]+)`', text)


def _card_data(module: dict) -> dict:
    """读域卡：页面/端点/测试/事件。平台端模块没有域卡，返回空登记。"""
    empty = {'exists': False, 'pages': [], 'endpoints': [], 'tests': [],
             'events_publish': [], 'events_subscribe': [], 'status_line': ''}
    if not module['dir']:
        return empty
    card = REPO_ROOT / 'src/modules' / module['dir'] / 'README.md'
    if not card.exists():
        return empty
    text = _read(card)
    secs = _sections(text)
    pages = [s for s in _spans(secs.get('1', '')) if '.vue' in s]
    endpoints = [f'{m} {p}' for m, p in re.findall(
        r'\|\s*(GET|POST|PUT|DELETE|PATCH)\s*\|\s*`([^`]+)`', secs.get('2', ''))]
    tests = [s for s in _spans(secs.get('6', '')) if 'test' in s or '.spec.' in s]
    event_re = re.compile(r'^[a-z][a-z0-9-]*(?::[a-z0-9-]+|\.[a-z0-9_]+)$')
    pub = [s for s in _spans(secs.get('4', '')) if event_re.match(s)]
    sub = [s for s in _spans(secs.get('5', '')) if event_re.match(s)]
    first_lines = [ln for ln in text.splitlines()[:8] if ln.strip()]
    status_line = ''
    for ln in first_lines:
        if '状态' in ln or '已实现' in ln or '未开发' in ln:
            status_line = ln.lstrip('> ').strip()
            break
    return {'exists': True, 'pages': pages, 'endpoints': endpoints, 'tests': tests,
            'events_publish': pub, 'events_subscribe': sub, 'status_line': status_line}


def _scan_page_files() -> dict[str, str]:
    """页面名 -> 相对路径。同时覆盖 .vtj/vue 与手写页，缺一不可（域卡 3.2 条）。"""
    found: dict[str, str] = {}
    for base in [REPO_ROOT / '.vtj/vue', REPO_ROOT / 'src/views']:
        if not base.exists():
            continue
        for path in base.rglob('*.vue'):
            found.setdefault(path.stem, path.relative_to(REPO_ROOT).as_posix())
    return found


def _scan_test_files() -> list[str]:
    found: list[str] = []
    tests_dir = REPO_ROOT / 'backend/tests'
    if tests_dir.exists():
        found += [p.relative_to(REPO_ROOT).as_posix()
                  for p in sorted(tests_dir.glob('test_*.py'))]
    modules_dir = REPO_ROOT / 'src/modules'
    if modules_dir.exists():
        found += [p.relative_to(REPO_ROOT).as_posix()
                  for p in sorted(modules_dir.rglob('__tests__/*.spec.ts'))]
    return found


def build(now: datetime | None = None) -> dict:
    api = json.loads(_read(API_SURFACE))
    page_files = _scan_page_files()
    all_tests = _scan_test_files()
    assigned_files: set[str] = set()
    modules: list[dict] = []

    for module in MODULES:
        card = _card_data(module)
        files = [f for f in module['files'] if f in api]
        assigned_files.update(files)
        count = sum(api[f]['endpoint_count'] for f in files)
        prefixes = sorted({api[f]['prefix'] for f in files})
        domains = sorted({api[f]['domain'] for f in files})

        pages = [page_files[n] for n in module['page_names'] if n in page_files]
        pages += [p for p in card['pages'] if p not in pages]
        missing_pages = [n for n in module['page_names'] if n not in page_files]

        kw = re.compile(module['test_kw'])
        candidates = [t for t in all_tests if kw.search(t)]
        # shells.spec.ts 是 20 个模块共用的外壳冒烟，逐行重复只会淹没真正的域内测试。
        # 域卡可能只写文件名、候选是仓库相对路径，故按 basename 去重。
        seen = {Path(t).name for t in candidates}
        registered = [t for t in card['tests']
                      if Path(t).name not in seen and 'shells.spec.ts' not in t]
        test_kw = module['test_kw']
        modules.append({
            'no': module['no'],
            'id': module['id'],
            'name': module['name'],
            'scope': module['scope'],
            'status': module['status'],
            'dir': f'src/modules/{module["dir"]}' if module['dir'] else None,
            'card': (f'src/modules/{module["dir"]}/README.md' if module['dir'] else None),
            'card_filled': bool(card['pages'] or card['endpoints'] or card['tests']),
            'card_status_line': card['status_line'],
            'api_domains': domains,
            'api_files': files,
            'endpoint_count': count,
            'endpoint_prefixes': prefixes,
            'card_endpoint_count': len(card['endpoints']),
            'pages': pages,
            'pages_missing': missing_pages,
            'tests_registered': registered,
            'tests_candidates': candidates,
            'test_command': (f'cd backend; python -m pytest tests -q -k "{test_kw}"'
                             if candidates else ''),
            'events_publish': card['events_publish'],
            'events_subscribe': card['events_subscribe'],
        })

    total = sum(m['endpoint_count'] for m in modules)
    unassigned_files = [f for f in api if f not in assigned_files]
    assigned_pages = {p for m in modules for p in m['pages']}
    unassigned_pages = {
        name: path for name, path in page_files.items() if path not in assigned_pages
    }
    card_gaps = [m['id'] for m in modules
                 if m['dir'] and not m['card_filled'] and not m['status'].startswith('未开发')]
    stub_cards = [m['id'] for m in modules
                  if m['dir'] and not m['card_filled'] and m['status'].startswith('未开发')]
    no_tests = [m['id'] for m in modules
                if not m['status'].startswith('未开发')
                and not m['tests_registered'] and not m['tests_candidates']]
    stamp = (now or datetime.now(TZ)).strftime('%Y-%m-%d %H:%M:%S')

    return {
        'version': 'v1',
        'generated_at': stamp,
        'source': 'scripts/qbdm/gen_module_ledger.py',
        'note': '端点以 api_surface.json 为准；页面/测试为登记口径+候选口径，候选需人工确认',
        'totals': {
            'modules': len(modules),
            'endpoints': total,
            'api_files': len(api),
            'api_files_unassigned': unassigned_files,
            'pages_assigned': len(assigned_pages),
            'pages_unassigned': unassigned_pages,
            'card_gaps': card_gaps,
            'stub_cards': stub_cards,
            'modules_without_tests': no_tests,
        },
        'modules': modules,
    }


def render_md(ledger: dict) -> str:
    t = ledger['totals']
    lines = [
        '# 题库模块台账 v1',
        '',
        '> 由 `scripts/qbdm/gen_module_ledger.py` 从 `api_surface.json`、20 份域卡与仓库实际文件生成。',
        '> **不要手改本文件**：改模块归属请改生成脚本里的 `MODULES`，改端点请改基线并发起重生成。',
        f'> 生成时间：{ledger["generated_at"]}｜模块 {t["modules"]} 个｜端点 {t["endpoints"]} 个',
        '',
        '## 0 口径说明',
        '',
        '| 口径 | 含义 |',
        '|---|---|',
        '| 端点 | 以 `backend/data/refactor_baseline/api_surface.json` 为准，按 `api_files` 求和 |',
        '| 页面 | 精确页面名匹配 `.vtj/vue` 与 `src/views/**`，再并上域卡登记；组件不计 |',
        '| 测试（登记） | 域卡 §6 明文登记的测试文件 |',
        '| 测试（候选） | 按模块关键字从 66 个后端测试 + 前端 spec 中**匹配出的候选**，需人工确认 |',
        '| 状态 | 模块级现状，未开发模块不认领分支 |',
        '',
        '## 1 模块总表',
        '',
        '| # | 模块 | 范围 | 端点 | 页面 | 测试 登记/候选 | 事件 发/订 | 状态 | 域卡 |',
        '|---|---|---|---|---|---|---|---|---|',
    ]
    for m in ledger['modules']:
        card = '✅' if m['card_filled'] else ('空表' if m['dir'] else '—')
        lines.append(
            f'| {m["no"]} | {m["name"]} | {m["scope"]} | {m["endpoint_count"]} | '
            f'{len(m["pages"])} | {len(m["tests_registered"])}/{len(m["tests_candidates"])} | '
            f'{len(m["events_publish"])}/{len(m["events_subscribe"])} | {m["status"]} | {card} |'
        )
    lines += [
        '',
        '## 2 端点归属核对',
        '',
        f'- 25 模块归属端点合计：**{t["endpoints"]}**；基线总数：343（`test_api_surface.py` 守住）。',
        f'- 未归属 API 文件：{("、".join(t["api_files_unassigned"]) or "无")}',
        f'- 未归属页面（组件/系统页）：'
        f'{("、".join(f"`{k}`" for k in sorted(t["pages_unassigned"])) or "无")}',
    ]
    if t['api_files_unassigned']:
        lines.append('')
        lines.append('> 未归属文件必须显式解释：要么补进 `MODULES`，要么登记为通用/未认领。')
    lines += ['', '## 3 缺口清单（模块层质量）', '']
    if t['card_gaps']:
        lines.append(f'- **域卡空表（已实现模块）**：{ "、".join(t["card_gaps"]) }')
    if t.get('stub_cards'):
        lines.append(f'- 未开发模块的占位域卡（正常，开工时再填）：{ "、".join(t["stub_cards"]) }')
    if t['modules_without_tests']:
        lines.append(f'- **已实现但无任何测试线索**：{ "、".join(t["modules_without_tests"]) }')
    if not t['card_gaps'] and not t['modules_without_tests']:
        lines.append('- 无')
    lines += ['', '> 20 个模块共用 `src/modules/__tests__/shells.spec.ts` 外壳冒烟，故不逐行登记。']
    lines += ['', '## 4 端点前缀明细', '', '| # | 模块 | 域 | 前缀 | 端点数 |', '|---|---|---|---|---|']
    for m in ledger['modules']:
        if not m['endpoint_prefixes']:
            continue
        lines.append(
            f'| {m["no"]} | {m["name"]} | {",".join(m["api_domains"])} | '
            f'{ "<br>".join(m["endpoint_prefixes"]) } | {m["endpoint_count"]} |'
        )
    lines += [
        '',
        '## 5 页面归属明细',
        '',
        '| # | 模块 | 页面 |',
        '|---|---|---|',
    ]
    for m in ledger['modules']:
        if not m['pages']:
            continue
        lines.append(f'| {m["no"]} | {m["name"]} | { "<br>".join(f"`{p}`" for p in m["pages"]) } |')
    lines += [
        '',
        '## 6 测试与事件',
        '',
        '| # | 模块 | 登记测试 | 候选测试 | 发布事件 | 订阅事件 |',
        '|---|---|---|---|---|---|',
    ]
    for m in ledger['modules']:
        reg = '<br>'.join(f'`{x}`' for x in m['tests_registered']) or '—'
        cand = '<br>'.join(f'`{x}`' for x in m['tests_candidates']) or '—'
        pub = '<br>'.join(f'`{x}`' for x in m['events_publish']) or '—'
        sub = '<br>'.join(f'`{x}`' for x in m['events_subscribe']) or '—'
        lines.append(f'| {m["no"]} | {m["name"]} | {reg} | {cand} | {pub} | {sub} |')
    lines += [
        '',
        '> 候选测试是按关键字匹配的结果，可能包含跨模块用例；首次认领模块时须逐条确认。',
        '',
        '## 7 使用方式',
        '',
        '```powershell',
        'python scripts/qbdm/qbdm.py modules              # 列出全部模块与端点/页面/测试数量',
        'python scripts/qbdm/qbdm.py module wrongbook     # 打印单模块的设计/优化/测试清单',
        'python scripts/qbdm/gen_module_ledger.py --check # 台账是否与仓库漂移',
        '```',
        '',
        '> 模块层的设计/优化/测试清单见 `docs/superpowers/specs/题库设计模式_v2.md`；',
        '> 热加载一页版见 `docs/superpowers/specs/题库设计模式_模块作战卡_v1.md`。',
        '',
    ]
    return '\n'.join(lines)


def _normalize(ledger: dict) -> dict:
    """比对时忽略生成时间，否则 --check 永远漂移。"""
    copy = json.loads(json.dumps(ledger, ensure_ascii=False))
    copy.pop('generated_at', None)
    return copy


def _normalize_md(text: str) -> str:
    """Markdown 头部的生成时间同样不参与漂移比对。"""
    return re.sub(r'生成时间：\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '生成时间：*', text)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description='生成/校验题库模块台账')
    parser.add_argument('--check', action='store_true', help='只校验台账是否与仓库一致')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    ledger = build()
    md = render_md(ledger)
    body = json.dumps(ledger, ensure_ascii=False, indent=2) + '\n'

    if args.check:
        ok = True
        if not OUT_JSON.exists() or _normalize(json.loads(_read(OUT_JSON))) != _normalize(ledger):
            print('DRIFT docs/design/题库模块台账_v1.json 与仓库不一致')
            ok = False
        if not OUT_MD.exists() or _normalize_md(_read(OUT_MD)) != _normalize_md(md):
            print('DRIFT docs/design/题库模块台账_v1.md 与仓库不一致')
            ok = False
        print('结论：' + ('台账最新' if ok else '台账漂移，请运行 gen_module_ledger.py'))
        return 0 if ok else 1

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(body, encoding='utf-8', newline='\n')
    OUT_MD.write_text(md, encoding='utf-8', newline='\n')
    if not args.quiet:
        total = ledger['totals']
        print(f'模块 {total["modules"]} 个｜端点 {total["endpoints"]} 个｜'
              f'域卡空表 {len(total["card_gaps"])} 个｜无测试线索 {len(total["modules_without_tests"])} 个')
        print(f'写入 {OUT_JSON.relative_to(REPO_ROOT).as_posix()}')
        print(f'写入 {OUT_MD.relative_to(REPO_ROOT).as_posix()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
