# -*- coding: utf-8 -*-
"""T15 六套试点：覆盖 5 类命名异常，固化端到端导入链路。

试点语料由计划指定，每套必覆盖至少一个结构/命名异常：
  1. 国考 2025 地市级—— 文件名「题干.pdf」冒充题本（唯一命名异常）
  2. 国考 2025 副省级 —— 三卷并行中的对照卷
  3. 国考 2023 地市级 —— 既有 G2 门禁基线所在卷（证明不劣化）
  4. 江苏 2025 C类   —— 卷别标记（C类）+ 行测最高卷数
  5. 甘肃 2025       —— 省份名缺「省」字
  6. 广东 2023 县级卷—— 同年双卷并存

每套断言：配对完整 / 无blocked / 分区落位 / 材料归组 / 元数据正确 / 考点归一 / need_review 标记
"""
import os
import sys
import io
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf
from app.api.v1.catalog.question_import import (
    _separate_match_xingce,
    _resolve_xingce_paper_metadata,
    _xingce_doc_role,
    _xingce_paper_variant,
)
from app.core.database import SessionLocal

ROOT = 'D:/砺安题库/砺安题库/题库/行测'
fails = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  -> ' + str(detail)) if detail else ''))
    if not cond:
        fails.append(name)


def pdf_text(p):
    d = pymupdf.open(p)
    s = '\n'.join(d[i].get_text('text') for i in range(len(d)))
    d.close()
    return s


def find(folder, year, want_role, want_variant=None):
    """按(年份, 角色, 卷别)定位文件；want_role 用 _xingce_doc_role 判定。"""
    d = os.path.join(ROOT, folder)
    hit = {}
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith('.pdf'):
            continue
        if str(year) not in fn:
            continue
        role = _xingce_doc_role(fn)
        if role != want_role:
            continue
        var = _xingce_paper_variant(fn)
        if want_variant is not None and var != want_variant:
            continue
        hit.setdefault(var, fn)
    if not hit:
        return None
    if want_variant is None:
        return hit[sorted(hit)[0]]
    return hit.get(want_variant)


PILOT = [
    ('国考行测', 2025, '地市级', '题干.pdf 冒充题本（唯一命名异常）'),
    ('国考行测', 2025, '副省级', '三卷并行中的对照卷'),
    ('国考行测', 2023, '地市级', '既有 G2 门禁基线所在卷（须证明不劣化）'),
    ('江苏行测', 2025, None, '卷别标记（C类）+ 行测最高卷数'),
    ('甘肃行测', 2025, None, '省份名缺「省」字'),
    ('广东行测', 2023, '县级卷', '同年双卷并存'),
]

# 江苏取 C类；广东取县级卷；其余按卷别
PILOT = [
    ('国考行测', 2025, '地市级', '题干.pdf 冒充题本（唯一命名异常）'),
    ('国考行测', 2025, '副省级', '三卷并行中的对照卷'),
    ('国考行测', 2023, '地市级', '既有 G2 门禁基线所在卷（须证明不劣化）'),
    ('江苏行测', 2025, 'C类', '卷别标记（C类）+ 行测最高卷数'),
    ('甘肃行测', 2025, None, '省份名缺「省」字'),
    ('广东行测', 2023, '县级卷', '同年双卷并存'),
]

