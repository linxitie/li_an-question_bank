#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_question_counts.py — 三端题目计数一致性基线采集与校验（只读）。

P0-2 任务（docs/plans/三端数据流一致性修复方案_v1.md）：
  采集「题库表计数 / 知识点关联 / 题组」当前基线，输出 JSON 与人工可读摘要，
  并记录一致性检查结果（允许失败，只记录不修复）。

用法:
  python backend/scripts/verify_question_counts.py --baseline            # 写基线 JSON，退出码恒为 0
  python backend/scripts/verify_question_counts.py --assert              # 执行断言，任一检查失败则退出码 1
  python backend/scripts/verify_question_counts.py                       # 只打印摘要，不写文件
  python backend/scripts/verify_question_counts.py --db <path> --json-out <path>

约束:
  - 仅使用 Python 3 标准库（argparse/json/sqlite3/pathlib/datetime/os/sys）。
  - 不导入 FastAPI 应用或 SQLAlchemy 模型。
  - 数据库以只读方式打开（mode=ro + PRAGMA query_only=ON），绝不写库。
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "backend" / "data" / "question_bank.db"
DEFAULT_JSON_OUT = (
    REPO_ROOT / "backend" / "data" / "refactor_baseline"
    / "question_counts_baseline_20261019.json"
)

# 科目 1/2/3 分别对应的子分类列；NULL / '' / '无' 统一归入「未分类」
SUBJECT_NAMES_FALLBACK = {1: "行测", 2: "申论", 3: "公专"}
SUBCATEGORY_COLUMN = {
    1: "xingce_subcategory",
    2: "shenlun_subcategory",
    3: "gongzhuan_subcategory",
}
UNCLASSIFIED_VALUES = {"", "无"}
UNCLASSIFIED_BUCKET = "未分类"
VISIBLE_WHERE = "status = 1 AND audit_status = 1"


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """以只读方式打开 SQLite（mode=ro + query_only=ON）。"""
    uri = db_path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


def _scalar(con, sql, params=()):
    row = con.execute(sql, params).fetchone()
    return row[0] if row else None


def _dist(con, sql):
    return {str(k): v for k, v in con.execute(sql).fetchall()}


