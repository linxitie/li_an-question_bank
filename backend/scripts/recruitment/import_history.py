#!/usr/bin/env python3
"""导入历年考情 Excel（省份、地区、单位、岗位、年份、进面分数、报录比）。"""
from __future__ import annotations

import argparse
import json

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import JobHistoryStat


def _value(row: dict, *names: str):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _int(value):
    number = _num(value)
    return int(number) if number is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--source", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    wb = load_workbook(args.file, data_only=True, read_only=True)
    ws = wb.active
    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    mappings = []
    for values in ws.iter_rows(min_row=2, values_only=True):
        row = dict(zip(headers, values))
        year = _value(row, "年份", "考试年份", "year")
        if not year:
            continue
        try:
            year = int(str(year)[:4])
        except ValueError:
            continue
        province = str(_value(row, "省份", "地区", "province") or "").strip()
        employer = str(_value(row, "单位", "招录单位", "employer") or "").strip()
        job_name = str(_value(row, "岗位", "职位", "job_name") or "").strip()
        post_type = str(_value(row, "岗位类型", "post_type") or "").strip()
        source_name = str(_value(row, "来源名称", "source_name") or args.source or "Excel").strip()
        source_url = str(_value(row, "来源URL", "来源链接", "source_url") or "").strip()
        mappings.append(
            {
                "province": province or None,
                "employer": employer or None,
                "job_name": job_name or None,
                "post_type": post_type or None,
                "year": year,
                "min_score": _num(_value(row, "进面分数线", "最低进面分", "min_score")),
                "avg_score": _num(_value(row, "平均分", "avg_score")),
                "applicants": _int(_value(row, "报名人数", "applicants")),
                "plan_count": _int(_value(row, "招录人数", "plan_count")),
                "ratio": str(_value(row, "报录比", "竞争比") or "") or None,
                "source_name": source_name,
                "source_url": source_url or None,
                "confidence": 1.0,
            }
        )
    db: Session = SessionLocal()
    try:
        if args.apply:
            for start in range(0, len(mappings), 1000):
                db.bulk_insert_mappings(JobHistoryStat, mappings[start : start + 1000])
                db.commit()
        print(
            json.dumps(
                {
                    "file": args.file,
                    "rows": len(mappings),
                    "apply": args.apply,
                    "provinces": len({m["province"] for m in mappings if m["province"]}),
                    "years": sorted({m["year"] for m in mappings}),
                    "sample": mappings[:3],
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
