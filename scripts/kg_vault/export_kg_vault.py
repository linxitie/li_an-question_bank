#!/usr/bin/env python3
"""知识图谱 → Obsidian 自生长知识库（CLI 薄壳，2026-11-18）。

核心逻辑在 backend/app/services/kg_vault_export.py（后端注册/定时任务复用同一份实现）；
这里只做命令行入口，方便手动刷新与校验。

用法：
    python scripts/kg_vault/export_kg_vault.py                 # 全部学生
    python scripts/kg_vault/export_kg_vault.py --user 202516001  # 单个学生（学号/用户名/user_id）
    python scripts/kg_vault/export_kg_vault.py --check          # 只统计，不写文件
    python scripts/kg_vault/export_kg_vault.py --out D:/某个目录
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.services import kg_vault_export  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="知识图谱 → Obsidian 自生长知识库")
    parser.add_argument("--out", default=None, help="输出目录（默认项目内 docs/obsidian/知识图谱自生长）")
    parser.add_argument("--user", default=None, help="学号/用户名/user_id，缺省=全部学生")
    parser.add_argument("--check", action="store_true", help="只统计，不写文件")
    args = parser.parse_args()

    if args.check:
        conn = kg_vault_export.open_db()
        users = kg_vault_export.load_students(conn, args.user)
        rows = [
            {
                "学号": u["user_no"] or u["username"],
                "目录": kg_vault_export.user_dir_name(u),
                "节点": len(kg_vault_export.load_nodes(conn, u["user_id"])),
            }
            for u in users
        ]
        conn.close()
        print(json.dumps({"users": len(rows), "detail": rows}, ensure_ascii=False, indent=2))
        return 0

    result = kg_vault_export.export_vault(
        out=Path(args.out) if args.out else None, only=args.user
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
