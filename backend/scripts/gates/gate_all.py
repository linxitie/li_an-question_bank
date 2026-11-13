#!/usr/bin/env python3
"""gate_all.py — 一键执行 L0-L7，聚合退出码"""
import subprocess, sys, os, json, time, sqlite3

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WORKSPACE_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))

# L6 是 Node 脚本（模块化约束），其余层均为 Python；L6 须以 workspace root 为 cwd。
NODE_GATES = ('L6',)

GATES = [
    ('L0', 'scripts/gates/gate_l0_redlines.py', []),
    # L1-G 必须排在 L1 之前：它守「做题字段一个都不能变」+「题量不许下降」两条线，
    # 且耗时 ~2s，故纳入 --quick。基线见 data/gates/gongzhuan_field_fingerprint.json
    # （含 meta.expected_counts 护栏；重定基线须 --rebaseline --reason "…"）。
    ('L1-G', 'scripts/gates/gate_l1g_field_fingerprint.py', []),
    ('L3', 'scripts/gates/gate_l3_ingest.py', []),
    ('L1', 'scripts/gates/gate_l1_parser.py', ['--subject', 'gongzhuan']),
    # L1-H 排在 L1 之后：它校验的是解析器在行测材料题上的产出（分节、材料边界、
    # 题组归属），须待 L1 解析层稳定后再判。带 --real 以覆盖生产缓存真实题本；
    # 缓存缺失时该段记 SKIP 而非 FAIL，不会造成环境相关的误报。
    ('L1-H', 'scripts/gates/gate_l1h_composite_material.py', ['--real']),
    ('L2', 'scripts/gates/gate_l2_matching.py', []),
    ('L4', 'scripts/gates/gate_l4_api_contract.py', []),
    ('L5', 'scripts/gates/gate_l5_frontend_contract.py', []),
    # L6：模块化约束（VTJ 版本锁定 / 92 处路由动态 import 目标 / 跨域 import）。
    # 脚本自身由文件位置推导仓库根，此处仍按要求以 workspace root 为 cwd。
    ('L6', 'scripts/verify-modularization-constraints.mjs', []),
    # L7：底座一致性（7 表/事件只增/越界引用/迁移/对账/路由角色/容量/内容完整性）。
    # 15 项中 1-5 为 FAIL，6-15 先 WARN，随 F2/F3 逐步升级（方案 §11.2）。
    ('L7', 'scripts/gates/gate_l7_foundation.py', []),
]

QUICK_GATES = ('L0', 'L1-G', 'L1', 'L1-H')

def _has_local_question_db() -> bool:
    """CI 的干净 checkout 不含 gitignore 的 question_bank.db，L1-G 无法执行。"""
    db = os.path.join(BACKEND_ROOT, 'data', 'question_bank.db')
    if not os.path.exists(db):
        return False
    try:
        con = sqlite3.connect('file:%s?mode=ro' % db.replace('\\', '/'), uri=True)
        try:
            return con.execute('SELECT COUNT(*) FROM question_bank').fetchone()[0] > 0
        finally:
            con.close()
    except Exception:
        return False

def main():
    # Windows 控制台默认 GBK：门禁脚本会打印 ✅/ℹ 等字符，子进程直接写 GBK 管道时
    # 抛 UnicodeEncodeError 被误判成 FAIL，本进程再打印含 U+FFFD 的结果又会二次崩溃。
    # 因此强制子进程 UTF-8，并让本进程输出永不因编码失败。
    child_env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

    quick = '--quick' in sys.argv
    ci = '--ci' in sys.argv
    layer_filter = None
    if '--layer' in sys.argv:
        idx = sys.argv.index('--layer')
        layer_filter = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    results = []
    for name, script, args in GATES:
        if quick and name not in QUICK_GATES:
            continue
        if layer_filter and name != layer_filter:
            continue
        if ci and name == 'L1-G' and not _has_local_question_db():
            print('  SKIP  L1-G  (CI 无 question_bank.db 快照；本地仍强制执行)')
            results.append({'layer': name, 'status': 'SKIP', 'elapsed_s': 0.0})
            continue
        t0 = time.time()
        is_node = name in NODE_GATES
        r = subprocess.run(
            (['node'] if is_node else [sys.executable]) + [script] + args,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            cwd=WORKSPACE_ROOT if is_node else BACKEND_ROOT,
            env=child_env,
        )
        elapsed = time.time() - t0
        status = 'PASS' if r.returncode == 0 else 'FAIL'
        results.append({'layer': name, 'status': status, 'elapsed_s': round(elapsed, 1)})
        print(f'  {status}  {name}  ({elapsed:.1f}s)')
        if r.returncode != 0 and r.stdout:
            for line in r.stdout.strip().split('\n')[-3:]:
                print(f'       {line}')

    # 写 last_run.json：必须锚定 BACKEND_ROOT。原先用相对路径 'data/gates'，
    # 从仓库根调用时会写出一个与 backend/data/gates 无关的根级 data/ 目录，
    # 门禁结果既不进基线、又污染工作树。
    out_dir = os.path.join(BACKEND_ROOT, 'data', 'gates')
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'last_run.json'), 'w', encoding='utf-8') as f:
        json.dump({'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'results': results}, f, ensure_ascii=False, indent=2)

    failed = sum(1 for r in results if r['status'] == 'FAIL')
    skipped = sum(1 for r in results if r['status'] == 'SKIP')
    suffix = f'，{skipped} SKIP' if skipped else ''
    print(f'\ngate_all: {len(results) - failed - skipped}/{len(results) - skipped} 通过{suffix}')
    sys.exit(1 if failed > 0 else 0)

if __name__ == '__main__':
    main()
