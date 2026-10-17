#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedup_questions.py — 同题重复副本去重（问题4-R4）

背景：同一 docx 被重复导入 4~5 次，题干相同但内嵌图片路径不同，
精确去重失效，产生大量重复副本（且副本间题型/答案不一致）。

判定规则（三重条件，宁漏勿错）：
  1. 同 subject_id
  2. 题干归一化（clean_question_text + 剥离<img>标签）后相似度 ≥ 0.95
  3. 图片签名一致（题干中所有图片文件名的 md5 指纹排序后相等）
     —— 防止"同题干不同图表"被误合并

保留策略（信息最全者胜出）：
  解析非空 > 答案有效(非空非待补充) > 选项非空 > question_id 最小

处置策略：
  - 保留副本：status=1 不动
  - 重复副本：status=0 软删除
  - 行为数据（答题/错题/收藏/笔记/试卷关联等）：question_id 重定向到保留副本
  - 辅助数据（detail 分类、图片映射）：随副本删除（保留副本自有数据不受影响）

用法:
  python scripts/dedup_questions.py             # dry-run 输出清单（默认）
  python scripts/dedup_questions.py --apply     # 执行（先备份+审计）
  python scripts/dedup_questions.py --restore data/audit/dedup_{ts}.jsonl
"""
import sys
import os
import re
import json
import shutil
import sqlite3
import argparse
import logging
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text as sa_text
from app.core.database import SessionLocal
from app.models.models import QuestionBank
from app.services.text_parser import clean_question_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB_PATH = os.path.join(_BACKEND_DIR, 'data', 'question_bank.db')
SIM_THRESHOLD = 0.95

IMG_MD5_RE = re.compile(r'_([0-9a-f]{8})\.(?:png|jpg|jpeg|webp|gif)', re.IGNORECASE)
IMG_TAG_RE = re.compile(r'<img[^>]*>', re.IGNORECASE)

# 重定向表（行为/关联数据）；辅助表（detail/image）随副本删除
REDIRECT_TABLES = [
    'paper_question_relation', 'exam_answer_detail', 'practice_record',
    'wrong_question_personal', 'wrong_question_class', 'video_watch_record',
    'video_resource', 'favorite_question', 'question_note', 'question_marker',
    'question_knowledge', 'question_edit_log',
]
AUX_DELETE_TABLES = ['question_detail_category', 'question_image']


def normalize_stem(content: str) -> str:
    """归一化题干：剥离<img>标签后走统一清洗"""
    if not content:
        return ''
    no_img = IMG_TAG_RE.sub('', content)
    return clean_question_text(no_img)


def image_signature(content: str) -> tuple:
    """提取题干中图片文件名的 md5 指纹（排序元组），作为图表身份标识"""
    return tuple(sorted(set(m.lower() for m in IMG_MD5_RE.findall(content or ''))))


def quality_score(q: QuestionBank) -> tuple:
    """保留优先级评分：解析非空 > 答案有效 > 选项非空 > qid 最小"""
    analysis_ok = 1 if (q.answer_analysis or '').strip() not in ('', '无', '待补充') else 0
    answer_ok = 0 if (q.answer or '').strip() in ('', '待补充') else 1
    opts = q.options
    opts_ok = 0
    if opts:
        try:
            import json as _json
            parsed = _json.loads(opts) if isinstance(opts, str) else opts
            opts_ok = 1 if parsed else 0
        except Exception:
            opts_ok = 0
    return (analysis_ok, answer_ok, opts_ok, -q.question_id)


def find_duplicate_groups(db):
    """返回 [(keep_qid, [dup_qid...], similarity), ...]"""
    questions = db.query(QuestionBank).filter(QuestionBank.status == 1).all()
    logger.info(f"活跃题目: {len(questions)}")
    by_subject = defaultdict(list)
    for q in questions:
        by_subject[q.subject_id].append(q)

    groups = []
    for sid, qs in sorted(by_subject.items()):
        # 预计算归一化与签名
        metas = [(q, normalize_stem(q.question_content or ''),
                  image_signature(q.question_content or '')) for q in qs]
        used = set()
        for i in range(len(metas)):
            if metas[i][0].question_id in used:
                continue
            qi, ni, si = metas[i]
            if not ni:
                continue
            group_dups = []
            for j in range(i + 1, len(metas)):
                qj, nj, sj = metas[j]
                if qj.question_id in used or not nj:
                    continue
                if si != sj:
                    continue  # 图片签名不同 → 不同题
                # 长度快速过滤
                if abs(len(ni) - len(nj)) / max(len(ni), len(nj)) > 0.2:
                    continue
                sim = SequenceMatcher(None, ni, nj).ratio()
                if sim >= SIM_THRESHOLD:
                    group_dups.append((qj, sim))
            if group_dups:
                candidates = [qi] + [d[0] for d in group_dups]
                keep = max(candidates, key=quality_score)
                dups = [c for c in candidates if c.question_id != keep.question_id]
                best_sim = max([s for _, s in group_dups] + [1.0])
                groups.append((keep, dups, best_sim))
                used.add(keep.question_id)
                for d in dups:
                    used.add(d.question_id)
    return groups


def _backup_db() -> str:
    backup_dir = os.path.join(_BACKEND_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(backup_dir, f'backup_pre_dedup_{ts}.sqlite')
    con = sqlite3.connect(_DB_PATH)
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    shutil.copy2(_DB_PATH, dst)
    return dst


def _tables_with_question_id(con):
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    out = []
    for (t,) in rows:
        cols = con.execute(f'PRAGMA table_info({t})').fetchall()
        if any(c[1] == 'question_id' for c in cols):
            out.append(t)
    return out


def do_dry_run(db):
    groups = find_duplicate_groups(db)
    print('=' * 70)
    print(f'[DRY RUN] 发现 {len(groups)} 组重复（未修改任何数据）')
    print('=' * 70)
    total_dups = 0
    for keep, dups, sim in groups:
        total_dups += len(dups)
        print(f"\n◆ 保留 qid={keep.question_id}  "
              f"解析[{'有' if (keep.answer_analysis or '').strip() else '无'}] "
              f"答案[{(keep.answer or '')[:12]!r}]  相似度={sim:.3f}")
        print(f"  题干: {normalize_stem(keep.question_content or '')[:60]}")
        for d in dups:
            print(f"  ├─ 软删 qid={d.question_id}  "
                  f"解析[{'有' if (d.answer_analysis or '').strip() else '无'}] "
                  f"答案[{(d.answer or '')[:12]!r}] 类型[{d.type.type_name if d.type else '?'}]")
    print(f"\n合计: {len(groups)} 组 / {total_dups} 道重复副本将被软删除并重定向引用")
    print("确认后执行: python scripts/dedup_questions.py --apply")
    return groups


def do_apply(db):
    groups = find_duplicate_groups(db)
    if not groups:
        logger.info("无重复组（幂等：可能已处理），0 changes")
        return
    backup_path = _backup_db()
    logger.info(f"已备份整库 → {backup_path}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    audit_dir = os.path.join(_BACKEND_DIR, 'data', 'audit')
    os.makedirs(audit_dir, exist_ok=True)
    audit_path = os.path.join(audit_dir, f'dedup_{ts}.jsonl')
    audit_f = open(audit_path, 'w', encoding='utf-8')

    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    all_tables = _tables_with_question_id(con)

    try:
        for keep, dups, sim in groups:
            keep_id = keep.question_id
            for d in dups:
                dup_id = d.question_id
                audit_f.write(json.dumps({
                    'action': 'soft_delete', 'qid': dup_id, 'keep_qid': keep_id,
                    'similarity': round(sim, 4),
                    'snapshot': {
                        'question_content': d.question_content,
                        'options': d.options, 'answer': d.answer,
                        'answer_analysis': d.answer_analysis,
                        'type_id': d.type_id, 'subject_id': d.subject_id,
                    },
                }, ensure_ascii=False) + '\n')
                # 1) 重定向行为数据
                for t in REDIRECT_TABLES:
                    if t not in all_tables:
                        continue
                    cur = con.execute(
                        f'UPDATE OR IGNORE {t} SET question_id=? WHERE question_id=?',
                        (keep_id, dup_id))
                    if cur.rowcount:
                        audit_f.write(json.dumps({
                            'action': 'redirect', 'table': t,
                            'from_qid': dup_id, 'to_qid': keep_id,
                            'rows': cur.rowcount,
                        }, ensure_ascii=False) + '\n')
                # 2) 删除辅助数据（保留副本自有，不受影响）
                for t in AUX_DELETE_TABLES:
                    if t not in all_tables:
                        continue
                    cur = con.execute(f'DELETE FROM {t} WHERE question_id=?', (dup_id,))
                    if cur.rowcount:
                        audit_f.write(json.dumps({
                            'action': 'delete_aux', 'table': t, 'qid': dup_id,
                            'rows': cur.rowcount,
                        }, ensure_ascii=False) + '\n')
                # 3) 软删除副本
                con.execute('UPDATE question_bank SET status=0 WHERE question_id=?',
                            (dup_id,))
        con.commit()
        audit_f.close()
        logger.info(f"完成: {len(groups)} 组 / "
                    f"{sum(len(d) for _, d, _ in groups)} 道副本软删除")
        logger.info(f"审计日志 → {audit_path}")
        logger.info(f"回滚: python scripts/dedup_questions.py --restore {audit_path}")
    except Exception:
        con.rollback()
        audit_f.close()
        raise
    finally:
        con.close()


def do_restore(audit_path):
    if not os.path.exists(audit_path):
        print(f'❌ 审计文件不存在: {audit_path}')
        sys.exit(1)
    con = sqlite3.connect(_DB_PATH)
    entries = [json.loads(l) for l in open(audit_path, encoding='utf-8') if l.strip()]
    # 逆序回滚
    for e in reversed(entries):
        act = e['action']
        if act == 'soft_delete':
            snap = e['snapshot']
            con.execute("""UPDATE question_bank SET status=1, question_content=?,
                options=?, answer=?, answer_analysis=?, type_id=?, subject_id=?
                WHERE question_id=?""",
                        (snap['question_content'], snap['options'], snap['answer'],
                         snap['answer_analysis'], snap['type_id'], snap['subject_id'],
                         e['qid']))
        elif act == 'redirect':
            con.execute(f"UPDATE OR IGNORE {e['table']} SET question_id=? "
                        "WHERE question_id=?",
                        (e['from_qid'], e['to_qid']))
        elif act == 'delete_aux':
            pass  # 辅助行删除不可精确逆序重插（无快照），软删副本恢复后不影响主数据
    con.commit()
    con.close()
    print(f'✅ 已回滚（来自 {audit_path}）')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='同题重复副本去重')
    parser.add_argument('--apply', action='store_true', help='实际执行（默认dry-run）')
    parser.add_argument('--restore', metavar='JSONL', help='从审计日志回滚')
    args = parser.parse_args()

    if args.restore:
        do_restore(args.restore)
    else:
        db = SessionLocal()
        try:
            if args.apply:
                do_apply(db)
            else:
                do_dry_run(db)
        finally:
            db.close()
