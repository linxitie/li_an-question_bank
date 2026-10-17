# -*- coding: utf-8 -*-
"""T13 复核：小 min 边图片到底是碎片还是合法宽扁图表？

仅看 min_side 会把「20 x 400」这类宽扁图表误判为碎片。
本探针按 (min_side, max_side, 长宽比, 总像素) 四维交叉核对。
"""
import os
import re
import sys
import collections

ROOT = 'D:/砺安题库/砺安题库/题库/行测'
CS_SPEC = {'devicergb', 'rgb', 'devicegray', 'g', 'calgray',
           'devicecmyk', 'cmyk'}


def main():
    import pdfplumber
    rows = []
    for prov in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, prov)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith('.pdf') or '答案解析' in fn:
                continue
            try:
                with pdfplumber.open(os.path.join(d, fn)) as pdf:
                    for pg in pdf.pages:
                        for im in (getattr(pg, 'images', None) or []):
                            cs = im.get('colorspace')
                            if not cs or im.get('bits') != 8:
                                continue
                            key = re.sub(r'[^A-Za-z0-9]', '', str(cs[0])).lower()
                            if key not in CS_SPEC:
                                continue
                            ss = im.get('srcsize') or (0, 0)
                            w, h = int(ss[0]), int(ss[1])
                            if w > 0 and h > 0:
                                rows.append((prov, w, h))
            except Exception:
                pass

    print('总图片 %d' % len(rows))

    # 小 min 边但大总像素 —— 若存在且不少，则不能只看 min_side
    small_but_big = [r for r in rows
                     if min(r[1], r[2]) < 40 and max(r[1], r[2]) * min(r[1], r[2]) >= 20000]
    print()
    print('=== min<40 且 总像素>=2万 的图（宽扁图表候选）===')
    print('  数量: %d' % len(small_but_big))
    for prov, w, h in small_but_big[:15]:
        print('    %-12s %dx%d  min=%d max=%d 总像素=%d 长宽比=%.1f'
              % (prov, w, h, min(w, h), max(w, h), w * h, max(w, h) / max(1, min(w, h))))

    # 真正的小碎片：min<40 且 max 也小（近正方的小块）
    frag = [r for r in rows if min(r[1], r[2]) < 40 and max(r[1], r[2]) < 100]
    print()
    print('=== min<40 且 max<100 的近方小块（碎片候选）===')
    print('  数量: %d' % len(frag))
    print('  尺寸分布:')
    for k, v in sorted(collections.Counter(
            '%dx%d' % (min(r[1], r[2]), max(r[1], r[2])) for r in frag).items(),
            key=lambda kv: -kv[1])[:12]:
        print('    %-10s %d 张' % (k, v))

    # 分段小结
    print()
    print('=== 按 min 边分段：总数 / 近方小块 / 宽扁大图 ===')
    print('  %-12s %-8s %-10s %-10s' % ('min边区间', '总数', 'max<100', '总像素>=2万'))
    for lo, hi in ((0, 10), (10, 20), (20, 30), (30, 40), (40, 60),
                   (60, 100), (100, 10000)):
        seg = [r for r in rows if lo <= min(r[1], r[2]) < hi]
        sq = [r for r in seg if max(r[1], r[2]) < 100]
        bg = [r for r in seg if r[1] * r[2] >= 20000]
        print('  %-12s %-8d %-10d %-10d'
              % ('%d-%d' % (lo, hi), len(seg), len(sq), len(bg)))

    # 20-29 区间到底是什么
    print()
    print('=== 20-29px 区间逐条（阈值下调与否的关键区间）===')
    seg = [r for r in rows if 20 <= min(r[1], r[2]) < 30]
    print('  数量 %d' % len(seg))
    c = collections.Counter('%dx%d' % (min(r[1], r[2]), max(r[1], r[2])) for r in seg)
    for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:20]:
        print('    %-12s %d 张' % (k, v))
    wide = [r for r in seg if max(r[1], r[2]) >= 100]
    print('  其中 max>=100（宽扁，可能合法）: %d' % len(wide))
    for prov, w, h in wide[:10]:
        print('    %-12s %dx%d 总像素=%d' % (prov, w, h, w * h))
    return 0


if __name__ == '__main__':
    sys.exit(main())