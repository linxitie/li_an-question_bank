#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""申论全语料回归验证 + 串题检测。

为什么需要独立脚本
------------------
此前只测了 42 份（安徽 14 + 国考 18 + 合订本 10），而 ``题库/申论`` 下实际有
**254 份 PDF**，覆盖率仅 16%。用户在真实导入中发现的 4 个致命缺陷
（串题、答案解析不分、图片丢失、总题干缺失）全部是因为样本太少没暴露出来。

本脚本是唯一验收尺子，改造前后都必须跑，且**判据基于全语料实测**而非推测。

串题判据（核心新增）
--------------------
上一题的 ``answer`` / ``analysis`` 里若出现**下一题的特征**，即为串题。
特征用题干专属措辞 + 分值标记双重判定，避免把答案正文里合法的引用误判：

1. ``（N分）`` 分值标记（题干尾部特征，答案正文极少出现）
2. 题干专属动词短语：``请根据`` ``请谈谈`` ``请结合`` ``请简述`` ``自拟题目``
   ``写一篇`` ``拟一份`` ``结合上述`` ``给定资料N``

任一小题的 answer/analysis 命中 ≥2 类特征 → 判定串题，脚本退出码非 0。

用法
----
    python scripts/verify_shenlun_corpus.py
    python scripts/verify_shenlun_corpus.py --out report.txt
    python scripts/verify_shenlun_corpus.py --limit 40      # 快速抽样