def collect_metrics(con: sqlite3.Connection) -> dict:
    m = {}

    # ---- question_bank 全局 ----
    m["question_bank"] = {
        "total": _scalar(con, "SELECT COUNT(*) FROM question_bank"),
        "status_1_total": _scalar(con, "SELECT COUNT(*) FROM question_bank WHERE status = 1"),
        "status_0_total": _scalar(con, "SELECT COUNT(*) FROM question_bank WHERE status = 0"),
        "status_other_total": _scalar(con, "SELECT COUNT(*) FROM question_bank WHERE status NOT IN (0, 1)"),
        "status_distribution": _dist(con, "SELECT status, COUNT(*) FROM question_bank GROUP BY status"),
        "audit_status_distribution": _dist(con, "SELECT audit_status, COUNT(*) FROM question_bank GROUP BY audit_status"),
    }

    # ---- 按科目 ----
    subject_names = {
        sid: name for sid, name in con.execute(
            "SELECT subject_id, subject_name FROM question_subject"
        )
    }
    per_subject = {}
    for sid in (1, 2, 3):
        name = subject_names.get(sid) or SUBJECT_NAMES_FALLBACK.get(sid, str(sid))
        col = SUBCATEGORY_COLUMN[sid]
        visible_total = _scalar(
            con, f"SELECT COUNT(*) FROM question_bank WHERE subject_id = ? AND {VISIBLE_WHERE}", (sid,)
        )
        all_total = _scalar(con, "SELECT COUNT(*) FROM question_bank WHERE subject_id = ?", (sid,))
        status0_total = _scalar(
            con, "SELECT COUNT(*) FROM question_bank WHERE subject_id = ? AND status = 0", (sid,)
        )
        # 可见行子分类计数（正确列：行测/申论/公专各用各的列）
        subcat_rows = con.execute(
            f"SELECT {col}, COUNT(*) FROM question_bank "
            f"WHERE subject_id = ? AND {VISIBLE_WHERE} GROUP BY {col}",
            (sid,),
        ).fetchall()
        classified = {}
        unclassified = 0
        for val, cnt in subcat_rows:
            if val is None or str(val).strip() in UNCLASSIFIED_VALUES:
                unclassified += cnt
            else:
                classified[str(val).strip()] = cnt
        classified_sum = sum(classified.values())
        subcat_sum = classified_sum + unclassified
        # 可见题中已关联知识点（question_knowledge）的去重题数
        linked = _scalar(
            con,
            """
            SELECT COUNT(DISTINCT qk.question_id)
            FROM question_knowledge qk
            JOIN question_bank qb ON qb.question_id = qk.question_id
            WHERE qb.subject_id = ? AND qb.status = 1 AND qb.audit_status = 1
            """,
            (sid,),
        )
        unlinked = visible_total - linked
        distinct_content = _scalar(
            con,
            "SELECT COUNT(DISTINCT question_content) FROM question_bank "
            "WHERE subject_id = ? AND status = 1 AND audit_status = 1",
            (sid,),
        )
        per_subject[str(sid)] = {
            "subject_name": name,
            "visible_total": visible_total,
            "all_total": all_total,
            "status0_total": status0_total,
            "subcategory_classified_counts": classified,
            "subcategory_classified_sum": classified_sum,
            "subcategory_unclassified": unclassified,
            "subcategory_sum_incl_unclassified": subcat_sum,
            "knowledge_linked_distinct_questions": linked,
            "knowledge_unlinked_questions": unlinked,
            "knowledge_linked_exceeds_visible": bool(int(linked or 0) > int(visible_total or 0)),
            "distinct_question_content": distinct_content,
        }
    m["per_subject"] = per_subject

    # ---- knowledge_point ----
    dup = con.execute(
        "SELECT point_name, COUNT(*) AS c FROM knowledge_point "
        "GROUP BY point_name HAVING c > 1"
    ).fetchall()
    m["knowledge_point"] = {
        "total": _scalar(con, "SELECT COUNT(*) FROM knowledge_point"),
        "distinct_point_name": _scalar(con, "SELECT COUNT(DISTINCT point_name) FROM knowledge_point"),
        "rows_point_name_qita": _scalar(con, "SELECT COUNT(*) FROM knowledge_point WHERE point_name = '其他'"),
        "duplicate_name_count": len(dup),
        "duplicate_row_excess": sum(int(c) - 1 for _, c in dup),
    }

    # ---- question_knowledge ----
    m["question_knowledge"] = {
        "total": _scalar(con, "SELECT COUNT(*) FROM question_knowledge"),
        "distinct_knowledge_point_id": _scalar(con, "SELECT COUNT(DISTINCT knowledge_point_id) FROM question_knowledge"),
        "distinct_question_id": _scalar(con, "SELECT COUNT(DISTINCT question_id) FROM question_knowledge"),
    }

    # ---- question_bank.point_id 填充情况 ----
    m["point_id_population"] = {
        "non_null": _scalar(con, "SELECT COUNT(*) FROM question_bank WHERE point_id IS NOT NULL"),
        "non_null_non_zero": _scalar(con, "SELECT COUNT(*) FROM question_bank WHERE point_id IS NOT NULL AND point_id != 0"),
    }

    # ---- 申论可见行明细 ----
    shenlun_visible = per_subject["2"]["visible_total"]
    m["shenlun_visible"] = {
        "total": shenlun_visible,
        "options_empty_or_null": _scalar(
            con,
            "SELECT COUNT(*) FROM question_bank WHERE subject_id = 2 AND " + VISIBLE_WHERE +
            " AND (options IS NULL OR TRIM(options) IN ('', '[]', '{}', 'null', '\"\"'))",
        ),
        "group_id_gt_0": _scalar(
            con,
            "SELECT COUNT(*) FROM question_bank WHERE subject_id = 2 AND " + VISIBLE_WHERE +
            " AND group_id IS NOT NULL AND group_id > 0",
        ),
        "group_id_eq_0": _scalar(
            con,
            "SELECT COUNT(*) FROM question_bank WHERE subject_id = 2 AND " + VISIBLE_WHERE +
            " AND (group_id IS NULL OR group_id = 0)",
        ),
    }

    # ---- question_groups ----
    group_rows = con.execute(
        """
        SELECT g.id,
               COUNT(qb.question_id) AS total_members,
               SUM(CASE WHEN qb.status = 1 THEN 1 ELSE 0 END) AS visible_members
        FROM question_groups g
        LEFT JOIN question_bank qb ON qb.group_id = g.id
        GROUP BY g.id
        ORDER BY g.id
        """
    ).fetchall()
    m["question_groups"] = {
        "total": _scalar(con, "SELECT COUNT(*) FROM question_groups"),
        "groups_with_visible_member": sum(1 for _, _, vm in group_rows if (vm or 0) >= 1),
        "groups_with_0_visible_members": sum(1 for _, _, vm in group_rows if (vm or 0) == 0),
        "groups_with_0_members_all_statuses": sum(1 for _, tm, _ in group_rows if (tm or 0) == 0),
    }

    def group_detail(gid: int) -> dict:
        row = con.execute(
            "SELECT shared_content, source, subject, group_type FROM question_groups WHERE id = ?",
            (gid,),
        ).fetchone()
        if not row:
            return {"exists": False, "group_id": gid}
        sc, src, subj, gtype = row
        members = _scalar(con, "SELECT COUNT(*) FROM question_bank WHERE group_id = ?", (gid,))
        distinct_src = _scalar(
            con,
            "SELECT COUNT(DISTINCT source) FROM question_bank "
            "WHERE group_id = ? AND source IS NOT NULL AND source != ''",
            (gid,),
        )
        return {
            "exists": True,
            "group_id": gid,
            "member_count": members,
            "distinct_source_count": distinct_src,
            "group_source": src,
            "group_subject": subj,
            "group_type": gtype,
            "shared_content_length": len(sc) if sc else 0,
            "shared_content_head80": (sc or "")[:80],
        }

    m["group_24"] = group_detail(24)
    m["group_1"] = group_detail(1)
    return m


