# -*- coding: utf-8 -*-
"""
verify_parser_regression.py — 题目解析器回归验收（P2/P3）
=========================================================

对指定目录下的 docx 逐份解析，输出可对比的指标表：
  块数 / 题号连续性 / **分节污染数** / 题型分布 / 空答案数 / 选项形态

用法：
    python scripts/verify_parser_regression.py "<docx目录>" [--limit 30] [--out <报告路径>]

设计要点：
  - 指标必须**可跨版本对比**，因此固定输出格式，前后各跑一次做 diff
  - 分节污染是 P2 的核心验收项：被分节指令段污染的题块数必须为 0
  - 不写数据库，纯只读解析，可随时安全运行
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
from collections import Counter

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.api.v1.question_import import _extract_text_from_docx  # noqa: E402
from app.services.text_parser import (  # noqa: E402
    extract_question_blocks, _MATERIAL_HEAD_RE,
    _SECTION_DIRECTIVE_RE,
)

# 污染探针：分节指令段（与 _SECTION_DIRECTIVE_RE 同一形态，但独立实现，
# 避免"用被测代码测被测代码"）
POLLUTION_RE = re.compile(
    '[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341]{1,3}\\s*[\u3001\uff0c\uff0e.]\\s*'
    '(?:\u5355\u9879\u9009\u62e9\u9898|\u591a\u9879\u9009\u62e9\u9898|\u4e0d\u5b9a\u9879\u9009\u62e9\u9898|'
    '\u9009\u62e9\u9898|\u5224\u65ad\u9898|\u60c5\u666f\u5206\u6790\u9898|\u6848\u4f8b\u5206\u6790\u9898|'
    '\u7b80\u7b54\u9898|\u8bba\u8ff0\u9898|\u5199\u4f5c\u9898|\u6750\u6599\u9898)'
    '\\s*[\u3002\uff0e.\u3001\uff0c]'
)


def scan(path: str, limit: int, out_path: str) -> int:
    files = [n for n in sorted(os.listdir(path)) if n.lower().endswith('.docx')][:limit]
    f = io.open(out_path, 'w', encoding='utf-8')
    w = f.write

    w('题目解析器回归报告  (docx 目录: %s)\n' % path)
    w('=' * 118 + '\n')
    w('%-3s %-40s %6s %5s %5s %6s %7s %6s  %s\n' % (
        '#', '文件', '块数', '题号', '分节', '污染', '空答案', '断号', '题型分布(前3)'))
    w('-' * 118 + '\n')

    total = Counter()
    contaminated_total = 0
    parsed = 0
    bad_files = []

    for i, name in enumerate(files, 1):
        buf = open(os.path.join(path, name), 'rb').read()
        try:
            text = _extract_text_from_docx(buf)
        except Exception as e:  # noqa: BLE001
            w('%-3d %-40s  PARSE-FAIL %s\n' % (i, name[:40], e))
            bad_files.append(name)
            continue
        blocks = extract_question_blocks(text)
        if not blocks:
            w('%-3d %-40s  0 blocks (len=%d)\n' % (i, name[:40], len(text)))
            bad_files.append(name)
            continue
        parsed += 1
        ns = [b['question_number'] for b in blocks]
        n_contam = sum(1 for b in blocks if POLLUTION_RE.search(b['content']))
        n_empty = sum(1 for b in blocks if not b['answer'])
        n_gap = sum(1 for a, c in zip(ns, ns[1:]) if c != a + 1)
        contiguous = 'OK' if n_gap == 0 else 'GAP%d' % n_gap
        types = Counter(b['question_type'] for b in blocks).most_common(3)
        tstr = ','.join('%s:%d' % (k, v) for k, v in types)

        w('%-3d %-40s %6d %5s %5d %6d %7d %6s  %s\n' % (
            i, name[:40], len(blocks), '1..%d' % max(ns),
            len(POLLUTION_RE.findall(text)), n_contam, n_empty, contiguous, tstr))

        total['blocks'] += len(blocks)
        total['section'] += len(POLLUTION_RE.findall(text))
        total['material'] += len(_MATERIAL_HEAD_RE.findall(text))
        total['empty'] += n_empty
        total['gap'] += n_gap
        contaminated_total += n_contam
        for b in blocks:
            total['type:' + b['question_type']] += 1
            total['opt:%d' % len(b['options'])] += 1

    w('-' * 118 + '\n')
    w('汇总（成功解析 %d / %d 份）\n' % (parsed, len(files)))
    w('  题目块总数        : %d\n' % total['blocks'])
    w('  分节指令段出现次数: %d\n' % total['section'])
    w('  材料头出现次数    : %d\n' % total['material'])
    w('  **被污染题块数**  : %d   %s\n' % (
        contaminated_total,
        'PASS 目标为 0' if contaminated_total == 0 else 'FAIL 存在污染'))
    w('  断号文档行数      : %d\n' % total['gap'])
    w('  空答案题块数      : %d（docx 本就不含答案，属正常）\n' % total['empty'])
    w('  题型分布          : %s\n' % {k[4:]: v for k, v in total.items() if k.startswith('type:')})
    w('  选项数分布        : %s\n' % {k[4:]: v for k, v in total.items() if k.startswith('opt:')})
    if bad_files:
        w('  解析异常文件      : %s\n' % bad_files)
    w('=' * 118 + '\n')

    # ---- 污染残留明细（P2 调试用，设 SHOW_CONTAMINATION=1 开启）----
    if os.environ.get('SHOW_CONTAMINATION') == '1' and contaminated_total:
        w('\n污染题块明细\n')
        w('-' * 118 + '\n')
        shown = 0
        for name in files:
            buf = open(os.path.join(path, name), 'rb').read()
            try:
                text = _extract_text_from_docx(buf)
            except Exception:  # noqa: BLE001
                continue
            for b in extract_question_blocks(text):
                mm = POLLUTION_RE.search(b['content'])
                if not mm:
                    continue
                shown += 1
                w('  [%s] qnum=%s type=%s opts=%d' % (
                    name[:34], b['question_number'], b['question_type'], len(b['options'])))
                w('     ...%r' % b['content'][max(0, mm.start() - 80):mm.start() + 140])
                if shown >= 8:
                    break
            if shown >= 8:
                break
        w('-' * 118 + '\n')

    # 验收判定
    ok = (contaminated_total == 0 and parsed == len(files))
    w('验收结论: %s\n' % ('PASS' if ok else 'FAIL'))
    f.close()
    return 0 if ok else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('docx_dir')
    ap.add_argument('--limit', type=int, default=30)
    ap.add_argument('--out', default=os.path.join(BACKEND_DIR, 'data', 'parser_regression.txt'))
    a = ap.parse_args()
    raise SystemExit(scan(a.docx_dir, a.limit, a.out))
