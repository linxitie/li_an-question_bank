# -*- coding: utf-8 -*-
"""把历史申论题的「题干 + 要求」拆开（一次性）。

默认 dry-run；--apply 前用 sqlite3.backup() 备份（AGENTS.md R10）。
只处理 requirements 为空且切分结果非空的题，不改已有要求。
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import QuestionBank  # noqa: E402
from app.services.text_parser import _split_essay_requirements  # noqa: E402

DB_PATH = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
BACKUP_DIR = os.path.join(BACKEND_DIR, 'data', 'backups')


def backup_database() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, f'question_bank_pre_essay_req_{datetime.now():%Y%m%d_%H%M%S}.db')
    source, dest = sqlite3.connect(DB_PATH), sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description='拆分申论题干与要求')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()

    db = SessionLocal()
    pending, skipped = [], 0
    try:
        rows = db.query(QuestionBank).filter(QuestionBank.subject_id == 2).all()
        for row in rows:
            if (row.requirements or '').strip():
                skipped += 1
                continue
            stem, reqs = _split_essay_requirements(row.question_content or '')
            if not reqs or stem == (row.question_content or '').strip():
                skipped += 1
                continue
            pending.append((row.question_id, stem, reqs))
    finally:
        db.close()

    print(f'申论题: {len(rows)}；可拆分: {len(pending)}；跳过: {skipped}')
    for qid, stem, reqs in pending[:args.limit]:
        print(f'  #{qid} stem={stem[-24:]!r} reqs={reqs}')
    if not args.apply:
        print('DRY-RUN：未写库。')
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
        for qid, stem, reqs in pending:
            db.query(QuestionBank).filter(QuestionBank.question_id == qid).update(
                {QuestionBank.question_content: stem, QuestionBank.requirements: '\n'.join(reqs)},
                synchronize_session=False,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f'已修复 {len(pending)} 题。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
