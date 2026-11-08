#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P5-0：资料状态 ↔ 可作答卷状态 的一致性巡检 / 修复（默认 dry-run）。

唯一真源（方案 §2.3）：`study_material.status`
  - 1 已上架 ──▶ 关联卷应为 PUBLISHED
  - 0 未上架 / -1 回收站 ──▶ 关联卷应为 DRAFT
  - 卷为 ENDED（回收站卷）──▶ **不动**（不因上架复活）
  - 关联键：`study_material.paper_code`（空则回落 `badge`）
  - 同一 `paper_code` 被多条资料引用时：**任一条 status=1 即 PUBLISHED**，全部不为 1 才 DRAFT

用法（在 backend/ 下执行）：
  python scripts/check_material_paper_drift.py                # 只报告（默认）
  python scripts/check_material_paper_drift.py --json         # 机器可读
  python scripts/check_material_paper_drift.py --apply        # 真的改（需人工确认后再跑）

退出码：0 = 无漂移；1 = 有漂移（dry-run）或修复后仍有异常；2 = 库不可用。

为什么单独一个脚本（而不是塞进端点）：
  · 走 API 会新增端点 → 触 R11（API 面 343 条冻结）；
  · 它是"运维核对/回滚"资产，不是业务功能；
  · dry-run 默认，永不会在无人看着时改数据。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
DEFAULT_DB = os.path.join(_BACKEND, "data", "question_bank.db")

PUBLISHED = "PUBLISHED"
DRAFT = "DRAFT"
ENDED = "ENDED"


def _conn(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        print(f"[ERR] 数据库不存在: {db_path}", file=sys.stderr)
        raise SystemExit(2)
    # 只读打开：dry-run 阶段绝不产生写入（WAL 模式下也不会触发 checkpoint 写）
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def collect(conn: sqlite3.Connection) -> tuple[list[dict], dict]:
    materials = list(conn.execute(
        "SELECT material_id, title, status, COALESCE(paper_code,''), COALESCE(badge,'') "
        "FROM study_material WHERE type='paper' AND status >= 0 ORDER BY material_id"
    ))
    papers = {
        row[0]: {"paper_id": row[0], "paper_type": row[1], "paper_name": row[2]}
        for row in conn.execute(
            "SELECT paper_id, paper_type, paper_name FROM exam_paper")
    }
    by_code: dict[str, list] = defaultdict(list)
    for mid, title, status, code, badge in materials:
        key = (code or badge or "").strip()
        by_code[key].append({"material_id": mid, "title": title,
                             "status": status, "paper_code": key})

    rows: list[dict] = []
    for code, mats in by_code.items():
        if not code:
            for m in mats:
                rows.append({**m, "expect": None, "actual": None,
                             "paper_id": None, "drift": False,
                             "skip": "empty_code"})
            continue
        paper = None
        # exam_paper 按 paper_code 关联（与 services/paper_registry.find_exam_by_code 同一口径）
        for row in conn.execute(
                "SELECT paper_id, paper_type, paper_name FROM exam_paper WHERE paper_code=?",
                (code,)):
            paper = {"paper_id": row[0], "paper_type": row[1], "paper_name": row[2]}
        if paper is None:
            for m in mats:
                rows.append({**m, "expect": None, "actual": None, "paper_id": None,
                             "drift": False, "skip": "no_paper"})
            continue
        if paper["paper_type"] == ENDED:
            for m in mats:
                rows.append({**m, "expect": ENDED, "actual": paper["paper_type"],
                             "paper_id": paper["paper_id"], "drift": False,
                             "skip": "ended"})
            continue
        expect = PUBLISHED if any(m["status"] == 1 for m in mats) else DRAFT
        for m in mats:
            rows.append({**m, "expect": expect, "actual": paper["paper_type"],
                         "paper_id": paper["paper_id"],
                         "drift": paper["paper_type"] != expect, "skip": None})
    return rows, papers


def main() -> int:
    ap = argparse.ArgumentParser(description="资料状态 ↔ 可作答卷 一致性巡检")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--apply", action="store_true", help="按真源修正 paper_type")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    conn = _conn(args.db)
    try:
        rows, papers = collect(conn)
    finally:
        conn.close()

    drift = [r for r in rows if r["drift"]]
    skipped: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["skip"]:
            skipped[r["skip"]] += 1

    if args.json:
        print(json.dumps({"rows": rows, "drift": drift,
                          "skipped": dict(skipped)}, ensure_ascii=False, indent=2))
    else:
        print("=" * 78)
        print("资料状态 ↔ 可作答卷 一致性巡检（唯一真源 = study_material.status）")
        print(f"库: {args.db}")
        print("=" * 78)
        print(f"{'资料':>6}  {'status':>6}  {'编号':<18} {'卷':>4}  {'现在':<10} {'应为':<10} 判定")
        for r in rows:
            flag = "漂移" if r["drift"] else (r["skip"] or "OK")
            print(f"{r['material_id']:>6}  {r['status']:>6}  {r['paper_code'] or '—':<18} "
                  f"{(r['paper_id'] if r['paper_id'] else '—'):>4}  "
                  f"{(r['actual'] or '—'):<10} {(r['expect'] or '—'):<10} {flag}")
        print("-" * 78)
        print(f"资料行 {len(rows)} 条 / 试卷 {len(papers)} 张 / "
              f"漂移 {len(drift)} 条 / 跳过 {dict(skipped) or '{}'}")
        if drift:
            print("\n漂移明细：")
            for r in drift:
                print(f"  · 资料 {r['material_id']}（status={r['status']}）"
                      f" {r['paper_code']} → 卷 #{r['paper_id']} "
                      f"{r['actual']} 应为 {r['expect']}")
            if not args.apply:
                print("\n（dry-run）加 --apply 才会真的改 paper_type")
        else:
            print("\n✅ 无漂移：资料可见性与可作答性一致")

    if not args.apply:
        return 1 if drift else 0

    # --apply：按真源修正（逐条 UPDATE，逐条打印）
    changed = 0
    raw = sqlite3.connect(args.db)
    try:
        for r in drift:
            raw.execute("UPDATE exam_paper SET paper_type=? WHERE paper_id=?",
                        (r["expect"], r["paper_id"]))
            changed += 1
            print(f"[apply] 卷 #{r['paper_id']} {r['actual']} → {r['expect']}"
                  f"（资料 {r['material_id']}，{datetime.now():%H:%M:%S}）")
        raw.commit()
    finally:
        raw.close()
    print(f"\n已修正 {changed} 条。建议复跑一次 dry-run 确认「漂移 0 条」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
