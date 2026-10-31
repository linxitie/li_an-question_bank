# -*- coding: utf-8 -*-
"""P3-6：批量扫描题目/题组内嵌图片并原位 OCR。

默认 dry-run，只打印候选；确认后加 --apply 才写库。
只替换「识别出文字且不是大图/图表」的图片，几何图、统计图、资料图默认保留原图。

用法：
  python scripts/ocr_question_images.py --limit 20
  python scripts/ocr_question_images.py --subject 行测 --limit 20 --apply
  python scripts/ocr_question_images.py --question-id 432 --apply
  python scripts/ocr_question_images.py --group-id 31 --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import QuestionBank, QuestionGroup, QuestionSubject  # noqa: E402
from app.services.ocr_pipeline import (  # noqa: E402
    apply_group_decisions,
    apply_question_decisions,
    group_candidates,
    question_candidates,
)


def _auto_select(candidates, include_figures: bool) -> list[dict]:
    out = []
    for item in candidates:
        if item.error or not item.text.strip():
            continue
        if item.suggest_keep_image and not include_figures:
            continue
        out.append({
            "location": item.location,
            "index": item.index,
            "text": item.text,
            "replace": True,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="题目内嵌图片批量 OCR（默认 dry-run）")
    parser.add_argument("--apply", action="store_true", help="写库；缺省只预览")
    parser.add_argument("--limit", type=int, default=20, help="最多扫描多少道题")
    parser.add_argument("--subject", default="", help="按科目名过滤：行测/申论/公专")
    parser.add_argument("--question-id", type=int, default=0)
    parser.add_argument("--group-id", type=int, default=0)
    parser.add_argument("--include-figures", action="store_true",
                        help="连大图/图表也替换（不推荐，容易丢失图形信息）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.group_id:
            groups = db.query(QuestionGroup).filter(
                QuestionGroup.id == args.group_id).all()
            for group in groups:
                candidates = group_candidates(db, group, run_ocr=True)
                decisions = _auto_select(candidates, args.include_figures)
                print(json.dumps({
                    "group_id": group.id,
                    "images": len(candidates),
                    "selected": len(decisions),
                    "items": [item.as_dict() for item in candidates],
                }, ensure_ascii=False, indent=2))
                if args.apply and decisions:
                    report = apply_group_decisions(db, group, decisions)
                    print(f"[applied] group={group.id} {report.as_dict()}")
            return 0

        query = db.query(QuestionBank)
        if args.question_id:
            query = query.filter(QuestionBank.question_id == args.question_id)
        elif args.subject:
            subject = db.query(QuestionSubject).filter(
                QuestionSubject.subject_name == args.subject).first()
            if not subject:
                print(f"科目不存在: {args.subject}")
                return 2
            query = query.filter(QuestionBank.subject_id == subject.subject_id)
        query = query.order_by(QuestionBank.question_id.asc()).limit(max(1, args.limit))

        total_images = 0
        total_selected = 0
        for question in query:
            candidates = question_candidates(db, question, run_ocr=True)
            if not candidates:
                continue
            decisions = _auto_select(candidates, args.include_figures)
            total_images += len(candidates)
            total_selected += len(decisions)
            print(json.dumps({
                "question_id": question.question_id,
                "images": len(candidates),
                "selected": len(decisions),
                "items": [item.as_dict() for item in candidates],
            }, ensure_ascii=False, indent=2))
            if args.apply and decisions:
                report = apply_question_decisions(db, question, decisions)
                print(f"[applied] question={question.question_id} {report.as_dict()}")

        print(json.dumps({
            "apply": args.apply,
            "images": total_images,
            "selected": total_selected,
        }, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
