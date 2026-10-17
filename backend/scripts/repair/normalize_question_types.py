"""
存量题目类型归一化迁移
====================
将 question_type 表和 question_detail_category 表中的旧题型
归一化为4种标准类型：单选题、多选题、论述题、写作题。

影响范围：
1. question_type 表: 合并重复类型，重映射 type_id
2. question_bank 表: 更新 type_id → 标准类型 ID
3. question_detail_category 表: 更新 question_type_detail

用法:
  python scripts/normalize_question_types.py --dry-run    # 预览模式
  python scripts/normalize_question_types.py              # 实际执行
"""
import sys
import os
import logging
import argparse
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..','..',  '..'))

from app.core.database import SessionLocal
from app.models.models import QuestionBank, QuestionType, QuestionDetailCategory, QuestionEditLog
from app.services.text_parser import TYPE_NORMALIZE_MAP, normalize_type_name, VALID_QUESTION_TYPES

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def normalize_question_types(dry_run: bool = False):
    """
    归一化题目类型。

    策略：
    1. 对每个 subject_id，找到"单选题/多选题/论述题/写作题"的标准 type_id
    2. 将旧类型映射到对应的标准类型
    3. 更新 question_bank.type_id
    4. 更新 question_detail_category.question_type_detail
    5. 清理 question_type 表中的冗余记录
    """
    db = SessionLocal()
    try:
        # === 第1步：扫描现有类型 ===
        all_types = db.query(QuestionType).all()
        logger.info(f"question_type 表共 {len(all_types)} 条记录")

        # 按 subject_id 分组
        types_by_subject = defaultdict(list)
        for t in all_types:
            types_by_subject[t.subject_id or 0].append(t)

        # 构建映射：old_type_id → standard_type_id
        type_id_remap = {}  # {old_id: standard_id}
        stats = defaultdict(lambda: {'from': [], 'to': ''})

        for subject_id, types in types_by_subject.items():
            # 找出该科目下的4种标准类型ID
            standard_ids = {}
            for t in types:
                normalized = normalize_type_name(t.type_name)
                if normalized in VALID_QUESTION_TYPES:
                    if normalized not in standard_ids:
                        standard_ids[normalized] = t.type_id
                        logger.debug(f"  subject={subject_id} 标准类型 {normalized}: type_id={t.type_id}")

            # 映射旧类型 → 标准类型
            for t in types:
                normalized = normalize_type_name(t.type_name)
                if normalized in standard_ids and t.type_id != standard_ids[normalized]:
                    type_id_remap[t.type_id] = standard_ids[normalized]
                    stats[t.type_id]['from'].append(t.type_name)
                    stats[t.type_id]['to'] = normalized

        logger.info(f"需重映射的 type_id 数量: {len(type_id_remap)}")

        if not type_id_remap:
            logger.info("所有类型已标准化，无需迁移")
            return

        # === 第2步：更新 question_bank 表 ===
        total_bank_updated = 0
        for old_id, new_id in type_id_remap.items():
            count = db.query(QuestionBank).filter(
                QuestionBank.type_id == old_id
            ).count()
            if count > 0:
                logger.info(
                    f"  type_id {old_id}({stats[old_id]['from']}) → "
                    f"{new_id}({stats[old_id]['to']}): {count} 条题目"
                )
                if not dry_run:
                    db.query(QuestionBank).filter(
                        QuestionBank.type_id == old_id
                    ).update(
                        {QuestionBank.type_id: new_id, QuestionBank.update_time: datetime.now()},
                        synchronize_session=False
                    )
                total_bank_updated += count

        logger.info(f"question_bank 表共需更新 {total_bank_updated} 条题目")

        # === 第3步：更新 question_detail_category 表 ===
        total_detail_updated = 0
        for old_name, new_name in TYPE_NORMALIZE_MAP.items():
            if old_name == new_name:
                continue
            count = db.query(QuestionDetailCategory).filter(
                QuestionDetailCategory.question_type_detail == old_name
            ).count()
            if count > 0:
                logger.info(f"  question_type_detail '{old_name}' → '{new_name}': {count} 条")
                if not dry_run:
                    db.query(QuestionDetailCategory).filter(
                        QuestionDetailCategory.question_type_detail == old_name
                    ).update(
                        {QuestionDetailCategory.question_type_detail: new_name},
                        synchronize_session=False
                    )
                total_detail_updated += count

        logger.info(f"question_detail_category 表共需更新 {total_detail_updated} 条")

        # === 第4步：清理冗余 question_type 记录 ===
        redundant_ids = list(type_id_remap.keys())
        if redundant_ids:
            count = db.query(QuestionType).filter(
                QuestionType.type_id.in_(redundant_ids)
            ).count()
            logger.info(f"可清理的冗余 question_type 记录: {count} 条")
            if not dry_run and count > 0:
                db.query(QuestionType).filter(
                    QuestionType.type_id.in_(redundant_ids)
                ).delete(synchronize_session=False)

        if dry_run:
            logger.info("=== DRY-RUN 完成，以上为预览信息，未实际修改 ===")
            db.rollback()
        else:
            db.commit()
            logger.info("=== 迁移已提交 ===")

        # 汇总
        logger.info(f"汇总: 重映射 type_id {len(type_id_remap)} 个, "
                    f"更新 question_bank {total_bank_updated} 条, "
                    f"更新 question_detail_category {total_detail_updated} 条")

    except Exception as e:
        logger.error(f"迁移出错: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='归一化存量题目类型')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际修改')
    args = parser.parse_args()

    normalize_question_types(dry_run=args.dry_run)
