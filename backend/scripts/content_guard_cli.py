#!/usr/bin/env python
"""敏感词自生长知识库运维 CLI（不依赖 HTTP 服务）。

用法（在 backend 目录执行）：
  python scripts/content_guard_cli.py seed
  python scripts/content_guard_cli.py stats
  python scripts/content_guard_cli.py detect "待测文本"
  python scripts/content_guard_cli.py redteam --limit 50
  python scripts/content_guard_cli.py reconcile
  python scripts/content_guard_cli.py verify
  python scripts/content_guard_cli.py export --vault D:/vault --dry-run
  python scripts/content_guard_cli.py import-reviews --vault D:/vault
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.services.content_guard import (  # noqa: E402
    audit,
    obsidian,
    reconcile,
    redteam,
    seed_defaults,
    stats,
)


def _print(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description="敏感词知识库运维 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="幂等建表并补种目录（等价于应用启动迁移）")
    sub.add_parser("seed", help="幂等补种政策/词条/变体")
    sub.add_parser("stats", help="打印看板统计")
    sub.add_parser("verify", help="校验审计哈希链")

    detect = sub.add_parser("detect", help="检测文本（不落判定）")
    detect.add_argument("text")

    team = sub.add_parser("redteam", help="运行红队规避测试")
    team.add_argument("--limit", type=int, default=50)
    team.add_argument("--no-proposals", action="store_true")

    sub.add_parser("reconcile", help="跨层一致性对账")

    export = sub.add_parser("export", help="导出 Obsidian 投影")
    export.add_argument("--vault", default=None)
    export.add_argument("--dry-run", action="store_true")

    impt = sub.add_parser("import-reviews", help="导入 Obsidian 人工审阅结果")
    impt.add_argument("--vault", default=None)
    impt.add_argument("--reviewer-id", type=int, default=None)
    impt.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.command == "migrate":
            from app.core.content_guard_schema import ensure_content_guard_schema
            from app.core.database import engine

            _print(ensure_content_guard_schema(engine))
        elif args.command == "seed":
            report = seed_defaults(db)
            db.commit()
            _print(report)
        elif args.command == "stats":
            _print({"overview": stats.overview(db), "top": stats.top_terms(db, 10)})
        elif args.command == "verify":
            _print(audit.verify_chain(db))
        elif args.command == "detect":
            from app.services.content_guard import check_text

            result = check_text(db, args.text, scene="cli")
            result.pop("_policies", None)
            result.pop("index", None)
            result.pop("compact", None)
            _print(result)
        elif args.command == "redteam":
            report = redteam.run(
                db, limit=args.limit, create_proposals=not args.no_proposals
            )
            db.commit()
            _print(report)
        elif args.command == "reconcile":
            report = reconcile.run(db)
            db.commit()
            _print(report)
        elif args.command == "export":
            _print(
                obsidian.export_all(
                    db,
                    vault=Path(args.vault) if args.vault else None,
                    dry_run=args.dry_run,
                )
            )
        elif args.command == "import-reviews":
            _print(
                obsidian.import_reviews(
                    db,
                    vault=Path(args.vault) if args.vault else None,
                    dry_run=args.dry_run,
                    reviewer_id=args.reviewer_id,
                )
            )
    except Exception as exc:  # noqa: BLE001 —— CLI 需要可读的错误而不是 traceback
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
