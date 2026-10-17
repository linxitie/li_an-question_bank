# -*- coding: utf-8 -*-
"""历史复合题重组扫描脚本 —— 复用 composite_matcher 识别存量被分割的复合题。

背景
----
question_groups 仅 21 组、20 题带 group_id，存量公专「情境题/材料题」绝大多数仍是
扁平散题，三端（教师/学生/管理员）无法完整查看。本脚本扫描存量，生成重组建议。

安全与运维
----------
- 默认 dry-run：只读数据库、只输出 JSON 建议，绝不写库。
- --apply 才写库：建 question_groups + 回填 question_bank.group_id/parent_id/
  question_level/sort_order；写入前自动备份（sqlite3 backup API，禁 shutil.copy2）。
- 幂等：已带 group_id 的题跳过；题组复用键用「subject + 材料头内容指纹」，重复运行不产生重复题组。

复用边界（去粗取精，不新建识别算法）
----------------------------------
- 识别复用 app/services/composite_matcher.py 的 semantic_grouping（层1规则 + 层2语义）。
- 题号提取/相似度等由 composite_matcher 内部复用 text_parser，本脚本零重写。

用法
----
  python scripts/regroup_composite_questions.py --dry-run --subject gongzhuan --limit 500
  python scripts/regroup_composite_questions.py --apply --out data/gates/regroup_applied.json
"""

import sqlite3
import json
import argparse
import os
import re
import sys
import hashlib
import datetime

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BACKEND_DIR)

from app.services.composite_matcher import match_group_head, infer_member_qnums, semantic_grouping
from app.services.text_parser import extract_question_numbers

SUBJECT_ID = {'gongzhuan': 3, 'shenlun': 2, 'xingce': 1}
SUBJECT_NAME = {3: '公专', 2: '申论', 1: '行测'}


def _parse_options(raw):
    """options（JSON 串 / list）归一化为 list。"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except Exception:
            return []
    return []


def load_questions(db_path, subject_id, limit=0):
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT q.question_id, q.question_content, q.options, q.answer,
               q.answer_analysis, t.type_name AS question_type_detail,
               q.group_id, q.question_number, q.source, q.difficulty
        FROM question_bank q
        LEFT JOIN question_type t ON t.type_id = q.type_id
        WHERE q.subject_id = ? AND q.status = 1
        ORDER BY q.question_id
    """
    params = [subject_id]
    if limit:
        sql += ' LIMIT ?'
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _group_fingerprint(subject_id, head_content):
    """题组复用键：subject + 材料头内容指纹（重复运行不产生重复题组）。"""
    norm = re.sub(r'\s+', '', head_content or '')
    return f"{subject_id}:{hashlib.sha256(norm.encode('utf-8')).hexdigest()[:16]}"


def _extract_first_qnum(text):
    """从文本提取第一个题号（复用 text_parser 统一题号提取器，禁另写解析）。"""
    try:
        nums = extract_question_numbers(text or '')
        return nums[0].number if nums else None
    except Exception:
        return None


def build_suggestions(rows):
    """识别复合题：层1规则（match_group_head + infer_member_qnums）为主，层2语义兜底。"""
    questions = []
    for r in rows:
        questions.append({
            'question_id': r['question_id'],
            'question_content': r['question_content'] or '',
            'options': _parse_options(r['options']),
            'answer': r['answer'] or '',
            'question_type_detail': r['question_type_detail'] or '',
            'question_number': r['question_number'],
            'group_id': r['group_id'],
            'source': r['source'],
            'difficulty': r['difficulty'],
        })

    # 预提取题号（层1 infer_member_qnums 需要）
    for q in questions:
        q['_qnum'] = _extract_first_qnum(q['question_content'])

    suggestions = []
    used = set()

    # 层1规则：match_group_head 识别题组头（range/material/scenario/passage）
    for i, q in enumerate(questions):
        if i in used:
            continue
        head = match_group_head(q['question_content'])
        if head is None:
            continue
        group_type, qnum_range = head
        head_qnum = q['_qnum']
        window = questions[i + 1:i + 31]  # 最多挂 30 道小题（与 composite_matcher._MAX_MEMBERS 一致）
        candidate_qnums = [qq['_qnum'] for qq in window]
        member_qnums = infer_member_qnums(head_qnum, candidate_qnums, qnum_range)
        member_indices = []
        for qn in member_qnums:
            for offset, qq in enumerate(window):
                j = i + 1 + offset
                if qq['_qnum'] == qn and j not in used:
                    member_indices.append(j)
                    break
        if not member_indices:
            continue
        suggestions.append({
            'head_index': i,
            'member_indices': member_indices,
            'group_type': group_type,
            'confidence': 1.0,
            'reason': 'rule: 题组头标识(根据以下...回答X-Y题/材料/情境) + 题号范围',
        })
        used.add(i)
        for m in member_indices:
            used.add(m)

    # 层2语义兜底：对层1未命中的题目做 semantic_grouping
    for s in semantic_grouping(questions):
        if s['head_index'] in used:
            continue
        members = [m for m in s.get('member_indices', []) if m not in used]
        if not members:
            continue
        s['member_indices'] = members
        suggestions.append(s)
        used.add(s['head_index'])
        for m in members:
            used.add(m)

    return suggestions, questions


def _backup_db(db_path):
    """sqlite3 backup API 备份（WAL 安全，禁 shutil.copy2）。"""
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = f'{db_path}.bak_regroup_{ts}'
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(bak)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return bak


