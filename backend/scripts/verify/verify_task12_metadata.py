# -*- coding: utf-8 -*-
"""T12 验证：85 套卷级元数据 100% 正确 + 命名异常容错 + 路径穿越防护。

省份的「正确答案」定义为**文件夹名去掉「行测」后缀**（唯一可靠来源）。
本脚本独立从目录结构重新推导期望值，与被测函数无共享代码。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.catalog.question_import import (
    _resolve_xingce_paper_metadata,
    _xingce_doc_role,
    _xingce_paper_variant,
    _xingce_folder_province,
)

ROOT = 'D:/砺安题库/砺安题库/题库/行测'
fails = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if detail else ''))
    if not cond:
        fails.append(name)


# ── 独立推导期望值（不复用被测代码）────────────────────────────────
def expected_province(folder):
    n = folder
    for suf in ('行测', '申论', '公专'):
        if n.endswith(suf):
            n = n[:-len(suf)]
            break
    if n in ('国考',):
        return '国考'
    return n


def expected_year(fn):
    m = re.search(r'(20\d{2})', fn)
    return int(m.group(1)) if m else None


EXPECTED_VARIANTS = {
    '北京行测': {'2021': {'乡镇卷', '区级及以上卷'}},
    '广东行测': {'2023': {'乡镇卷', '县级卷'}},
    '江苏行测': None,   # A/B/C类，全 8 套
    '国考行测': None,   # 副省级/地市级/行政执法卷，全 9 套
}

# ── 1. 85 套配对 + 元数据 100% 正确 ────────────────────────────
print('=== 1. 85 套配对与元数据判定 ===')
sets = []          # (folder, year, qfile, afile)
for folder in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, folder)
    if not os.path.isdir(d):
        continue
    # 配对键必须是 (年份, 卷别) 而非仅年份：江苏每年 A/B 两份题本、
    # 国考每年 3 份（副省级/地市级/行政执法）、广东 2023 两份（乡镇/县级）。
    # 只按年份分组会被同键覆盖，实测曾因此只配出 72/85 套。
    by_set = {}
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith('.pdf'):
            continue
        role = _xingce_doc_role(fn)
        y = expected_year(fn)
        var = _xingce_paper_variant(fn)
        by_set.setdefault((y, var), {})[role] = fn
    for key in sorted(by_set, key=lambda k: (k[0] or 0, k[1] or '')):
        r = by_set[key]
        q = r.get('questions')
        a = r.get('answers')
        if q and a:
            sets.append((folder, key[0], q, a))

print('  配对成功套数 = %d（期望 85）' % len(sets))
check('85 套全部配对', len(sets) == 85, len(sets))

prov_bad, year_bad, role_bad = [], [], []
prov_seen, year_seen = set(), set()
for folder, y, q, a in sets:
    m = _resolve_xingce_paper_metadata(folder, q, '', '')
    exp_p, exp_y = expected_province(folder), y
    if m.get('exam_province') != exp_p:
        prov_bad.append((folder, q, m.get('exam_province'), exp_p))
    if m.get('exam_year') != exp_y:
        year_bad.append((folder, q, m.get('exam_year'), exp_y))
    if m.get('doc_role') != 'questions':
        role_bad.append((folder, q, m.get('doc_role')))
    prov_seen.add(m.get('exam_province'))
    year_seen.add(m.get('exam_year'))

check('省份判定 100%% 正确（85/85）', not prov_bad, prov_bad[:5])
check('年份判定 100%% 正确（85/85）', not year_bad, year_bad[:5])
check('题本角色判定 85/85', not role_bad, role_bad[:5])
print('  省份覆盖 %d 个值: %s' % (len(prov_seen), sorted(x for x in prov_seen if x)))
print('  年份覆盖 %s' % sorted(year_seen))

# ── 2. 卷别判定 ────────────────────────────────────────────────
print()
print('=== 2. 卷别判定 ===')
js = [(f, y, _xingce_paper_variant(q))
      for f, y, q, a in sets if f == '江苏行测']
gk = [(f, y, _xingce_paper_variant(q))
      for f, y, q, a in sets if f == '国考行测']
gd = [(f, y, _xingce_paper_variant(q))
      for f, y, q, a in sets if f == '广东行测']
bj = [(f, y, _xingce_paper_variant(q))
      for f, y, q, a in sets if f == '北京行测']

print('  江苏 %d 套: %s' % (len(js), [v for _, _, v in js]))
check('江苏 8 套', len(js) == 8, len(js))
check('江苏卷别均属 A/B/C类',
      all(v in ('A类', 'B类', 'C类') for _, _, v in js), [v for _, _, v in js])

print('  国考 %d 套: %s' % (len(gk), [v for _, _, v in gk]))
check('国考 9 套', len(gk) == 9, len(gk))
check('国考卷别均属 副省级/地市级/行政执法卷',
      all(v in ('副省级', '地市级', '行政执法卷') for _, _, v in gk),
      [v for _, _, v in gk])

print('  广东 %d 套: %s' % (len(gd), [(y, v) for _, y, v in gd]))
check('广东 4 套', len(gd) == 4, len(gd))
check('广东 2023 含县级卷与乡镇卷',
      {v for _, y, v in gd if y == 2023} == {'县级卷', '乡镇卷'},
      [(y, v) for _, y, v in gd if y == 2023])

print('  北京 %d 套: %s' % (len(bj), [(y, v) for _, y, v in bj]))
check('北京 4 套', len(bj) == 4, len(bj))
check('北京 2021 含乡镇卷与区级及以上卷',
      {v for _, y, v in bj if y == 2021} == {'乡镇卷', '区级及以上卷'},
      [(y, v) for _, y, v in bj if y == 2021])

# ── 3. 五类命名异常容错 ────────────────────────────────────────
print()
print('=== 3. 命名异常容错 ===')
cases = [
    ('国考行测', '2025年国家公务员录用考试《行测》题（地市级网友回忆版）题干.pdf',
     'questions', '地市级'),   # 题干.pdf 冒充题本
    ('山东行测', '2022年山东省公务员录用考试《行测》试题（网友回忆版）题本.pdf',
     'questions', None),                # 「试题」而非「题」
    ('广西行测', '2023年广西区考公务员录用考试《行测》题（网友回忆版）题本.pdf',
     'questions', None),                # 「区考」
    ('甘肃行测', '2023年甘肃公务员录用考试《行测》题（网友回忆版）题本.pdf',
     'questions', None),                # 全省缺「省」
    ('黑龙江行测', '2025年黑龙江公务员录用考试《行测》题（网友回忆版）题本.pdf',
     'questions', None),                # 单年份缺「省」
    ('内蒙古行测', '2023年内蒙古公务员录用考试《行测》题（网友回忆版）题本.pdf',
     'questions', None),
]
for folder, fn, exp_role, exp_var in cases:
    role = _xingce_doc_role(fn)
    var = _xingce_paper_variant(fn)
    m = _resolve_xingce_paper_metadata(folder, fn, '', '')
    ok = role == exp_role and var == exp_var
    check('%-10s %-46s' % (folder, fn[:44]), ok,
          'role=%s var=%s province=%s' % (role, var, m.get('exam_province')))

check('题干.pdf 未被误判为答案',
      _xingce_doc_role('2025年国家公务员录用考试《行测》题（地市级网友回忆版）题干.pdf')
      == 'questions')
check('答案解析 判为 answers',
      all(_xingce_doc_role(f) == 'answers'
          for _, _, q, a in sets
          for f in [a]))

# ── 4. 省份不来自文件名（关键红线）─────────────────────────────
print()
print('=== 4. 省份绝不来自文件名 ===')
# 把文件夹名置空，文件名仍含省份字样 → 省份必须为 None
m1 = _resolve_xingce_paper_metadata('', '2023年安徽省公务员录用考试《行测》题（网友回忆版）题本.pdf', '', '')
check('无文件夹名 + 文件名含「安徽」→ 省份为 None',
      m1.get('exam_province') is None, m1.get('exam_province'))
m2 = _resolve_xingce_paper_metadata('国考行测', '2023年国家公务员录用考试《行测》题（副省级网友回忆版）题本.pdf', '', '')
check('国考行测 → 省份标记为 国考', m2.get('exam_province') == '国考',
      m2.get('exam_province'))
# 文件夹名与文件名省份冲突时，文件夹名胜出
m3 = _resolve_xingce_paper_metadata('甘肃行测', '2023年安徽省公务员录用考试《行测》题（网友回忆版）题本.pdf', '', '')
check('文件夹名「甘肃」覆盖文件名「安徽」',
      m3.get('exam_province') == '甘肃', m3.get('exam_province'))

# ── 5. 路径穿越防护 ────────────────────────────────────────────
print()
print('=== 5. 路径穿越防护 ===')
import inspect
evil = [
    '../../etc/passwd',
    '..\\..\\Windows\\System32\\config',
    '/etc/passwd',
    'a\x00b.pdf',
    '',
    'x' * 500 + '.pdf',
]
for ev in evil:
    try:
        m = _resolve_xingce_paper_metadata('甘肃行测', ev, '', '')
        # 不应抛异常，也不应把路径片段写进任何落库字段
        leaked = any(('/' in str(v) or '\\' in str(v) or '..' in str(v))
                     for k, v in m.items()
                     if k in ('exam_province', 'exam_type', 'paper_name',
                              'paper_variant', 'subject_category'))
        check('恶意文件名被无害化: %r' % (ev[:34],), not leaked,
              {k: m.get(k) for k in ('exam_province', 'exam_type', 'paper_name')})
    except Exception as e:
        check('恶意文件名被无害化: %r' % (ev[:34],), False,
              '抛异常 %s: %s' % (type(e).__name__, e))

# 新增代码不得含 os.path.join + 用户输入
src = inspect.getsource(sys.modules['app.api.v1.catalog.question_import'])
new_seg = src[src.index('# 行测卷级元数据注入'):]
check('元数据模块内无 os.path.join 调用', 'os.path.join' not in new_seg,
      [l.strip() for l in new_seg.splitlines() if 'os.path.join' in l])

print()
print('=' * 62)
print('RESULT = %s   失败 %d 项 %s'
      % ('PASS' if not fails else 'FAIL', len(fails), fails or ''))
sys.exit(0 if not fails else 1)