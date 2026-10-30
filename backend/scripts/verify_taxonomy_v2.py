#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_taxonomy_v2.py — 知识点分类 V2 迁移验收校验（只读，stdlib only）。

用途:
  校验已完成「分类 V2」迁移的题库数据库是否满足验收基线：
    - 知识点表新增列 / 唯一索引
    - 知识点树 canonical / alias / hidden 数量
    - 题目与关联表的知识点指向分布
    - 以 question_bank.point_id 为主口径的 科目 → 子分类 → L2/L3 树完整性

用法:
  python backend/scripts/verify_taxonomy_v2.py
  python backend/scripts/verify_taxonomy_v2.py --db PATH --json-out PATH --assert

约束:
  - 仅使用 Python 3 标准库（argparse/json/sqlite3/pathlib/sys）。
  - 数据库以只读方式打开（mode=ro + PRAGMA query_only=ON），绝不写库。
  - 输出确定，不含时间戳等易变字段。
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "backend" / "data" / "question_bank.db"

VISIBLE_WHERE = "status = 1 AND audit_status = 1"
INDEX_NAME = "uq_knowledge_point_sibling_visible"
SUBJECT_IDS = (1, 2, 3)
SUBJECT_NAMES_FALLBACK = {1: "行测", 2: "申论", 3: "公专"}

# 期望值（验收基线）
EXPECTED = {
    # 知识点树
    "kp_total": 1049,
    "canonical": 518,
    "status0": 531,
    "alias_nonnull": 464,
    "alias_null_status0": 67,
    "visible_duplicate_siblings": 0,
    "canonical_l2": 91,
    "canonical_l3": 427,
    # 题库
    "qb_total": 3357,
    "qb_sub_category_nonnull": 2940,
    "qb_sub_category_null": 417,
    "qb_point_id_nonnull": 2131,
    "qb_point_id_null": 1226,
    "qb_point_to_canonical_l2": 0,
    "qb_point_to_hidden": 0,
    # 关联
    "qk_total": 2775,
    "qk_to_canonical_l2": 0,
    "qk_to_hidden": 643,
    "qk_duplicate_pairs": 0,
}


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """以只读方式打开 SQLite（mode=ro + query_only=ON）。"""
    uri = db_path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


def _scalar(con, sql, params=()):
    row = con.execute(sql, params).fetchone()
    return row[0] if row else None


def table_columns(con, table: str) -> set:
    return {row[1] for row in con.execute("PRAGMA table_info(%s)" % table)}


def index_names(con) -> set:
    return {
        row[0]
        for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    }


def _subject_names(con) -> dict:
    names = dict(SUBJECT_NAMES_FALLBACK)
    try:
        for sid, name in con.execute(
            "SELECT subject_id, subject_name FROM question_subject"
        ):
            try:
                names[int(sid)] = name
            except (TypeError, ValueError):
                continue
    except sqlite3.Error:
        pass
    return names


