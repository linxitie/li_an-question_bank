#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regroup_composite.py — 存量复合题（题组）重组脚本（P2-3）

背景：历史导入的复合题（大题套小题）在早期版本中被拆散为扁平题目，
虽然后续导入已通过 question_import 的批内识别挂组，但存量数据仍散落。
本脚本扫描 group_id=0 的存量题目，用 composite_matcher 规则集（层1）+
语义增强（层2）重新识别题组，并（--apply 时）写入 question_groups +
更新 question_bank 的 group_id/question_level/sort_order。

五件套：--dry-run 默认预览 / --apply 显式写入 / 自动备份整库 / JSONL 审计 / 幂等可重跑。

用法:
  cd backend
  python scripts/regroup_composite.py                 # dry-run 预览分组建议
  python scripts/regroup_composite.py --apply         # 实际写入
  python scripts/regroup_composite.py --source 江西    # 仅处理指定来源
"""
import sys
import os
import json
import shutil
import argparse
import logging
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BACKEND_DIR, 'data', 'question_bank.db')


def _backup():
    """备份整库（--apply 前调用），返回备份路径"""
    backup_dir = os.path.join(_BACKEND_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backup_dir, f'backup_pre_regroup_{ts}.sqlite')
    con = __import__('sqlite3').connect(_DB_PATH)
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    shutil.copy2(_DB_PATH, dst)
    return dst


def _extract_first_qnum(content: str):
    """提取题干中第一个题号（复用 text_parser 统一题号提取器）"""
    try:
        from app.services.text_parser import extract_question_numbers
        nums = extract_question_numbers(content or '')
        return nums[0].number if nums else None
    except Exception:
        return None


def _analyze_batch(questions):
    """对一组题目做题组识别（层1规则引擎 + 层2语义增强），返回分组建议列表。

    questions: [{question_id, question_content, options, question_type_detail, answer, source}]
    返回: [{group_type, head_question_id, member_question_ids, confidence}]
    不操作数据库。
    """
    from app.services.composite_matcher import (
        match_group_head, infer_member_qnums, semantic_grouping,
    )

    suggestions = []
    claimed = set()

    # 预提取题号
    qnums = {}
    for q in questions:
        qnums[q['question_id']] = _extract_first_qnum(q['question_content'] or '')

    # 层1：规则引擎（显式标识）
    for i, q in enumerate(questions):
        qid = q['question_id']
        if qid in claimed:
            continue
        head = match_group_head(q.get('question_content') or '')
        if not head:
            continue
        group_type, qnum_range = head
        head_qn = qnums.get(qid)
        candidate_qnums = [qnums[x['question_id']] for j, x in enumerate(questions)
                           if x['question_id'] != qid and x['question_id'] not in claimed
                           and qnums.get(x['question_id']) is not None]
        member_qnums = infer_member_qnums(head_qn, candidate_qnums, qnum_range)
        if not member_qnums:
            continue
        member_ids = [qid]
        claimed.add(qid)
        for mqn in member_qnums:
            for x in questions:
                if x['question_id'] not in claimed and qnums.get(x['question_id']) == mqn:
                    member_ids.append(x['question_id'])
                    claimed.add(x['question_id'])
                    break
        suggestions.append({
            'group_type': group_type,
            'head_question_id': qid,
            'member_question_ids': member_ids,
            'confidence': 1.0,
        })

    # 层2：语义增强（无显式标识的复合题）
    unclaimed = [q for q in questions if q['question_id'] not in claimed]
    if len(unclaimed) >= 2:
        sem_suggestions = semantic_grouping(unclaimed)
        for sug in sem_suggestions:
            head_local = sug.get('head_index')
            member_locals = sug.get('member_indices') or []
            if head_local is None or not member_locals:
                continue
            head_q = unclaimed[head_local]
            member_qs = [unclaimed[ml] for ml in member_locals if 0 <= ml < len(unclaimed)]
            suggestions.append({
                'group_type': sug.get('group_type') or 'material',
                'head_question_id': head_q['question_id'],
                'member_question_ids': [head_q['question_id']] + [m['question_id'] for m in member_qs],
                'confidence': sug.get('confidence', 0.6),
            })

    return suggestions


def _load_questions(source_filter=None):
    """读取存量未分组题目（group_id=0 且 status=1），按 (source, subject_id) 分组返回"""
    from app.core.database import SessionLocal
    from app.models.models import QuestionBank

    db = SessionLocal()
    try:
        q = db.query(QuestionBank).filter(
            QuestionBank.group_id == 0,
            QuestionBank.status == 1,
        )
        if source_filter:
            q = q.filter(QuestionBank.source.like(f'%{source_filter}%'))
        rows = q.order_by(QuestionBank.question_id.asc()).all()

        groups = defaultdict(list)
        for r in rows:
            key = (r.source or '', r.subject_id or 0)
            groups[key].append({
                'question_id': r.question_id,
                'question_content': r.question_content or '',
                'options': r.options,
                'question_type_detail': getattr(r, 'question_type_detail', ''),
                'answer': r.answer or '',
                'source': r.source or '',
            })
        return groups
    finally:
        db.close()


def do_dry_run(source_filter=None):
    groups = _load_questions(source_filter)
    total_suggestions = []
    for key, questions in groups.items():
        if len(questions) < 2:
            continue
        suggestions = _analyze_batch(questions)
        for s in suggestions:
            s['_source'] = key[0]
            total_suggestions.append(s)

    print('=' * 60)
    print('[DRY RUN] 存量复合题重组计划（未修改）')
    print('=' * 60)
    print(f"识别到 {len(total_suggestions)} 个候选题组")
    for i, s in enumerate(total_suggestions, 1):
        print(f"  #{i} 来源={s['_source']} 类型={s['group_type']} 置信度={s['confidence']}")
        print(f"     头题 #{s['head_question_id']} + 小题 {[m for m in s['member_question_ids'] if m != s['head_question_id']]}")
    return total_suggestions


def do_apply(source_filter=None):
    from app.core.database import SessionLocal
    from app.models.models import QuestionBank, QuestionGroup

    backup = _backup()
    logger.info(f"已备份整库 → {backup}")

    groups = _load_questions(source_filter)
    total_suggestions = []
    for key, questions in groups.items():
        if len(questions) < 2:
            continue
        total_suggestions.extend(_analyze_batch(questions))

    audit_path = os.path.join(_BACKEND_DIR, 'data', 'audit',
                              f'regroup_composite_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl')
    os.makedirs(os.path.dirname(audit_path), exist_ok=True)

    db = SessionLocal()
    created = 0
    linked = 0
    try:
        for s in total_suggestions:
            head_q = db.query(QuestionBank).filter(
                QuestionBank.question_id == s['head_question_id']).first()
            if not head_q:
                continue
            # 幂等：头题若已挂组则跳过
            if head_q.group_id != 0:
                continue
            group = QuestionGroup(
                group_type=s['group_type'],
                shared_content=head_q.question_content or '',
                title=(head_q.question_content or '')[:200],
                subject='',
                source=s.get('_source') or head_q.source or '',
            )
            db.add(group)
            db.flush()
            created += 1
            for sort_idx, mid in enumerate(s['member_question_ids'], 1):
                row = db.query(QuestionBank).filter(QuestionBank.question_id == mid).first()
                if row and row.group_id == 0:
                    row.group_id = group.id
                    row.question_level = 2
                    row.sort_order = sort_idx
                    linked += 1
            with open(audit_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'group_id': group.id,
                    'group_type': s['group_type'],
                    'head_question_id': s['head_question_id'],
                    'member_question_ids': s['member_question_ids'],
                    'confidence': s['confidence'],
                }, ensure_ascii=False) + '\n')
        db.commit()
        logger.info(f"重组完成：创建 {created} 个题组，挂组 {linked} 题")
        logger.info(f"审计 → {audit_path}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='存量复合题重组（五件套：dry-run/备份/审计/幂等）')
    p.add_argument('--apply', action='store_true', help='实际写入（默认dry-run）')
    p.add_argument('--source', type=str, help='仅处理指定来源（模糊匹配）')
    args = p.parse_args()
    if args.apply:
        do_apply(args.source)
    else:
        do_dry_run(args.source)