def _check(cid, description, actual, expected, status, note=None):
    c = {"id": cid, "description": description, "actual": actual, "expected": expected, "status": status}
    if note:
        c["note"] = note
    return c


def build_checks(m: dict) -> list:
    checks = []
    for key in sorted(m["per_subject"], key=int):
        sid = int(key)
        ps = m["per_subject"][key]
        name = ps["subject_name"]

        a = ps["subcategory_sum_incl_unclassified"]
        e = ps["visible_total"]
        checks.append(_check(
            f"subject_{sid}_subcategory_sum_equals_visible",
            f"{name} 子分类计数之和（含未分类）== 可见总数",
            a, e, "pass" if a == e else "fail",
        ))

        a = ps["knowledge_linked_distinct_questions"] + ps["knowledge_unlinked_questions"]
        checks.append(_check(
            f"subject_{sid}_knowledge_linked_plus_unlinked_equals_visible",
            f"{name} 关联题数 + 未关联题数 == 可见总数",
            a, e, "pass" if a == e else "fail",
        ))

        a = ps["distinct_question_content"]
        checks.append(_check(
            f"subject_{sid}_distinct_content_le_visible",
            f"{name} 去重题干数 <= 可见总数",
            a, f"<= {e}", "pass" if a <= e else "fail",
        ))

    n = m["point_id_population"]["non_null_non_zero"]
    checks.append(_check(
        "point_id_populated",
        "question_bank.point_id 非空且非零的行数 > 0",
        n, "> 0", "pass" if n > 0 else "fail",
    ))

    checks.append({
        "id": "three_end_default_counts_equal",
        "description": "三端默认口径计数一致",
        "actual": None,
        "expected": None,
        "status": "not_evaluated",
        "note": "API-level check deferred to P1",
    })
    return checks


