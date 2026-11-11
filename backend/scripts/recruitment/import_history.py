#!/usr/bin/env python3
"""导入历年考情 Excel（省份、单位、岗位、年份、进面分数、报录比）。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import JobHistoryStat


def _value(row: dict, *names: str):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--source", default="历年考情 Excel")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    wb = load_workbook(args.file, data_only=True)
    ws = wb.active
    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in ws[1]]
    rows = []
    for values in ws.iter_rows(min_row=2, values_only=True):
        row = dict(zip(headers, values))
        year = _value(row, "年份", "考试年份", "year")
        if not year:
            continue
        try:
            year = int(str(year)[:4])
        except ValueError:
            continue
        raw_ratio = _value(row, "报录比", "竞争比")
        rows.append(
            JobHistoryStat(
                province=str(_value(row, "省份", "地区", "province") or ""),
                employer=str(_value(row, "单位", "招录单位", "employer") or ""),
                post_type=str(_value(row, "岗位", "岗位类型", "post_type") or ""),
                year=year,
                min_score=_value(row, "进面分数线", "最低进面分", "min_score"),
                avg_score=_value(row, "平均分", "avg_score"),
                applicants=_value(row, "报名人数", "applicants"),
                plan_count=_value(row, "招录人数", "plan_count"),
                ratio=str(raw_ratio) if raw_ratio is not None else None,
                source_name=args.source,
                confidence=1.0,
            )
        )
    db: Session = SessionLocal()
    try:
        if args.apply:
            db.add_all(rows)
            db.commit()
        print(
            json.dumps(
                {
                    "file": args.file,
                    "rows": len(rows),
                    "apply": args.apply,
                    "sample": [
                        {
                            "province": r.province,
                            "post_type": r.post_type,
                            "year": r.year,
                            "min_score": r.min_score,
                            "ratio": r.ratio,
                        }
                        for r in rows[:3]
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
