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
    # 104 → 101：2026-11-04 徽章展示模块下线，/badges、/badges-demo、/badge-preview 移除
    # 101 → 105：2026-11-04 远端 main 再前进（新闻时间线/详情 + 平板与手机端），共 4 条
    # 105 → 104：2026-11-04 远端二次合并，管理端用户/权限页改用 AdminUsersWorkspace、
    #            平板论坛页移除，净减 1 条（与 scripts/verify-modularization-constraints.mjs 的 104 同步）
    # 104 → 105：2026-11-07 A0 管理端画风组件库预览页 /admin/dev/style（仅 admin 可见），
    #            供 E1/E2 画风改造做视觉基准（与 verify-modularization-constraints.mjs 的 105 同步）
    # 105 → 104：2026-11-12 S4 **旧版资料页 /admin/materials/legacy 路由下线** ——
    #            S3（xlsx 卡片智能导入）与 S2（富文本正文/卡片正反面）已搬进新版页；
    #            `.vtj/vue/admin_materials.vue` 按 R1 保留（不删不改），只是不再挂路由。
    #            与 scripts/verify-modularization-constraints.mjs 的 104 同步。
    # 104 → 105：2026-11-15 D6 手机端结果页 /mobile/paper-result ——
    #            手机答完试不再跳 PC 的 /paper-result（桌面版式），改用手机版式；
    #            与 scripts/verify-modularization-constraints.mjs 的 105 同步。
    # 105 → 134：2026-11-16 合并远端 main（201 个提交）。远端侧新增 29 条页面路由
    #            （招聘雷达/报价与收藏/签到/成长复习/内容守卫/小智 Studio/知识图谱/换卷等）
    #            使远端为 133，叠加本线 /mobile/paper-result 1 条 = 134。
    #            注：`/admin/papers` 页面路由在本线已按「试卷收敛 P4=A」改为 redirect（无 component），
    #            远端仍是页面版，合并取本线 redirect，故不是 135。两处门禁已同步为 134。
    # 134 → 136：2026-11-16 三端登录 P2 新增教师设备端首页 2 条页面路由
    #            （/tablet/teacher/home、/mobile/teacher/home —— 同一手写组件供两端复用，守 R12；
    #             教师端其余功能页在 P3/P4 增。与 verify-modularization-constraints.mjs 的 136 同步）
    assert len(_pages()) == 138


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


def test_device_routes_allow_student_and_teacher_only():
    """设备端（/tablet、/mobile）只能出现 student / teacher；管理员必须电脑端。

    旧规则是「设备端必须恰好 ['student']」——2026-11-16 三端登录方案（D-8/D-16）起
    教师也可在设备端登录，故放宽为"角色集合 ⊆ {student, teacher}"；
    同时明确禁止 admin 出现在设备端路由（与后端 device_policy 的硬约束一致）。
    """
    allowed = set(l7.DEVICE_ALLOWED_ROLES)
    bad = [
        r['path'] for r in _pages()
        if r['path'].startswith(l7.MOBILE_PREFIXES)
        and (not r['roles'] or set(r['roles']) - allowed)
    ]
    assert bad == []


def test_device_routes_never_contain_admin():
    offenders = [
        r['path'] for r in _pages()
        if r['path'].startswith(l7.MOBILE_PREFIXES) and 'admin' in r['roles']
    ]
    assert offenders == []


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
