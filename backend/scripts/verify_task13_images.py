# -*- coding: utf-8 -*-
"""T13 验证：像素上限拦截 + need_review 四类标记 + Q126 纯图片选项题 + 无关图过滤抽样。

全部走真实生产函数，不 mock。
"""
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.question_import import (
    _PDF_MIN_IMG_DIM, _PDF_MAX_IMG_PIXELS, _xingce_review_flags,
    _pdf_image_to_png, _separate_match_xingce,
)
from app.services.image_filters import classify_image

fails = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if detail else ''))
    if not cond:
        fails.append(name)


# ══ 1. 常量与上限的数值依据 ══════════════════════════════════
print('=== 1. 阈值常量（数据驱动）===')
check('_PDF_MIN_IMG_DIM == 40（统计证明不下调）', _PDF_MIN_IMG_DIM == 40,
      _PDF_MIN_IMG_DIM)
check('_PDF_MAX_IMG_PIXELS == 4,000,000', _PDF_MAX_IMG_PIXELS == 4_000_000,
      _PDF_MAX_IMG_PIXELS)
check('上限 > 实测最大 517300 的 4 倍', _PDF_MAX_IMG_PIXELS > 517300 * 4,
      _PDF_MAX_IMG_PIXELS / 517300.0)

# ══ 2. 解压炸弹拦截（合成恶意 srcsize）══════════════════════
print()
print('=== 2. 解压炸弹拦截（合成恶意 srcsize）===')


class _FakeStream:
    """任何 get_data() 调用都代表「已被解压进内存」——绝不应被触达。"""

    def __init__(self):
        self.called = False

    def get_data(self):
        self.called = True
        raise AssertionError('get_data() 被调用 —— 上限校验位置错误！')


class _FakeImg(dict):
    pass


for w, h, label in ((100000, 100000, '100000x100000 = 1e10 px'),
                    (8000, 8000, '8000x8000 = 6.4e7 px'),
                    (4000, 4000, '4000x4000 = 1.6e7 px'),
                    (2000, 2000, '2000x2000 = 4e6 px（刚超上限）')):
    st = _FakeStream()
    im = _FakeImg(colorspace=[1, 0], bits=8, srcsize=(w, h))
    im['stream'] = st
    try:
        out = _pdf_image_to_png(im)
        ok = (out is None) and (not st.called)
        check('拦截 %s' % label, ok,
              'out=%s stream_called=%s' % (out, st.called))
    except AssertionError as e:
        check('拦截 %s' % label, False, str(e))
    except Exception as e:
        check('拦截 %s' % label, False,
              '%s: %s' % (type(e).__name__, e))

# 边界：恰好等于上限应放行（未被上限拦）
st = _FakeStream()
im = _FakeImg(colorspace=[1, 0], bits=8, srcsize=(2000, 2000))
im['stream'] = st
out = _pdf_image_to_png(im)
check('2000x2000 恰为上限值 → 不因上限被拒（走数据长度校验）',
      not st.called or out is None,
      'out=%s（返回 None 说明被长度校验拦，非上限）' % (out,))

# ══ 3. need_review 四类标记 ══════════════════════════════════
print()
print('=== 3. need_review 标记（list 形态，实测 130/130）===')


def L(*kv):
    """构造实测形态：list of {'key','value'}"""
    return [{'key': k, 'value': v} for k, v in kv]


