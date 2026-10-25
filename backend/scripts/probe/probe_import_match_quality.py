#!/usr/bin/env python3
"""导入匹配质量探针（只读）。

用途：在改动 `smart_match_questions_answers` 之前建立可复现基线，量化
「题号 → 答案 → 解析」逐层命中率，并输出失败样例，避免继续凭感觉叠补丁。

用法（backend/ 下）：
    python scripts/probe/probe_import_match_quality.py --limit 10 --step auto
    python scripts/probe/probe_import_match_quality.py --limit 85 --json out.json

口径：
    blocks        题本切出的题块数
    matched       拿到答案的题数（answer 非空）
    analysis      拿到解析的题数
    empty_answer  题块存在但答案为空
    no_options    题块无选项（主观题/判断/材料题），这类题不应落 A/B/C/D
    bad_letter    无选项却落了字母答案（历史事故口径，应为 0）
"""
import argparse
import io
import json
import os
import sys
import time
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
sys.path.insert(0, BACKEND_ROOT)

from app.services.text_parser import smart_match_questions_answers  # noqa: E402
from scripts.gates.gate_l2_matching import CACHE_DIR, cached_text  # noqa: E402

DEFAULT_ROOT = os.path.join(REPO_ROOT, '题库', '行测')


def enumerate_pairs(root):
    """按目录配对题本/答案（与门禁 L2 同源口径）。"""
    pairs = []
    if not os.path.isdir(root):
        return pairs
    for province in sorted(os.listdir(root)):
        pdir = os.path.join(root, province)
        if not os.path.isdir(pdir):
            continue
        qb = ans = None
        for name in sorted(os.listdir(pdir)):
            if not name.lower().endswith('.pdf'):
                continue
            if '答案' in name:
                ans = os.path.join(pdir, name)
            else:
                qb = os.path.join(pdir, name)
        if qb and ans:
            pairs.append((province + '::' + os.path.splitext(os.path.basename(qb))[0], qb, ans))
    return pairs


def load_text(path):
    try:
        text, _hit = cached_text(path, CACHE_DIR)
        return text
    except Exception as exc:  # noqa: BLE001 — 单份失败不阻断探针
        print(f'[skip] {os.path.basename(path)}: {exc}', file=sys.stderr)
        return ''


def measure(key, qb_text, an_text):
    t0 = time.time()
    result = smart_match_questions_answers(qb_text, an_text, key)
    blocks = result.questions or []

    empty_answer = 0
    no_options = 0
    bad_letter = 0
    for block in blocks:
        options = block.get('options') or []
        answer = (block.get('answer') or '').strip()
        if not options:
            no_options += 1
            if answer and all(c in 'ABCD' for c in answer):
                bad_letter += 1
        if not answer:
            empty_answer += 1

    return {
        'paper': key,
        'blocks': len(blocks),
        'matched': result.matched_count,
        'analysis': result.analysis_count,
        'match_rate': round(result.match_rate, 4),
        'empty_answer': empty_answer,
        'no_options': no_options,
        'bad_letter': bad_letter,
        'strategy': result.strategy_used,
        'elapsed_s': round(time.time() - t0, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--step', default='auto', help="'auto' 或整数")
    ap.add_argument('--json', default='')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    pairs = enumerate_pairs(args.root)
    if not pairs:
        print(f'[fatal] 未找到题本/答案配对: {args.root}', file=sys.stderr)
        return 2

    step = max(1, len(pairs) // args.limit) if args.step == 'auto' else max(1, int(args.step))
    sample = pairs[::step][: args.limit]

    rows = []
    for key, qb, ans in sample:
        qb_text = load_text(qb)
        an_text = load_text(ans)
        if not qb_text or not an_text:
            continue
        row = measure(key, qb_text, an_text)
        rows.append(row)
        if not args.quiet:
            print(json.dumps(row, ensure_ascii=False))

    total_blocks = sum(r['blocks'] for r in rows)
    total_matched = sum(r['matched'] for r in rows)
    total_analysis = sum(r['analysis'] for r in rows)
    total_empty = sum(r['empty_answer'] for r in rows)
    total_bad = sum(r['bad_letter'] for r in rows)
    strategies = Counter(r['strategy'] for r in rows)

    summary = {
        'papers': len(rows),
        'blocks': total_blocks,
        'matched': total_matched,
        'analysis': total_analysis,
        'match_rate': round(total_matched / total_blocks, 4) if total_blocks else 0.0,
        'analysis_rate': round(total_analysis / total_blocks, 4) if total_blocks else 0.0,
        'empty_answer': total_empty,
        'bad_letter': total_bad,
        'papers_below_90': [r['paper'] for r in rows if r['match_rate'] < 0.9],
        'strategies': dict(strategies),
    }
    print('\n=== SUMMARY ===')
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.json:
        with io.open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'summary': summary, 'rows': rows}, fh, ensure_ascii=False, indent=2)
        print(f'[json] {args.json}')

    return 0 if summary['match_rate'] >= 0.9 else 1


if __name__ == '__main__':
    raise SystemExit(main())
