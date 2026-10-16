# -*- coding: utf-8 -*-
"""T11 端点验证：返回契约一致性 + 配对正确性 + 阻断语义 + 鉴权/入参校验。"""
import sys, os, json, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf

PDF_ROOT = 'D:/砺安题库/砺安题库/题库/行测/安徽行测'
STEM = '2023年安徽省公务员录用考试《行测》题（网友回忆版）'
ANS23 = '2023年安徽省公务员录用考试《行测》题（网友回忆版）答案解析.pdf'
QB23 = STEM + '题本.pdf'


def pdf_text(p):
    d = pymupdf.open(p)
    s = '\n'.join(d[i].get_text('text') for i in range(len(d)))
    d.close()
    return s


fails = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if detail else ''))
    if not cond:
        fails.append(name)


# ── 1. 路由注册 + 返回契约 ──────────────────────────────���───────────
print('=== 1. 路由注册与返回契约 ===')
from app.api.v1.catalog.question_import import router, _separate_match_xingce
paths = [r.path for r in router.routes]
check('/separate-match-xingce 已注册',
      any('separate-match-xingce' in p for p in paths),
      [p for p in paths if 'separate-match' in p])

from app.api.v1.catalog.question_import import separate_match_endpoint
import inspect
src = inspect.getsource(separate_match_endpoint)
# 既有端点返回的顶层键（从 return dict 字面量提取）
base_keys = set()
m = src[src.rfind("return {"):]
for line in m.splitlines():
    line = line.strip()
    if line.startswith("'"):
        base_keys.add(line.split("'")[1])
    if line == '}':
        break
print('  既有端点顶层键(%d): %s' % (len(base_keys), sorted(base_keys)))

# 走真实数据，拿新端点的键
from app.core.database import SessionLocal
db = SessionLocal()
try:
    r = _separate_match_xingce(db, {'paper_name': '安徽2023行测'},
                               pdf_text(os.path.join(PDF_ROOT, QB23)),
                               pdf_text(os.path.join(PDF_ROOT, ANS23)),
                               user_id=1, subject_name='')
    new_keys = set(r.keys())
    check('既有 12 字段全部存在', base_keys.issubset(new_keys),
          '缺 %s' % (base_keys - new_keys))
    check('仅新增 xingce_report', new_keys - base_keys == {'xingce_report'},
          '多出 %s' % (new_keys - base_keys))

    # ── 2. 安徽 2023 配对（110 vs 101 缺陷的端到端证明）──────────────
    print()
    print('=== 2. 安徽 2023 配对正确性 ===')
    check('match_rate >= 99', r['match_rate'] >= 99.0, r['match_rate'])
    check('total_questions = 110', r['total_questions'] == 110,
          r['total_questions'])
    check('matched_count = 110', r['matched_count'] == 110,
          r['matched_count'])
    check('blocked_count = 0', r['xingce_report']['blocked_count'] == 0,
          r['xingce_report']['blocked_count'])
    check('X-1 分节序列全等', r['xingce_report']['x']['x1_section_sequence'] is True)
    check('X-2 分节区间一致', r['xingce_report']['x']['x2_section_intervals'] is True)
    check('strategy_used 标记', r['strategy_used'] == 'xingce_section_cross_validate')

    # 分区落位
    subs = {}
    for q in r['questions']:
        subs[q.get('xingce_subcategory')] = subs.get(q.get('xingce_subcategory'), 0) + 1
    print('  分区落位分布: %s' % subs)
    check('全部题目落在枚举内',
          all(k in ('政治理论', '常识判断', '言语理解与表达', '数量关系',
                    '判断推理', '资料分析', '知觉速度与准确性', '科学推理',
                    '常识', '速度与知觉训练', '语言理解与表达', '无')
              for k in subs), list(subs))

    # 材料归组
    mg = r['xingce_report']['material_groups']
    check('材料组数 = 3', len(mg) == 3, len(mg))
    members = sorted(int(q['question_number']) for q in r['questions']
                     if q.get('material_group'))
    print('  材料成员题号: %s' % members)
    check('101-110 已正确归入材料（曾被780吞掉）',
          members == [96, 97, 98, 99, 100, 101, 102, 103, 104, 105,
                      106, 107, 108, 109, 110], members)

    # 考点归一
    prov = [(q['question_number'], q.get('kao_points_normalized'))
            for q in r['questions']
            if any('特色' in (k or '') for k in (q.get('kao_points') or []))]
    check('省级私有考点已剥离前缀',
          all(not any('特色' in n for n in (v or [])) for _, v in prov),
          prov[:3])

    check('preview_confirmable = True',
          r['xingce_report']['preview_confirmable'] is True)
    check('已写 question_import_record 且未 commit',
          r['xingce_report']['import_id'] is not None,
          r['xingce_report']['import_id'])

    # ── 3. 错配年份 → 阻断（计划指定 2025题本 + 2024答案）──────────
    print()
    print('=== 3. 错配年份阻断语义（2025题本 + 2024答案）===')
    qb25 = [f for f in os.listdir(PDF_ROOT) if f.startswith('2025') and '题本' in f]
    ans24 = [f for f in os.listdir(PDF_ROOT) if f.startswith('2024') and '答案解析' in f]
    if qb25 and ans24:
        r2 = _separate_match_xingce(db, {'paper_name': '错配'},
                                    pdf_text(os.path.join(PDF_ROOT, qb25[0])),
                                    pdf_text(os.path.join(PDF_ROOT, ans24[0])),
                                    user_id=1, subject_name='')
        print('  题本=%s' % qb25[0])
        print('  答案=%s' % ans24[0])
        print('  blocked_count=%s preview_confirmable=%s'
              % (r2['xingce_report']['blocked_count'],
                 r2['xingce_report']['preview_confirmable']))
        check('错配年份 blocked_count > 0',
              r2['xingce_report']['blocked_count'] > 0,
              r2['xingce_report']['blocked_count'])
        check('错配年份 preview_confirmable = False',
              r2['xingce_report']['preview_confirmable'] is False)
    else:
        check('找到 2025题本 与 2024答案', False, (qb25, ans24))

    # ── 3b. 同结构不同年份的诚实边界（记录限制，非失败）──────────────
    print()
    print('=== 3b. 同结构年份错配（结构性安全网的固有边界）===')
    r3 = _separate_match_xingce(db, {'paper_name': '同结构错配'},
                               pdf_text(os.path.join(PDF_ROOT, QB23)),
                               pdf_text(os.path.join(PDF_ROOT, ans24[0])),
                               user_id=1, subject_name='')
    print('  2023题本 + 2024答案 -> blocked_count=%s'
          % r3['xingce_report']['blocked_count'])
    print('  两卷分节区间:')
    for s in r3['xingce_report']['section_intervals_q']:
        print('    %-14s %s-%s (%s题)' % (s['name'], s['min'], s['max'], s['count']))
    print('  >> 安徽 2023/2024 结构完全相同，安全网按**结构**而非**身份**校验，')
    print('     故无法区分。答案文本仍会逐题错配，但结构校验无法识别。')
    print('     这是分节区间安全网的固有边界，须在F1 审计中如实记录。')

    db.rollback()
