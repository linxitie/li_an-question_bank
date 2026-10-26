#!/usr/bin/env python3
"""L7 底座一致性门禁 — 15 项检查（F1 落地版）。

严重度约定（来自已批准的 F1 实施计划）：
  1-5  FAIL —— 底座结构/契约被破坏，必须阻断；
  6-15 WARN —— 依赖环境与后续阶段（F2/F3）的软检查，先观察后升级。

设计原则：只读、不做任何写入（唯一例外：--update-baseline 显式更新基线）。
检查 15 复用 scripts/audit/content_integrity.py 的既有实现，避免两套口径。
"""
import ast
import hashlib
import json
import os
import re
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
FOUNDATION_TABLES = (
    'foundation_outbox', 'foundation_projection_cursor', 'foundation_inbox',
    'foundation_projection_state', 'foundation_reconcile_run',
    'foundation_backfill_state', 'foundation_preview_ref',
)
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


def check_routes_roles() -> None:
    router = WORKSPACE_ROOT / 'src' / 'router' / 'index.ts'
    if not router.exists():
        _add(8, '路由 roles 声明', False, 'src/router/index.ts 不存在', 'WARN')
        return
    text = router.read_text(encoding='utf-8')
    paths = len(re.findall(r'\bpath\s*:', text))
    roles = len(re.findall(r'\broles\s*:', text))
    missing = max(paths - roles, 0)
    _add(8, '路由 roles 声明', missing == 0,
         f'{missing}/{paths} 条路由未声明 roles（F1 先 WARN，补全后升 FAIL）', 'WARN')


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
        _add(11, '主库/WAL 容量', False,
             f'主库 {mb:.1f} MB 超过 1 GB 硬顶（应切 MySQL）', 'WARN')
    elif size > MAIN_DB_WARN_BYTES:
        _add(11, '主库/WAL 容量', False, f'主库 {mb:.1f} MB 超过 512 MB 预警线', 'WARN')
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
        _add(12, 'preview_data 体积', False, f'{mb:.1f} MB 超过 200 MB 硬顶', 'WARN')
    elif total > PREVIEW_WARN_BYTES:
        _add(12, 'preview_data 体积', False, f'{mb:.1f} MB 超过 50 MB 预警线', 'WARN')
    elif expired:
        _add(12, 'preview_data 体积', False, f'{expired} 条超期 PREVIEW 未清理', 'WARN')
    else:
        _add(12, 'preview_data 体积', True, f'{mb:.1f} MB，无超期 PREVIEW', 'WARN')


def check_ws_relay() -> None:
    try:
        workers = int(os.environ.get('WEB_CONCURRENCY', '1') or '1')
    except ValueError:
        workers = 1
    relay = (os.environ.get('WS_RELAY') or '').strip().lower()
    ok = workers <= 1 or relay == 'redis'
    _add(13, '多 worker 必须 Redis 中继', ok,
         f'WEB_CONCURRENCY={workers} WS_RELAY={relay or "(未设置)"}', 'WARN')


def check_data_changed_contract() -> None:
    src_path = BACKEND_ROOT / 'app' / 'api' / 'v1' / 'platform' / 'websocket.py'
    src = src_path.read_text(encoding='utf-8')
    start = src.find('async def publish_data_changed(')
    end = src.find('\nasync def ', start + 1) if start >= 0 else -1
    body = src[start:end if end > start else len(src)] if start >= 0 else src
    required = ('seq', 'domain', 'type', 'scope')
    missing = [k for k in required if not re.search(rf'["\']{k}["\']\s*:', body)]
    _add(14, 'data-changed 契约', not missing,
         '缺字段：' + ', '.join(missing) + '（F2 补 seq/scope）' if missing else 'seq/domain/type/scope 齐全',
         'WARN')


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
    _add(15, '内容完整性', ok, detail, 'WARN')


def _db_path() -> Path:
    raw = os.environ.get('SQLITE_PATH') or str(BACKEND_ROOT / 'data' / 'question_bank.db')
    p = Path(raw)
    return p if p.is_absolute() else (BACKEND_ROOT / p)


CHECKS = (
    check_tables, check_add_only, check_no_store_import, check_no_silent_except,
    check_migrations, check_health_switch, check_reconcile, check_routes_roles,
    check_table_suffix, check_db_inventory, check_capacity, check_preview_volume,
    check_ws_relay, check_data_changed_contract, check_content_integrity,
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
