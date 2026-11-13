#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""未分类题回填子科目（默认 dry-run）。

原则：
1. 只处理 status=1 且 sub_category_id IS NULL 的题；
2. 只用两类证据：旧字段（xingce/shenlun/gongzhuan_subcategory）精确匹配，
   或 question_knowledge 指向的 knowledge_point.sub_category_id；
3. 只写 sub_category_id，不改 point_id、题干、答案、选项；
4. --apply 前用 sqlite3.backup() 备份，禁止 shutil.copy2（WAL 下不安全）。

用法：
  python scripts/backfill_unclassified_subcategory.py
  python scripts/backfill_unclassified_subcategory.py --apply
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BASE_DIR / "data" / "question_bank.db"
AUDIT_DIR = BASE_DIR / "data" / "audit"

LEGACY_COLUMNS = {
    1: "xingce_subcategory",
    2: "shenlun_subcategory",
    3: "gongzhuan_subcategory",
}
SUBJECT_NAMES = {1: "行测", 2: "申论", 3: "公专"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_subcategories(con: sqlite3.Connection) -> Tuple[Dict[Tuple[int, str], int], Dict[int, Tuple[int, str]]]:
    """返回 (科目+名称 -> 子科目ID, 子科目ID -> (科目, 名称))。"""
    by_name: Dict[Tuple[int, str], int] = {}
    by_id: Dict[int, Tuple[int, str]] = {}
    for row in con.execute("SELECT id, subject_id, name FROM sub_categories"):
        sc_id, subject_id, name = int(row[0]), int(row[1]), str(row[2] or "").strip()
        if not name:
            continue
        by_name[(subject_id, name)] = sc_id
        by_id[sc_id] = (subject_id, name)
    return by_name, by_id


def load_candidates(con: sqlite3.Connection) -> List[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    sql = """
        SELECT
            q.question_id,
            q.subject_id,
            q.xingce_subcategory,
            q.shenlun_subcategory,
            q.gongzhuan_subcategory,
            q.point_id,
            q.year,
            q.question_content,
            (
                SELECT kp.sub_category_id
                FROM question_knowledge qk
                JOIN knowledge_point kp ON kp.point_id = qk.knowledge_point_id
                WHERE qk.question_id = q.question_id
                  AND kp.sub_category_id IS NOT NULL
                LIMIT 1
            ) AS qk_sub_category_id
        FROM question_bank q
        WHERE q.status = 1
          AND q.sub_category_id IS NULL
        ORDER BY q.question_id
    """
    return list(con.execute(sql))


def decide_target(row: sqlite3.Row,
                  by_name: Dict[Tuple[int, str], int],
                  by_id: Dict[int, Tuple[int, str]]) -> Tuple[Optional[int], str]:
    subject_id = int(row["subject_id"] or 0)
    legacy_col = LEGACY_COLUMNS.get(subject_id)
    legacy_name = str(row[legacy_col] or "").strip() if legacy_col else ""
    if legacy_name and legacy_name != "无":
        target = by_name.get((subject_id, legacy_name))
        if target:
            return target, f"legacy:{legacy_name}"

    qk_target = row["qk_sub_category_id"]
    if qk_target is not None:
        target = int(qk_target)
        owner = by_id.get(target)
        if owner and owner[0] == subject_id:
            return target, f"qk:{owner[1]}"
    return None, "no_evidence"


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "question_id", "subject", "year", "legacy_value",
        "qk_sub_category_id", "suggested_sub_category_id",
        "suggested_sub_category_name", "decision", "content_preview",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def backup_database(db_path: Path) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.bak_unclassified_{ts}")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup))
    try:
        src.backup(dst)
        check = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"备份完整性校验失败: {check}")
    finally:
        dst.close()
        src.close()
    return backup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true", help="实际写库；默认只 dry-run")
    args = parser.parse_args()

    db_path = args.db.resolve()
    if not db_path.exists():
        raise SystemExit(f"数据库不存在: {db_path}")

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        by_name, by_id = load_subcategories(con)
        candidates = load_candidates(con)
        before_unclassified = len(candidates)
        by_subject = {str(k): 0 for k in SUBJECT_NAMES}
        decisions: List[dict] = []
        updates: List[Tuple[int, int]] = []
        no_evidence: List[dict] = []

        for row in candidates:
            subject_id = int(row["subject_id"] or 0)
            by_subject[str(subject_id)] = by_subject.get(str(subject_id), 0) + 1
            target, why = decide_target(row, by_name, by_id)
            legacy_col = LEGACY_COLUMNS.get(subject_id)
            legacy_value = str(row[legacy_col] or "") if legacy_col else ""
            item = {
                "question_id": int(row["question_id"]),
                "subject": SUBJECT_NAMES.get(subject_id, str(subject_id)),
                "year": row["year"],
                "legacy_value": legacy_value,
                "qk_sub_category_id": row["qk_sub_category_id"],
                "suggested_sub_category_id": target,
                "suggested_sub_category_name": by_id[target][1] if target else "",
                "decision": why,
                "content_preview": str(row["question_content"] or "").replace("\n", " ")[:120],
            }
            decisions.append(item)
            if target is not None:
                updates.append((int(row["question_id"]), target))
            else:
                no_evidence.append(item)

        ts = time.strftime("%Y%m%d_%H%M%S")
        csv_path = AUDIT_DIR / f"unclassified_questions_{ts}.csv"
        write_csv(csv_path, decisions)

        sql_path = AUDIT_DIR / f"unclassified_backfill_{ts}.sql"
        sql_lines = [
            "-- 未分类题回填子科目（只改 sub_category_id）",
            f"-- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"-- 候选: {before_unclassified}; 可回填: {len(updates)}; 保留未分类: {len(no_evidence)}",
            "BEGIN IMMEDIATE;",
        ]
        for question_id, target_id in updates:
            sql_lines.append(
                f"UPDATE question_bank SET sub_category_id = {target_id} "
                f"WHERE question_id = {question_id} AND sub_category_id IS NULL;"
            )
        sql_lines.append("COMMIT;")
        sql_path.write_text(chr(10).join(sql_lines) + chr(10), encoding="utf-8")

        result = {
            "mode": "apply" if args.apply else "dry-run",
            "db": str(db_path),
            "db_sha256_before": sha256(db_path),
            "unclassified_before": before_unclassified,
            "candidates_by_subject": by_subject,
            "will_backfill": len(updates),
            "will_stay_unclassified": len(no_evidence),
            "csv": str(csv_path),
            "sql": str(sql_path),
            "backup": None,
            "db_sha256_after": None,
            "unclassified_after": before_unclassified,
        }

        if not args.apply:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if not updates:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        backup = backup_database(db_path)
        result["backup"] = str(backup)
        try:
            con.execute("BEGIN IMMEDIATE")
            con.executemany(
                "UPDATE question_bank SET sub_category_id = ? "
                "WHERE question_id = ? AND sub_category_id IS NULL AND status = 1",
                [(target, question_id) for question_id, target in updates],
            )
            changed = con.execute(
                "SELECT COUNT(*) FROM question_bank "
                "WHERE status = 1 AND sub_category_id IS NULL"
            ).fetchone()[0]
            expected = before_unclassified - len(updates)
            if int(changed) != expected:
                raise RuntimeError(f"回填后未分类数 {changed} != 预期 {expected}，已回滚")
            con.commit()
        except Exception:
            con.rollback()
            raise

        result["db_sha256_after"] = sha256(db_path)
        result["unclassified_after"] = con.execute(
            "SELECT COUNT(*) FROM question_bank "
            "WHERE status = 1 AND sub_category_id IS NULL"
        ).fetchone()[0]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
