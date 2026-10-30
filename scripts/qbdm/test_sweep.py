#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QBDM 逐文件测试扫描器 —— 全量 pytest 挂起时用来定位"卡在哪个文件 + 哪些文件红"。

为什么需要它：
    `pytest tests -q` 在本项目会挂起（实测 CPU 5 分钟仅 +1.2s，无输出），
    一次挂起就把"能不能合并"的判定拖死。逐文件 + 单文件超时，可在 5-10 分钟内
    得到"OK / FAIL / HANG"三态清单，并锁定挂起文件。

用法（在 backend/ 下执行）：
    python ../scripts/qbdm/test_sweep.py --suite tests --timeout 90
    python ../scripts/qbdm/test_sweep.py --suite tests/test_api_surface.py

退出码：0 = 全 OK；1 = 存在 FAIL 或 HANG（便于接 CI / 门禁）。
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import tempfile
import time


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description='QBDM 逐文件测试扫描器（单文件超时）')
    parser.add_argument('--suite', default='tests', help='测试目录或单个文件，默认 tests')
    parser.add_argument('--timeout', type=int, default=90, help='单文件超时秒数，默认 90')
    parser.add_argument('--log', default=None, help='失败详情日志路径，默认写入系统临时目录')
    args = parser.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.suite, 'test_*.py'))) if os.path.isdir(args.suite) else [args.suite]
    if not files:
        print('未找到测试文件:', args.suite)
        return 1

    log_path = args.log or os.path.join(tempfile.gettempdir(), f'qbdm_test_sweep_{time.strftime("%Y%m%d_%H%M%S")}.log')
    counts = {'OK': 0, 'FAIL': 0, 'HANG': 0}
    bad: list[tuple[str, str]] = []
    out_tmp = os.path.join(tempfile.gettempdir(), 'qbdm_sweep_one.out')

    print(f'files {len(files)} | timeout {args.timeout}s/file | detail {log_path}', flush=True)
    with open(log_path, 'w', encoding='utf-8') as log:
        for path in files:
            started = time.time()
            with open(out_tmp, 'w', encoding='utf-8') as fh:
                try:
                    code = subprocess.run(
                        [sys.executable, '-m', 'pytest', path, '-q', '--no-header', '-p', 'no:cacheprovider'],
                        stdout=fh, stderr=subprocess.STDOUT, timeout=args.timeout).returncode
                    status = 'OK' if code == 0 else 'FAIL'
                except subprocess.TimeoutExpired:
                    status = 'HANG'
            counts[status] += 1
            print(f'{status:5} {path:50} {time.time() - started:5.1f}s', flush=True)
            if status != 'OK':
                bad.append((status, path))
                log.write('=' * 70 + f'\n{status} {path}\n')
                with open(out_tmp, encoding='utf-8', errors='replace') as fh:
                    log.writelines(fh.readlines()[-40:])
                log.flush()

    print(f'SUMMARY {counts}')
    for status, path in bad:
        print(f'BAD {status:5} {path}')
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main())
