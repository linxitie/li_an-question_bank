"""
存量题目内容清洗脚本
====================
遍历 question_bank 表的 question_content 和 answer_analysis，
应用 ContentCleaner.clean_question_content() 去除推广/营销/无关内容。

用法:
  python scripts/clean_promo_content.py --dry-run    # 预览模式（不写入）
  python scripts/clean_promo_content.py              # 实际执行
  python scripts/clean_promo_content.py --limit 100  # 仅处理前100条
"""
import sys
import os
import re
import logging
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionEditLog
from app.services.text_parser import ContentCleaner

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def clean_promo_content(dry_run: bool = False, limit: int = None):
    """
    清洗存量题目内容。

    Args:
        dry_run: True 时仅预览，不写入数据库
        limit: 限制处理条数（None = 全部）
    """
    db = SessionLocal()
    try:
        query = db.query(QuestionBank).filter(QuestionBank.status == 1)
        if limit:
            query = query.limit(limit)

        total = query.count()
        logger.info(f"共 {total} 条活跃题目待检查")

        cleaned_count = 0
        skipped_count = 0
        error_count = 0

        questions = query.all()
        for i, q in enumerate(questions):
            if (i + 1) % 100 == 0:
                logger.info(f"进度: {i + 1}/{total}")

            try:
                old_content = q.question_content or ''
                old_analysis = q.answer_analysis or ''

                new_content = ContentCleaner.clean_question_content(old_content)
                new_analysis = ContentCleaner.clean_question_content(old_analysis)

                content_changed = new_content != old_content
                analysis_changed = new_analysis != old_analysis

                if not content_changed and not analysis_changed:
                    skipped_count += 1
                    continue

                if dry_run:
                    if content_changed:
                        removed = _diff_summary(old_content, new_content)
                        logger.info(f"[DRY-RUN] Q#{q.question_id} 题干: {removed}")
                    if analysis_changed:
                        removed = _diff_summary(old_analysis, new_analysis)
                        logger.info(f"[DRY-RUN] Q#{q.question_id} 解析: {removed}")
                else:
                    # 记录编辑日志
                    if content_changed:
                        log_entry = QuestionEditLog(
                            question_id=q.question_id,
                            editor_id=q.creator_id or 1,
                            action_type='UPDATE',
                            old_data={'question_content': old_content[:500]},
                            new_data={'question_content': new_content[:500]},
                            edit_time=datetime.now(),
                            remark='存量推广内容清洗'
                        )
                        db.add(log_entry)
                        q.question_content = new_content

                    if analysis_changed:
                        q.answer_analysis = new_analysis

                    q.update_time = datetime.now()

                cleaned_count += 1

            except Exception as e:
                logger.error(f"处理 Q#{q.question_id} 出错: {e}")
                error_count += 1
                continue

        if not dry_run:
            db.commit()
            logger.info(f"已提交数据库更改")

        logger.info(f"清洗完成: 清洗 {cleaned_count} 条, 跳过 {skipped_count} 条, 错误 {error_count} 条")

    finally:
        db.close()


def _diff_summary(old_text: str, new_text: str) -> str:
    """生成差异摘要：显示被移除的内容"""
    if len(old_text) <= len(new_text):
        return "无变化"
    removed_chars = len(old_text) - len(new_text)
    # 找到被移除的文本段
    old_lines = set(old_text.split('\n'))
    new_lines = set(new_text.split('\n'))
    removed_lines = old_lines - new_lines
    if removed_lines:
        samples = list(removed_lines)[:3]
        return f"移除 {removed_chars} 字符, 示例: {' | '.join(s[:60] for s in samples)}"
    return f"移除 {removed_chars} 字符"


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='清洗存量题目中的推广/无关内容')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际修改数据库')
    parser.add_argument('--limit', type=int, default=None, help='限制处理条数')
    args = parser.parse_args()

    clean_promo_content(dry_run=args.dry_run, limit=args.limit)
