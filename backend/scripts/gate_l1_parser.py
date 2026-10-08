#!/usr/bin/env python3
"""L1 解析器结构化指纹门禁 — 包装现有 G1/G2 脚本"""
import subprocess, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def main():
    subject = 'gongzhuan'
    if '--subject' in sys.argv:
        idx = sys.argv.index('--subject')
        subject = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else 'gongzhuan'

    if subject == 'gongzhuan':
        r = subprocess.run(
            [sys.executable, 'scripts/verify_parser_regression.py',
             r'D:\砺安题库\砺安题库\题库\公安题目（打印）', '--out', 'data/parser_regression.txt'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        print(r.stdout[-500:] if r.stdout else '')
        print(f'L1 公专: {"PASS" if r.returncode == 0 else "FAIL"}')
        sys.exit(r.returncode)
    elif subject == 'xingce':
        r = subprocess.run(
            [sys.executable, 'scripts/verify_xingce_regression.py',
             r'D:\砺安题库\砺安题库\题库\行测', '--out', 'data/xingce_regression.txt'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        print(r.stdout[-500:] if r.stdout else '')
        print(f'L1 行测: {"PASS" if r.returncode == 0 else "FAIL"}')
        sys.exit(r.returncode)
    else:
        print(f'L1 {subject}: 暂无专用脚本，跳过')
        sys.exit(0)

if __name__ == '__main__':
    main()