summary = []
db = SessionLocal()
try:
    for folder, year, variant, why in PILOT:
        qf = find(folder, year, 'questions', variant)
        af = find(folder, year, 'answers', variant)
        print()
        print('=' * 66)
        print('【%s %s%s】%s' % (folder, year,
                              (' ' + variant) if variant else '', why))
        print('  题本: %s' % (qf or '未找到'))
        print('  答案: %s' % (af or '未找到'))
        check('题本存在', bool(qf), qf)
        check('答案存在', bool(af), af)
        if not (qf and af):
            continue

        meta = _resolve_xingce_paper_metadata(folder, qf, '', '')
        print('  元数据: province=%s year=%s type=%s variant=%s'
              % (meta.get('exam_province'), meta.get('exam_year'),
                 meta.get('exam_type'), meta.get('paper_variant')))

        r = _separate_match_xingce(db, {'paper_name': os.path.basename(qf)},
                                   pdf_text(os.path.join(ROOT, folder, qf)),
                                   pdf_text(os.path.join(ROOT, folder, af)),
                                   user_id=1, subject_name='')
        xr = r['xingce_report']
        total = r['total_questions']
        print('  配对: %d/%d  match_rate=%s  blocked=%d  策略=%s'
              % (r['matched_count'], total, r['match_rate'],
                 xr['blocked_count'], r['strategy_used']))
        print('  分区: %s' % [(s['name'], '%s-%s' % (s['min'], s['max']))
                        for s in xr['section_intervals_q']])

        check('配对完整 matched==total', r['matched_count'] == total,
              '%s/%s' % (r['matched_count'], total))
        check('blocked_count == 0', xr['blocked_count'] == 0,
              xr['blocked_count'])
        check('X-1 分节序列全等', xr['x']['x1_section_sequence'] is True)
        check('X-2 分节区间一致', xr['x']['x2_section_intervals'] is True)
        check('match_rate >= 99', r['match_rate'] >= 99.0, r['match_rate'])
        check('preview_confirmable', xr['preview_confirmable'] is True)

        # 分区落位
        subs = {}
        for q in r['questions']:
            subs[q.get('xingce_subcategory')] = subs.get(q.get('xingce_subcategory'), 0) + 1
        check('分区落位非空且总和==total', sum(subs.values()) == total and subs,
              subs)

        # 材料归组：资料分析卷必有组
        mg = xr['material_groups']
        members = [q['question_number'] for q in r['questions']
                   if q.get('material_group')]
        print('  材料组=%d  成员题号=%s' % (len(mg), members))
        # ★ 正确的断言：材料组**并非只出现在资料分析** —— 任务 9 全语料实测分布为
        # 资料分析 299 / 言语理解 39 / 判断推理 19 / 常识判断 7。故不可断言
        # 「成员数 == 资料分析题数」（首版就是这么写的，误报 4 项）。
        # 真正的不变量有两条：
        #   (a) 每个成员的分区必须与其所属材料的分区一致（不得跨分区吞题）
        #   (b) 存在材料的分区，该分区全部题都必须归组
        bad_sec = [(q['question_number'], q['material_group']['section'],
                    q.get('section_name'))
                   for q in r['questions']
                   if q.get('material_group')
                   and q['material_group']['section'] != q.get('section_name')]
        check('材料组成员分区 == 材料所属分区（无跨分区吞题）',
              not bad_sec, bad_sec[:5])

        # 只有**资料分析**是「每题必属某个材料」（每题都引用图表/表格）。
        # 言语理解/判断推理/常识判断 则是「多篇共用材料 + 独立题并存」，
        # 故只有部分题归组 —— 对这几个分区断言「整分区归组」同样是错的
        # （首版即因此误报 5 项）。正确做法：这几分区只要求「至少有题归组」。
        for sec in sorted({g['section'] for g in mg}):
            n_in = subs.get(sec, 0)
            n_gr = sum(1 for q in r['questions']
                       if q.get('section_name') == sec
                       and q.get('material_group'))
            if sec == '资料分析':
                check('「资料分析」每题必属材料（%d 题）' % n_in,
                      n_in == n_gr and n_in > 0, '%d vs %d' % (n_in, n_gr))
            else:
                check('「%s」至少部分题归组（%d/%d）' % (sec, n_gr, n_in),
                      0 < n_gr <= n_in, '%d vs %d' % (n_gr, n_in))
            # 无论如何都不得出现「材料关联异常」
            unrel = [q['question_number'] for q in r['questions']
                     if q.get('section_name') == sec
                     and '材料关联异常' in (q.get('review_reasons') or [])]
            check('「%s」无材料关联异常标记' % sec, not unrel, unrel[:5])

        # 考点归一（省级前缀必须剥离）
        prov_bad = [(q['question_number'], n)
                    for q in r['questions']
                    for n in (q.get('kao_points_normalized') or [])
                    if '特色-' in n or '特色 -' in n]
        check('考点归一：无残留省级前缀', not prov_bad, prov_bad[:3])

        # need_review 分布（低质量题入库并标红，不丢弃）
        nr = sum(1 for q in r['questions'] if q.get('need_review') == 1)
        reasons = {}
        for q in r['questions']:
            for x in (q.get('review_reasons') or []):
                reasons[x] = reasons.get(x, 0) + 1
        print('  need_review=1 共 %d 题，原因分布: %s' % (nr, reasons))
        check('低质量题未被丢弃（总数不变）', len(r['questions']) == total,
              '%d vs %d' % (len(r['questions']), total))

        # 元数据断言
        exp_prov = '国考' if folder == '国考行测' else folder.replace('行测', '')
        check('省份正确（取自文件夹名）', meta.get('exam_province') == exp_prov,
              '%s vs %s' % (meta.get('exam_province'), exp_prov))
        check('年份正确', meta.get('exam_year') == year, meta.get('exam_year'))
        if variant:
            check('卷别正确', meta.get('paper_variant') == variant,
                  meta.get('paper_variant'))

        summary.append({
            'folder': folder, 'year': year, 'variant': variant,
            'qfile': qf, 'afile': af, 'total': total,
            'matched': r['matched_count'], 'match_rate': r['match_rate'],
            'blocked': xr['blocked_count'], 'material_groups': len(mg),
            'subcategories': subs, 'need_review': nr,
            'reasons': reasons, 'province': meta.get('exam_province'),
            'exam_type': meta.get('exam_type'),
        })
        db.rollback()
finally:
    db.close()

print()
print('=' * 66)
print('六套试点汇总')
print('%-12s %-6s %-8s %-7s %-8s %-8s %-6s %s'
      % ('目录', '年份', '卷别', '省份', '题数', '匹配率', '阻断', '材料组'))
for s in summary:
    print('%-12s %-6s %-8s %-7s %-8d %-8s %-6d %d'
          % (s['folder'], s['year'], s['variant'] or '-', s['province'],
             s['total'], s['match_rate'], s['blocked'], s['material_groups']))
tot = sum(s['total'] for s in summary)
mt = sum(s['matched'] for s in summary)
print()
print('合计 %d 套 / %d 题，匹配 %d 题（%.2f%%），阻断合计 %d'
      % (len(summary), tot, mt, 100.0 * mt / tot,
         sum(s['blocked'] for s in summary)))

os.makedirs('tmp', exist_ok=True)
with io.open('tmp/task15_pilot.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print('已留档: tmp/task15_pilot.json')

print()
print('RESULT = %s   失败 %d 项 %s'
      % ('PASS' if not fails else 'FAIL', len(fails), fails or ''))
sys.exit(0 if not fails else 1)