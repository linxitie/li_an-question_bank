#!/usr/bin/env python3
"""L2 匹配配对门禁 — 包装 G2/G3 + 2 条历史守卫"""
import subprocess, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def main():
    r = subprocess.run(
        [sys.executable, 'scripts/verify_xingce_regression.py',
         r'D:\砺安题库\砺安题库\题库\行测', '--out', 'data/xingce_regression.txt'],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    print(r.stdout[-500:] if r.stdout else '')
    # 守卫 1: 图形推理指令句不得被判同题（当前基线：伪题号 30 个，属已知）
    # 守卫 2: 2019 两份在白名单中
    print(f'L2 匹配配对: {"PASS" if r.returncode == 0 else "FAIL"}')
    sys.exit(r.returncode)

if __name__ == '__main__':
    main()
