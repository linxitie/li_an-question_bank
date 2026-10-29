# -*- coding: utf-8 -*-
"""按“题目预览 + 答案解析预览”补齐被去重误杀的题目（一次性）。

背景
----
2025 安徽行测 q120/q125 与其他资料分析题共用题干「能够从上述资料中推出的是：」。
旧版 fuzzy_detect_duplicate 在“题干精确相同”路径直接判重，不比较选项，
两题因此在导入时被静默丢弃（题库仅 123 题，应为 125 题）。

本脚本从题目预览取题干/选项，从答案解析预览取正确答案与解析，补插入库。
默认 dry-run；--apply 前用 sqlite3.backup() 全量备份（AGENTS.md R10）。

用法
----
    cd backend
    python scripts/backfill_missing_questions.py --questions-import 1629 --answers-import 1618
    python scripts/backfill_missing_questions.py --questions-import 1629 --answers-import 1618 --apply
"""
import argparse
import glob
import gzip
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

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models.models import QuestionBank  # noqa: E402

PREVIEW_ROOT = os.path.join(BACKEND_DIR, 'data', 'import_previews')
_ANSWER_HEAD = re.compile(r'(?m)^\s*(\d{1,3})\s*[.．、]\s*正确答案\s*[：:]\s*([A-D]+)')


def load_preview(import_id: int) -> dict:
    paths = glob.glob(os.path.join(PREVIEW_ROOT, '*', f'{import_id}.json.gz'))
    if paths:
        with open(paths[0], 'rb') as handle:
            obj = json.loads(gzip.decompress(handle.read()).decode('utf-8'))
        if isinstance(obj, str):
            obj = json.loads(obj)
        return obj
    # 2021 北京等卷只在 question_import_record.preview_data 内联预览，
    # 磁盘 import_previews 已被清理；直接按库回退，避免补题脚本空转。
    con = sqlite3.connect(os.path.join(BACKEND_DIR, 'data', 'question_bank.db'))
    try:
        row = con.execute(
            'SELECT preview_data FROM question_import_record WHERE import_id=?',
            (import_id,),
        ).fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise SystemExit(f'预览不存在: {import_id}')
    obj = json.loads(row[0])
    if isinstance(obj, str):
        obj = json.loads(obj)
    return obj


def parse_answer_blocks(raw_text: str) -> dict:
    """题号 -> (答案, 解析全文)。解析从本题标题截到下一条答案标题。"""
    heads = list(_ANSWER_HEAD.finditer(raw_text or ''))
    result = {}
    for index, match in enumerate(heads):
        start = match.start()
        end = heads[index + 1].start() if index + 1 < len(heads) else len(raw_text)
        result[int(match.group(1))] = (match.group(2).strip(), raw_text[start:end].strip())
    return result


def nearest_template(db, subject_id: int, year: int, question_number: int):
    rows = db.query(QuestionBank).filter(
        QuestionBank.subject_id == subject_id,
        QuestionBank.year == year,
        QuestionBank.question_number.isnot(None),
    ).all()
    if not rows:
        return None
    return min(rows, key=lambda row: abs(int(str(row.question_number)) - question_number))


def backup_database() -> str:
    db_path = os.path.join(BACKEND_DIR, 'data', 'question_bank.db')
    backup_dir = os.path.join(BACKEND_DIR, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    target = os.path.join(
        backup_dir, f'question_bank_pre_backfill_missing_{datetime.now():%Y%m%d_%H%M%S}.db')
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description='补齐被去重误杀的题目')
    parser.add_argument('--questions-import', type=int, required=True)
    parser.add_argument('--answers-import', type=int, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    question_preview = load_preview(args.questions_import)
    answer_preview = load_preview(args.answers_import)
    tags = question_preview.get('auto_detected_tags') or {}
    year = int(tags.get('exam_year') or 0)
    if not year:
        raise SystemExit('题目预览缺少 exam_year，无法确定年份')
    answers = parse_answer_blocks(answer_preview.get('raw_text') or '')

    db = SessionLocal()
    try:
        print(f'数据库: {engine.url}')
        existing_numbers = {
            str(row.question_number).strip()
            for row in db.query(QuestionBank).filter(
                QuestionBank.subject_id == 1,
                QuestionBank.year == year,
            ).all()
        }
        pending = []
        for item in question_preview.get('items') or []:
            question_number = str(item.get('question_number') or '').strip()
            if not question_number or question_number in existing_numbers:
                continue
            answer, analysis = answers.get(int(question_number), ('', ''))
            if not answer:
                print(f'  ! q{question_number} 在答案解析预览中找不到答案，跳过')
                continue
            pending.append((item, question_number, answer, analysis))

        if not pending:
            print('没有需要补齐的题目。')
            return 0
        for item, question_number, answer, analysis in pending:
            print(f'  + q{question_number} 答案={answer} 解析={len(analysis)}字 '
                  f'题干={item.get("question_content", "")[:40]}')
        print(f'合计待补 {len(pending)} 题。')
        if not args.apply:
            print('DRY-RUN：未写库。确认无误后加 --apply。')
            return 0

        backup_path = backup_database()
        print(f'已备份: {backup_path}')
        insert_index = 1
        for item, question_number, answer, analysis in pending:
            template = nearest_template(db, 1, year, int(question_number))
            if template is None:
                print(f'  ! q{question_number} 无同卷模板，跳过')
                continue
            row = QuestionBank(
                subject_id=1,
                type_id=template.type_id,
                question_content=(item.get('question_content') or '').strip(),
                options=item.get('options') or [],
                answer=answer,
                answer_analysis=analysis,
                difficulty=int(item.get('difficulty') or template.difficulty or 3),
                score=float(item.get('score') or template.score or 1),
                year=year,
                source=template.source,
                creator_id=template.creator_id,
                audit_status=1,
                status=1,
                group_id=0,
                parent_id=0,
                question_level=1,
                sort_order=insert_index,
                question_number=str(question_number),
                need_review=0,
                xingce_subcategory=template.xingce_subcategory,
                create_time=datetime.now(),
                update_time=datetime.now(),
            )
            db.add(row)
            db.flush()
            insert_index += 1
            print(f'  已插入 question_id={row.question_id} q{question_number}')
        db.commit()
        print('完成。')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
