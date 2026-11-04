"""路由角色可见性守卫（F2 Step 5）。

L7-08 从正则计数改为结构化解析：页面路由（含 component）除 4 条公共白名单外
必须声明 roles；/tablet 与 /mobile 只能是 student。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
GATES = BACKEND / 'scripts' / 'gates'
sys.path.insert(0, str(GATES))

import gate_l7_foundation as l7  # noqa: E402

ROUTER = BACKEND.parent / 'src' / 'router' / 'index.ts'


def _pages():
    records = l7.parse_route_records(ROUTER.read_text(encoding='utf-8'))
    return [r for r in records if r['has_component']]


def test_page_route_count():
    # 92 → 99：备考资料交付线新增 7 条页面路由（2026-11-01 核对）
    #   /badges、/badges-demo、/badge-preview、/materials/upload、
    #   /materials-preview、/materials/detail、/admin/material-rules
    # 99 → 100：平板徽章墙 /tablet/badges（2026-11-02，复用 PC 徽章页，守 R12）
    # 100 → 101：平板整页详情 /tablet/materials/detail（2026-11-02，复用 PC 详情页）
    # 101 → 98：平板与电脑同版 —— 上面三条改 redirect（无 component，不计入），
    #           /tablet/home 只是换 component 不增删
    # 98 → 104：2026-11-04 合并远端 main，模块4/7 新增 6 条页面路由
    #           /ai-assistant、/study-plan、/profile-quiz、/knowledge、/memories、/teacher/forum
    #           （与 scripts/verify-modularization-constraints.mjs 的 104 同步）
    # 路由只增不减；再新增时请同步本数字并在提交信息写明。
    assert len(_pages()) == 104


def test_whitelist_has_no_roles():
    by_path = {r['path']: r for r in _pages()}
    for path in l7.ROUTE_WHITELIST:
        assert path in by_path, f'白名单路由缺失：{path}'
        assert by_path[path]['roles'] == []


def test_every_non_whitelist_page_declares_roles():
    missing = [
        r['path'] for r in _pages()
        if r['path'] not in l7.ROUTE_WHITELIST and not r['roles']
    ]
    assert missing == []


def test_mobile_and_tablet_are_student_only():
    bad = [
        r['path'] for r in _pages()
        if r['path'].startswith(l7.MOBILE_PREFIXES) and r['roles'] != ['student']
    ]
    assert bad == []


def test_child_inherits_parent_roles():
    text = """
const routes: RouteRecordRaw[] = [
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { roles: ['admin'] },
    children: [
      { path: 'dashboard', component: () => import('@/views/AdminDashboard.vue') }
    ]
  }
];
"""
    records = l7.parse_route_records(text)
    child = [r for r in records if r['path'] == 'dashboard'][0]
    assert child['roles'] == ['admin']