finally:
    db.close()

# ── 4. 省级私有考点归一（江苏，清单路径修复后此项才真正有效）──────
print()
print('=== 4. 省级私有考点归一（江苏 2023 A类）===')
JS = 'D:/砺安题库/砺安题库/题库/行测/江苏行测'
js_qb = [f for f in os.listdir(JS) if f.startswith('2023') and 'A类' in f and '题本' in f]
js_ans = [f for f in os.listdir(JS) if f.startswith('2023') and 'A类' in f and '答案解析' in f]
from app.core.database import SessionLocal
db2 = SessionLocal()
try:
    rj = _separate_match_xingce(db2, {'paper_name': '江苏2023A'},
                                pdf_text(os.path.join(JS, js_qb[0])),
                                pdf_text(os.path.join(JS, js_ans[0])),
                                user_id=1, subject_name='')
    print('  total=%s matched=%s blocked=%s'
          % (rj['total_questions'], rj['matched_count'],
             rj['xingce_report']['blocked_count']))
    raw_special, norm_special = [], []
    for q in rj['questions']:
        for k in (q.get('kao_points') or []):
            if '特色' in k:
                raw_special.append((q['question_number'], k))
        for n in (q.get('kao_points_normalized') or []):
            if '特色' in n:
                norm_special.append((q['question_number'], n))
    print('  原始含「特色」token 数 = %d  例: %s' % (len(raw_special), raw_special[:3]))
    print('  归一后仍含「特色」数 = %d  例: %s' % (len(norm_special), norm_special[:3]))
    check('江苏存在省级私有 token（证明测试非空过）', len(raw_special) > 0,
          len(raw_special))
    check('归一后全部剥离前缀', len(norm_special) == 0, norm_special[:3])
    db2.rollback()
finally:
    db2.close()

print()
print('=' * 60)
print('RESULT = %s   失败 %d 项 %s'
      % ('PASS' if not fails else 'FAIL', len(fails), fails or ''))
sys.exit(0 if not fails else 1)