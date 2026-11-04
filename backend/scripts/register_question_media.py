# -*- coding: utf-8 -*-
"""四库知识图谱 P1：题目图片资产登记 CLI。

默认 dry-run：只扫描并打印可解析率/缺失清单，不写库、不写对象存储。
--apply：先 sqlite3.backup() 全量备份，再登记 media_assets 并把可解析文件
复制进内容寻址对象存储；不移动 backend/app/static 下的原文件。

用法：
    cd backend
    python scripts/register_question_media.py
    python scripts/register_question_media.py --apply
    python scripts/register_question_media.py --limit 100 --json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.foundation.media_schema import ensure_media_schema  # noqa: E402
from app.services.question_media import (  # noqa: E402
    collect_db_refs,
    register_media_refs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="题目图片资产登记（四库 P1）")
    parser.add_argument("--db", default=str(BACKEND_DIR / "data" / "question_bank.db"),
                        help="SQLite 路径，默认 backend/data/question_bank.db")
    parser.add_argument("--apply", action="store_true", help="实际写库/写对象存储")
    parser.add_argument("--limit", type=int, default=0,
                        help="只扫描前 N 道题（调试用，0=全部）")
    parser.add_argument("--json", action="store_true", help="stdout 只输出 JSON 摘要")
    parser.add_argument("--backup-dir", default=str(BACKEND_DIR / "data" / "backups"))
    parser.add_argument("--report-dir",
                        default=str(BACKEND_DIR / "data" / "reports" / "media"))
    return parser.parse_args()


def backup_database(db_path: str, backup_dir: str) -> str:
    """WAL 模式下必须用 sqlite3.backup()，不能用 shutil.copy2。"""
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = os.path.join(backup_dir, f"question_bank_pre_media_register_{stamp}.db")
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return target


def _write_report(report: dict, report_dir: str) -> str:
    os.makedirs(report_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = os.path.join(report_dir, f"register_question_media_{stamp}.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return target


def _rate(report: dict) -> dict:
    total = report["refs_total"] or 1
    explicit = max(report["refs_total"] - report["ambiguous_refs"], 1)
    return {
        "resolvable_rate": round(report["resolved_refs"] / total, 4),
        "resolvable_rate_excluding_ambiguous": round(
            report["resolved_refs"] / explicit, 4
        ),
    }


def main() -> int:
    args = parse_args()
    engine = create_engine(f"sqlite:///{args.db}")
    raw = engine.raw_connection()
    try:
        ensure_media_schema(raw.driver_connection)
        raw.commit()
    finally:
        raw.close()

    session = sessionmaker(bind=engine)()
    try:
        refs = collect_db_refs(session, limit_questions=args.limit or None)
        if not args.apply:
            report = register_media_refs(session, refs, apply=False)
            summary = report.as_dict()
            summary.update(_rate(summary))
            summary.update({
                "mode": "dry-run",
                "db": args.db,
                "report_path": _write_report(summary, args.report_dir),
            })
            session.rollback()
        else:
            backup_path = backup_database(args.db, args.backup_dir)
            report = register_media_refs(session, refs, apply=True)
            session.commit()
            summary = report.as_dict()
            summary.update(_rate(summary))
            summary.update({
                "mode": "apply",
                "db": args.db,
                "backup_path": backup_path,
                "report_path": _write_report(summary, args.report_dir),
            })
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"模式: {summary['mode']}")
        print(f"引用: {summary['refs_total']} 条，唯一 {summary['refs_unique']} 条")
        print(f"可解析: {summary['resolved_refs']} / {summary['refs_total']} "
              f"({summary['resolvable_rate']:.1%})，"
              f"排除歧义 marker 后 "
              f"{summary['resolvable_rate_excluding_ambiguous']:.1%}")
        print(f"缺失: {summary['missing_assets']} 个资产；"
              f"歧义 marker: {summary['ambiguous_refs']} 条")
        print(f"资产: active={summary['active_assets']} "
              f"missing={summary['missing_assets']} "
              f"inserted={summary['inserted']} updated={summary['updated']} "
              f"reused={summary['reused']}")
        if summary.get("backup_path"):
            print(f"备份: {summary['backup_path']}")
        print(f"报告: {summary['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
