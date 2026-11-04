# -*- coding: utf-8 -*-
"""把历史「一个选项塞多张图」还原成 A–D（一次性）。

默认 dry-run；--apply 前备份。只改图片选项结构，不动正文与答案。
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import QuestionBank  # noqa: E402
from app.services.text_parser import _split_image_only_options  # noqa: E402

DB_PATH = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
BACKUP_DIR = os.path.join(BACKEND_DIR, 'data', 'backups')


def backup_database() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, f'question_bank_pre_image_opts_{datetime.now():%Y%m%d_%H%M%S}.db')
    source, dest = sqlite3.connect(DB_PATH), sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description='还原图片选项')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()

    db = SessionLocal()
    pending, missing = [], []
    try:
        rows = db.query(QuestionBank).all()
        for row in rows:
            options = row.options
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except ValueError:
                    continue
            if not isinstance(options, list) or not options:
                continue
            # 只修 [IMAGE:] 标记：<img> 选项往往已有 A/C/D 键，重建会丢标签。
            if any('<img' in str(o.get('value', '')).lower() for o in options):
                continue
            fixed = _split_image_only_options(options)
            if fixed == options:
                continue
            markers = []
            for opt in fixed:
                markers.extend(re.findall(r'\[IMAGE:([^\]\s]+)\]', str(opt.get('value', ''))))
            absent = [m for m in markers if not os.path.exists(
                os.path.join(BACKEND_DIR, 'app', 'static', 'questions', f'{m}.png'))]
            if absent:
                missing.append((row.question_id, absent))
                continue
            pending.append((row.question_id, options, fixed))
    finally:
        db.close()

    print(f'题目: {len(rows)}；可还原图片选项: {len(pending)}；因图片缺失跳过: {len(missing)}')
    for qid, before, after in pending[:args.limit]:
        print(f'  #{qid} {before} -> {after}')
    for qid, absent in missing[:args.limit]:
        print(f'  #{qid} 跳过：缺图 {absent}')
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
        for qid, _, after in pending:
            db.query(QuestionBank).filter(QuestionBank.question_id == qid).update(
                {QuestionBank.options: after}, synchronize_session=False
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