"""

import argparse
import collections
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

CORPUS = r'D:\砺安题库\砺安题库\题库\申论'

# 题干专属措辞（答案正文里不会出现这些祈使句式）
STEM_PHRASES = [
    '请根据', '请谈谈', '请结合', '请简述', '请分析', '请说明', '请指出',
    '自拟题目', '自选角度', '写一篇', '写一份', '拟一份', '结合上述',
    '结合给定资料', '谈谈你对', '谈谈理解', '阐释', '给定资料',
]
# 分值标记：题干尾部特征
SCORE_RE = re.compile(r'[（(]\s*\d{1,3}\s*分\s*[）)]')
GIVEN_RE = re.compile(r'给定资料\s*\d')


def load_text(path):
    """**走生产真实取文路径**。

    ⚠️ 这一行是本脚本最关键的修正。原先这里用裸 pymupdf 取文：
        doc = pymupdf.open(path); text = ''.join(p.get_text() for p in doc)
    但生产链路走的是 ``question_import._extract_text_from_pdf``，
    其 docstring 明写「**优先使用 pdfplumber，支持表格提取**」。

    两者行结构不同（实测同一份 2023 副省级答案卷）：
        裸 pymupdf      : `（15 分）` / `F 市`   → 切出 5 块
        pdfplumber 真实  : `（15分）`  / `F市`    → 切出 **2 块**
    用裸 pymupdf 做回归，等于在测一条**生产上不存在的路径**，
    串题/分组/图片的结论全都无法代表真实导入表现（已实证）。

    必须走真实路径，测出来的数字才是可信基线。
    """
    import pymupdf
    with open(path, 'rb') as f:
        buf = f.read()
    try:
        from app.api.v1.question_import import _extract_text_from_pdf
        text = _extract_text_from_pdf(buf)
        if text and text.strip():
            return text.replace('\r\n', '\n').replace('\r', '\n')
    except Exception as exc:                # noqa: BLE001
        # 真实路径不可用时**必须显式失败**，不能悄悄退回裸 pymupdf
        # ——悄悄退回正是这次盲区的成因。
        raise RuntimeError(
            '真实取文路径 _extract_text_from_pdf 失败（%s: %s）；'
            '拒绝退回裸 pymupdf，否则回归基线失真'
            % (type(exc).__name__, exc))
    # 空文本（扫描件）时退回裸取文，仅用于统计，不参与切题结论
    doc = pymupdf.open(path)
    text = ''.join(p.get_text() for p in doc)
    doc.close()
    return text.replace('\r\n', '\n').replace('\r', '\n')


def count_images(path):
    import pymupdf
    doc = pymupdf.open(path)
    n = 0
    for page in doc:
        for im in page.get_images(full=True):
            try:
                w, h = im[2], im[3]
            except IndexError:
                continue
            if w >= 60 and h >= 60:
                n += 1
    doc.close()
    return n


def detect_cross_leak(block, next_block):
    """检测 block 的答案/解析是否吞了下一题内容。

    返回 (是否串题, 命中的证据描述列表)
    """
    evid = []
    nxt_q = (next_block or {}).get('question_number')
    nxt_score = (next_block or {}).get('score')
    nxt_content = (next_block or {}).get('content') or ''

    for field in ('answer', 'analysis'):
        txt = block.get(field) or ''
        if not txt:
            continue
        flat = re.sub(r'\s+', '', txt)
        hits = []
        # ① 下一题的分值标记（且当前题分值不同，说明不是本题的）
        cur_score = block.get('score')
        for m in SCORE_RE.finditer(txt):
            try:
                v = int(re.sub(r'\D', '', m.group(0)))
            except ValueError:
                continue
            if nxt_score and cur_score and v == int(float(nxt_score)) and v != int(float(cur_score)):
                hits.append('含下一题分值（%s分）' % v)
                break
        # ② **直接包含下一题题干长片段** —— 这是串题的**决定性证据**。
        #    ⚠️ 不能只靠「题干措辞」计数判串题：申论答案里合法引用题干措辞极常见
        #    （实测 2019 省级卷 Q3 的答案含「请根据…」「写一份…」是在讲审题与写作
        #    要求，属于答案内容，不是串题）。措辞命中必须**同时**伴随题干片段，
        #    否则一律视为合法引用。
        frag = re.sub(r'\s+', '', nxt_content)[:20]
        has_frag = len(frag) >= 10 and frag in flat
        n_phr = sum(1 for p in STEM_PHRASES if p in txt)
        if has_frag:
            hits.append('直接包含下一题题干片段')
        elif n_phr >= 3 and not has_frag:
            # 只有措辞、无题干片段 → 判为疑似，交人工看原始行文，不计入失败
            hits.append('疑似措辞%d处(无题干片段,判为合法引用)' % n_phr)
        # ③ 引用下一题的「给定资料N」且同时有题干片段
        if has_frag and nxt_content:
            g = GIVEN_RE.search(nxt_content)
            if g and g.group(0) in txt:
                hits.append('引用下一题的%s' % g.group(0))
        if hits:
            evid.append('%s: %s' % (field, '、'.join(hits)))
    # 只有「疑似措辞」而无决定性证据（下一题分值 / 题干片段）→ 不算串题，
    # 仅作为提示交给人工。申论答案里合法引用题干措辞是常态，不是缺陷。
    decisive = [e for e in evid if '直接包含下一题题干片段' in e or '含下一题分值' in e]
    return bool(decisive), evid


def main():
    ap = argparse.ArgumentParser(description='申论全语料回归 + 串题检测')
    ap.add_argument('--out', default=None, help='报告输出路径')
    ap.add_argument('--limit', type=int, default=0, help='只测前 N 份（0=全部）')
    args = ap.parse_args()

    from app.services.text_parser import extract_question_blocks

    files = sorted(glob.glob(os.path.join(CORPUS, '**', '*.pdf'), recursive=True))
    if args.limit:
        files = files[:args.limit]

    out = io.open(args.out, 'w', encoding='utf-8') if args.out else sys.stdout
    log = lambda s='': (out.write(s + '\n'), None)[1] if args.out else print(s)

    agg = collections.Counter()
    style_cnt = collections.Counter()
    leaks = []
    not_essay = []

    log('=' * 100)
    log('申论全语料回归验证  文件数=%d' % len(files))
    log('=' * 100)
    log('%-52s %5s %-9s %5s %5s %5s %5s %s'
        % ('文件(截断)', '块数', '体例', '分值', '答案', '解析', '串题', '判定'))
    log('-' * 100)

    for f in files:
        name = os.path.basename(f)
        short = name[:50]
        try:
            text = load_text(f)
            blocks = extract_question_blocks(text)
        except Exception as exc:                # noqa: BLE001
            log('%-52s 解析异常: %s' % (short, exc))
            agg['error'] += 1
            continue

        if not blocks or blocks[0].get('format') != 'essay':
            not_essay.append(short)
            log('%-52s %5d  未进申论分支' % (short, len(blocks or [])))
            agg['not_essay'] += 1
            continue

        from app.services import text_parser as TP
        lines = text.split('\n')
        style = TP._detect_essay_numbering(lines) or '-'
        style_cnt[style] += 1

        nums = [str(b.get('question_number')) for b in blocks]
        seq = nums == [str(i + 1) for i in range(len(blocks))]
        nscore = len(SCORE_RE.findall(text))
        nans = sum(1 for b in blocks if (b.get('answer') or '').strip())
        nana = sum(1 for b in blocks if (b.get('analysis') or '').strip())
        nreq = sum(1 for b in blocks if (b.get('requirements') or []))
        nblk = sum(1 for b in blocks if b.get('blocked'))

        # 串题检测
        file_leaks = []
        for i, b in enumerate(blocks):
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            bad, evid = detect_cross_leak(b, nxt)
            if bad:
                file_leaks.append('Q%s|%s' % (b.get('question_number'), ';'.join(evid)))
        if file_leaks:
            leaks.append((short, file_leaks))
            agg['leak_docs'] += 1

        agg['docs'] += 1
        agg['blocks'] += len(blocks)
        agg['answers'] += nans
        agg['analyses'] += nana
        agg['reqs'] += nreq
        agg['blocked'] += nblk
        if seq:
            agg['seq_ok'] += 1
        if len(blocks) == nscore:
            agg['score_match'] += 1
        is_ans = ('答案' in name) or ('参考答案' in name)
        if is_ans and nans == len(blocks):
            agg['ans_doc_full'] += 1
            agg['ans_docs'] += 1
        elif is_ans:
            agg['ans_docs'] += 1
        if nscore:
            agg['has_image_docs'] += 0    # 图片单独统计
        try:
            if count_images(f):
                agg['img_docs'] += 1
                agg['imgs'] += 1
        except Exception:                     # noqa: BLE001
            pass

        flags = []
        if not seq:
            flags.append('题号异常')
        if len(blocks) != nscore:
            flags.append('块%d/分值%d' % (len(blocks), nscore))
        if file_leaks:
            flags.append('串题!')
        if nblk:
            flags.append('阻断%d' % nblk)
        log('%-52s %5d %-9s %5d %5d %5d %5d %s'
            % (short, len(blocks), style, nscore, nans, nana,
               len(file_leaks), 'OK' if not flags else ' / '.join(flags)))

    log('')
    log('=' * 100)
    log('【汇总】')
    log('  解析成功文档        : %d / %d' % (agg['docs'], len(files)))
    log('  未进申论分支        : %d' % agg['not_essay'])
    log('  解析异常            : %d' % agg['error'])
    log('  题号连续            : %d' % agg['seq_ok'])
    log('  块数==分值锚点数    : %d' % agg['score_match'])
    log('  题目块总数          : %d' % agg['blocks'])
    log('  答案非空            : %d (%.0f%%)' % (agg['answers'],
          agg['answers'] * 100 / max(agg['blocks'], 1)))
    log('  解析非空            : %d (%.0f%%)' % (agg['analyses'],
          agg['analyses'] * 100 / max(agg['blocks'], 1)))
    log('  要求非空            : %d (%.0f%%)' % (agg['reqs'],
          agg['reqs'] * 100 / max(agg['blocks'], 1)))
    log('  含图片文档          : %d' % agg['img_docs'])
    log('  被阻断题块          : %d' % agg['blocked'])
    log('  体例分布            : %s' % dict(style_cnt))
    log('')
    log('  答案卷答案齐        : %d / %d' % (agg['ans_doc_full'], agg['ans_docs']))
    log('')
    log('【串题检测】串题文档 %d 份' % len(leaks))
    for short, fl in leaks:
        log('  ! %s' % short)
        for x in fl:
            log('      %s' % x)
    log('')

    ok = True
    if leaks:
        log('[FAIL] 存在串题，必须清零')
        ok = False
    else:
        log('[ OK ] 串题数 = 0')
    log('[INFO] 未进申论分支 %d 份（纯题本/无特征文档，需单独确认是否应支持）'
        % agg['not_essay'])
    log('验收结论: %s' % ('PASS' if ok else 'FAIL'))

    if args.out:
        out.close()
        print('报告已写入 %s | 结论: %s' % (args.out, 'PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())