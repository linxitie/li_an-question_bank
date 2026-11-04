"""生成「远端 main 页面 / 接口清单」文档（可重复运行：python ../_gen_inventory.py）。"""
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / 'docs/plans/远端main页面与接口清单_v1.md'
ROUTER = REPO / 'src/router/index.ts'
API = REPO / 'backend/app/api'
MAIN = REPO / 'backend/app/main.py'

DECOR = re.compile(
    r'@(?P<router>[A-Za-z_][A-Za-z0-9_]*)\.(?P<method>get|post|put|patch|delete|head)\('
    r'\s*["\'](?P<path>[^"\']*)["\']', re.S)


# ---------------- 页面 ----------------
def find_array(text: str, start: int):
    depth = 0
    i = start
    quote = ''
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != '\\':
                quote = ''
            i += 1
            continue
        if ch in ('\'', '"', '`'):
            quote = ch
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i
        i += 1
    return text[start + 1:], len(text)


def split_objects(text: str):
    out, depth, start, quote = [], 0, None, ''
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != '\\':
                quote = ''
            i += 1
            continue
        if ch in ('\'', '"', '`'):
            quote = ch
        elif ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i + 1])
                start = None
        i += 1
    return out


def parse_route(block: str, parent: str = '') -> list[dict]:
    pm = re.search(r"path:\s*'([^']*)'", block)
    if not pm:
        return []
    raw = pm.group(1)
    full = (parent.rstrip('/') + '/' + raw.lstrip('/')).replace('//', '/') if raw else parent
    if not full.startswith('/'):
        full = '/' + full
    comp = re.search(r"import\('([^']+)'\)", block)
    redirect = re.search(r"redirect:\s*'([^']*)'", block)
    meta = re.search(r"meta:\s*\{([^{}]*)\}", block)
    roles = []
    if meta:
        rm = re.search(r"roles:\s*\[([^\]]*)\]", meta.group(1))
        if rm:
            roles = re.findall(r"'([^']+)'", rm.group(1))
    rows = [{'path': full if (raw or parent) else '/',
             'component': comp.group(1) if comp else '',
             'redirect': redirect.group(1) if redirect else '',
             'roles': roles}]
    cm = re.search(r'children:\s*\[', block)
    if cm:
        arr, _ = find_array(block, block.index('[', cm.start()))
        for child in split_objects(arr):
            rows.extend(parse_route(child, full))
    return rows


def parse_pages() -> list[dict]:
    text = ROUTER.read_text(encoding='utf-8')
    m = re.search(r'const routes[^=]*=\s*\[', text)
    if not m:
        return []
    arr, _ = find_array(text, text.index('[', m.end() - 1))
    out = []
    for block in split_objects(arr):
        out.extend(parse_route(block))
    return out


# ---------------- 接口（静态解析，带文件/行号） ----------------
def parse_api_file(p: Path) -> list[dict]:
    text = p.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'APIRouter\(\s*(?:[^)]*?)prefix\s*=\s*["\']([^"\']*)["\']', text, re.S)
    prefix = m.group(1) if m else ''
    rows = []
    for mt in DECOR.finditer(text):
        sub = mt.group('path')
        full = (prefix.rstrip('/') + '/' + sub.lstrip('/')).replace('//', '/')
        if not full.startswith('/'):
            full = '/' + full
        line = text[:mt.start()].count('\n') + 1
        rest = text[mt.end():]
        dm = re.search(r'\ndef\s+([A-Za-z_][A-Za-z0-9_]*)', rest)
        rows.append({'method': mt.group('method').upper(), 'path': full,
                     'func': dm.group(1) if dm else '—', 'line': line, 'file': p})
    return rows


