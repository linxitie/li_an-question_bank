#!/usr/bin/env python3
"""gate_all.py — 一键执行 L0-L5，聚合退出码"""
import subprocess, sys, os, json, time

GATES = [
    ('L0', 'scripts/gate_l0_redlines.py', []),
    # L1-G 必须排在 L1 之前：它守「公专基线内 2583 题逐字段不变」这条最高红线，
    # 且耗时 ~2s，故纳入 --quick。
    ('L1-G', 'scripts/gate_l1g_field_fingerprint.py', []),
    ('L3', 'scripts/gate_l3_ingest.py', []),
    ('L1', 'scripts/gate_l1_parser.py', ['--subject', 'gongzhuan']),
    ('L2', 'scripts/gate_l2_matching.py', []),
    ('L4', 'scripts/gate_l4_api_contract.py', []),
    ('L5', 'scripts/gate_l5_frontend_contract.py', []),
]

QUICK_GATES = ('L0', 'L1-G', 'L1')

def main():
    quick = '--quick' in sys.argv
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
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, script] + args,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            cwd=os.path.join(os.path.dirname(__file__), '..')
        )
        elapsed = time.time() - t0
        status = 'PASS' if r.returncode == 0 else 'FAIL'
        results.append({'layer': name, 'status': status, 'elapsed_s': round(elapsed, 1)})
        print(f'  {status}  {name}  ({elapsed:.1f}s)')
        if r.returncode != 0 and r.stdout:
            for line in r.stdout.strip().split('\n')[-3:]:
                print(f'       {line}')

    # 写 last_run.json
    os.makedirs('data/gates', exist_ok=True)
    with open('data/gates/last_run.json', 'w', encoding='utf-8') as f:
        json.dump({'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'results': results}, f, ensure_ascii=False, indent=2)

    failed = sum(1 for r in results if r['status'] == 'FAIL')
    print(f'\ngate_all: {len(results) - failed}/{len(results)} 通过')
    sys.exit(1 if failed > 0 else 0)

if __name__ == '__main__':
    main()
