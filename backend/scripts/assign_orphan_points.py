#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「没有主考点」的可见题精确落到「其他（未细分）」收容叶子（默认 dry-run）。

背景（2026-11-14 实测）：可见题 3528 道里有 555 道 point_id 为空
（行测 239 / 公专 316，全部 sub_category_id 也为空）。它们在图库里没有节点、
在文档/向量里没有考点路径、在练习记录里写不出 scope_name——用户看到的
「考点显示其他 / 练习记录为空」有这一半的锅。

本脚本只改 question_bank.point_id 一个字段：
  R1 按 (subject_id, sub_category_id) 找到该范围下的 canonical 收容叶子；
     不存在则新建（level=3, parent_id=0, sort_order=999）；
  R2 把该范围内的孤儿题 point_id 指过去；
  R3 写审计 JSON + 先 sqlite3.backup()（R10：WAL 下不能用 shutil.copy2）。

用法：
  python scripts/assign_orphan_points.py            # dry-run
  python scripts/assign_orphan_points.py --apply
  python scripts/assign_orphan_points.py --revert   # 还原最近一次 apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BASE_DIR / "data" / "question_bank.db"
AUDIT_DIR = BASE_DIR / "data" / "audit"

FALLBACK_NAME = "其他（未细分）"
FALLBACK_NAMES = ("其他（未细分）", "其他")
SUBJECT_NAMES = {1: "行测", 2: "申论", 3: "公专"}

ORPHAN_WHERE = """
    qb.status = 1 AND qb.audit_status = 1
    AND (qb.point_id IS NULL
         OR qb.point_id NOT IN (SELECT point_id FROM knowledge_point WHERE status = 1))
"""


def _has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in con.execute(f"PRAGMA table_info({table})"))


def _fallback_point(con: sqlite3.Connection, subject_id: int,
                    sub_category_id: Optional[int]) -> Optional[int]:
    has_alias = _has_column(con, "knowledge_point", "alias_of")
    extra = " AND (alias_of IS NULL OR alias_of = '')" if has_alias else ""
    sc_clause = "sub_category_id IS NULL" if sub_category_id is None else "sub_category_id = ?"
    params: List[object] = [int(subject_id)]
    if sub_category_id is not None:
        params.append(int(sub_category_id))
    row = con.execute(
        "SELECT point_id FROM knowledge_point "
        "WHERE level = 3 AND status = 1 AND subject_id = ? AND " + sc_clause +
        " AND TRIM(point_name) IN (?, ?)" + extra +
        " ORDER BY point_id LIMIT 1",
        (*params, *FALLBACK_NAMES),
    ).fetchone()
    return int(row[0]) if row else None


def load_plan(con: sqlite3.Connection) -> Dict[str, List[dict]]:
    groups: Dict[tuple, List[int]] = {}
    for question_id, subject_id, sc_id in con.execute(
        "SELECT qb.question_id, qb.subject_id, qb.sub_category_id "
        "FROM question_bank qb WHERE " + ORPHAN_WHERE + " ORDER BY qb.question_id"
    ):
        key = (int(subject_id), None if sc_id is None else int(sc_id))
        groups.setdefault(key, []).append(int(question_id))

    items: List[dict] = []
    for (subject_id, sc_id), question_ids in sorted(groups.items()):
        existing = _fallback_point(con, subject_id, sc_id)
        items.append({
            "subject_id": subject_id,
            "subject": SUBJECT_NAMES.get(subject_id, str(subject_id)),
            "sub_category_id": sc_id,
            "questions": question_ids,
            "count": len(question_ids),
            "target_point_id": existing,
            "will_create": existing is None,
        })
    return {"items": items}


def print_plan(plan: Dict[str, List[dict]]) -> None:
    total = sum(item["count"] for item in plan["items"])
    print(f"== 待归位的孤儿题：{total} 道，{len(plan['items'])} 个 (科目, 子科目) 分组 ==")
    for item in plan["items"]:
        action = ("新建收容叶子" if item["will_create"]
                  else f"指向 point_id={item['target_point_id']}")
        print(f"  {item['subject']:<3} 子科目={item['sub_category_id']!s:<5} "
              f"{item['count']:>4} 题 → {action}")


def backup_db(db_path: Path) -> Path:
    target = db_path.parent / f"question_bank.bak_orphan_{time.strftime('%Y%m%d_%H%M%S')}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def apply_plan(con: sqlite3.Connection, plan: Dict[str, List[dict]]) -> dict:
    created: List[int] = []
    updates: List[dict] = []
    for item in plan["items"]:
        target = item["target_point_id"]
        if target is None:
            cur = con.execute(
                "INSERT INTO knowledge_point "
                "(point_name, subject_id, sub_category_id, parent_id, level, description, "
                " sort_order, status) VALUES (?, ?, ?, 0, 3, ?, 999, 1)",
                (
                    FALLBACK_NAME,
                    item["subject_id"],
                    item["sub_category_id"],
                    "导入时无法归入具体考点、且未挂子科目的题目统一收容于此",
                ),
            )
            target = int(cur.lastrowid)
            created.append(target)
        for question_id in item["questions"]:
            con.execute(
                "UPDATE question_bank SET point_id = ? WHERE question_id = ? AND point_id IS NULL",
                (target, question_id),
            )
            updates.append({"question_id": question_id, "to": target})
    return {"created_points": created, "updated_questions": updates}


def write_audit(record: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"orphan_points_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_audit() -> Path:
    files = sorted(AUDIT_DIR.glob("orphan_points_*.json"))
    if not files:
        raise SystemExit("没有可还原的审计记录（backend/data/audit/orphan_points_*.json）")
    return files[-1]


def revert(db_path: Path, audit_path: Path) -> None:
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    con = sqlite3.connect(str(db_path))
    try:
        for item in record.get("updated_questions", []):
            con.execute(
                "UPDATE question_bank SET point_id = NULL WHERE question_id = ? AND point_id = ?",
                (int(item["question_id"]), int(item["to"])),
            )
        for point_id in record.get("created_points", []):
            con.execute("DELETE FROM knowledge_point WHERE point_id = ?", (int(point_id),))
        con.commit()
    finally:
        con.close()
    print(f"已还原：{audit_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="孤儿题归入「其他（未细分）」")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--apply", action="store_true", help="真正写库（默认 dry-run）")
    parser.add_argument("--revert", action="store_true", help="还原最近一次 apply")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"数据库不存在：{db_path}")

    if args.revert:
        revert(db_path, latest_audit())
        return

    con = sqlite3.connect(str(db_path))
    try:
        plan = load_plan(con)
        print_plan(plan)
        if not args.apply:
            print()
            print("[dry-run] 未写库。确认无误后加 --apply 执行。")
            return
        if not plan["items"]:
            print()
            print("没有孤儿题，无需处理。")
            return
        backup = backup_db(db_path)
        print()
        print(f"已备份：{backup}")
        result = apply_plan(con, plan)
        con.commit()
        path = write_audit(result)
        print(f"新建收容叶子 {len(result['created_points'])} 个，"
              f"归位题目 {len(result['updated_questions'])} 道")
        print(f"审计：{path}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
