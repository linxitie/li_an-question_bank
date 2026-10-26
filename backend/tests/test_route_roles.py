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
    assert len(_pages()) == 92


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
