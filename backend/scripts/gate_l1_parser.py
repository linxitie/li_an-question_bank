#!/usr/bin/env python3
"""L1 解析器结构化指纹门禁 — 包装现有 G1/G2 脚本 + 材料块指纹键。

用法:
  python scripts/gate_l1_parser.py --subject gongzhuan   # 公专 G1
  python scripts/gate_l1_parser.py --subject xingce      # 行测 G2 + 材料块指纹

任务 35（模块 J）新增指纹键（仅 xingce）:
  材料块数                — 资料分析 `（一）…（十）` 材料标记总数
  材料页表格行归属正确率   — 表格行原位落在所属材料块内的比例（J-2-1）

两个键都由 material_guard_scan() 在**真实题本语料**上用生产
`_extract_text_from_pdf` 实测（带磁盘缓存，L1→L2 连续跑不重复扫）。
行测侧原有的 byte 级指纹由 verify_xingce_regression.py 的 .pairs.json 承担，
本脚本只新增这 2 个键，不改既有指纹。
"""
import io
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, '..'))

GONGZHUAN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_DIR)), '题库', '公安题目（打印）')
XINGCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_DIR)), '题库', '行测')
# 材料块指纹基线（S6：资料分析材料块 364 块，J-2 修复后表格行应 100% 归位）
MATERIAL_FINGERPRINT_BASELINE = {
    '材料块数': 364,
    '材料页表格行归属正确率': 1.0,
}

def parse_report_material_blocks(report_path: str):
    """从回归报告里读「资料分析材料块总数」。报告缺失/行缺失 → None。"""
    import re
    if not os.path.exists(report_path):
        return None
    with io.open(report_path, encoding='utf-8', errors='replace') as fh:
        m = re.search(r'资料分析材料块总数\s*[:：]\s*(\d+)', fh.read())
    return int(m.group(1)) if m else None


def main():
    subject = 'gongzhuan'
    if '--subject' in sys.argv:
        idx = sys.argv.index('--subject')
        subject = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else 'gongzhuan'

    if subject == 'gongzhuan':
        r = subprocess.run(
            [sys.executable, 'scripts/verify_parser_regression.py',
             GONGZHUAN_DIR, '--out', 'data/parser_regression.txt'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        print(r.stdout[-500:] if r.stdout else '')
        print(f'L1 公专: {"PASS" if r.returncode == 0 else "FAIL"}')
        sys.exit(r.returncode)
    elif subject == 'xingce':
        out_path = os.path.join(SCRIPT_DIR, '..', 'data', 'xingce_regression.txt')
        r = subprocess.run(
            [sys.executable, 'scripts/verify_xingce_regression.py',
             XINGCE_DIR, '--out', os.path.normpath(out_path)],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        print(r.stdout[-500:] if r.stdout else '')

        # 材料块数：延续 L1 既有 byte 级指纹（S6 基线 364），取自回归报告，
        # 与 data/xingce_regression_baseline.txt 同源可比。
        report_blocks = parse_report_material_blocks(os.path.normpath(out_path))
        from gate_l2_matching import fingerprint, material_guard_scan
        stats = material_guard_scan(XINGCE_DIR)
        fp = fingerprint(stats)
        if report_blocks is not None:
            fp['材料块数'] = report_blocks

        print('\n材料块指纹（真实题本语料）')
        for key, base in MATERIAL_FINGERPRINT_BASELINE.items():
            val = fp[key]
            mark = '✅' if abs(float(val) - float(base)) < 1e-9 else '❌'
            print(f'  {mark} {key}: {val}（基线 {base}）')
        print(f'L1 材料指纹 JSON: {json.dumps(fp, ensure_ascii=False)}')

        fp_ok = all(
            abs(float(fp[key]) - float(base)) < 1e-9
            for key, base in MATERIAL_FINGERPRINT_BASELINE.items())
        print(f'L1 行测: {"PASS" if (r.returncode == 0 and fp_ok) else "FAIL"}')
        sys.exit(r.returncode if r.returncode != 0 else (0 if fp_ok else 1))
    else:
        print(f'L1 {subject}: 暂无专用脚本，跳过')
        sys.exit(0)


if __name__ == '__main__':
    main()
