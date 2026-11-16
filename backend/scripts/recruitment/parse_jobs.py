#!/usr/bin/env python3
"""解析招考公告岗位（默认 dry-run 不写库）。"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.models.models import RecruitmentInfo
from app.services.recruitment_job_parser import parse_announcement


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default="", help="逗号分隔的 recruitment_id")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ids = [int(x) for x in args.ids.split(",") if x.strip()]
    db = SessionLocal()
    try:
        query = db.query(RecruitmentInfo).filter(RecruitmentInfo.status == 1)
        if ids:
            query = query.filter(RecruitmentInfo.recruitment_id.in_(ids))
        else:
            query = query.filter(RecruitmentInfo.parse_status.in_(["pending", "failed"]))
        records = query.order_by(RecruitmentInfo.recruitment_id.desc()).limit(args.limit).all()
        results = []
        for rec in records:
            if not args.apply:
                results.append(
                    {
                        "recruitment_id": rec.recruitment_id,
                        "title": rec.title,
                        "status": "dry_run",
                        "content_chars": len(rec.content or ""),
                    }
                )
                continue
            results.append(parse_announcement(db, rec))
    finally:
        db.close()
    print(json.dumps({"apply": args.apply, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
