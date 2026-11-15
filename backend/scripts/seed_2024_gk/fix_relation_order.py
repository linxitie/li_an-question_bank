# -*- coding: utf-8 -*-
"""检查/修复某张卷的题序（`question_order = question_number`）。

D8（2026-11-15）之后，**规则只写在一处**：`app.services.paper_stats.normalize_question_orders`。
导入路径（`/api/questions/import/batch-parsed` 与「确认导入」）在写完关联后会自动调用它，
所以正常情况下这个脚本**只用来检查或兜底**，不再需要人工修。

背景：导入的题序原本是"追加模型"（`order_base = next_question_order()`），
一张卷分批补录时，后补的题会排到卷尾 —— 2024 国考卷 #4 实测 100 条里 60 条错位。

用法：
  python backend/scripts/seed_2024_gk/fix_relation_order.py --paper 4          # 只报告
  python backend/scripts/seed_2024_gk/fix_relation_order.py --paper 4 --apply   # 真改

安全边界（与 D8 的服务函数同口径）：
  · 只改 `paper_question_relation.question_order`，**不碰题干/答案/选项/图片**；
  · 仅在"该卷所有关联题都有纯数字题号、且互不重复"时才动手，否则一条不改。
"""
import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal                       # noqa: E402
from app.models.models import PaperQuestionRelation, QuestionBank  # noqa: E402
from app.services.paper_stats import normalize_question_orders    # noqa: E402


def snapshot(db, paper_id: int):
    """[(question_order, question_number, question_id)]，按题序排。"""
    rows = (
        db.query(PaperQuestionRelation.question_order,
                 PaperQuestionRelation.question_id,
                 QuestionBank.question_number)
        .join(QuestionBank, QuestionBank.question_id == PaperQuestionRelation.question_id)
        .filter(PaperQuestionRelation.paper_id == paper_id)
        .order_by(PaperQuestionRelation.question_order)
        .all()
    )
    return [(int(o or 0), str(n) if n is not None else None, q) for o, q, n in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = snapshot(db, args.paper)
        print(f"卷 #{args.paper} 关联 {len(rows)} 条")
        if not rows:
            print("没有关联题，什么都不用做")
            return 0

        result = normalize_question_orders(db, args.paper, apply=args.apply)
        print(f"total={result['total']} changed={result['changed']} "
              f"skipped_reason={result['skipped_reason']}")
        if result["skipped_reason"] == "empty":
            print("没有关联题，什么都不用做")
            return 0
        if result["skipped_reason"] == "non-numeric":
            print("→ 有题号缺失/非纯数字，为保证不误伤，本次一条不改")
            return 2
        if result["skipped_reason"] == "duplicate":
            print("→ 题号有重复，无法定义唯一顺序，本次一条不改")
            return 2
        if not result["changed"]:
            print("已经对齐，无需改")
            return 0
        if not args.apply:
            print(f"（dry-run）有 {result['changed']} 条错位，加 --apply 才会写库")
            return 0

        db.commit()
        after = snapshot(db, args.paper)
        mism = [(o, n) for o, n, _q in after if str(o) != str(n)]
        orders = [o for o, _n, _q in after]
        print(f"改完：order 数 {len(orders)}，去重 {len(set(orders))}，"
              f"min {min(orders)} / max {max(orders)}，不一致 {len(mism)} 条")
        return 0 if not mism else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
