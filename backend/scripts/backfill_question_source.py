# -*- coding: utf-8 -*-
"""把题库 source 回填为导入文档标题（一次性）。

背景
----
旧导入把 source 写成「未标注」「考试」「联考」这类泛化值，管理端题目列表
无法回答“这道题来自哪份卷子”。本脚本按以下优先级回填：

A. 题目在 paper_question_relation 中，且试卷标题完整 -> 用试卷标题
B. 题干预览 items 能唯一精确匹配 -> 用 question_import_record.original_filename
C. 都匹配不到 -> 跳过并列入报告，不猜

安全约束
--------
1. 默认 dry-run，只打印统计与样例，不改库。
2. --apply 前用 sqlite3.backup() 备份（AGENTS.md R10）。
3. 只覆盖空值/泛化值；--overwrite 才覆盖已有具体标题。
4. 标题统一经 _clean_source_title 清洗，最长 200 字。

用法
----
    cd backend
    python scripts/backfill_question_source.py
    python scripts/backfill_question_source.py --apply
"""
import argparse
import glob
import gzip
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, Optional, Tuple

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models.models import QuestionBank  # noqa: E402
from app.services.question_ingest.tags import _clean_source_title  # noqa: E402

DB_PATH = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
PREVIEW_ROOT = os.path.join(BACKEND_DIR, 'data', 'import_previews')
BACKUP_DIR = os.path.join(BACKEND_DIR, 'data', 'backups')
_TAG_RE = re.compile(r'<[^>]+>')
_IMG_RE = re.compile(r'\[IMAGE:[^\]]+\]', re.I)
_WS_RE = re.compile(r'\s+')
_GENERIC = {'', '未标注', '考试', '模拟', '真题', '联考', '练习题', '测试', '题库', '未知'}


def norm_text(value: str) -> str:
    """题干归一化：剥离图片占位、HTML 与空白，供精确匹配。"""
    value = _IMG_RE.sub('', value or '')
    value = _TAG_RE.sub('', value)
    return _WS_RE.sub('', value)


def is_generic_source(value: Optional[str]) -> bool:
    title = (value or '').strip()
    return title in _GENERIC or len(title) < 6


def is_truncated_title(value: Optional[str]) -> bool:
    """试卷标题常见两种截断：省略号结尾、括号未闭合。"""
    title = (value or '').strip()
    if not title:
        return True
    if title.endswith(('…', '...')):
        return True
    pairs = {'（': '）', '(': ')', '《': '》', '“': '”'}
    return any(title.count(left) > title.count(right) for left, right in pairs.items())


def load_preview(import_id: int, db) -> Optional[dict]:
    paths = glob.glob(os.path.join(PREVIEW_ROOT, '*', f'{import_id}.json.gz'))
    if paths:
        try:
            with open(paths[0], 'rb') as handle:
                obj = json.loads(gzip.decompress(handle.read()).decode('utf-8'))
            if isinstance(obj, str):
                obj = json.loads(obj)
            return obj
        except (OSError, ValueError) as exc:
            print(f'[{import_id}] 预览文件解析失败: {exc}')
            return None
    row = db.execute(
        text('SELECT preview_data FROM question_import_record WHERE import_id=:import_id'),
        {'import_id': import_id},
    ).first()
    if row and row[0]:
        try:
            obj = json.loads(row[0])
            return json.loads(obj) if isinstance(obj, str) else obj
        except (TypeError, ValueError):
            return None
    return None


def build_preview_index(db) -> Dict[str, str]:
    """归一化题干 -> 文档标题；同一题干命中多份文档时视为歧义并丢弃。"""
    records = db.execute(text(
        'SELECT import_id, original_filename FROM question_import_record '
        'WHERE original_filename IS NOT NULL AND original_filename != ""'
    )).mappings().all()
    candidates: Dict[str, set] = defaultdict(set)
    for record in records:
        title = _clean_source_title(record['original_filename'])
        if not title:
            continue
        preview = load_preview(int(record['import_id']), db)
        if not preview:
            continue
        for item in preview.get('items') or []:
            stem = norm_text(item.get('question_content') or '')
            if len(stem) >= 8:
                candidates[stem].add(title)
    return {stem: next(iter(titles)) for stem, titles in candidates.items() if len(titles) == 1}


