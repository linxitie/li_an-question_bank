#!/usr/bin/env python3
"""R1 Scout 决策落库 + Obsidian 全量/审核看板导出。

用法（在 backend 目录）：
    python -m scripts.content_hub.apply_scout --dry-run
    python -m scripts.content_hub.apply_scout --apply
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.database import SessionLocal
from app.models.models import EssayQuote
from app.services.obsidian_export import export_all
from app.services.review_board_export import export_review_board
from app.services.scout_apply_service import apply_scout_decisions

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = BACKEND_ROOT / "content_hub_vault"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scout 决策落库并导出 Obsidian")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--high", type=float, default=85.0)
    parser.add_argument("--low", type=float, default=60.0)
    parser.add_argument("--apply", action="store_true", help="真正更新状态；默认 dry-run")
    parser.add_argument("--skip-export", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.apply:
            high = db.query(EssayQuote).filter(EssayQuote.quality_score >= args.high).count()
            low = db.query(EssayQuote).filter(EssayQuote.quality_score < args.low).count()
            print(json.dumps({"apply": False, "approved": high, "rejected": low}, ensure_ascii=False, indent=2))
            return 0

        report = apply_scout_decisions(db, high=args.high, low=args.low)

        if not args.skip_export:
            vault = Path(args.vault)
            vault.mkdir(parents=True, exist_ok=True)
            report["full_export"] = export_all(db, vault)
            report["review_board"] = export_review_board(db, vault)
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