def collect_api() -> list[dict]:
    items = []
    for p in sorted(API.rglob('*.py')):
        if '__pycache__' in p.parts or p.name == '__init__.py':
            continue
        items.extend(parse_api_file(p))
    if MAIN.exists():
        text = MAIN.read_text(encoding='utf-8', errors='replace')
        for mt in re.finditer(r'@app\.(?P<method>get|post|put|patch|delete)\('
                              r'\s*["\'](?P<path>[^"\']*)', text):
            line = text[:mt.start()].count('\n') + 1
            rest = text[mt.end():]
            dm = re.search(r'\ndef\s+([A-Za-z_][A-Za-z0-9_]*)', rest)
            items.append({'method': mt.group('method').upper(), 'path': mt.group('path'),
                          'func': dm.group(1) if dm else '—', 'line': line, 'file': MAIN})
    seen, uniq = set(), []
    for it in items:
        key = (it['method'], it['path'], str(it['file']), it['line'])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq


def domain_of(p: Path) -> str:
    try:
        rel = p.relative_to(API / 'v1')
    except ValueError:
        return p.stem if p.name != 'main.py' else 'app-main'
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


PAGE_GROUPS = [
    ('/admin', '管理端', '`src/views/admin/**` 或 `.vtj/vue/admin_*`'),
    ('/teacher', '教师端', '`src/views/teacher/**` 或 `.vtj/vue/teacher_*`'),
    ('/mobile', '手机端专用', '复用/轻量包装，守 R12'),
    ('/tablet', '平板端专用', '多数是 redirect 到电脑端'),
    ('/materials', '备考资料（资料页/详情/上传/预览）', '本模块主力页面'),
    ('/study-plan', '模块4 学习计划', '远端新增'),
    ('/ai-assistant', '模块7 联考小智', '远端新增'),
    ('/knowledge', '模块7 知识图谱', '远端新增'),
    ('/memories', '模块7 AI 记忆', '远端新增'),
    ('/profile-quiz', 'AI 错题本（问卷式）', '远端新增'),
    ('/news', '新闻模块', '远端新增'),
    ('/forum', '社区论坛', ''),
    ('/exam', '考试与试卷', ''),
    ('/paper', '试卷答题与结果', ''),
    ('/practice', '练习', ''),
    ('/wrong', '错题本', ''),
    ('/growth', '成长/目标', ''),
    ('/achievements', '成长/目标', ''),
    ('/profile', '个人中心', ''),
]

DOMAIN_LABEL = {
    'platform': '平台域（管理端/教师端/通知/反馈/LLM/WebSocket）',
    'catalog': '题库域（目录/题目/试卷/导入）',
    'community': '社区域（论坛/举报/治理）',
    'exam': '考试域（考试执行/成绩/练习）',
    'library': '资料域（备考资料/个人库/上传/图片）',
    'growth': '成长域（成就/金币/目标/学习计划）',
    'content': '内容域（新闻/招聘/日历）',
    'identity': '身份域（登录/注册/设备/二维码）',
    'personal': '个人域（收藏/笔记）',
    'reward': '奖励域（金币流水）',
    'agent': 'Agent 路由',
    'knowledge': '知识图谱',
    'llm': '大模型对话',
    'media_assets': '媒体资产代理',
    'app-main': '应用级（健康检查/指标/静态）',
    'post': '帖子（根级旧接口）',
}


def page_group(path: str):
    for prefix, title, note in PAGE_GROUPS:
        if path == prefix or path.startswith(prefix.rstrip('/') + '/'):
            return title, note
    return '其它页面（首页/登录/答题等）', ''


def link_for(comp: str) -> str:
    if not comp:
        return ''
    if comp.startswith('@/'):
        return '../../src/' + comp[2:]
    if comp.startswith('$vtj/'):
        return '../../.vtj/' + comp[len('$vtj/'):]
    return '../../' + comp


