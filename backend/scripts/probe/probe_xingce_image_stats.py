# -*- coding: utf-8 -*-
"""T13 前置：统计行测图片尺寸分布（阈值必须数据驱动，不得盲目下调）。

沿用生产路径 pdfplumber 的取法：page.images -> im['srcsize'] / colorspace / bits，
与 _extract_images_from_pdf_page → _pdf_image_to_png 看到的完全是同一批对象。
"""
import os
import re
import sys
import collections
import statistics

ROOT = 'D:/砺安题库/砺安题库/题库/行测'
MIN_DIM = 40          # 现行阈值
CS_SPEC = {'devicergb', 'rgb', 'devicegray', 'g', 'calgray',
           'devicecmyk', 'cmyk'}


def walk_pdfs(root):
    for prov in sorted(os.listdir(root)):
        d = os.path.join(root, prov)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith('.pdf') and '答案解析' not in fn:
                yield prov, os.path.join(d, fn)


def main():
    import pdfplumber
    dims = []            # (min_side, w, h, total_px)
    unsupported = 0
    bits_bad = 0
    per_prov = collections.Counter()
    files = 0
    pages_with_img = 0
    try:
        for prov, path in walk_pdfs(ROOT):
            files += 1
            with pdfplumber.open(path) as pdf:
                for pg in pdf.pages:
                    imgs = getattr(pg, 'images', None) or []
                    if imgs:
                        pages_with_img += 1
                    for im in imgs:
                        cs = im.get('colorspace')
                        if not cs:
                            unsupported += 1
                            continue
                        key = re.sub(r'[^A-Za-z0-9]', '', str(cs[0])).lower()
                        if key not in CS_SPEC:
                            unsupported += 1
                            continue
                        if im.get('bits') != 8:
                            bits_bad += 1
                            continue
                        ss = im.get('srcsize') or (0, 0)
                        w, h = int(ss[0]), int(ss[1])
                        if w <= 0 or h <= 0:
                            continue
                        dims.append((min(w, h), w, h, w * h))
                        per_prov[prov] += 1
    except Exception as e:
        print('统计中断: %s: %s' % (type(e).__name__, e))
        return 1

    n = len(dims)
    print('题本文件数        : %d' % files)
    print('含图页数          : %d' % pages_with_img)
    print('可解码图片数      : %d' % n)
    print('色彩空间不支持    : %d' % unsupported)
    print('位深非 8bit       : %d' % bits_bad)
    if not n:
        print('!! 无可用图片，阈值无从谈起')
        return 1

    ms = sorted(d[0] for d in dims)
    px = sorted(d[3] for d in dims)

    def pct(seq, q):
        return seq[min(len(seq) - 1, int(len(seq) * q))]

    print()
    print('=== 最小边长分布 ===')
    print('  min=%d  p10=%d  p25=%d  median=%d  p75=%d  p90=%d  max=%d'
          % (ms[0], pct(ms, .10), pct(ms, .25), statistics.median(ms),
             pct(ms, .75), pct(ms, .90), ms[-1]))
    print('=== 总像素分布 ===')
    print('  min=%d  p50=%d  p90=%d  p99=%d  max=%d  (%.1f MP)'
          % (px[0], pct(px, .50), pct(px, .90), pct(px, .99), px[-1],
             px[-1] / 1e6))

    print()
    print('=== 阈值敏感性：不同 MIN_DIM 会保留多少张 ===')
    print('  %-10s %-10s %-8s %s' % ('MIN_DIM', '保留', '保留率', '被丢弃尺寸区间'))
    for t in (0, 10, 14, 20, 25, 30, 40, 50, 60, 80, 100):
        keep = [d for d in dims if d[0] >= t]
        lost = [d for d in dims if d[0] < t]
        rng = ('%d-%d' % (min(x[0] for x in lost), max(x[0] for x in lost))
               if lost else '-')
        print('  %-10d %-10d %-8s %s'
              % (t, len(keep), '%.1f%%' % (100.0 * len(keep) / n), rng))

    print()
    print('=== 现阈值 40 会被丢弃的图片（按尺寸分桶）===')
    bucket = collections.Counter()
    for d in dims:
        if d[0] < MIN_DIM:
            bucket['%d-%d' % (d[0] // 10 * 10, d[0] // 10 * 10 + 9)] += 1
    for k in sorted(bucket):
        print('  最小边 %s px : %d 张' % (k, bucket[k]))
    print('  合计丢弃: %d / %d' % (sum(bucket.values()), n))

    print()
    print('=== 解压炸弹风险（当前无上限）===')
    mx = max(dims, key=lambda d: d[3])
    print('  最大总像素: %d x %d = %d (%.1f MP)'
          % (mx[1], mx[2], mx[3], mx[3] / 1e6))
    print('  按 colorspace 3 通道估算原始缓冲: %.1f MB' % (mx[3] * 3 / 1e6))
    for cap in (2e6, 4e6, 8e6, 16e6, 40e6):
        over = sum(1 for d in dims if d[3] > cap)
        print('  上限 %6.0f 万像素 -> 超限 %d 张' % (cap / 1e4, over))

    print()
    print('=== 各省图片数 ===')
    for p in sorted(per_prov):
        print('  %-12s %d' % (p, per_prov[p]))
    return 0


if __name__ == '__main__':
    sys.exit(main())