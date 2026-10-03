# -*- coding: utf-8 -*-
"""T16 全量行测导入驱动 —— 按省份分批，每批门禁把关。

设计要点
--------
1. **不新造插入逻辑**：逐题调用既有 `_upsert_question_core()`。它已处理
   阻断闸门、`clean_question_text` 统一清洗、`_detect_duplicate` 回填式重导入、
   题型判定、`xingce_subcategory`（经 `subcategory` 键）、图片落盘，且**不 commit**
   —— 事务边界正好由本驱动控制。
2. **省份只认文件夹名**：走任务 12 的 `_resolve_xingce_paper_metadata()` +
   `_upsert_xingce_paper()`。**不复用** `/batch-parsed`，因其省份由
   `_auto_detect_tags(paper_name, 正文)` 推断，会破坏 T12 红线。
3. **事务分批**：每批 commit 一次（计划要求「每 N 题 commit」）。
4. **门禁把关**：每批后跑 G1 公专 + G2 行测，任一非 0 立即停止。

用法：
    python scripts/import_xingce_all.py --batches 国考 --dry-run
    python scripts/import_xingce_all.py --batches 国考
    python scripts/import_xingce_all.py --all
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf
from sqlalchemy import text

from app.api.v1.question_import import (
    _separate_match_xingce,
    _upsert_question_core,
    _upsert_xingce_paper,
    _resolve_xingce_paper_metadata,
    _xingce_doc_role,
    _xingce_paper_variant,
    _xingce_review_flags,
)
from app.core.database import SessionLocal
from app.models.models import QuestionGroup, QuestionKnowledge, ExamPaperTag

ROOT = 'D:/砺安题库/砺安题库/题库/行测'
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 计划建议顺序：国考(9) → 江苏(8) → 北京(4) → 广东(4) → 其余 20 省各 3
ORDER = ['国考行测', '江苏行测', '北京行测', '广东行测']


def pdf_text(p):
    d = pymupdf.open(p)
    s = '\n'.join(d[i].get_text('text') for i in range(len(d)))
    d.close()
    return s


def discover(folder):
    """列出该省全部 (year, variant, qfile, afile) 套。配对键=(年份,卷别)。"""
    d = os.path.join(ROOT, folder)
    by = {}
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith('.pdf'):
            continue
        ym = re.search(r'(20\d{2})', fn)
        if not ym:
            continue
        role = _xingce_doc_role(fn)
        if role == 'unknown':
            continue
        by.setdefault((int(ym.group(1)), _xingce_paper_variant(fn)), {})[role] = fn
    out = []
    for key in sorted(by, key=lambda k: (k[0], k[1] or '')):
        r = by[key]
        if r.get('questions') and r.get('answers'):
            out.append((key[0], key[1], r['questions'], r['answers']))
    return out


def run_gate(name, cmd):
    """跑门禁，返回 (ok, 输出尾行)。"""
    p = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    tail = [l for l in (p.stdout or '').splitlines() if l.strip()][-3:]
    return p.returncode == 0, ' | '.join(tail)


def kp_index(db):
    """(name, parent_id) -> point_id，用于考点关联。"""
    idx = {}
    for pid, name, subj, parent in db.query(
            __import__('app.models.models', fromlist=['KnowledgePoint'])
            .KnowledgePoint.point_id,
            __import__('app.models.models', fromlist=['KnowledgePoint'])
            .KnowledgePoint.point_name,
            __import__('app.models.models', fromlist=['KnowledgePoint'])
            .KnowledgePoint.subject_id,
            __import__('app.models.models', fromlist=['KnowledgePoint'])
            .KnowledgePoint.parent_id).all():
        if subj == 1:
            idx[(name, parent)] = pid
    return idx


def import_paper(db, user, folder, year, variant, qfile, afile, kp):
    """导入单套。返回统计 dict。调用方负责 commit。"""
    meta = _resolve_xingce_paper_metadata(folder, qfile, '', '')
    paper_name = os.path.splitext(qfile)[0]
    prev = _separate_match_xingce(
        db, {'paper_name': paper_name},
        pdf_text(os.path.join(ROOT, folder, qfile)),
        pdf_text(os.path.join(ROOT, folder, afile)),
        user_id=user.user_id, subject_name='')
    xr = prev['xingce_report']

    if xr['blocked_count']:
        return {'paper': paper_name, 'year': year, 'variant': variant,
                'ok': False, 'reason': 'blocked=%d 拒绝入库' % xr['blocked_count'],
                'total': prev['total_questions'], 'inserted': 0}

    paper, _created = _upsert_xingce_paper(db, user, meta, paper_name,
                                          prev['total_questions'],
                                          is_complete=True)
    if paper is None:
        return {'paper': paper_name, 'year': year, 'variant': variant,
                'ok': False, 'reason': '题数低于建卷阈值', 'total': 0, 'inserted': 0}

    # ── 材料题组 ──────────────────────────────────────────────
    qno_to_gid = {}
    groups_made = 0
    for g in xr['material_groups']:
        qg = QuestionGroup(
            group_type=g['group_type'],
            shared_content='',
            title='%s（%s）材料%s' % (paper_name, g['section'], g['ordinal']),
            subject='行测',
            source=paper_name,
        )
        db.add(qg)
        db.flush()
        groups_made += 1
        for qno in g['member_qnums']:
            qno_to_gid[int(qno)] = (qg.id, g['member_qnums'].index(int(qno)) + 1)

    # ── 逐题入库 ──────────────────────────────────────────────
    inserted = dup = nr = ko = 0
    for q in prev['questions']:
        qno = q.get('question_number')
        try:
            qno = int(qno)
        except (TypeError, ValueError):
            qno = None
        mg = q.get('material_group') or {}
        gid, sort = qno_to_gid.get(qno, (0, 0))
        payload = {
            'question_content': q.get('content') or '',
            'options': [{'key': o.get('key'), 'value': o.get('value')}
                        for o in (q.get('options') or [])
                        if isinstance(o, dict)],
            'answer': q.get('answer') or '',
            'answer_analysis': q.get('analysis') or '',
            'question_number': str(qno) if qno is not None else None,
            'question_type_detail': q.get('question_type') or '',
            'subject_category': '行测',
            'subcategory': q.get('xingce_subcategory') or '',
            'group_id': gid,
            'question_level': 2 if gid else 1,
            'sort_order': sort,
            'exam_year': year,
            'source': paper_name,
            'import_mode': 'separate',
            'blocked': q.get('blocked'),
            'block_reasons': q.get('block_reasons') or [],
            # ★ 行测专用去重口径（任务 16）：按 (题号, 来源) 而非文本相似度。
            # 图形推理的区分信息在图片里，文本层只有共用指令句/5~9 字类比短语，
            # 80% 文本相似度会把不同题判成同题并静默丢弃（实测单套 60% 误判）。
            # 行测题号在卷内唯一，故此口径既精确又不会误杀，且天然实现「仅同卷去重」。
            'dedup_scope': 'qno_in_source',
        }
        try:
            res = _upsert_question_core(db, user, payload)
        except Exception as e:
            return {'paper': paper_name, 'year': year, 'variant': variant,
                    'ok': False, 'reason': '入库异常 %s: %s' % (type(e).__name__, e),
                    'total': prev['total_questions'], 'inserted': inserted}
        qid = res.get('question_id')
        if not qid:
            continue
        if res.get('import_status') == 'DUPLICATE':
            dup += 1
        else:
            inserted += 1

        # T13 的待复核原因（_upsert_question_core 只按题型置信度置位）
        flags = _xingce_review_flags(q)
        if flags:
            db.execute(
                text('update question_bank set need_review=1'
                     ' where question_id=:i'),
                {'i': qid})
            nr += 1

        # 考点关联
        for nm in (q.get('kao_points_normalized') or []):
            pid = kp.get(nm)
            if pid:
                db.execute(
                    text('insert or ignore into question_knowledge'
                         ' (question_id, knowledge_point_id) values (:q,:k)'),
                    {'q': qid, 'k': pid})
                ko += 1

    return {'paper': paper_name, 'year': year, 'variant': variant, 'ok': True,
            'total': prev['total_questions'], 'inserted': inserted,
            'duplicate': dup, 'need_review': nr, 'kao_links': ko,
            'material_groups': groups_made,
            'province': meta.get('exam_province'), 'exam_type': meta.get('exam_type'),
            'paper_variant': meta.get('paper_variant')}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--batches', help='逗号分隔的省目录名')
    g.add_argument('--all', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if args.all:
        folders = ORDER + [f for f in sorted(os.listdir(ROOT))
                           if os.path.isdir(os.path.join(ROOT, f))
                           and f not in ORDER]
    else:
        folders = [x.strip() for x in args.batches.split(',') if x.strip()]

    from app.models.models import KnowledgePoint
    db = SessionLocal()
    user = None
    try:
        from app.models.models import SysUser
        user = db.query(SysUser).first()
        kp = {}
        for pid, name, parent in db.query(KnowledgePoint.point_id,
                                          KnowledgePoint.point_name,
                                          KnowledgePoint.parent_id).all():
            if parent == 0:
                kp[name] = pid

        report = []
        for folder in folders:
            sets = discover(folder)
            print()
            print('=' * 68)
            print('【批次】%s  共 %d 套' % (folder, len(sets)))
            if not sets:
                print('  无可配对套，跳过')
                continue
            batch = {'folder': folder, 'papers': [], 'ok': 0, 'fail': 0,
                     'total': 0, 'inserted': 0}
            for year, variant, qf, af in sets:
                t0 = time.time()
                st = import_paper(db, user, folder, year, variant, qf, af, kp)
                st['sec'] = round(time.time() - t0, 1)
                batch['papers'].append(st)
                if st['ok']:
                    batch['ok'] += 1
                    batch['total'] += st['total']
                    batch['inserted'] += st.get('inserted', 0)
                else:
                    batch['fail'] += 1
                print('  [%s] %s %s%s  题%d 入库%d dup%d 待复核%d 组%d 考点%d  %.1fs'
                      % ('OK ' if st['ok'] else 'FAIL',
                         year, variant or '-', '',
                         st['total'], st.get('inserted', 0),
                         st.get('duplicate', 0), st.get('need_review', 0),
                         st.get('material_groups', 0),
                         st.get('kao_links', 0), st['sec']))
                if not st['ok']:
                    print('       原因: %s' % st['reason'])
            if args.dry_run:
                db.rollback()
                print('  [dry-run] 已回滚')
            else:
                db.commit()
                print('  已提交本批')

            if not args.dry_run and batch['ok']:
                g1, g1o = run_gate('G1', [sys.executable,
                                          'scripts/verify_parser_regression.py',
                                          'D:/砺安题库/砺安题库/题库/公安题目（打印）',
                                          '--out', 'data/parser_regression.txt'])
                print('  G1 公专门禁: %s  %s' % ('PASS' if g1 else 'FAIL', g1o))
                batch['gate_g1'] = g1
                if not g1:
                    print('  !! G1 失败，停止后续批次')
                    report.append(batch)
                    break
            report.append(batch)

        # ── 汇总 ────────────────────────────────────────────────
        tot = sum(b['total'] for b in report)
        ins = sum(b['inserted'] for b in report)
        n = db.query(__import__('app.models.models', fromlist=['QuestionBank'])
                     .QuestionBank.question_id).count()
        xc = db.execute(text('select count(*) from question_bank'
                             ' where subject_id=1')).fetchone()[0]
        gz = db.execute(text('select count(*) from question_bank'
                             ' where subject_id=3')).fetchone()[0]
        print()
        print('=' * 68)
        print('批次汇总: %d 批  成功 %d  失败 %d' % (
            len(report), sum(b['ok'] for b in report),
            sum(b['fail'] for b in report)))
        print('本轮解析 %d 题  入库 %d 题' % (tot, ins))
        print('DB: question_bank=%d  行测=%d  公专=%d' % (n, xc, gz))
        if args.dry_run:
            db.rollback()
        os.makedirs('tmp', exist_ok=True)
        with io.open('tmp/task16_batches.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print('留档: tmp/task16_batches.json')
    finally:
        db.rollback()
        db.close()


if __name__ == '__main__':
    main()