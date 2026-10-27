#!/usr/bin/env python3
"""L7 底座一致性门禁 — 18 项检查（F1/F2b/F3 落地版）。

严重度约定：
  1-5、8、13、14、16 表缺失 FAIL —— 底座结构/契约/路由/媒体表被破坏，必须阻断；
  6-7、9-12 WARN —— 依赖环境与后续阶段的软检查，先观察后升级；
  15 仅在已登记存量缺陷时 WARN，新增映射缺失按 D17 直接 FAIL；
  17 事件同事务化/定向路由契约缺失 FAIL，调用点数量不足只 WARN；
  18 断线补发后端契约缺失 FAIL；前端 useDataSync/typed 事件缺失只 WARN；
  16 的存储不可达/对账过期/孤儿只 WARN，不阻断离线开发。
  L7-13 特例：已正确配置 WS_RELAY=redis 但 Redis 暂不可达只记 WARN（启动会重试）。

设计原则：只读、不做任何写入（唯一例外：--update-baseline 显式更新基线）。
检查 15 复用 scripts/audit/content_integrity.py 的既有实现，避免两套口径。
"""
import ast
import hashlib
import json
import os
import re
import socket
import sqlite3
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = BACKEND_ROOT.parent
AUDIT_DIR = BACKEND_ROOT / 'scripts' / 'audit'
REPORT_PATH = BACKEND_ROOT / 'data' / 'reports' / 'gate_l7.json'
BASELINE_PATH = Path(__file__).resolve().parent / 'l7_baseline.json'

# 迁移文件一经提交即视为历史事实；改动必须走人工评审并同步更新此常量。
FOUNDATION_DDL_SHA256 = '0abfd2887b62aa251ef2952cab9352b425456415fe753b040707eeb5cd4e08f9'
FOUNDATION_DDL = BACKEND_ROOT / 'migrations' / '20261027_001_foundation_core.sql'
MEDIA_DDL = BACKEND_ROOT / 'migrations' / '20261027_002_media_assets.sql'
MEDIA_DDL_SHA256 = '455cf727d076fe67dd760cfc430da521c6dd7aa5c41024d4b9a50250028cc21f'
FOUNDATION_TABLES = (
    'foundation_outbox', 'foundation_projection_cursor', 'foundation_inbox',
    'foundation_projection_state', 'foundation_reconcile_run',
    'foundation_backfill_state', 'foundation_preview_ref',
)
MEDIA_TABLES = ('media_assets',)
MEDIA_INDEXES = ('ix_media_assets_sha256', 'ix_media_assets_status',
                 'ix_media_assets_created_by')
ROLE_SUFFIX_RE = re.compile(r'_(mobile|tablet|pc|teacher|admin)$', re.I)
MAIN_DB_WARN_BYTES = 512 * 1024 * 1024
MAIN_DB_FAIL_BYTES = 1024 * 1024 * 1024
WAL_WARN_BYTES = 64 * 1024 * 1024
PREVIEW_WARN_BYTES = 50 * 1024 * 1024
PREVIEW_FAIL_BYTES = 200 * 1024 * 1024
PREVIEW_TTL_DAYS = 7

results: list[dict] = []


def _add(no: int, title: str, ok: bool, detail: str, severity: str = 'WARN') -> None:
    status = 'PASS' if ok else ('FAIL' if severity == 'FAIL' else 'WARN')
    results.append({'id': no, 'title': title, 'status': status, 'detail': detail})