def apply_regroup(db_path, subject_id, suggestions, questions):
    """写入题组 + 回填 group_id（幂等）。返回 (created_groups, updated_questions)。"""
    # 建议里 member_indices 是 questions 列表的索引，转成 question_id
    by_index = {i: questions[i] for i in range(len(questions))}
    created = 0
    updated = 0
    applied = []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for sug in suggestions:
            head = by_index.get(sug['head_index'])
            if head is None:
                continue
            members = [by_index[i] for i in sug['member_indices'] if i in by_index]
            if not members:
                continue

            # 幂等：head 已带 group_id 则跳过（说明已重组过）
            if head.get('group_id') and head['group_id'] != 0:
                continue

            fp = _group_fingerprint(subject_id, head['question_content'])
            # 复用键：同指纹已存在题组则复用，否则新建
            existing = conn.execute(
                'SELECT id FROM question_groups WHERE source = ? LIMIT 1', (fp,)
            ).fetchone()
            if existing:
                gid = existing['id']
            else:
                cur = conn.execute(
                    """INSERT INTO question_groups
                       (group_type, shared_content, title, subject, difficulty, source, create_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sug.get('group_type') or 'material',
                        head['question_content'],
                        (head['question_content'] or '')[:200],
                        SUBJECT_NAME.get(subject_id, ''),
                        str(head.get('difficulty') or ''),
                        fp,
                        datetime.datetime.now().isoformat(' '),
                    ),
                )
                gid = cur.lastrowid
                created += 1

            # 回填 head（母题）
            conn.execute(
                'UPDATE question_bank SET group_id=?, parent_id=0, question_level=1, sort_order=0 WHERE question_id=?',
                (gid, head['question_id']),
            )
            # 回填 members（小题）
            for order, m in enumerate(members, start=1):
                conn.execute(
                    'UPDATE question_bank SET group_id=?, parent_id=?, question_level=2, sort_order=? WHERE question_id=?',
                    (gid, head['question_id'], order, m['question_id']),
                )
                updated += 1

            applied.append({
                'group_id': gid,
                'group_type': sug.get('group_type'),
                'confidence': sug.get('confidence'),
                'reason': sug.get('reason'),
                'head_question_id': head['question_id'],
                'member_question_ids': [m['question_id'] for m in members],
            })

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {'created_groups': created, 'updated_questions': updated, 'applied': applied}


def main():
    parser = argparse.ArgumentParser(description='历史复合题重组扫描（复用 composite_matcher）')
    parser.add_argument('--subject', choices=['gongzhuan', 'shenlun', 'xingce'], default='gongzhuan')
    parser.add_argument('--limit', type=int, default=0, help='限制扫描题数（0=全部）')
    parser.add_argument('--db', default='data/question_bank.db')
    parser.add_argument('--out', default='data/gates/regroup_suggestions.json')
    parser.add_argument('--dry-run', action='store_true', default=True, help='只读扫描（默认）')
    parser.add_argument('--apply', action='store_true', help='写库（与 --dry-run 互斥）')
    args = parser.parse_args()
    if args.apply:
        args.dry_run = False

    db_path = os.path.join(_BACKEND_DIR, args.db)
    subject_id = SUBJECT_ID[args.subject]

    rows = load_questions(db_path, subject_id, args.limit)
    print(f'[regroup] subject={args.subject}(id={subject_id}) 扫描题目 {len(rows)} 道（dry_run={not args.apply}）')

    suggestions, questions = build_suggestions(rows)
    # 过滤：排除已带 group_id 的题组头（幂等）
    by_index = {i: questions[i] for i in range(len(questions))}
    fresh = []
    for sug in suggestions:
        head = by_index.get(sug['head_index'])
        if head and head.get('group_id') and head['group_id'] != 0:
            continue
        fresh.append(sug)
    print(f'[regroup] 识别候选题组 {len(fresh)} 个（已排除 {len(suggestions) - len(fresh)} 个已重组）')

    result = {
        'subject': args.subject,
        'subject_id': subject_id,
        'scanned_questions': len(rows),
        'suggestion_count': len(fresh),
        'dry_run': not args.apply,
        'suggestions': [
            {
                'group_type': s.get('group_type'),
                'confidence': s.get('confidence'),
                'reason': s.get('reason'),
                'head_index': s.get('head_index'),
                'head_question_id': by_index[s['head_index']]['question_id'],
                'head_content_preview': (by_index[s['head_index']]['question_content'] or '')[:80],
                'member_indices': s.get('member_indices'),
                'member_question_ids': [by_index[i]['question_id'] for i in s.get('member_indices') if i in by_index],
            }
            for s in fresh
        ],
    }

    if args.apply:
        if not fresh:
            print('[regroup] 无可应用的候选，跳过写入')
        else:
            bak = _backup_db(db_path)
            print(f'[regroup] 已备份 DB -> {bak}')
            applied = apply_regroup(db_path, subject_id, fresh, questions)
            result['apply_report'] = applied
            print(f"[regroup] 应用完成：新建题组 {applied['created_groups']} 个、回填小题 {applied['updated_questions']} 道")

    os.makedirs(os.path.dirname(os.path.join(_BACKEND_DIR, args.out)), exist_ok=True)
    out_path = os.path.join(_BACKEND_DIR, args.out)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'[regroup] 结果已写入 {out_path}')


if __name__ == '__main__':
    main()
