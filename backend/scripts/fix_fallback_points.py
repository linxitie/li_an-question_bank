#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""「其他（未细分）」收容叶子的治理脚本（默认 dry-run）。

背景（2026-11-14 实测）：
  3750 道可见题里 3115 道（83%）挂在名为「其他」的三级考点上，共 91 个 canonical
  节点，分散在 8 个子科目下。前端按 L2 下钻时，每个 L2 下面都挂着一个同名的「其他」，
  用户看到的就是"考点全叫其他、点进去还是其他"。这不是渲染 bug，是分类数据形态问题。

本脚本只做三件**可逆**的事，不动题干/答案/选项/子科目归属：
  R1 把 canonical L3 的裸名「其他」重命名为「其他（未细分）」——让前端能稳定识别
     "这是收容叶子，直接开练，不要再下钻"；
  R2 为「有题但没有任何收容节点」的子科目补建一个收容叶子，保证没有题目变成孤儿；
  R3 写审计 JSON（backend/data/audit/），支持 --revert 一键还原。

判定一律走名称，不新增 is_fallback 列：knowledge_point.alias_of 是历史 raw SQL 列，
ORM 模型没有它，加列会引出迁移与多库兼容风险（见 v6.0 方案 §3.3）。

用法：
  python scripts/fix_fallback_points.py            # dry-run，只打印计划
  python scripts/fix_fallback_points.py --apply    # 执行（先 sqlite3.backup 备份）
  python scripts/fix_fallback_points.py --revert   # 还原最近一次 apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BASE_DIR / "data" / "question_bank.db"
AUDIT_DIR = BASE_DIR / "data" / "audit"

FALLBACK_NEW = "其他（未细分）"
FALLBACK_LEGACY = "其他"
SUBJECT_NAMES = {1: "行测", 2: "申论", 3: "公专"}


def _has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in con.execute(f"PRAGMA table_info({table})"))


def _fallback_sql(has_alias: bool) -> str:
    """canonical L3「其他」的 WHERE 片段（alias_of 存在时排除已合并节点）"""
    extra = " AND (alias_of IS NULL OR alias_of = '')" if has_alias else ""
    return (
        "level = 3 AND status = 1 AND TRIM(point_name) = '" + FALLBACK_LEGACY + "'" + extra
    )


def load_plan(con: sqlite3.Connection) -> Dict[str, List[dict]]:
    """算出 R1/R2 的完整计划，dry-run 与 apply 共用同一份计算"""
    has_alias = _has_column(con, "knowledge_point", "alias_of")

    # 子科目：题目数 / 收容题数 / 现有收容节点
    subcats = {}
    for sc_id, subject_id, name in con.execute(
        "SELECT id, subject_id, name FROM sub_categories WHERE status = 1"
    ):
        subcats[int(sc_id)] = {
            "sub_category_id": int(sc_id),
            "subject_id": int(subject_id),
            "subject": SUBJECT_NAMES.get(int(subject_id), str(subject_id)),
            "name": str(name),
            "total_questions": 0,
            "fallback_questions": 0,
            "fallback_points": [],
        }

    # 每个考点的题量（可见口径：status=1 AND audit_status=1，与 QuestionStatsService 一致）
    # 按 (考点, 子科目) 双键计数：同一考点被跨子科目引用时不能重复计进两侧
    point_counts: Dict[tuple, int] = {}
    for point_id, sc_id, count in con.execute(
        "SELECT point_id, sub_category_id, COUNT(*) FROM question_bank "
        "WHERE status = 1 AND audit_status = 1 AND point_id IS NOT NULL "
        "GROUP BY point_id, sub_category_id"
    ):
        point_counts[(int(point_id), sc_id if sc_id is None else int(sc_id))] = int(count)

    null_by_subcat: Dict[int, int] = {}
    for sc_id, count in con.execute(
        "SELECT sub_category_id, COUNT(*) FROM question_bank "
        "WHERE status = 1 AND audit_status = 1 AND point_id IS NULL "
        "AND sub_category_id IS NOT NULL GROUP BY sub_category_id"
    ):
        null_by_subcat[int(sc_id)] = int(count)

    for sc_id, count in con.execute(
        "SELECT sub_category_id, COUNT(*) FROM question_bank "
        "WHERE status = 1 AND audit_status = 1 AND sub_category_id IS NOT NULL "
        "GROUP BY sub_category_id"
    ):
        if int(sc_id) in subcats:
            subcats[int(sc_id)]["total_questions"] = int(count)

    for row in con.execute(
        "SELECT point_id, point_name, sub_category_id FROM knowledge_point "
        "WHERE level = 3 AND status = 1"
    ):
        point_id, point_name, sc_id = int(row[0]), str(row[1] or ""), row[2]
        if sc_id is None or int(sc_id) not in subcats:
            continue
        name = point_name.strip()
        if name not in (FALLBACK_NEW, FALLBACK_LEGACY):
            continue
        sc = subcats[int(sc_id)]
        matched = point_counts.get((point_id, int(sc_id)), 0)
        sc["fallback_points"].append(
            {"point_id": point_id, "point_name": name, "questions": matched}
        )
        sc["fallback_questions"] += matched

    for sc_id, count in null_by_subcat.items():
        if sc_id in subcats:
            subcats[sc_id]["fallback_questions"] += count

    renames: List[dict] = []
    creates: List[dict] = []
    for sc in subcats.values():
        for item in sc["fallback_points"]:
            if item["point_name"] == FALLBACK_LEGACY:
                renames.append({**item, "sub_category_id": sc["sub_category_id"],
                                "to": FALLBACK_NEW})
        if sc["fallback_questions"] > 0 and not sc["fallback_points"]:
            creates.append({
                "sub_category_id": sc["sub_category_id"],
                "subject_id": sc["subject_id"],
                "subject": sc["subject"],
                "sub_category": sc["name"],
                "point_name": FALLBACK_NEW,
                "questions": sc["fallback_questions"],
            })
        sc["fallback_points"].sort(key=lambda item: item["point_id"])

    return {"subcats": list(subcats.values()), "renames": renames, "creates": creates}


