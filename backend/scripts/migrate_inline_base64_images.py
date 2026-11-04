# -*- coding: utf-8 -*-
"""存量 base64 图片迁移：把解析正文里的 data:image 落盘并改写为 /static URL。

背景
----
旧版 _extract_and_save_images 只把 base64 解码落盘，却没有把正文里的 src 替换掉，
导致同一张图既存在磁盘、又整段留在 SQLite。单题 answer_analysis 可达 20 万字符，
教师端列表接口每页 20 题原样返回后达到 579 KB，是界面卡顿的主要来源。

本脚本对存量行重新调用导入链路的同一函数（已改为落盘后回写 src），
默认 dry-run；--apply 前用 sqlite3.backup() 全量备份（AGENTS.md R10）。

用法
----
    cd backend
    python scripts/migrate_inline_base64_images.py
    python scripts/migrate_inline_base64_images.py --apply
"""
import argparse
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
from app.services.question_ingest.images import _extract_and_save_images  # noqa: E402

DATA_URI_RE = re.compile(r'data:image/[a-zA-Z0-9.+-]+;base64,', re.I)


def backup_database() -> str:
    db_path = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
    backup_dir = os.path.join(BACKEND_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    target = os.path.join(
        backup_dir, f'question_bank_pre_base64_migration_{datetime.now():%Y%m%d_%H%M%S}.db'
    )
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def field_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def scan(db):
    rows = db.query(QuestionBank).all()
    hit = []
    for q in rows:
        scope = ' '.join([
            field_text(q.question_content),
            field_text(q.options),
            field_text(q.answer),
            field_text(q.answer_analysis),
        ])
        count = len(DATA_URI_RE.findall(scope))
        if count:
            hit.append((q, count, len(scope)))
    return hit


def main() -> int:
    parser = argparse.ArgumentParser(description='迁移题目正文中的内联 base64 图片')
    parser.add_argument('--apply', action='store_true', help='实际写入（默认只预览）')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        hits = scan(db)
        total_chars = sum(size for _q, _c, size in hits)
        total_images = sum(count for _q, count, _s in hits)
        print(f'命中 {len(hits)} 道题，内联图片 {total_images} 张，正文合计 {total_chars:,} 字符')
        for q, count, size in hits[:40]:
            print(f'  #{q.question_id} 图片={count} 正文字符={size:,}')
        if not args.apply:
            print('DRY-RUN：未写库。确认后加 --apply。')
            return 0
        if not hits:
            print('无需迁移。')
            return 0

        backup = backup_database()
        print(f'已备份: {backup}')

        migrated = 0
        saved_chars = 0
        for q, _count, before in hits:
            scope = ' '.join([
                field_text(q.question_content),
                field_text(q.options),
                field_text(q.answer),
                field_text(q.answer_analysis),
            ])
            try:
                _extract_and_save_images(scope, q.question_id, question_obj=q)
            except Exception as exc:  # noqa: BLE001 — 单题失败不应中断整批
                print(f'  ! #{q.question_id} 迁移失败: {exc}')
                continue
            after = sum(len(field_text(v)) for v in (
                q.question_content, q.options, q.answer, q.answer_analysis))
            saved_chars += max(0, before - after)
            migrated += 1
        db.commit()
        print(f'完成：迁移 {migrated} 道题，正文净减少 {saved_chars:,} 字符')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
