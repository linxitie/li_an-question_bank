#!/usr/bin/env python3
"""
fix_utb_in_db.py — 批量清洗数据库中已有的 UTB ID 残留
运行方式：
  cd backend && python fix_utb_in_db.py [--dry-run]

功能：
  1. 扫描 question_bank 表所有记录
  2. 清洗 question_content、options、answer_analysis 字段中的 UTB ID
  3. 同步清洗 answer 字段中的 UTB 残留
  4. 输出统计报告
"""
import re
import sys
import os

# 设置 backend 目录为工作路径，确保 app 模块可被导入
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.core.database import SessionLocal
from sqlalchemy import text

# UTB ID 模式（与 text_parser.py 保持一致）
UTB_PATTERN = re.compile(r'UTB[a-f0-9]{8,}[-－]?\s*选项?[A-H]?[-－]?\d*', re.IGNORECASE)
UTB_OPTION_PATTERN = re.compile(r'UTB[a-f0-9]{8,}[-－]\s*选项[A-D]\s*[\d\-]*', re.IGNORECASE)
UTB_LINE_PATTERN = re.compile(r'^\s*UTB[a-f0-9]{8,}\s*$', re.IGNORECASE)


def clean_field(value: str) -> str:
    """清洗单个字段中的 UTB ID"""
    if not value:
        return value
    cleaned = UTB_OPTION_PATTERN.sub('', value)  # 先清理选项格式
    cleaned = UTB_PATTERN.sub('', cleaned)        # 再清理所有 UTB
    cleaned = re.sub(r'\s+', ' ', cleaned)        # 合并空白
    cleaned = cleaned.strip()
    return cleaned


def main():
    dry_run = '--dry-run' in sys.argv

    db = SessionLocal()
    try:
        # 统计
        total = 0
        updated = 0
        fields_changed = {
            'question_content': 0,
            'options': 0,
            'answer_analysis': 0,
            'answer': 0,
        }

        # 分页扫描（每次1000条）
        offset = 0
        batch_size = 1000
        while True:
            rows = db.execute(
                text(f"SELECT question_id, question_content, options, answer, answer_analysis "
                     f"FROM question_bank ORDER BY question_id LIMIT {batch_size} OFFSET {offset}")
            ).fetchall()

            if not rows:
                break

            for row in rows:
                qid = row[0]
                total += 1
                changed = False

                # 清洗 question_content
                raw_content = row[1] or ''
                clean_content = clean_field(raw_content)
                if clean_content != raw_content:
                    db.execute(
                        text("UPDATE question_bank SET question_content = :val WHERE question_id = :qid"),
                        {'val': clean_content, 'qid': qid}
                    )
                    fields_changed['question_content'] += 1
                    changed = True

                # 清洗 options
                raw_options = row[2] or ''
                clean_options = clean_field(raw_options)
                if clean_options != raw_options:
                    db.execute(
                        text("UPDATE question_bank SET options = :val WHERE question_id = :qid"),
                        {'val': clean_options, 'qid': qid}
                    )
                    fields_changed['options'] += 1
                    changed = True

                # 清洗 answer
                raw_answer = row[3] or ''
                clean_answer = UTB_PATTERN.sub('', raw_answer).strip()
                if clean_answer != raw_answer:
                    db.execute(
                        text("UPDATE question_bank SET answer = :val WHERE question_id = :qid"),
                        {'val': clean_answer, 'qid': qid}
                    )
                    fields_changed['answer'] += 1
                    changed = True

                # 清洗 answer_analysis
                raw_analysis = row[4] or ''
                clean_analysis = clean_field(raw_analysis)
                if clean_analysis != raw_analysis:
                    db.execute(
                        text("UPDATE question_bank SET answer_analysis = :val WHERE question_id = :qid"),
                        {'val': clean_analysis, 'qid': qid}
                    )
                    fields_changed['answer_analysis'] += 1
                    changed = True

                if changed:
                    updated += 1

            offset += batch_size
            print(f"  已扫描 {total} 条...")

        if not dry_run:
            db.commit()

        # 输出报告
        print(f"\n{'[DRY RUN] ' if dry_run else ''}UTB 清洗报告:")
        print(f"  扫描题目总数: {total}")
        print(f"  更新题目数量: {updated}")
        for field, count in fields_changed.items():
            print(f"  {field} 字段修改: {count}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
