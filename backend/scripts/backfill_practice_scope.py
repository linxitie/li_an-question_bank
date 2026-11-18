#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回填历史练习记录的考点范围（默认 dry-run）。

背景（2026-11-14 实测）：practice_record 共 318 行，scope_type/scope_id/scope_name
/sub_category_id 四个字段**从未被写入**（全库 scope_name 恒 NULL），所以「练习记录」
只能显示空值、前端回落成「其他」。practice_grading 已在本轮补上写入逻辑，但历史记录
仍是空的，用户翻旧账时看到的还是「其他」。

本脚本按「题目主考点 > 子科目 > 未分类」的优先级回填，只写这四个 scope 字段，
不动 answer/is_correct/practice_time 等既有判分数据。

用法：
  python scripts/backfill_practice_scope.py            # dry-run，只统计
  python scripts/backfill_practice_scope.py --apply    # 写入（先 sqlite3.backup 备份）
  python scripts/backfill_practice_scope.py --revert   # 撤销最近一次 apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BASE_DIR / "data" / "question_bank.db"
AUDIT_DIR = BASE_DIR / "data" / "audit"


def backup_db(db_path: Path) -> Path:
    """R10：WAL 模式下用 sqlite3.backup()，不要 shutil.copy2"""
    target = db_path.parent / f"question_bank.bak_scope_{time.strftime('%Y%m%d_%H%M%S')}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def load_targets(con: sqlite3.Connection) -> List[Tuple]:
    """待回填记录 + 每题解析出的 scope（一次 JOIN 拿全）"""
    sql = """
        SELECT r.record_id,
               q.point_id,
               kp.point_name,
               q.sub_category_id,
               sc.name,
               q.subject_id
        FROM practice_record r
        LEFT JOIN question_bank q ON q.question_id = r.question_id
        LEFT JOIN knowledge_point kp ON kp.point_id = q.point_id
        LEFT JOIN sub_categories sc ON sc.id = q.sub_category_id
        WHERE r.scope_name IS NULL OR TRIM(r.scope_name) = ''
        ORDER BY r.record_id
    """
    return list(con.execute(sql))


def build_updates(rows: List[Tuple]) -> List[dict]:
    updates: List[dict] = []
    for record_id, point_id, point_name, sub_category_id, sub_name, subject_id in rows:
        if point_name:
            updates.append({
                "record_id": int(record_id),
                "scope_type": "point",
                "scope_id": int(point_id) if point_id is not None else None,
                "scope_name": str(point_name),
                "sub_category_id": int(sub_category_id) if sub_category_id is not None else None,
            })
        elif sub_name:
            updates.append({
                "record_id": int(record_id),
                "scope_type": "subcategory",
                "scope_id": int(sub_category_id),
                "scope_name": str(sub_name),
                "sub_category_id": int(sub_category_id),
            })
        else:
            updates.append({
                "record_id": int(record_id),
                "scope_type": "unclassified",
                "scope_id": None,
                "scope_name": "未分类",
                "sub_category_id": int(sub_category_id) if sub_category_id is not None else None,
            })
    return updates


def summarize(updates: List[dict]) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for item in updates:
        key = item["scope_name"]
        stats[key] = stats.get(key, 0) + 1
    return dict(sorted(stats.items(), key=lambda kv: -kv[1]))


def write_audit(record: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"practice_scope_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="历史练习记录 scope 回填")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"数据库不存在：{db_path}")

    if args.revert:
        files = sorted(AUDIT_DIR.glob("practice_scope_*.json"))
        if not files:
            raise SystemExit("没有可还原的审计记录")
        record = json.loads(files[-1].read_text(encoding="utf-8"))
        con = sqlite3.connect(str(db_path))
        try:
            for record_id in record.get("touched", []):
                con.execute(
                    "UPDATE practice_record SET scope_type = NULL, scope_id = NULL, "
                    "scope_name = NULL, sub_category_id = NULL WHERE record_id = ?",
                    (record_id,),
                )
            con.commit()
        finally:
            con.close()
        print(f"已还原 {len(record.get('touched', []))} 条（{files[-1]}）")
        return

    con = sqlite3.connect(str(db_path))
    try:
        updates = build_updates(load_targets(con))
        print(f"待回填记录：{len(updates)} 条")
        for name, count in summarize(updates).items():
            print(f"   {name:<20} {count:>5}")
        if not args.apply:
            print("\n[dry-run] 未写库。确认无误后加 --apply 执行。")
            return

        backup = backup_db(db_path)
        print(f"\n已备份：{backup}")
        for item in updates:
            con.execute(
                "UPDATE practice_record SET scope_type = ?, scope_id = ?, "
                "scope_name = ?, sub_category_id = ? WHERE record_id = ?",
                (item["scope_type"], item["scope_id"], item["scope_name"],
                 item["sub_category_id"], item["record_id"]),
            )
        con.commit()
    finally:
        con.close()

    audit = write_audit({
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db": str(db_path),
        "touched": [item["record_id"] for item in updates],
    })
    print(f"完成：{len(updates)} 条；审计 {audit}")


if __name__ == "__main__":
    main()
