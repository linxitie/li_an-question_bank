"""
修复历史题目类型错误
====================
针对有选项但被误标为"论述题"/"简答题"的题目重新检测类型。

典型场景：题目含（　　）被误判为填空题，启动时迁移为论述题，
但实际有 ABCD 选项，应为单选题/多选题。

用法: python scripts/fix_question_types.py [--dry-run]
"""
import sys
import os
import re
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..','..',  '..'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionDetailCategory

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def parse_options(raw):
    """解析选项，返回选项列表"""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []
    opts = []
    for item in raw:
        if isinstance(item, dict):
            v = item.get('value') or item.get('text') or ''
            if v:
                opts.append(str(v))
        elif isinstance(item, str):
            opts.append(item)
    return opts


def detect_type(q):
    """根据选项数量、答案和内容重新检测题型（与 text_parser._detect_question_type 逻辑一致）"""
    options = parse_options(q.options)
    opt_count = len(options)
    content = q.question_content or ''
    content_lower = content.lower()

    # 多选题判断：内容关键词 OR 答案含多个字母
    multi_keywords = ['多选', '不定项', '至少', '两项', '哪些', '正确的有', '错误的有']
    is_multi = any(kw in content for kw in multi_keywords)

    # 答案含多个字母（如 AB、ABC、ABCD）→ 多选题
    answer = str(q.answer or '').strip().upper()
    answer_letters = re.sub(r'[^A-D]', '', answer)
    if len(answer_letters) >= 2:
        is_multi = True

    # 有选项 → 单选/多选
    if opt_count >= 3:
        return '多选题' if is_multi else '单选题'
    if opt_count == 2:
        return '单选题'

    # 无选项 → 按内容判断
    if any(kw in content for kw in ['论述题', '论述', '论证题']):
        return '论述题'
    if any(kw in content for kw in ['案例', '案例分析']):
        return '案例分析题'
    if any(kw in content for kw in ['写作', '作文', '应用文']):
        return '写作题'
    if any(kw in content for kw in ['简答', '简述']):
        return '简答题'
    return '单选题'


def fix(dry_run=False):
    db = SessionLocal()
    try:
        # 查找所有活跃题目
        questions = db.query(QuestionBank).filter(
            QuestionBank.status == 1
        ).all()

        total = len(questions)
        logger.info(f"扫描 {total} 道题目...")

        fixed_count = 0
        unchanged_count = 0
        type_changes = {}

        for q in questions:
            # 查找题型的 detail 记录
            detail = db.query(QuestionDetailCategory).filter(
                QuestionDetailCategory.question_id == q.question_id
            ).first()

            old_type = detail.question_type_detail if detail else ''
            new_type = detect_type(q)

            # 只修复有选项但被标为主观题，或单选应为多选的情况
            options = parse_options(q.options)
            has_options = len(options) >= 2

            # 答案含多个字母 → 应为多选题
            answer = str(q.answer or '').strip().upper()
            answer_letters = re.sub(r'[^A-D]', '', answer)
            is_multi_answer = len(answer_letters) >= 2

            needs_fix = False
            if has_options and old_type in ('论述题', '简答题', '案例分析题', '写作题', '填空题', '判断题'):
                # 有选项但被标为主观题 → 重新检测
                needs_fix = True
            elif has_options and is_multi_answer and old_type == '单选题':
                # 单选题但答案含多字母 → 应为多选题
                needs_fix = True
            elif not old_type:
                # 缺失题型 → 补充
                needs_fix = True

            if not needs_fix:
                unchanged_count += 1
                continue

            if new_type != old_type:
                key = f"{old_type} -> {new_type}"
                type_changes[key] = type_changes.get(key, 0) + 1

                if not dry_run:
                    if detail:
                        detail.question_type_detail = new_type
                    else:
                        detail = QuestionDetailCategory(
                            question_id=q.question_id,
                            question_type_detail=new_type,
                            xingce_subcategory='无',
                            shenlun_subcategory='无',
                            gongzhuan_subcategory='无'
                        )
                        db.add(detail)

                fixed_count += 1

        if not dry_run:
            db.commit()
            logger.info("数据库写入完成")
        else:
            logger.info("[DRY-RUN] 未写入数据库")

        logger.info(f"总题目: {total}")
        logger.info(f"修复: {fixed_count}")
        logger.info(f"未变: {unchanged_count}")

        if type_changes:
            logger.info("题型变更明细:")
            for k, v in sorted(type_changes.items()):
                logger.info(f"  {k}: {v}题")

    except Exception as e:
        db.rollback()
        logger.error(f"修复失败: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    fix(dry_run)