def main():
    routes = parse_pages()
    pages = [r for r in routes if r['component']]
    redirects = [r for r in routes if r['redirect']]
    apis = collect_api()

    by_page = defaultdict(list)
    for p in pages:
        by_page[page_group(p['path'])[0]].append(p)

    by_domain = defaultdict(list)
    for a in apis:
        by_domain[domain_of(a['file'])].append(a)

    L = []
    L.append('# 远端 main 页面与接口清单 v1')
    L.append('')
    L.append('> 自动生成，可重复运行刷新：`python scripts/gen_inventory.py`（在仓库根执行）')
    L.append('> 页面：解析 `src/router/index.ts`（含嵌套 children 展开）；'
             '接口：静态解析 `backend/app/api/**` 的 `@router.<method>(...)` + `main.py` 的 `@app.<method>`')
    L.append(f'> 统计：**页面 {len(pages)} 条**（另有 {len(redirects)} 条 redirect）、'
             f'**接口 {len(apis)} 个操作**')
    L.append('')
    L.append('文件列是相对本文件的链接（带行号锚点），编辑器 / GitHub 可直接点开。')
    L.append('')

    L.append('## 一、页面路由（按模块）')
    L.append('')
    order = [g[1] for g in PAGE_GROUPS] + ['其它页面（首页/登录/答题等）']
    seen = set()
    for title in order:
        if title in seen:
            continue
        seen.add(title)
        items = by_page.get(title)
        if not items:
            continue
        note = next((n for _, t, n in PAGE_GROUPS if t == title), '')
        L.append(f'### {title}（{len(items)}）')
        if note:
            L.append(f'> {note}')
        L.append('')
        L.append('| 路径 | 角色 | 组件文件 |')
        L.append('|---|---|---|')
        for p in sorted(items, key=lambda x: x['path']):
            target = link_for(p['component'])
            cell = f'[{p["component"]}]({target})' if target else '—'
            L.append(f"| `{p['path']}` | {','.join(p['roles']) or '—'} | {cell} |")
        L.append('')

    if redirects:
        L.append(f'### redirect（{len(redirects)}）')
        L.append('')
        L.append('| 旧路径 | 跳转到 |')
        L.append('|---|---|')
        for r in sorted(redirects, key=lambda x: x['path']):
            L.append(f"| `{r['path']}` | `{r['redirect']}` |")
        L.append('')

    L.append('## 二、接口（按后端域）')
    L.append('')
    for domain in sorted(by_domain, key=lambda d: (-len(by_domain[d]), d)):
        items = by_domain[domain]
        label = DOMAIN_LABEL.get(domain, domain)
        L.append(f'### {label}（`{domain}`，{len(items)} 操作）')
        L.append('')
        L.append('| 方法 | 路径 | 处理函数 | 代码位置 |')
        L.append('|---|---|---|---|')
        for a in sorted(items, key=lambda x: (x['path'], x['method'])):
            rel = a['file'].relative_to(REPO).as_posix()
            L.append(f"| `{a['method']}` | `{a['path']}` | `{a['func']}` | "
                     f"[{rel}:{a['line']}](../../{rel}#L{a['line']}) |")
        L.append('')

    L.append('## 三、代码位置索引')
    L.append('')
    L.append('| 层 | 位置 | 说明 |')
    L.append('|---|---|---|')
    L.append('| 前端路由 | [src/router/index.ts](../../src/router/index.ts) | 全部页面与守卫 |')
    L.append('| 前端页面 | [src/views/](../../src/views/) | 手写页（admin/teacher/student/dev） |')
    L.append('| VTJ 页面 | [.vtj/vue/](../../.vtj/vue/) | 设计器页面（禁改 template，守 R3） |')
    L.append('| 后端入口 | [backend/app/main.py](../../backend/app/main.py) | 全部 `include_router` |')
    L.append('| 后端接口 | [backend/app/api/v1/](../../backend/app/api/v1/) | 按域分目录 |')
    L.append('| 数据模型 | [backend/app/models/models.py](../../backend/app/models/models.py) | 全部 ORM 模型 |')
    L.append('| 门禁 | [backend/scripts/gates/](../../backend/scripts/gates/) | L0–L7 + 注解前瞻检查 |')
    L.append('')
    L.append('---')
    L.append('')
    L.append('**基线**：远端 `main@1864593`（2026-11-04）')
    L.append('')

    DOC.write_text('\n'.join(L), encoding='utf-8')
    print('written', DOC)
    print('pages', len(pages), 'redirects', len(redirects), 'ops', len(apis),
          'page_groups', len(by_page), 'domains', len(by_domain))


if __name__ == '__main__':
    main()