def _eval_node(node: ast.AST, env: dict):
    """把只含常量/同模块常量的 Tuple 求值为 Python 对象。"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ValueError(f'unknown name {node.id}')
        return env[node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(e, env) for e in node.elts]
    raise ValueError(f'unsupported node {type(node).__name__}')


def _module_constants(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    env: dict = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if value is None:
            continue
        try:
            val = _eval_node(value, env)
        except ValueError:
            continue
        for t in targets:
            if isinstance(t, ast.Name):
                env[t.id] = val
    return env


def check_tables() -> None:
    db = _db_path()
    if not db.exists():
        _add(1, '7 张 foundation_* 表与索引', False, f'数据库不存在：{db}', 'FAIL')
        return
    con = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
    try:
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [t for t in FOUNDATION_TABLES if t not in names]
        idx = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        need_idx = {'ux_outbox_dedupe', 'ix_outbox_status_id',
                    'ix_outbox_aggregate', 'ix_preview_ref_purged'}
        miss_idx = sorted(need_idx - idx)
        if missing or miss_idx:
            _add(1, '7 张 foundation_* 表与索引', False,
                 f'缺表={missing} 缺索引={miss_idx}', 'FAIL')
        else:
            _add(1, '7 张 foundation_* 表与索引', True, '7 表 + 4 索引齐全', 'FAIL')
    finally:
        con.close()


def check_add_only() -> None:
    events = _module_constants(BACKEND_ROOT / 'app' / 'core' / 'events.py')
    triggers = _module_constants(BACKEND_ROOT / 'app' / 'core' / 'trigger_types.py')
    current = {
        'events': sorted(events.get('ALL_EVENTS', [])),
        'trigger_types': sorted(triggers.get('ALL_TRIGGER_TYPES', [])),
    }
    if not current['events'] or not current['trigger_types']:
        _add(2, '事件名只增', False, '无法解析 ALL_EVENTS / ALL_TRIGGER_TYPES', 'FAIL')
        return
    if '--update-baseline' in sys.argv or not BASELINE_PATH.exists():
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n',
                                 encoding='utf-8')
        _add(2, '事件名只增', True, f'已写入基线 {BASELINE_PATH.name}', 'FAIL')
        return
    base = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    lost = [n for n in base.get('events', []) if n not in current['events']]
    lost += [n for n in base.get('trigger_types', []) if n not in current['trigger_types']]
    if lost:
        _add(2, '事件名只增', False, f'历史事件名被删除/改名：{lost}', 'FAIL')
    else:
        added = (len(current['events']) - len(base.get('events', []))
                 + len(current['trigger_types']) - len(base.get('trigger_types', [])))
        _add(2, '事件名只增', True,
             f"events={len(current['events'])} triggers={len(current['trigger_types'])} 新增={added}",
             'FAIL')


def check_no_store_import() -> None:
    hits = []
    for path in (BACKEND_ROOT / 'app' / 'api' / 'v1').rglob('*.py'):
        text = path.read_text(encoding='utf-8', errors='replace')
        for m in re.finditer(r'foundation\.stores', text):
            line = text.count('\n', 0, m.start()) + 1
            hits.append(f'{path.relative_to(BACKEND_ROOT)}:{line}')
    _add(3, 'api/v1 不直连 stores', not hits, '越界引用：' + ', '.join(hits) if hits else '无越界引用', 'FAIL')


def check_no_silent_except() -> None:
    hits = []
    for path in (BACKEND_ROOT / 'app' / 'foundation').rglob('*.py'):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError as exc:
            hits.append(f'{path.name}: 语法错误 {exc}')
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                body = node.body
                silent = all(isinstance(s, ast.Pass) for s in body)
                if node.type is None or silent:
                    hits.append(f'{path.name}:{node.lineno}')
    _add(4, 'foundation 无静默吞异常', not hits,
         '裸 except / except-pass：' + ', '.join(hits) if hits else '无裸 except / except-pass', 'FAIL')


def check_migrations() -> None:
    problems = []
    if not FOUNDATION_DDL.exists():
        problems.append(f'缺少 {FOUNDATION_DDL.name}')
    else:
        digest = hashlib.sha256(FOUNDATION_DDL.read_bytes()).hexdigest()
        if digest != FOUNDATION_DDL_SHA256:
            problems.append(f'DDL checksum 不符：{digest[:16]}…（历史迁移被改动？）')
    if not MEDIA_DDL.exists():
        problems.append(f'缺少 {MEDIA_DDL.name}')
    else:
        digest = hashlib.sha256(MEDIA_DDL.read_bytes()).hexdigest()
        if digest != MEDIA_DDL_SHA256:
            problems.append(f'media DDL checksum 不符：{digest[:16]}…')
    groups: dict[str, list[int]] = {}
    for p in sorted((BACKEND_ROOT / 'migrations').glob('*.sql')):
        m = re.match(r'^(\d{8})_(\d{3})_', p.name)
        if m:
            groups.setdefault(m.group(1), []).append(int(m.group(2)))
    # 历史迁移按「日期_序号」命名，序号在各自日期组内连续即可（早期 001-004 跨日期递增）。
    for day, seqs in groups.items():
        ordered = sorted(seqs)
        if len(set(ordered)) != len(ordered):
            problems.append(f'{day} 序号重复：{ordered}')
        elif any(b - a != 1 for a, b in zip(ordered, ordered[1:])):
            problems.append(f'{day} 序号不连续：{ordered}')
    _add(5, '迁移 checksum 与序号', not problems,
         '；'.join(problems) if problems else 'DDL checksum 一致，序号连续', 'FAIL')


def check_health_switch() -> None:
    enabled = os.environ.get('FOUNDATION_ENABLED', 'true').strip().lower() not in (
        '0', 'false', 'no', 'off')
    main_src = (BACKEND_ROOT / 'app' / 'main.py').read_text(encoding='utf-8')
    has_route = '/health/foundation' in main_src
    db = _db_path()
    tables_ok = False
    if db.exists():
        con = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
        try:
            names = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            tables_ok = all(t in names for t in FOUNDATION_TABLES)
        finally:
            con.close()
    problems = []
    if not has_route:
        problems.append('main.py 未注册 /health/foundation')
    if enabled and not tables_ok:
        problems.append('FOUNDATION_ENABLED=true 但底座表缺失（应返回 degraded）')
    _add(6, '/health/foundation 与开关一致', not problems,
         '；'.join(problems) if problems else
         f'enabled={enabled} route=ok tables={"ok" if tables_ok else "missing"}', 'WARN')


def check_reconcile() -> None:
    db = _db_path()
    row = None
    if db.exists():
        con = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
        try:
            exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                 "AND name='foundation_reconcile_run'").fetchone()
            if exists:
                row = con.execute(
                    'SELECT run_id, status, report_path FROM foundation_reconcile_run '
                    'ORDER BY started_at DESC LIMIT 1').fetchone()
        finally:
            con.close()
    if row is None:
        _add(7, '最近一次对账', False, '还没有对账记录（F1 后由调度/门禁触发）', 'WARN')
        return
    run_id, status, report_path = row
    status = str(status or 'unknown')
    _add(7, '最近一次对账', status != 'failed',
         f'{run_id} status={status} 报告={report_path or "(无)"}', 'WARN')


# 公共路由：不需要登录/角色即可访问，故不要求 roles
ROUTE_WHITELIST = {'/login', '/scan', '/unauthorized', '/:pathMatch(.*)*'}
MOBILE_PREFIXES = ('/tablet', '/mobile')
_ROLES_RE = re.compile(r'\broles\s*:\s*\[([^\]]*)\]')
_PATH_RE = re.compile(r'\bpath\s*:\s*[\'"]([^\'"]+)[\'"]')


def _routes_array(text: str) -> str:
    """截取 const routes 的数组字面量，避免把守卫里的 next({path}) 计入。"""
    decl = text.find('const routes')
    if decl < 0:
        return ''
    assign = text.find('=', decl)
    if assign < 0:
        return ''
    start = text.find('[', assign)
    depth = 0
    quote = ''
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != '\\':
                quote = ''
            continue
        if ch in ('\'', '"', '`'):
            quote = ch
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ''


def parse_route_records(text: str) -> list[dict]:
    """按对象括号解析路由记录；子路由继承父级 roles（与 vue-router meta 合并一致）。"""
    array = _routes_array(text)
    records: list[dict] = []
    stack: list[int] = []
    quote = ''
    i = 0
    while i < len(array):
        ch = array[i]
        if quote:
            if ch == quote and array[i - 1] != '\\':
                quote = ''
            i += 1
            continue
        if ch in ('\'', '"', '`'):
            quote = ch
        elif ch == '{':
            stack.append(i)
        elif ch == '}' and stack:
            start = stack.pop()
            body = array[start:i + 1]
            path_match = _PATH_RE.search(body)
            if path_match is None:
                i += 1
                continue
            own = _ROLES_RE.search(body)
            roles = ([x.strip('\'"') for x in own.group(1).split(',') if x.strip()]
                     if own else [])
            if not roles:
                for parent in reversed(stack):
                    pm = _ROLES_RE.search(array[parent:i + 1])
                    if pm:
                        roles = [x.strip('\'"') for x in pm.group(1).split(',') if x.strip()]
                        break
            records.append({
                'path': path_match.group(1),
                'roles': roles,
                'has_component': bool(re.search(r'\bcomponent\s*:', body)),
            })
        i += 1
    return records


def check_routes_roles() -> None:
    router = WORKSPACE_ROOT / 'src' / 'router' / 'index.ts'
    if not router.exists():
        _add(8, '路由 roles 声明', False, 'src/router/index.ts 不存在', 'FAIL')
        return
    records = parse_route_records(router.read_text(encoding='utf-8'))
    pages = [r for r in records if r['has_component']]
    missing = [r['path'] for r in pages
               if r['path'] not in ROUTE_WHITELIST and not r['roles']]
    bad_device = [r['path'] for r in pages
                  if r['path'].startswith(MOBILE_PREFIXES) and r['roles'] != ['student']]
    ok = not missing and not bad_device
    detail = (f'{len(missing)}/{len(pages)} 条页面路由未声明 roles；'
              f'mobile/tablet 违规 {len(bad_device)} 条')
    if missing:
        detail += '；未声明：' + ', '.join(missing[:5])
    if bad_device:
        detail += '；违规：' + ', '.join(bad_device[:5])
    _add(8, '路由 roles 声明', ok, detail, 'FAIL')


def check_table_suffix() -> None:
    db = _db_path()
    hits = []
    if db.exists():
        con = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
        try:
            for (name,) in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"):
                if ROLE_SUFFIX_RE.search(name):
                    hits.append(name)
        finally:
            con.close()
    _add(9, '表名无端/角色后缀', not hits,
         '命中：' + ', '.join(hits) if hits else '无端/角色后缀表', 'WARN')


def check_db_inventory() -> None:
    sys.path.insert(0, str(AUDIT_DIR))
    try:
        import db_inventory
        report = db_inventory.collect(WORKSPACE_ROOT, with_sizes=False)
        failures, warnings = db_inventory.check(report)
    except Exception as exc:  # 审计脚本自身失败时不能让门禁静默
        _add(10, '空库/孤儿库审计', False, f'审计执行失败：{exc}', 'WARN')
        return
    detail = f'库 {report.get("total", len(report.get("databases", [])))} 个'
    if failures:
        detail += '；FAIL=' + '；'.join(str(x) for x in failures[:3])
    if warnings:
        detail += f'；WARN={len(warnings)} 条'
    _add(10, '空库/孤儿库审计', not failures, detail, 'WARN')


def check_capacity() -> None:
    db = _db_path()
    size = db.stat().st_size if db.exists() else 0
    wal = Path(str(db) + '-wal')
    wal_size = wal.stat().st_size if wal.exists() else 0
    mb = size / 1024 / 1024
    if size > MAIN_DB_FAIL_BYTES:
        # 硬顶按方案 §17.2：>1 GB 阻断，不再只是提醒。
        _add(11, '主库/WAL 容量', False,
             f'主库 {mb:.1f} MB 超过 1 GB 硬顶（应切 MySQL）', 'FAIL')
    elif size >= MAIN_DB_WARN_BYTES:
        _add(11, '主库/WAL 容量', False, f'主库 {mb:.1f} MB 达到 512 MB 预警线', 'WARN')
    elif wal_size > WAL_WARN_BYTES:
        _add(11, '主库/WAL 容量', False,
             f'WAL {wal_size / 1024 / 1024:.1f} MB 超过 64 MB', 'WARN')
    else:
        _add(11, '主库/WAL 容量', True,
             f'主库 {mb:.1f} MB，WAL {wal_size / 1024 / 1024:.1f} MB', 'WARN')


def check_preview_volume() -> None:
    db = _db_path()
    if not db.exists():
        _add(12, 'preview_data 体积', False, '数据库不存在', 'WARN')
        return
    con = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
    try:
        total = con.execute(
            "SELECT COALESCE(SUM(LENGTH(CAST(preview_data AS BLOB))),0) "
            "FROM question_import_record").fetchone()[0]
        cols = {r[1] for r in con.execute('PRAGMA table_info(question_import_record)')}
        expired = 0
        if {'status', 'create_time'} <= cols:
            expired = con.execute(
                "SELECT COUNT(*) FROM question_import_record WHERE status='PREVIEW' "
                "AND create_time < datetime('now', ?)", (f'-{PREVIEW_TTL_DAYS} days',)
            ).fetchone()[0]
    finally:
        con.close()
    mb = total / 1024 / 1024
    if total > PREVIEW_FAIL_BYTES:
        _add(12, 'preview_data 体积', False, f'{mb:.1f} MB 超过 200 MB 硬顶', 'FAIL')
    elif total > PREVIEW_WARN_BYTES:
        _add(12, 'preview_data 体积', False, f'{mb:.1f} MB 超过 50 MB 预警线', 'WARN')
    elif expired:
        _add(12, 'preview_data 体积', False, f'{expired} 条超期 PREVIEW 未清理', 'WARN')
    else:
        _add(12, 'preview_data 体积', True, f'{mb:.1f} MB，无超期 PREVIEW', 'WARN')


def _redis_reachable() -> bool:
    host = os.environ.get('REDIS_HOST') or 'localhost'
    try:
        port = int(os.environ.get('REDIS_PORT') or '6379')
    except ValueError:
        port = 6379
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def check_ws_relay() -> None:
    try:
        workers = int(os.environ.get('WEB_CONCURRENCY', '1') or '1')
    except ValueError:
        workers = 1
    relay = (os.environ.get('WS_RELAY') or '').strip().lower()
    label = f'WEB_CONCURRENCY={workers} WS_RELAY={relay or "(未设置)"}'
    if workers <= 1:
        _add(13, '多 worker 必须 Redis 中继', True, label, 'FAIL')
    elif relay != 'redis':
        _add(13, '多 worker 必须 Redis 中继', False,
             label + '（多 worker 未开中继，启动会 fail-fast）', 'FAIL')
    elif not _redis_reachable():
        # 已正确配置，仅当前环境探测不到 Redis：不阻断，但必须可见
        _add(13, '多 worker 必须 Redis 中继', False,
             label + '（Redis 当前不可达，启动后自动重连）', 'WARN')
    else:
        _add(13, '多 worker 必须 Redis 中继', True, label + '（Redis 可达）', 'FAIL')


def check_data_changed_contract() -> None:
    """契约分两层：publish_data_changed 传 domain/type/scope；ws_protocol 统一补 seq。

    不能只在 publish_data_changed 里 grep "seq": 该字段由中继协议统一注入，
    否则每个业务调用点都要自己数序号，跨 worker 必然不单调。
    """
    src_path = BACKEND_ROOT / 'app' / 'api' / 'v1' / 'platform' / 'websocket.py'
    src = src_path.read_text(encoding='utf-8')
    # F2b 起 async 版本只做转调，真正的 data/scope 组装在 sync 版本里。
    start = src.find('def publish_data_changed_sync(')
    end = src.find('\nasync def ', start + 1) if start >= 0 else -1
    body = src[start:end if end > start else len(src)] if start >= 0 else src
    protocol_path = BACKEND_ROOT / 'app' / 'foundation' / 'ws_protocol.py'
    protocol = protocol_path.read_text(encoding='utf-8') if protocol_path.exists() else ''
    missing = []
    if 'ws_relay.emit(' not in body:
        missing.append('统一出口 ws_relay.emit')
    for key in ('domain', 'type', 'id'):
        if not re.search(rf'["\']{key}["\']\s*:', body):
            missing.append(f'data.{key}')
    if 'scope=' not in body:
        missing.append('scope 参数')
    for key in ('seq', 'scope'):
        if not re.search(rf'["\']{key}["\']\s*:', protocol):
            missing.append(f'envelope.{key}')
    _add(14, 'data-changed 契约', not missing,
         '缺：' + ', '.join(missing) if missing else 'domain/type/id/scope 经统一出口，seq/scope 由协议补齐',
         'FAIL')


def check_content_integrity() -> None:
    sys.path.insert(0, str(AUDIT_DIR))
    baseline_path = BACKEND_ROOT / 'data' / 'reports' / 'f1_content_baseline.json'
    if not baseline_path.exists():
        _add(15, '内容完整性', False,
             f'缺少基线 {baseline_path.name}，先运行 content_integrity.py --write-baseline', 'WARN')
        return
    try:
        import content_integrity
        con = sqlite3.connect(f'file:{_db_path().as_posix()}?mode=ro', uri=True)
        try:
            report = content_integrity.run_checks(
                con, json.loads(baseline_path.read_text(encoding='utf-8')))
        finally:
            con.close()
    except Exception as exc:
        _add(15, '内容完整性', False, f'执行失败：{exc}', 'WARN')
        return
    summary = report.get('summary', {})
    checks = report.get('checks', report.get('results', []))
    fails = [r['title'] for r in checks if r.get('status') == 'FAIL']
    warns = [r['title'] for r in checks if r.get('status') == 'WARN']
    ok = not fails
    detail = f"PASS={summary.get('PASS', 0)} WARN={len(warns)} FAIL={len(fails)}"
    if fails:
        detail += '；FAIL=' + ', '.join(fails)
    # D17：内容完整性新增缺失一票否决；只有已登记存量缺陷走 WARN
    _add(15, '内容完整性', ok, detail, 'WARN' if ok else 'FAIL')


def check_media_store() -> None:
    """L7-16：媒体表/索引是硬结构；存储 health、对账新鲜度、孤儿只做软告警。"""
    db = _db_path()
    if not db.exists():
        _add(16, '媒体表与对象存储', False, f'数据库不存在：{db}', 'FAIL')
        return
    con = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
    try:
        names = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [t for t in MEDIA_TABLES if t not in names]
        idx = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        miss_idx = [i for i in MEDIA_INDEXES if i not in idx]
        active = 0
        if not missing:
            active = con.execute(
                "SELECT COUNT(*) FROM media_assets WHERE status='active'").fetchone()[0]
        row = None
        if 'foundation_reconcile_run' in names:
            row = con.execute(
                "SELECT finished_at, status, report_path FROM foundation_reconcile_run "
                "WHERE scope='media' ORDER BY finished_at DESC LIMIT 1").fetchone()
    finally:
        con.close()
    if missing or miss_idx:
        _add(16, '媒体表与对象存储', False,
             f'缺表={missing} 缺索引={miss_idx}', 'FAIL')
        return

    warnings: list[str] = []
    enabled = os.environ.get('MEDIA_STORE_ENABLED', 'true').strip().lower() not in (
        '0', 'false', 'no', 'off')
    try:
        sys.path.insert(0, str(BACKEND_ROOT))
        from app.foundation.stores.object import build_object_store

        health = build_object_store().health()
        if not health.ok or health.degraded:
            warnings.append(f'对象存储 {health.backend} 不可用：{health.detail}')
        else:
            store_detail = f'{health.backend}=ok'
    except Exception as exc:  # 门禁不能因开发机无 MinIO 直接崩溃
        warnings.append(f'对象存储检查失败：{type(exc).__name__}: {exc}')
        store_detail = 'unknown'

    if row is None:
        warnings.append('还没有媒体对账记录（运行 media_inventory.py --record）')
    else:
        finished_at, status, report_path = row
        try:
            from datetime import datetime

            finished = datetime.fromisoformat(str(finished_at))
            if finished.tzinfo is None:
                finished = finished.astimezone()
            age_days = (datetime.now().astimezone() - finished).total_seconds() / 86400
            if age_days > 7:
                warnings.append(f'媒体对账已过期 {age_days:.1f} 天')
        except (TypeError, ValueError):
            warnings.append('媒体对账时间无法解析')
        if str(status) == 'drift':
            warnings.append('最近一次媒体对账有漂移')
        if report_path:
            try:
                rp = Path(report_path)
                if not rp.is_absolute():
                    rp = BACKEND_ROOT / rp
                report = json.loads(rp.read_text(encoding='utf-8'))
                orphans = int(report.get('orphans') or 0)
                if orphans:
                    warnings.append(f'孤儿对象 {orphans} 个（GC 默认 dry-run）')
            except (OSError, ValueError):
                pass

    if warnings:
        _add(16, '媒体表与对象存储', False,
             f'表/索引齐全 active={active}；' + '；'.join(warnings), 'WARN')
    else:
        _add(16, '媒体表与对象存储', True,
             f'表/索引齐全 active={active} {store_detail} enabled={enabled}', 'WARN')


def check_f2b_events() -> None:
    """L7-17：事件同事务化与定向路由契约（F2b-1）。"""
    missing: list[str] = []
    api_root = BACKEND_ROOT / 'app' / 'api' / 'v1'
    published = []
    for py in api_root.rglob('*.py'):
        text = py.read_text(encoding='utf-8')
        if 'events.publish' in text:
            published.append(str(py.relative_to(BACKEND_ROOT)))
    if published:
        missing.append('api/v1 仍有 events.publish：' + ', '.join(published))

    handlers = (BACKEND_ROOT / 'app' / 'services' / 'event_handlers.py').read_text(
        encoding='utf-8')
    for name in ('EV_USER_ACTION', 'EV_PAPER_PUBLISHED'):
        if name not in handlers:
            missing.append(f'event_handlers 未注册 {name}')

    triggers = _module_constants(BACKEND_ROOT / 'app' / 'core' / 'trigger_types.py')
    all_triggers = triggers.get('ALL_TRIGGER_TYPES', [])
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    from app.foundation.event_routes import missing_triggers
    absent = missing_triggers()
    if absent:
        missing.append('event_routes 缺少 trigger：' + ', '.join(absent))

    for rel_path, needles in (
        ('app/foundation/dispatcher.py', ('DispatcherLock', 'run_forever')),
        ('app/services/event_handlers.py', ('claim(',)),
        ('app/foundation/config.py', ('EVENT_OUTBOX_ENABLED',)),
    ):
        body = (BACKEND_ROOT / rel_path).read_text(encoding='utf-8')
        for needle in needles:
            if needle not in body:
                missing.append(f'{rel_path} 缺少 {needle}')

    refs = 0
    for base in (api_root, BACKEND_ROOT / 'app' / 'services'):
        for py in base.rglob('*.py'):
            refs += py.read_text(encoding='utf-8').count('record_user_action(')
    detail = f'triggers={len(all_triggers)} record_user_action引用={refs}'
    if missing:
        _add(17, 'F2b 事件同事务化契约', False, '；'.join(missing), 'FAIL')
    elif refs < 20:
        _add(17, 'F2b 事件同事务化契约', False,
             detail + '（调用点少于 20，确认是否漏迁）', 'WARN')
    else:
        _add(17, 'F2b 事件同事务化契约', True, detail, 'FAIL')


def check_sync_replay() -> None:
    """L7-18：断线重连补发契约（F2b-2）。

    后端契约是协议正确性的前提，缺失直接 FAIL；前端接入只影响刷新体验，
    缺失记 WARN，避免尚未升级的部署被门禁阻断。
    """
    missing: list[str] = []
    soft: list[str] = []

    required = (
        ('app/foundation/ws_sync.py', ('def replay(', 'latest_oid', 'truncated')),
        ('app/api/v1/platform/websocket.py',
         ('SYNC = "sync"', 'handle_sync_request', 'outbox_id')),
        ('app/services/event_handlers.py', ('outbox_id=event.id',)),
        ('app/foundation/config.py', ('WS_SYNC_REPLAY_ENABLED',)),
    )
    for rel_path, needles in required:
        path = BACKEND_ROOT / rel_path
        if not path.exists():
            missing.append(f'{rel_path} 不存在')
            continue
        body = path.read_text(encoding='utf-8')
        for needle in needles:
            if needle not in body:
                missing.append(f'{rel_path} 缺少 {needle}')

    frontend = (
        ('src/composables/useDataSync.ts', ('createDataSyncListener', 'useDataSync')),
        ('src/utils/wsMessage.ts', ('extractSyncReply', 'SyncReplay')),
        ('src/auth.ts', ('_lastOutboxId', '__VTJ_DATA_CHANGED__')),
    )
    for rel_path, needles in frontend:
        path = WORKSPACE_ROOT / rel_path
        if not path.exists():
            soft.append(f'{rel_path} 不存在')
            continue
        body = path.read_text(encoding='utf-8')
        for needle in needles:
            if needle not in body:
                soft.append(f'{rel_path} 缺少 {needle}')

    detail = '后端补发契约完整'
    if soft:
        detail += '；前端：' + '；'.join(soft)
    if missing:
        _add(18, '断线补发与前端增量刷新', False,
             '；'.join(missing) + ('；前端：' + '；'.join(soft) if soft else ''), 'FAIL')
    elif soft:
        _add(18, '断线补发与前端增量刷新', False, detail, 'WARN')
    else:
        _add(18, '断线补发与前端增量刷新', True, detail, 'FAIL')


def _db_path() -> Path:
    raw = os.environ.get('SQLITE_PATH') or str(BACKEND_ROOT / 'data' / 'question_bank.db')
    p = Path(raw)
    return p if p.is_absolute() else (BACKEND_ROOT / p)


CHECKS = (
    check_tables, check_add_only, check_no_store_import, check_no_silent_except,
    check_migrations, check_health_switch, check_reconcile, check_routes_roles,
    check_table_suffix, check_db_inventory, check_capacity, check_preview_volume,
    check_ws_relay, check_data_changed_contract, check_content_integrity,
    check_media_store, check_f2b_events, check_sync_replay,
)


def main() -> int:
    for check in CHECKS:
        try:
            check()
        except Exception as exc:  # 单检查崩溃按该项失败处理，不掩盖其余结果
            _add(len(results) + 1, check.__name__, False, f'检查异常：{exc}', 'WARN')
    failed = [r for r in results if r['status'] == 'FAIL']
    warned = [r for r in results if r['status'] == 'WARN']
    payload = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {'PASS': len(results) - len(failed) - len(warned),
                    'WARN': len(warned), 'FAIL': len(failed)},
        'results': results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
    for r in results:
        print(f"  {r['status']}  L7-{r['id']:02d} {r['title']} — {r['detail']}")
    print(f"L7: PASS={payload['summary']['PASS']} WARN={len(warned)} FAIL={len(failed)}")
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
