#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""量化「裸 pymupdf vs 生产真实路径(pdfplumber)」的切题差异。

背景
----
上一代理的 254 份回归全部用裸 pymupdf 取文，而生产走
``_extract_text_from_pdf``（内部优先 pdfplumber）。实测同一份
2023 副省级答案卷：裸取文 5 块 / 真实路径 2 块。

全量 254 份跑真实路径太慢（会超时），故**抽样**量化影响面：
每份同时用两种方式取文并切题，统计差异。

输出
----
    同为0 块（无题，扫描件等）      -> 跳过，不计差异
    块数相同                        -> 一致
    真实路径块数 < 裸取文块数        -> **少切**（数据损坏风险，最高优先级）
    真实路径块数 > 裸取文块数        -> 多切

用法：python scripts/compare_extract_paths.py [--sample 40]
"""
import argparse
import glob
import io
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CORPUS = r'D:\砺安题库\砺安题库\题库\申论'


def norm(text):
    return (text or '').replace('\r\n', '\n').replace('\r', '\n')


def blocks_of(text):
    from app.services.text_parser import extract_question_blocks
    try:
        bs = extract_question_blocks(norm(text))
    except Exception:
        return []
    return [b for b in bs if b.get('format') == 'essay']


def bare_pymupdf(path):
    import pymupdf
    d = pymupdf.open(path)
    t = ''.join(pg.get_text() for pg in d)
    d.close()
    return t


def real_path(path):
    from app.api.v1.catalog.question_import import _extract_text_from_pdf
    with open(path, 'rb') as f:
        return _extract_text_from_pdf(f.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=40)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(CORPUS, '**', '*.pdf'),
                             recursive=True))
    if args.sample and args.sample < len(files):
        random.seed(20261002)          # 固定种子，结果可复现
        files = random.sample(files, args.sample)

    same = fewer = more = both_zero = err = 0
    detail = []
    for p in files:
        name = os.path.basename(p)[:46]
        try:
            nb = len(blocks_of(bare_pymupdf(p)))
            nr = len(blocks_of(real_path(p)))
        except Exception as exc:                # noqa: BLE001
            err += 1
            detail.append('ERR  %s  %s' % (name, str(exc)[:40]))
            continue
        if nb == 0 and nr == 0:
            both_zero += 1
            continue
        if nr == nb:
            same += 1
        elif nr < nb:
            fewer += 1
            detail.append('LOSS %-46s 裸%d -> 真实%d' % (name, nb, nr))
        else:
            more += 1
            detail.append('MORE %-46s 裸%d -> 真实%d' % (name, nb, nr))

    out = ['=' * 92,
           '取文路径切题差异抽样（裸 pymupdf vs 生产 pdfplumber） 样本=%d' % len(files),
           '=' * 92,
           '一致          : %d' % same,
           '★少切（损坏） : %d' % fewer,
           '多切          : %d' % more,
           '两者均0块     : %d' % both_zero,
           '异常          : %d' % err,
           '']
    out += detail[:40]
    out += ['', '结论: %s' % ('真实路径存在切题损坏，必须修' if fewer
                            else '真实路径未见切题损失')]
    txt = '\n'.join(out)
    with io.open(os.path.join(os.environ.get('TEMP', '.'),
                               'path_diff.txt'), 'w', encoding='utf-8') as f:
        f.write(txt)
    print('SAME=%d LOSS=%d MORE=%d ZERO=%d ERR=%d'
          % (same, fewer, more, both_zero, err))
    return 0


if __name__ == '__main__':
    sys.exit(main())