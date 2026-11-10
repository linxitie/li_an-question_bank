# -*- coding: utf-8 -*-
"""修复存量题目的快速练习分类字段（point_id / sub_category_id）。

背景：历史导入只写 QuestionKnowledge 关联表，QuestionBank.point_id 为空，
快速练习按 point_id 统计时整科落到「其他」。本脚本把关联表已有的三级考点
回填到主表；没有具体考点的题，回填该子科目的 canonical「其他」L3。

默认 dry-run；--apply 前用 sqlite3.backup() 备份并做 integrity_check（AGENTS R10）。
不新建任何 taxonomy 节点，幂等，可重复执行。
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import (  # noqa: E402
    KnowledgePoint,
    QuestionBank,
    QuestionKnowledge,
    SubCategory,
)

DB_PATH = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
BACKUP_DIR = os.path.join(BACKEND_DIR, 'data', 'backups')


def backup_database() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(
        BACKUP_DIR, f'question_bank_pre_taxonomy_repair_{datetime.now():%Y%m%d_%H%M%S}.db'
    )
    source, dest = sqlite3.connect(DB_PATH), sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def _other_point(db, subject_id: int, sc_id: int):
    if not subject_id or not sc_id:
        return None
    return db.query(KnowledgePoint).filter(
        KnowledgePoint.subject_id == subject_id,
        KnowledgePoint.sub_category_id == sc_id,
        KnowledgePoint.level == 3,
        KnowledgePoint.status == 1,
        KnowledgePoint.point_name.in_(('其他', '其他（未细分）')),
    ).order_by(KnowledgePoint.point_id).first()


def _sc_by_name(db, subject_id: int, name: str):
    name = (name or '').strip()
    if not name or name == '无':
        return None
    return db.query(SubCategory).filter(
        SubCategory.subject_id == subject_id,
        SubCategory.name == name,
        SubCategory.status == 1,
    ).first()


def plan_for(db, q):
    """返回 (point_id, sub_category_id, reason) 或 None（保持未分类）。"""
    if q.point_id:
        kp = db.query(KnowledgePoint).filter(
            KnowledgePoint.point_id == int(q.point_id),
            KnowledgePoint.level == 3,
            KnowledgePoint.status == 1,
        ).first()
        if kp:
            return int(kp.point_id), int(kp.sub_category_id or q.sub_category_id or 0), 'kp-主表已有'

    row = db.query(QuestionKnowledge, KnowledgePoint).join(
        KnowledgePoint,
        KnowledgePoint.point_id == QuestionKnowledge.knowledge_point_id,
    ).filter(
        QuestionKnowledge.question_id == q.question_id,
        KnowledgePoint.level == 3,
        KnowledgePoint.status == 1,
    ).order_by(KnowledgePoint.point_id).all()
    if row:
        specific = [r for r in row if (r[1].point_name or '').strip() != '其他']
        kp = (specific or row)[0][1]
        return int(kp.point_id), int(kp.sub_category_id or 0), 'QK关联'

    sc = None
    if q.sub_category_id:
        sc = db.query(SubCategory).filter(
            SubCategory.id == int(q.sub_category_id), SubCategory.status == 1
        ).first()
    if sc is None:
        for name in (q.xingce_subcategory, q.shenlun_subcategory, q.gongzhuan_subcategory):
            sc = _sc_by_name(db, int(q.subject_id or 0), name)
            if sc:
                break
    if sc:
        other = _other_point(db, int(q.subject_id or 0), int(sc.id))
        if other:
            return int(other.point_id), int(sc.id), '回填其他'
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description='回填快速练习 point_id / sub_category_id')
    parser.add_argument('--apply', action='store_true', help='真实写库（默认 dry-run）')
    parser.add_argument('--limit', type=int, default=15, help='打印样本数量')
    args = parser.parse_args()

    db = SessionLocal()
    pending = []
    counters = Counter()
    try:
        rows = db.query(QuestionBank).filter(
            QuestionBank.status == 1,
            (QuestionBank.point_id.is_(None)) | (QuestionBank.point_id == 0)
            | (QuestionBank.sub_category_id.is_(None)) | (QuestionBank.sub_category_id == 0),
        ).all()
        for q in rows:
            planned = plan_for(db, q)
            if not planned:
                counters['keep_unclassified'] += 1
                continue
            point_id, sc_id, reason = planned
            if point_id == int(q.point_id or 0) and sc_id == int(q.sub_category_id or 0):
                counters['already_ok'] += 1
                continue
            counters[reason] += 1
            pending.append((q.question_id, point_id, sc_id, reason))
    finally:
        db.close()

    print(f'待检查题目: {len(rows)}；计划回填: {len(pending)}；保持未分类: {counters["keep_unclassified"]}')
    for key in ('kp-主表已有', 'QK关联', '回填其他', 'already_ok'):
        if counters[key]:
            print(f'  {key}: {counters[key]}')
    for qid, point_id, sc_id, reason in pending[:args.limit]:
        print(f'  #{qid} -> point={point_id} sc={sc_id} ({reason})')

    if not args.apply:
        print('DRY-RUN：未写库。')
        return 0
    if not pending:
        print('没有需要写入的题目。')
        return 0

    backup_path = backup_database()
    check = sqlite3.connect(backup_path)
    try:
        ok = check.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        check.close()
    if ok != 'ok':
        print(f'备份完整性检查失败: {ok}')
        return 2
    print(f'已备份: {backup_path}')

    db = SessionLocal()
    try:
        for index, (qid, point_id, sc_id, _reason) in enumerate(pending, 1):
            q = db.query(QuestionBank).filter(QuestionBank.question_id == qid).first()
            if not q:
                continue
            q.point_id = point_id
            if sc_id:
                q.sub_category_id = sc_id
            if index % 500 == 0:
                db.commit()
                print(f'  已写 {index}/{len(pending)}')
        db.commit()
    finally:
        db.close()
    print(f'完成：{len(pending)} 题已回填。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