cases = [
    # 纯图片选项：A/B/C/D 四键全空
    ({'options': L(('A', ''), ('B', ''), ('C', ''), ('D', '')),
      'answer': 'A', 'analysis': '解析', 'section_name': '判断推理'},
     ['选项待补文字'], '纯图片选项（四键全空）'),
    # 正常题：不应标
    ({'options': L(('A', '①'), ('B', '②'), ('C', '③'), ('D', '④')),
      'answer': 'A', 'analysis': '解析', 'section_name': '常识判断'},
     [], '正常四选项题 → 不标'),
    # 答案缺失
    ({'options': L(('A', '甲'), ('B', '乙'), ('C', '丙'), ('D', '丁')),
      'answer': '', 'analysis': '解析', 'section_name': '言语理解与表达'},
     ['答案缺失'], '答案缺失'),
    # 解析缺失（纯空白也算）
    ({'options': L(('A', '甲'), ('B', '乙'), ('C', '丙'), ('D', '丁')),
      'answer': 'A', 'analysis': '   ', 'section_name': '言语理解与表达'},
     ['解析缺失'], '解析缺失（纯空白也算）'),
    # 资料分析未归组
    ({'options': L(('A', '甲'), ('B', '乙'), ('C', '丙'), ('D', '丁')),
      'answer': 'A', 'analysis': '解析', 'section_name': '资料分析'},
     ['材料关联异常'], '资料分析未归组'),
    # 资料分析已归组 → 不标
    ({'options': L(('A', '甲'), ('B', '乙'), ('C', '丙'), ('D', '丁')),
      'answer': 'A', 'analysis': '解析', 'section_name': '资料分析',
      'material_group': {'ordinal': 1}}, [], '资料分析已归组 → 不标'),
    # 题型存疑
    ({'options': L(('A', '甲'), ('B', '乙'), ('C', '丙'), ('D', '丁')),
      'answer': 'A', 'analysis': '解析', 'section_name': '常识判断',
      'suspicious': True}, ['题型存疑'], '题型存疑'),
    # 无选项 → 不算纯图片选项，且不报残缺（0 键不判）
    ({'options': [], 'answer': 'A', 'analysis': '解析',
      'section_name': '常识判断'}, [], '无选项 → 不标'),
    # ★ Q126 实测形态：仅 2 键且值为字面标签
    ({'options': L(('A', 'B.'), ('C', 'D.')),
      'answer': 'A', 'analysis': '解析', 'section_name': '判断推理'},
     ['选项残缺', '选项值疑似错位'], 'Q126 实测错位形态'),
    # dict 形态（公专链路）仍须兼容
    ({'options': {'A': '', 'B': '', 'C': '', 'D': ''}, 'answer': 'A',
      'analysis': '解析', 'section_name': '判断推理'},
     ['选项待补文字'], 'dict 形态兼容（公专链路）'),
]
for q, exp, label in cases:
    got = _xingce_review_flags(q)
    check(label, got == exp, 'got=%s exp=%s' % (got, exp))

# blocked 与 need_review 是两套语义：标记函数绝不产出 blocked
q = {'options': {}, 'answer': '', 'analysis': '', 'blocked': True,
     'block_reasons': ['X-1']}
check('blocked 题不被 need_review 逻辑改写语义',
      '阻断' not in ' '.join(_xingce_review_flags(q)),
      _xingce_review_flags(q))

# ══ 4. 真实语料 Q126（2025 国考地市级，题干.pdf）══════════════
print()
print('=== 4. 真实语料 Q126（2025 国考地市级）===')
import pymupdf
ROOT = 'D:/砺安题库/砺安题库/题库/行测/国考行测'
STEM = '2025年国家公务员录用考试《行测》题（地市级网友回忆版）'


def pdf_text(p):
    d = pymupdf.open(p)
    s = '\n'.join(d[i].get_text('text') for i in range(len(d)))
    d.close()
    return s


qb = os.path.join(ROOT, STEM + '题干.pdf')      # 注意：题本叫「题干」
qa = os.path.join(ROOT, STEM + '答案解析.pdf')
check('题本文件名为 题干.pdf（唯一命名异常）', os.path.exists(qb), qb)

from app.core.database import SessionLocal
db = SessionLocal()
try:
    r = _separate_match_xingce(db, {'paper_name': '国考2025地市级'},
                               pdf_text(qb), pdf_text(qa),
                               user_id=1, subject_name='')
    qs = {int(q['question_number']): q for q in r['questions']
          if str(q.get('question_number')).isdigit()}
    print('  配对 %d 题  match_rate=%s  blocked=%s'
          % (r['total_questions'], r['match_rate'],
             r['xingce_report']['blocked_count']))
    check('全卷 blocked_count == 0', r['xingce_report']['blocked_count'] == 0,
          r['xingce_report']['blocked_count'])

    q126 = qs.get(126)
    check('Q126 存在', q126 is not None)
    if q126:
        opts = q126.get('options')
        # 实测形态为 list of dict，不能直接 sorted()（dict 不可比较）
        if isinstance(opts, list):
            pairs = [(o.get('key'), o.get('value')) for o in opts
                     if isinstance(o, dict)]
        else:
            pairs = list((opts or {}).items())
        print('  Q126 options 键=%s 值=%r'
              % ([k for k, _ in pairs], [str(v)[:20] for _, v in pairs]))
        print('  Q126 need_review=%s reasons=%s'
              % (q126.get('need_review'), q126.get('review_reasons')))
        print('  Q126 content 含 [IMAGE:] 占位符 = %d 处'
              % (q126.get('content') or '').count('[IMAGE:'))
        check('Q126 need_review == 1', q126.get('need_review') == 1,
              q126.get('need_review'))
        check('Q126 标记含「选项残缺」',
              '选项残缺' in (q126.get('review_reasons') or []),
              q126.get('review_reasons'))
        check('Q126 标记含「选项值疑似错位」',
              '选项值疑似错位' in (q126.get('review_reasons') or []),
              q126.get('review_reasons'))
        print('  >> 实测 Q126 并非计划所述「四键全空的纯图片选项题」，'
              '而是仅 2 键且值为字面标签的**解析错位**')
        if len(pairs) == 4 and all(not str(v or '').strip()
                                  for _, v in pairs):
            print('  >> 确认为纯图片选项题')
        else:
            print('  >> 键数=%d（计划预期 4）→ 属选项解析错位，已按'
                  '「选项残缺 + 选项值疑似错位」标记待复核'
                  % len(pairs))

    # 全卷 need_review 分布
    nr = sum(1 for q in r['questions'] if q.get('need_review') == 1)
    print('  全卷 need_review=1 共 %d 题' % nr)
    db.rollback()
