"""
历史数据重分类脚本
对 question_bank 中所有题目进行三级重分类（科目→子科目→考点），
更新 question_knowledge 关联表。
"""
import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import (
    QuestionBank, QuestionDetailCategory,
    KnowledgePoint, SubCategory, QuestionKnowledge,
    QuestionSubject
)
from app.services.question_classifier import QuestionClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def reclassify_all(dry_run: bool = False):
    """
    对所有题目进行重分类。

    Args:
        dry_run: True=仅报告不写入, False=实际写入数据库
    """
    db = SessionLocal()
    classifier = QuestionClassifier()

    try:
        # 获取所有活跃题目
        questions = db.query(QuestionBank).filter(
            QuestionBank.status == 1
        ).all()

        total = len(questions)
        logger.info(f"开始重分类 {total} 道题目...")

        stats = {
            "total": total,
            "classified": 0,        # 成功分类（置信度>=0.15）
            "low_confidence": 0,    # 低置信度
            "failed": 0,            # 完全无法分类
            "subcategory_changes": 0,  # 子科目变更
            "kp_linked": 0,         # 建立考点关联
            "by_subject": {},
            "by_subcategory": {},
        }

        for idx, q in enumerate(questions):
            subject_id = q.subject_id
            content = q.question_content or ""

            # 运行分类器
            result = classifier.classify_with_db(content, subject_id, db)

            # 统计
            sid = subject_id
            if sid not in stats["by_subject"]:
                stats["by_subject"][sid] = {"total": 0, "classified": 0, "low_conf": 0, "failed": 0}
            stats["by_subject"][sid]["total"] += 1

            old_sc = None
            if subject_id == 1:
                old_sc = q.xingce_subcategory
            elif subject_id == 2:
                old_sc = q.shenlun_subcategory
            elif subject_id == 3:
                old_sc = q.gongzhuan_subcategory

            new_sc = result.sub_category_name

            if result.confidence >= 0.15 and result.sub_category_id:
                stats["classified"] += 1
                stats["by_subject"][sid]["classified"] += 1

                # 检查子科目是否变更
                if old_sc != new_sc and new_sc != "无法分类":
                    stats["subcategory_changes"] += 1

                # 统计子科目分布
                sc_key = f"{subject_id}_{result.sub_category_name}"
                if sc_key not in stats["by_subcategory"]:
                    stats["by_subcategory"][sc_key] = 0
                stats["by_subcategory"][sc_key] += 1

                if not dry_run:
                    # 更新 question_bank 子科目字段
                    if subject_id == 1:
                        q.xingce_subcategory = new_sc
                    elif subject_id == 2:
                        q.shenlun_subcategory = new_sc
                    elif subject_id == 3:
                        q.gongzhuan_subcategory = new_sc

                    # 更新 question_detail_category
                    detail = db.query(QuestionDetailCategory).filter(
                        QuestionDetailCategory.question_id == q.question_id
                    ).first()
                    if detail:
                        if subject_id == 1:
                            detail.xingce_subcategory = new_sc
                        elif subject_id == 2:
                            detail.shenlun_subcategory = new_sc
                        elif subject_id == 3:
                            detail.gongzhuan_subcategory = new_sc
                    else:
                        detail = QuestionDetailCategory(
                            question_id=q.question_id,
                            xingce_subcategory=new_sc if subject_id == 1 else "无",
                            shenlun_subcategory=new_sc if subject_id == 2 else "无",
                            gongzhuan_subcategory=new_sc if subject_id == 3 else "无",
                        )
                        db.add(detail)

                    # 创建 question_knowledge 关联
                    if result.knowledge_point_id:
                        existing = db.query(QuestionKnowledge).filter(
                            QuestionKnowledge.question_id == q.question_id,
                            QuestionKnowledge.knowledge_point_id == result.knowledge_point_id
                        ).first()
                        if not existing:
                            qk = QuestionKnowledge(
                                question_id=q.question_id,
                                knowledge_point_id=result.knowledge_point_id,
                            )
                            db.add(qk)
                            stats["kp_linked"] += 1

            elif result.confidence > 0 and result.sub_category_name != "无法分类":
                stats["low_confidence"] += 1
                stats["by_subject"][sid]["low_conf"] += 1
            else:
                stats["failed"] += 1
                stats["by_subject"][sid]["failed"] += 1

            # 每50条提交一次，打印进度
            if idx % 50 == 0 and idx > 0:
                if not dry_run:
                    db.commit()
                logger.info(f"  进度: {idx}/{total}")

        # 最终提交
        if not dry_run:
            db.commit()
            logger.info("数据库写入完成")
        else:
            logger.info("DRY RUN — 未写入数据库")

        # 打印统计报告
        _print_report(stats)

    except Exception as e:
        db.rollback()
        logger.error(f"重分类失败: {e}")
        raise
    finally:
        db.close()


def _print_report(stats: dict):
    """打印分类统计报告"""
    logger.info("=" * 60)
    logger.info("重分类统计报告")
    logger.info("=" * 60)
    logger.info(f"总题目数:        {stats['total']}")
    logger.info(f"成功分类:        {stats['classified']} ({stats['classified']*100/max(stats['total'],1):.1f}%)")
    logger.info(f"低置信度:        {stats['low_confidence']}")
    logger.info(f"完全无法分类:    {stats['failed']}")
    logger.info(f"子科目变更:      {stats['subcategory_changes']}")
    logger.info(f"建立考点关联:    {stats['kp_linked']}")
    logger.info("")

    logger.info("按科目统计:")
    subject_names = {1: "行测", 2: "申论", 3: "公专"}
    for sid, s in sorted(stats["by_subject"].items()):
        name = subject_names.get(sid, f"科目{sid}")
        logger.info(f"  {name}: 总计{s['total']}, 分类{s['classified']}, "
                    f"低置信{s['low_conf']}, 失败{s['failed']}")

    logger.info("")
    logger.info("按子科目分布:")
    for sc_key in sorted(stats["by_subcategory"].keys()):
        count = stats["by_subcategory"][sc_key]
        logger.info(f"  {sc_key}: {count}题")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="题目重分类工具")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写入")
    args = parser.parse_args()

    reclassify_all(dry_run=args.dry_run)