def build_report(con: sqlite3.Connection, db_path: Path) -> dict:
    checks = []
    metrics = {}
    subjects = []

    def add(name, ok, expected, actual, detail=None):
        item = {
            "name": name,
            "ok": bool(ok),
            "expected": expected,
            "actual": actual,
        }
        if detail:
            item["detail"] = detail
        checks.append(item)
        return item

    kp_cols = table_columns(con, "knowledge_point")
    qb_cols = table_columns(con, "question_bank")

    has_kp_status = "status" in kp_cols
    has_kp_alias = "alias_of" in kp_cols
    has_kp_subcat = "sub_category_id" in kp_cols
    has_qb_subcat = "sub_category_id" in qb_cols
    has_index = INDEX_NAME in index_names(con)

    # ---- 1. Schema ----
    add("schema.knowledge_point.alias_of", has_kp_alias, True, has_kp_alias)
    add("schema.knowledge_point.status", has_kp_status, True, has_kp_status)
    add("schema.question_bank.sub_category_id", has_qb_subcat, True, has_qb_subcat)
    add("schema.index.%s" % INDEX_NAME, has_index, True, has_index)

    def compute(key, sql, params=(), missing=None):
        name = "metrics." + key
        if missing:
            add(name, False, EXPECTED[key], None, "not computable: " + missing)
            return None
        value = _scalar(con, sql, params)
        metrics[key] = value
        add(name, value == EXPECTED[key], EXPECTED[key], value)
        return value

    alias_missing = (
        None
        if (has_kp_alias and has_kp_status)
        else "missing knowledge_point.alias_of/status"
    )
    status_missing = None if has_kp_status else "missing knowledge_point.status"

    # ---- 2. Knowledge tree ----
    compute("kp_total", "SELECT COUNT(*) FROM knowledge_point")

    compute(
        "canonical",
        "SELECT COUNT(*) FROM knowledge_point "
        "WHERE status = 1 AND alias_of IS NULL",
        missing=alias_missing,
    )
    compute(
        "status0",
        "SELECT COUNT(*) FROM knowledge_point WHERE status = 0",
        missing=status_missing,
    )
    compute(
        "alias_nonnull",
        "SELECT COUNT(*) FROM knowledge_point WHERE alias_of IS NOT NULL",
        missing=None if has_kp_alias else "missing knowledge_point.alias_of",
    )
    compute(
        "alias_null_status0",
        "SELECT COUNT(*) FROM knowledge_point "
        "WHERE alias_of IS NULL AND status = 0",
        missing=alias_missing,
    )

    dup_missing = (
        None
        if (has_kp_status and has_kp_subcat and "parent_id" in kp_cols)
        else "missing knowledge_point.status/sub_category_id/parent_id"
    )
    compute(
        "visible_duplicate_siblings",
        "SELECT COUNT(*) FROM ("
        "  SELECT subject_id, sub_category_id, parent_id, point_name"
        "  FROM knowledge_point WHERE status = 1"
        "  GROUP BY subject_id, sub_category_id, parent_id, point_name"
        "  HAVING COUNT(*) > 1"
        ")",
        missing=dup_missing,
    )

    compute(
        "canonical_l2",
        "SELECT COUNT(*) FROM knowledge_point "
        "WHERE level = 2 AND status = 1 AND alias_of IS NULL",
        missing=alias_missing,
    )
    compute(
        "canonical_l3",
        "SELECT COUNT(*) FROM knowledge_point "
        "WHERE level = 3 AND status = 1 AND alias_of IS NULL",
        missing=alias_missing,
    )

    # ---- 3. Questions ----
    compute("qb_total", "SELECT COUNT(*) FROM question_bank")
    compute(
        "qb_sub_category_nonnull",
        "SELECT COUNT(*) FROM question_bank WHERE sub_category_id IS NOT NULL",
        missing=None
        if has_qb_subcat
        else "missing question_bank.sub_category_id",
    )
    compute(
        "qb_sub_category_null",
        "SELECT COUNT(*) FROM question_bank WHERE sub_category_id IS NULL",
        missing=None
        if has_qb_subcat
        else "missing question_bank.sub_category_id",
    )
    compute(
        "qb_point_id_nonnull",
        "SELECT COUNT(*) FROM question_bank WHERE point_id IS NOT NULL",
    )
    compute(
        "qb_point_id_null",
        "SELECT COUNT(*) FROM question_bank WHERE point_id IS NULL",
    )
    compute(
        "qb_point_to_canonical_l2",
        "SELECT COUNT(*) FROM question_bank qb "
        "JOIN knowledge_point kp ON kp.point_id = qb.point_id "
        "WHERE kp.level = 2 AND kp.status = 1 AND kp.alias_of IS NULL",
        missing=alias_missing,
    )
    compute(
        "qb_point_to_hidden",
        "SELECT COUNT(*) FROM question_bank qb "
        "JOIN knowledge_point kp ON kp.point_id = qb.point_id "
        "WHERE kp.status = 0",
        missing=status_missing,
    )

    # ---- 4. Relations ----
    compute("qk_total", "SELECT COUNT(*) FROM question_knowledge")
    compute(
        "qk_to_canonical_l2",
        "SELECT COUNT(*) FROM question_knowledge qk "
        "JOIN knowledge_point kp ON kp.point_id = qk.knowledge_point_id "
        "WHERE kp.level = 2 AND kp.status = 1 AND kp.alias_of IS NULL",
        missing=alias_missing,
    )
    compute(
        "qk_to_hidden",
        "SELECT COUNT(*) FROM question_knowledge qk "
        "JOIN knowledge_point kp ON kp.point_id = qk.knowledge_point_id "
        "WHERE kp.status = 0",
        missing=status_missing,
    )
    compute(
        "qk_duplicate_pairs",
        "SELECT COUNT(*) FROM ("
        "  SELECT question_id, knowledge_point_id"
        "  FROM question_knowledge"
        "  GROUP BY question_id, knowledge_point_id"
        "  HAVING COUNT(*) > 1"
        ")",
    )

    # ---- 5. Tree / A3 / A4 / A7 （以 question_bank.point_id 为单一口径）----
    tree_missing = None
    required_kp = {"point_name", "subject_id", "parent_id", "level", "status",
                   "alias_of", "sub_category_id"}
    missing_kp = sorted(required_kp - kp_cols)
    if missing_kp:
        tree_missing = "knowledge_point missing: " + ", ".join(missing_kp)
    elif not has_qb_subcat:
        tree_missing = "question_bank missing: sub_category_id"

    subject_names = _subject_names(con)

    if tree_missing:
        add("tree.evaluable", False, True, False, tree_missing)
        for sid in SUBJECT_IDS:
            visible_total = int(_scalar(
                con,
                "SELECT COUNT(*) FROM question_bank "
                "WHERE subject_id = ? AND " + VISIBLE_WHERE,
                (sid,),
            ) or 0)
            subjects.append({
                "subject_id": sid,
                "subject_name": subject_names.get(sid, str(sid)),
                "visible_total": visible_total,
                "evaluated": False,
            })
    else:
        for sid in SUBJECT_IDS:
            subject_name = subject_names.get(sid, str(sid))
            visible_total = int(_scalar(
                con,
                "SELECT COUNT(*) FROM question_bank "
                "WHERE subject_id = ? AND " + VISIBLE_WHERE,
                (sid,),
            ) or 0)

            qb_subcats = {
                row[0]
                for row in con.execute(
                    "SELECT DISTINCT sub_category_id FROM question_bank "
                    "WHERE subject_id = ? AND " + VISIBLE_WHERE +
                    " AND sub_category_id IS NOT NULL",
                    (sid,),
                )
            }
            kp_subcats = {
                row[0]
                for row in con.execute(
                    "SELECT DISTINCT sub_category_id FROM knowledge_point "
                    "WHERE subject_id = ? AND sub_category_id IS NOT NULL",
                    (sid,),
                )
            }
            subcats = sorted(qb_subcats | kp_subcats)

            subcat_entries = []
            subject_sum = 0
            subject_zero_returned = 0
            returned_point_ids = []

            for sc in subcats:
                total = int(_scalar(
                    con,
                    "SELECT COUNT(*) FROM question_bank "
                    "WHERE subject_id = ? AND sub_category_id = ? AND "
                    + VISIBLE_WHERE,
                    (sid, sc),
                ) or 0)

                l2_names = {
                    row[0]: row[1]
                    for row in con.execute(
                        "SELECT point_id, point_name FROM knowledge_point "
                        "WHERE subject_id = ? AND sub_category_id = ? "
                        "AND level = 2 AND status = 1 AND alias_of IS NULL",
                        (sid, sc),
                    )
                }
                l3_names = {}
                l3_parent = {}
                for pid, name, parent_id in con.execute(
                    "SELECT point_id, point_name, parent_id FROM knowledge_point "
                    "WHERE subject_id = ? AND sub_category_id = ? "
                    "AND level = 3 AND status = 1 AND alias_of IS NULL",
                    (sid, sc),
                ):
                    l3_names[pid] = name
                    l3_parent[pid] = parent_id

                l2_totals = {pid: 0 for pid in l2_names}
                l3_totals = defaultdict(int)
                classified = 0
                for pid, cnt in con.execute(
                    "SELECT point_id, COUNT(*) FROM question_bank "
                    "WHERE subject_id = ? AND sub_category_id = ? AND "
                    + VISIBLE_WHERE +
                    " AND point_id IS NOT NULL GROUP BY point_id",
                    (sid, sc),
                ):
                    if pid in l2_names:
                        l2_totals[pid] += cnt
                        classified += cnt
                        continue
                    parent = l3_parent.get(pid)
                    if parent in l2_names:
                        l2_totals[parent] += cnt
                        l3_totals[pid] += cnt
                        classified += cnt

                unclassified = total - classified
                l2_sum = sum(l2_totals.values())
                covered = l2_sum + unclassified
                subject_sum += total

                add(
                    "tree.subject_%d.subcat_%s.sum_matches_total" % (sid, sc),
                    covered == total,
                    total,
                    covered,
                )

                nodes = []
                for l2_pid in sorted(
                    l2_names, key=lambda p: (l2_names[p], p)
                ):
                    l2_total = l2_totals[l2_pid]
                    if l2_total <= 0:
                        continue
                    children = []
                    for l3_pid in sorted(l3_totals):
                        if l3_parent.get(l3_pid) != l2_pid:
                            continue
                        l3_total = l3_totals[l3_pid]
                        if l3_total <= 0:
                            continue
                        children.append({
                            "point_id": l3_pid,
                            "point_name": l3_names[l3_pid],
                            "total": l3_total,
                        })
                        returned_point_ids.append(l3_pid)
                    nodes.append({
                        "point_id": l2_pid,
                        "point_name": l2_names[l2_pid],
                        "total": l2_total,
                        "l3_children": children,
                    })
                    returned_point_ids.append(l2_pid)

                zero_returned = sum(
                    1
                    for node in nodes
                    if node["total"] <= 0
                ) + sum(
                    1
                    for node in nodes
                    for child in node["l3_children"]
                    if child["total"] <= 0
                )
                subject_zero_returned += zero_returned

                subcat_entries.append({
                    "sub_category_id": sc,
                    "total": total,
                    "classified": classified,
                    "unclassified": unclassified,
                    "l2_sum": l2_sum,
                    "sum_matches_total": covered == total,
                    "l2_nodes": nodes,
                })

            global_unclassified = int(_scalar(
                con,
                "SELECT COUNT(*) FROM question_bank "
                "WHERE subject_id = ? AND sub_category_id IS NULL AND "
                + VISIBLE_WHERE,
                (sid,),
            ) or 0)
            covered = subject_sum + global_unclassified
            add(
                "tree.subject_%d.subcategory_sum_equals_visible" % sid,
                covered == visible_total,
                visible_total,
                covered,
            )

            add(
                "tree.subject_%d.no_zero_total_nodes" % sid,
                subject_zero_returned == 0,
                0,
                subject_zero_returned,
            )

            hidden_returned = 0
            if returned_point_ids:
                placeholders = ",".join("?" * len(returned_point_ids))
                hidden_returned = _scalar(
                    con,
                    "SELECT COUNT(*) FROM knowledge_point "
                    "WHERE point_id IN (%s) AND status != 1" % placeholders,
                    returned_point_ids,
                )
            add(
                "tree.subject_%d.returned_points_visible" % sid,
                hidden_returned == 0,
                0,
                hidden_returned,
            )

            dup_child_names = _scalar(
                con,
                "SELECT COUNT(*) FROM ("
                "  SELECT parent_id, point_name FROM knowledge_point"
                "  WHERE subject_id = ? AND level = 3 AND status = 1"
                "    AND alias_of IS NULL"
                "  GROUP BY parent_id, point_name HAVING COUNT(*) > 1"
                ")",
                (sid,),
            )
            add(
                "tree.subject_%d.l2_no_duplicate_child_names" % sid,
                dup_child_names == 0,
                0,
                dup_child_names,
            )

            subjects.append({
                "subject_id": sid,
                "subject_name": subject_name,
                "visible_total": visible_total,
                "sub_category_sum": subject_sum,
                "global_unclassified": global_unclassified,
                "sum_equals_visible": covered == visible_total,
                "evaluated": True,
                "subcategories": subcat_entries,
            })

    report = {
        "ok": all(item["ok"] for item in checks),
        "db": str(db_path),
        "checks": checks,
        "metrics": metrics,
        "subjects": subjects,
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="知识点分类 V2 迁移验收校验（只读，stdlib only）",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="SQLite 数据库路径（默认 %s）" % DEFAULT_DB,
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="将 JSON 报告写入指定路径（默认只打印到 stdout）",
    )
    parser.add_argument(
        "--assert",
        dest="assert_mode",
        action="store_true",
        help="任一检查失败则退出码 1",
    )
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass

    db_path = args.db.resolve()
    if not db_path.exists():
        print("ERROR: database not found: %s" % db_path, file=sys.stderr)
        return 2

    con = connect_readonly(db_path)
    try:
        report = build_report(con, db_path)
    finally:
        con.close()

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")

    failed = [item for item in report["checks"] if not item["ok"]]
    if args.assert_mode:
        if failed:
            print(
                "ASSERT FAILED: %d check(s) failed" % len(failed),
                file=sys.stderr,
            )
            for item in failed:
                line = "  - %s: expected=%r actual=%r" % (
                    item["name"],
                    item["expected"],
                    item["actual"],
                )
                if item.get("detail"):
                    line += " (%s)" % item["detail"]
                print(line, file=sys.stderr)
            return 1
        print("ASSERT OK: all checks passed", file=sys.stderr)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