def print_plan(plan: Dict[str, List[dict]]) -> None:
    print("== 子科目一览 ==")
    print(f"{'子科目ID':>8} {'科目':<4} {'子科目':<16} {'题量':>6} {'收容题':>6} {'收容节点':>8}")
    for sc in plan["subcats"]:
        print(f"{sc['sub_category_id']:>8} {sc['subject']:<4} {sc['name'][:16]:<16} "
              f"{sc['total_questions']:>6} {sc['fallback_questions']:>6} "
              f"{len(sc['fallback_points']):>8}")
    print()
    print(f"R1 待重命名「其他」→「{FALLBACK_NEW}」：{len(plan['renames'])} 个")
    for item in plan["renames"][:10]:
        print(f"   point_id={item['point_id']} 题量={item['questions']}")
    if len(plan["renames"]) > 10:
        print(f"   ... 其余 {len(plan['renames']) - 10} 个")
    print(f"R2 待补建收容叶子：{len(plan['creates'])} 个")
    for item in plan["creates"]:
        print(f"   {item['subject']}/{item['sub_category']} 收容题量={item['questions']}")


def backup_db(db_path: Path) -> Path:
    """R10：WAL 模式下必须用 sqlite3.backup()，shutil.copy2 会丢 -wal 内容"""
    target = db_path.parent / f"question_bank.bak_fallback_{time.strftime('%Y%m%d_%H%M%S')}.db"
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def apply_plan(con: sqlite3.Connection, plan: Dict[str, List[dict]]) -> dict:
    has_alias = _has_column(con, "knowledge_point", "alias_of")
    where = _fallback_sql(has_alias)
    renamed: List[int] = []
    for item in plan["renames"]:
        con.execute(
            "UPDATE knowledge_point SET point_name = ? WHERE point_id = ? AND " + where,
            (FALLBACK_NEW, item["point_id"]),
        )
        renamed.append(item["point_id"])

    created: List[int] = []
    for item in plan["creates"]:
        cur = con.execute(
            "INSERT INTO knowledge_point "
            "(point_name, subject_id, sub_category_id, parent_id, level, description, "
            " sort_order, status) VALUES (?, ?, ?, 0, 3, ?, 999, 1)",
            (
                FALLBACK_NEW,
                item["subject_id"],
                item["sub_category_id"],
                "导入时无法归入具体考点的题目统一收容于此，可直接练习",
            ),
        )
        created.append(int(cur.lastrowid))
    return {"renamed": renamed, "created": created}


def write_audit(record: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"fallback_points_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_audit() -> Path:
    files = sorted(AUDIT_DIR.glob("fallback_points_*.json"))
    if not files:
        raise SystemExit("没有可还原的审计记录（backend/data/audit/fallback_points_*.json）")
    return files[-1]


def revert(db_path: Path, audit_path: Path) -> None:
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    con = sqlite3.connect(str(db_path))
    try:
        for point_id in record.get("renamed", []):
            con.execute(
                "UPDATE knowledge_point SET point_name = ? WHERE point_id = ?",
                (FALLBACK_LEGACY, point_id),
            )
        for point_id in record.get("created", []):
            con.execute("DELETE FROM knowledge_point WHERE point_id = ?", (point_id,))
        con.commit()
    finally:
        con.close()
    print(f"已还原：{audit_path}（重命名 {len(record.get('renamed', []))} 个，"
          f"删除新建 {len(record.get('created', []))} 个）")


def main() -> None:
    parser = argparse.ArgumentParser(description="「其他（未细分）」收容叶子治理")
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
            print("\n[dry-run] 未写库。确认无误后加 --apply 执行。")
            return

        backup = backup_db(db_path)
        print(f"\n已备份：{backup}")
        result = apply_plan(con, plan)
        con.commit()
    finally:
        con.close()

    audit = write_audit({
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db": str(db_path),
        **result,
    })
    print(f"完成：重命名 {len(result['renamed'])} 个，新建 {len(result['created'])} 个")
    print(f"审计记录：{audit}")


if __name__ == "__main__":
    main()