def build_paper_index(db) -> Dict[int, str]:
    rows = db.execute(text(
        "SELECT paper_id, COALESCE(original_title, paper_name) AS title FROM exam_paper "
        "WHERE composition_method = 'IMPORT'"
    )).mappings().all()
    result = {}
    for row in rows:
        title = _clean_source_title(row['title'])
        if not title or len(title) < 8 or is_truncated_title(title):
            continue
        if any(word in title for word in ('答案', '解析', '智能组卷', '模拟', '临时', '测试')):
            continue
        result[int(row['paper_id'])] = title
    return result


def build_question_paper_map(db) -> Dict[int, int]:
    rows = db.execute(text(
        'SELECT question_id, paper_id FROM paper_question_relation ORDER BY question_id, paper_id'
    )).all()
    result = {}
    for question_id, paper_id in rows:
        result.setdefault(int(question_id), int(paper_id))
    return result


def backup_database() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target = os.path.join(BACKUP_DIR, f'question_bank_pre_source_{stamp}.db')
    source = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description='回填题库来源为导入文档标题')
    parser.add_argument('--apply', action='store_true', help='实际写库（默认 dry-run）')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已有具体标题')
    parser.add_argument('--limit', type=int, default=8, help='每类打印样例数')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        preview_index = build_preview_index(db)
        paper_index = build_paper_index(db)
        question_paper = build_question_paper_map(db)

        stats = Counter()
        samples = defaultdict(list)
        pending = []
        questions = db.query(QuestionBank).all()
        for question in questions:
            current = (question.source or '').strip()
            if not args.overwrite and not is_generic_source(current):
                stats['already_specific'] += 1
                continue

            paper_title = paper_index.get(question_paper.get(int(question.question_id), -1))
            preview_title = preview_index.get(norm_text(question.question_content or ''))

            title, grade = '', 'C'
            if paper_title and preview_title:
                # 截断标题已排除；两者都完整时取更长的文档名。
                title = paper_title if len(paper_title) >= len(preview_title) else preview_title
                grade = 'A'
            elif paper_title:
                title, grade = paper_title, 'A'
            elif preview_title:
                title, grade = preview_title, 'B'

            stats[f'grade_{grade}'] += 1
            if not title:
                if len(samples['C']) < args.limit:
                    samples['C'].append((question.question_id, current, (question.question_content or '')[:40]))
                continue
            title = _clean_source_title(title)
            if not title or title == current:
                stats['unchanged'] += 1
                continue
            pending.append((question.question_id, title))
            stats['will_update'] += 1
            if len(samples[grade]) < args.limit:
                samples[grade].append((question.question_id, current, title))

    except Exception:
        db.close()
        raise
    else:
        db.close()

    print(f'题目总数: {len(questions)}')
    print(f'预览题干索引: {len(preview_index)}；可用试卷标题: {len(paper_index)}')
    for key in ('will_update', 'already_specific', 'unchanged', 'grade_A', 'grade_B', 'grade_C'):
        print(f'  {key}: {stats[key]}')
    for grade in ('A', 'B', 'C'):
        print(f'\n[{grade}] 样例:')
        for qid, before, after in samples[grade]:
            print(f'  #{qid}  {before!r} -> {after!r}')

    if not args.apply:
        print('\nDRY-RUN：未写库。确认后加 --apply。')
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
    print(f'\n已备份: {backup_path} (integrity_check=ok)')

    db = SessionLocal()
    try:
        for question_id, title in pending:
            db.query(QuestionBank).filter(QuestionBank.question_id == question_id).update(
                {QuestionBank.source: title}, synchronize_session=False
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f'已回填 {len(pending)} 题。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