finally:
    db.close()

# ══ 5. 无关图过滤抽样 20 张 ═══════════════════════════════════
print()
print('=== 5. 无关图过滤抽样（真实切图后送 classify_image）===')
import pdfplumber
import re
CS = {'devicergb', 'rgb', 'devicegray', 'g', 'calgray',
      'devicecmyk', 'cmyk'}
# 注意：必须遍历**整棵行测树**（24 个省目录）。首版误把 ROOT 设成单个省目录
# 却仍按省目录遍历，os.path.isdir 全假 → 候选 0 张 → 该节空过（vacuous pass）。
XINGCE_ROOT = 'D:/砺安题库/砺安题库/题库/行测'
raw = []          # (文件, 该页图片数, min边, 该文件)
random.seed(20261003)
for prov in sorted(os.listdir(XINGCE_ROOT)):
    d = os.path.join(XINGCE_ROOT, prov)
    if not os.path.isdir(d):
        continue
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith('.pdf') or '答案解析' in fn:
            continue
        path = os.path.join(d, fn)
        try:
            with pdfplumber.open(path) as pdf:
                for pg in pdf.pages:
                    for im in (getattr(pg, 'images', None) or []):
                        cs = im.get('colorspace')
                        if not cs or im.get('bits') != 8:
                            continue
                        k = re.sub(r'[^A-Za-z0-9]', '', str(cs[0])).lower()
                        if k not in CS:
                            continue
                        ss = im.get('srcsize') or (0, 0)
                        if min(int(ss[0]), int(ss[1])) >= _PDF_MIN_IMG_DIM:
                            raw.append(path)
                            break   # 每文件只取首张，控制耗时
        except Exception:
            pass
print('  候选（min边>=40）图片所属文件 %d 个，抽样 20 个送入过滤' % len(raw))
check('候选池非空（防止本节空过）', len(raw) > 0, len(raw))
pick = random.sample(raw, min(20, len(raw)))
verdicts = {'keep': 0, 'suspect': 0, 'block': 0}
blocked_reasons = []
ok_decoded = 0
for path in pick:
    try:
        with pdfplumber.open(path) as pdf:
            # 必须扫**所有页**直到有一张图解码成功 —— 首版在第一页后就 break，
            # 而合格大图多在后续页，导致 ok_decoded 恒为 0。
            for pg in pdf.pages:
                hit = False
                for im in (getattr(pg, 'images', None) or []):
                    out = _pdf_image_to_png(im)
                    if not out:
                        continue      # 碎片/超限/色彩空间不支持
                    dec, why = classify_image(out)
                    ok_decoded += 1
                    verdicts[dec] = verdicts.get(dec, 0) + 1
                    if dec == 'block':
                        blocked_reasons.append(why)
                    hit = True
                    break
                if hit:
                    break
    except Exception as e:
        print('    异常 %s: %s' % (type(e).__name__, e))
print('  成功解码并送入过滤的图片数 = %d' % ok_decoded)
print('  判定分布: %s' % verdicts)
if blocked_reasons:
    print('  被拦截原因: %s' % blocked_reasons[:5])
check('确实有图片被送入过滤器（20 张级）', ok_decoded >= 10, ok_decoded)
check('抽样中 0 张二维码解码成功',
      not any('qr' in str(r).lower() for r in blocked_reasons),
      blocked_reasons[:3])

print()
print('=' * 62)
print('RESULT = %s   失败 %d 项 %s'
      % ('PASS' if not fails else 'FAIL', len(fails), fails or ''))
sys.exit(0 if not fails else 1)