def print_summary(m: dict, checks: list) -> None:
    qb = m["question_bank"]
    print("== question_bank ==")
    print(f"  total={qb['total']} status_1={qb['status_1_total']} status_0={qb['status_0_total']} "
          f"status_other={qb['status_other_total']}")
    print(f"  status_distribution={qb['status_distribution']}")
    print(f"  audit_status_distribution={qb['audit_status_distribution']}")

    print("== per subject ==")
    for key in sorted(m["per_subject"], key=int):
        ps = m["per_subject"][key]
        print(f"  [{key} {ps['subject_name']}] visible={ps['visible_total']} all={ps['all_total']} "
              f"status0={ps['status0_total']}")
        print(f"    subcat: classified_sum={ps['subcategory_classified_sum']} "
              f"unclassified={ps['subcategory_unclassified']} sum_incl={ps['subcategory_sum_incl_unclassified']}")
        print(f"    knowledge: linked={ps['knowledge_linked_distinct_questions']} "
              f"unlinked={ps['knowledge_unlinked_questions']} "
              f"linked_exceeds_visible={ps['knowledge_linked_exceeds_visible']}")
        print(f"    distinct_content={ps['distinct_question_content']}")

    kp = m["knowledge_point"]
    print("== knowledge_point ==")
    print(f"  total={kp['total']} distinct_name={kp['distinct_point_name']} "
          f"qita={kp['rows_point_name_qita']} dup_names={kp['duplicate_name_count']} "
          f"dup_row_excess={kp['duplicate_row_excess']}")

    qk = m["question_knowledge"]
    print("== question_knowledge ==")
    print(f"  total={qk['total']} distinct_kp={qk['distinct_knowledge_point_id']} "
          f"distinct_question={qk['distinct_question_id']}")

    print(f"== point_id_population ==  {m['point_id_population']}")

    sl = m["shenlun_visible"]
    print("== shenlun visible ==")
    print(f"  total={sl['total']} options_empty={sl['options_empty_or_null']} "
          f"group_id_gt0={sl['group_id_gt_0']} group_id_eq0={sl['group_id_eq_0']}")

    g = m["question_groups"]
    print("== question_groups ==")
    print(f"  total={g['total']} with_visible={g['groups_with_visible_member']} "
          f"zero_visible={g['groups_with_0_visible_members']} zero_members={g['groups_with_0_members_all_statuses']}")

    g24, g1 = m["group_24"], m["group_1"]
    print(f"== group_24 ==  members={g24.get('member_count')} "
          f"distinct_sources={g24.get('distinct_source_count')} "
          f"shared_len={g24.get('shared_content_length')}")
    print(f"  head80: {g24.get('shared_content_head80')}")
    print(f"== group_1 ==  shared_len={g1.get('shared_content_length')}")
    print(f"  head80: {g1.get('shared_content_head80')}")

    print("== checks ==")
    for c in checks:
        line = f"  [{c['status']:<12}] {c['id']:<58} actual={c['actual']} expected={c['expected']}"
        if c.get("note"):
            line += f" ({c['note']})"
        print(line)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="三端题目计数一致性基线采集与校验（只读，stdlib only）",
    )
    ap.add_argument("--db", type=Path, default=DEFAULT_DB,
                    help=f"SQLite 数据库路径（默认 {DEFAULT_DB}）")
    ap.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT,
                    help=f"基线 JSON 输出路径（默认 {DEFAULT_JSON_OUT}）")
    ap.add_argument("--baseline", action="store_true",
                    help="采集并写入基线 JSON；即使检查失败退出码也为 0")
    ap.add_argument("--assert", dest="assert_mode", action="store_true",
                    help="执行一致性断言；任一检查失败则退出码 1")
    args = ap.parse_args(argv)

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
            getattr(sys.stderr, "reconfigure")(encoding="utf-8")
        except Exception:
            pass

    db_path = args.db.resolve()
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 2

    con = connect_readonly(db_path)
    try:
        metrics = collect_metrics(con)
    finally:
        con.close()

    checks = build_checks(metrics)
    failed = [c for c in checks if c["status"] == "fail"]

    doc = {
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "db_file_size_bytes": db_path.stat().st_size,
        "db_file_mtime": datetime.datetime.fromtimestamp(
            db_path.stat().st_mtime
        ).astimezone().isoformat(timespec="seconds"),
        "mode": "baseline" if args.baseline else ("assert" if args.assert_mode else "report"),
        "metrics": metrics,
        "checks": checks,
    }

    print_summary(metrics, checks)

    if args.baseline:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"BASELINE RECORDED; expected inconsistencies: {len(failed)}")
        print(f"JSON written to: {args.json_out}")
        return 0

    if args.assert_mode:
        if failed:
            print(f"ASSERT FAILED: {len(failed)} check(s) failed", file=sys.stderr)
            return 1
        print("ASSERT OK: all checks passed")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
