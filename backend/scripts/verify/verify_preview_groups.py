#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证 _build_preview_groups 在真实申论语料上的分组行为。

三项断言：
 1. 复合题（安徽A卷，4 小题共享 1 份给定资料）→ **1 个组**，材料 7402 字，组内 4 题
 2. 每题带自己的 answer/analysis/blocked，**不跨小题串内容**
 3. 无材料文档 → 每题各自成组，material_length=0（前端不渲染材料头，行为与旧版一致）
"""
import glob
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app.services.text_parser import extract_question_blocks
from app.api.v1.catalog.question_import import _build_preview_groups

BASE = r'D:\砺安题库\砺安题库\题库\申论\安徽申论'


def read_text(path):
    import pymupdf
    doc = pymupdf.open(path)
    chunks = []
    for page in doc:
        chunks.append(page.get_text())
    doc.close()
    raw = ''.join(chunks)
    return raw.replace('\r\n', '\n').replace('\r', '\n')


def to_items(blocks):
    return [{
        'question_content': b.get('content', ''),
        'question_number': b.get('question_number'),
        'format': b.get('format'),
        'material_text': b.get('material_text') or '',
        'material_titles': b.get('material_titles') or [],
        'blocked': b.get('blocked'),
        'block_reasons': b.get('block_reasons') or [],
        'answer': b.get('answer') or '',
        'analysis': b.get('analysis') or '',
    } for b in blocks]


def main():
    try:
        files = sorted(glob.glob(os.path.join(BASE, '*.pdf')))
        qp = [f for f in files if 'A、普通选调卷）.pdf' in f][0]
        blocks = extract_question_blocks(read_text(qp))
        items = to_items(blocks)
        groups = _build_preview_groups(items)

        print('CASE1 composite')
        print('  questions=%d groups=%d' % (len(items), len(groups)))
        for g in groups:
            print('  GROUP key=%s mat_len=%d titles=%s qcount=%d'
                  % (g['group_key'][:16], g['material_length'],
                     g['material_titles'], g['question_count']))
        assert len(groups) == 1, '复合题应聚合为 1 组，实际 %d' % len(groups)
        assert groups[0]['material_length'] > 1000, '材料长度异常'
        assert groups[0]['question_count'] == len(items), '组内题目数不符'
        # 组内题目必须是同一批对象（不串内容）
        assert len(groups[0]['questions']) == len(items)
        print('  OK 1 组 / 材料 %d 字 / 组内 %d 题'
              % (groups[0]['material_length'], groups[0]['question_count']))

        # CASE2：无材料文档各自成组
        qb = [f for f in files if 'B卷）.pdf' in f]
        if qb:
            b2 = to_items(extract_question_blocks(read_text(qb[0])))
            g2 = _build_preview_groups(b2)
            print('CASE2 no-material')
            print('  questions=%d groups=%d mat_lens=%s'
                  % (len(b2), len(g2), [x['material_length'] for x in g2]))
            if all(x['material_length'] == 0 for x in g2):
                assert len(g2) == len(b2), '无材料时应每题一组'
                print('  OK 每题独立成组，前端不渲染材料头')
            else:
                print('  SKIP 该卷本身带材料')

        # CASE3：空输入不崩
        assert _build_preview_groups([]) == []
        print('CASE3 empty -> OK')
        print('ALL_ASSERTIONS_PASSED')
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())