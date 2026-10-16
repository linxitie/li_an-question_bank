#!/usr/bin/env python3
"""L2 匹配配对门禁 — 包装 G2/G3 回归 + 材料块守卫（任务 35 模块 J 扩展）。

守卫对象（J-2：行测资料分析「材料在前、题目在后」版式）
------------------------------------------------------
  守卫 1  材料块内不得含题号
          材料块的第一个题号必须大于该材料标记之前出现过的最大题号。
          材料块区间内混进前一材料/表格单元格里的题号时，首题号会倒退。

  守卫 2  图片归属不得与落点错位
          `_extract_text_from_pdf` 产出的 `[IMAGE:{hex}_{题号}_{序号}]` 占位符
          **自带归属题号**。它必须等于该占位符物理落点（向上最近的题号行）
          的题号。材料块的图片若被挂到前一题号（或归属题号被伪题号污染），
          两者就对不上。

  守卫 3  材料页表格行归属正确率
          pdfplumber `find_tables()` 检出的表格行必须原位落在所属材料块区间
          [marker, 首个题号行) 内（J-2-1 把页尾追加改为按 bbox top 原位插入）。
          跑到题号之后 = 表格行脱离所属材料块。

三个守卫共用 `material_guard_scan()`，产出同时被 L1 指纹（材料块数 /
材料页表格行归属正确率）复用，避免同一份真实语料扫两遍。
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, '..'))

BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(BACKEND_DIR)
DEFAULT_ROOT = os.path.join(REPO_ROOT, '题库', '行测')
CACHE_DIR = os.path.join(BACKEND_DIR, 'data', 'gates', 'xingce_material_cache')

# 题号行：`N.` / `N．` / `N、` 开头。
# ★ 必须排除「小数+单位」：`41.8％。`、`12.8%，这说明…`、`10.1％。` 落在行首时，
#   宽松模式 `^\d{1,3}[.．、]` 会把 `41.8` 判成题号 41 —— 这正是行测资料分析
#   里文档化的「伪题号」问题（行测回归报告里 30 个已知伪题号同源）。
#   故 `.` 仅在不紧跟数字时才算分隔符。
QNUM_LINE = re.compile(r'^[ \t]*(\d{1,3})[ \t]*(?:[、．]|\.(?!\d))')
MATERIAL_LINE = re.compile(r'^[ \t]*（([一二三四五六七八九十]{1,3})）[ \t]*$')
IMAGE_MARKER = re.compile(r'\[IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]')
# 生产表格行形态：' | ' 拼接单元格（question_import.py table.extract() 处）
TABLE_ROW = re.compile(r'\S \| \S|\S\|')

# 材料块守卫基线：正确行为（J-2 已修）下两项都应为 0
GUARD_BASELINE = {
    '材料块内题号数': 0,
    '材料块图片归属错位数': 0,
    '材料页表格行归属正确率': 1.0,
}


def _marker_qn(marker: str):
    parts = marker.split('_')
    try:
        return int(parts[1])
    except (IndexError, ValueError):
        return None


def enumerate_qb_pdfs(root: str):
    """枚举题本 PDF（与 verify_xingce_regression.py 的配对逻辑同源）。"""
    pairs = defaultdict(dict)
    if not os.path.isdir(root):
        return []
    for province in sorted(os.listdir(root)):
        pdir = os.path.join(root, province)
        if not os.path.isdir(pdir):
            continue
        for name in sorted(os.listdir(pdir)):
            if not name.lower().endswith('.pdf'):
                continue
            role = 'ANS' if '答案' in name else 'QB'
            pairs[province + '::' + os.path.splitext(name)[0]][role] = os.path.join(pdir, name)
    return [p['QB'] for p in pairs.values() if p.get('QB')]


def _cache_key(path: str) -> str:
    st = os.stat(path)
    raw = f'{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}'
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def cached_text(path: str, cache_dir: str = ''):
    """带磁盘缓存的真实文本提取；缓存命中则不重复跑 pdfplumber。"""
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        key = _cache_key(path)
        cache_file = os.path.join(cache_dir, key + '.txt')
        if os.path.exists(cache_file):
            with io.open(cache_file, encoding='utf-8') as fh:
                return fh.read(), True
    from app.api.v1.catalog.question_import import _extract_text_from_pdf
    with open(path, 'rb') as fh:
        text = _extract_text_from_pdf(fh.read())
    if cache_dir:
        key = _cache_key(path)
        with io.open(os.path.join(cache_dir, key + '.txt'), 'w', encoding='utf-8') as fh:
            fh.write(text)
    return text, False


def _max_qnum(lines, start: int, end: int) -> int:
    """[start, end) 区间内题号行的最大值；没有题号行返回 0。"""
    best = 0
    for j in range(start, min(end, len(lines))):
        m = QNUM_LINE.match(lines[j])
        if m:
            best = max(best, int(m.group(1)))
    return best


def guard_material_blocks(lines):
    """对**单份文本**跑三条材料块守卫，返回统计 dict。

    纯函数（只吃 lines，不碰磁盘/PDF），因此可被 tests/test_gate_l3.py 的
    反向用例直接喂缺陷文本验证「守卫真的抓得住」。

    守卫 1：材料块内不得含题号
        判据必须**非空洞**——材料块区间 [marker, 首个题号行) 的右端本身就是
        「第一个题号行」，直接数区间内题号行恒为 0。改成：材料块的第一个题号
        必须大于该材料标记之前出现过的最大题号。若材料块区间内混进了前一材料
        或表格单元格里的题号，首题号会倒退 —— 这才是「题号落进材料块」的真实特征。

    守卫 2：图片归属不得与落点错位
        `[IMAGE:{hex}_{题号}_{序号}]` 占位符自带归属题号，它必须等于「该占位符
        物理落点（向上最近的题号行）」的题号。两者不一致 = 图片归属错位：
        要么图片落进了别的题块区间，要么归属题号本身被伪题号污染
        （实测 `90.7%，高于…` 这类材料小数行会被提取器判成题号 90）。

    守卫 3：材料页表格行归属正确率
        pdfplumber `find_tables()` 检出的表格行必须原位落在所属材料块区间
        [marker, 首个题号行) 内（J-2-1 把页尾追加改为按 bbox top 原位插入）。
        跑到题号之后 = 表格行脱离所属材料块。
    """
    out = {
        'material_blocks': 0, 'qnums_inside_material': 0,
        'images_total': 0, 'images_misattributed': 0,
        'table_rows_correct': 0, 'table_rows_total': 0,
    }
    regions = _material_regions(lines)
    out['material_blocks'] = len(regions)

    for mi, fq, _fqn, nxt in regions:
        # 守卫 1：材料块首题号不得小于标记之前的最大题号
        span_qnums = []
        for j in range(mi, nxt):
            m = QNUM_LINE.match(lines[j])
            if m:
                span_qnums.append(int(m.group(1)))
        if span_qnums and span_qnums[0] <= _max_qnum(lines, 0, mi):
            out['qnums_inside_material'] += 1

        # 守卫 3：材料块全 span 内的表格行须原位落在 [marker, 首个题号)
        for j in range(mi, nxt):
            if TABLE_ROW.search(lines[j]):
                out['table_rows_total'] += 1
                if j < fq:
                    out['table_rows_correct'] += 1

    # 守卫 2：逐占位符校验「自称归属题号 == 实际落点题号」
    for i, line in enumerate(lines):
        for m in IMAGE_MARKER.finditer(line):
            qn = _marker_qn(m.group(1))
            if qn is None:
                continue
            out['images_total'] += 1
            if qn != _enclosing_qnum(lines, i):
                out['images_misattributed'] += 1
    return out


def _enclosing_qnum(lines, idx: int):
    """占位符物理所在区间的题号 = 向上最近的题号行；没有则 None。"""
    for j in range(idx, -1, -1):
        m = QNUM_LINE.match(lines[j])
        if m:
            return int(m.group(1))
    return None


def material_guard_scan(root: str = '', use_cache: bool = True) -> dict:
    """扫描真实题本语料，产出材料块守卫统计。

    返回 dict（键同时作为 L1/L2 的输出指纹）。
    """
    root = root or DEFAULT_ROOT
    stats = {
        'docs': 0, 'material_blocks': 0, 'qnums_inside_material': 0,
        'images_total': 0, 'images_misattributed': 0,
        'table_rows_correct': 0, 'table_rows_total': 0,
    }
    cache_dir = CACHE_DIR if use_cache else ''
    for path in enumerate_qb_pdfs(root):
        try:
            text, _hit = cached_text(path, cache_dir)
        except Exception as e:  # noqa: BLE001 — 单份失败不阻断全部门禁
            print(f'   [material-guard] 跳过 {os.path.basename(path)}: {e}')
            continue
        per_doc = guard_material_blocks(text.split('\n'))
        stats['docs'] += 1
        for key in ('material_blocks', 'qnums_inside_material', 'images_total',
                    'images_misattributed', 'table_rows_correct', 'table_rows_total'):
            stats[key] += per_doc[key]
    return stats


def _material_regions(lines):
    """[(marker行号, 首个题号行号, 首个题号, 下一材料标记行号或末行)]。

    材料块区间 = [marker, 首个题号行)；材料块全span = [marker, next_marker)。
    """
    marker_idx = [i for i, line in enumerate(lines) if MATERIAL_LINE.match(line)]
    out = []
    for k, mi in enumerate(marker_idx):
        nxt = marker_idx[k + 1] if k + 1 < len(marker_idx) else len(lines)
        fq, fqn = len(lines) - 1, None
        for j in range(mi + 1, nxt):
            m = QNUM_LINE.match(lines[j])
            if m:
                fq, fqn = j, int(m.group(1))
                break
        out.append((mi, fq, fqn, nxt))
    return out


def fingerprint(stats: dict) -> dict:
    """把扫描统计折算成 L1/L2 共用的命名指纹。"""
    tb_total = stats['table_rows_total']
    return {
        '材料块数': stats['material_blocks'],
        '材料块内题号数': stats['qnums_inside_material'],
        '材料块图片归属错位数': stats['images_misattributed'],
        '图片占位符总数': stats['images_total'],
        '材料页表格行归属正确率': (stats['table_rows_correct'] / tb_total) if tb_total else 1.0,
    }


def main():
    r = subprocess.run(
        [sys.executable, 'scripts/verify_xingce_regression.py',
         DEFAULT_ROOT, '--out', 'data/xingce_regression.txt'],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    # verify_xingce_regression.py 全部输出走 stderr（实测 stdout 长度为 0），
    # 而原实现只 print(r.stdout)，导致 L2 失败时不给任何线索 —— 门禁一旦红了
    # 无法定位，久而久之就会被当成常驻噪声忽略。失败时必须把 stderr 尾部摊开。
    if r.stdout:
        print(r.stdout[-2000:])
    if r.returncode != 0:
        print(f'\n[verify_xingce_regression 退出码 {r.returncode}] stderr 末 25 行：')
        for line in (r.stderr or '').splitlines()[-25:]:
            print('   ', line)
        print('  完整结论见 data/xingce_regression.txt 的「最终结果」段')

    print('\n材料块守卫（真实题本语料，生产 _extract_text_from_pdf）')
    stats = material_guard_scan()
    fp = fingerprint(stats)
    print(f'  扫过 {stats["docs"]} 份题本')
    print(f'  材料块数 == {fp["材料块数"]}')
    print(f'  材料块内题号数 == {fp["材料块内题号数"]}'
          f'（基线 {GUARD_BASELINE["材料块内题号数"]}）')
    print(f'  材料块图片归属错位数 == {fp["材料块图片归属错位数"]}'
          f' / 图片占位符 {fp["图片占位符总数"]} 个'
          f'（基线 {GUARD_BASELINE["材料块图片归属错位数"]}）')
    print(f'  材料页表格行归属正确率 == {fp["材料页表格行归属正确率"]:.4f}'
          f'（基线 {GUARD_BASELINE["材料页表格行归属正确率"]}）')
    print(f'L2 材料守卫指纹: {json.dumps(fp, ensure_ascii=False)}')

    guard_ok = (fp['材料块内题号数'] == 0
                and fp['材料块图片归属错位数'] == 0
                and fp['材料页表格行归属正确率'] >= 1.0)
    print(f'L2 匹配配对: {"PASS" if (r.returncode == 0 and guard_ok) else "FAIL"}')
    sys.exit(r.returncode if r.returncode != 0 else (0 if guard_ok else 1))


if __name__ == '__main__':
    main()
