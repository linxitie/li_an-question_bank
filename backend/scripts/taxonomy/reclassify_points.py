# -*- coding: utf-8 -*-
"""v8 P2：把题目从收容节点重新分配到 91 个规范考点。

三档策略（见方案 M2）：
- auto   ：分数 >= 6 且领先第二名 >= 2 → 可直接落库
- review ：分数 >= 3 → 写进人工复核队列，不自动改
- unmatched：保留在收容节点（「其他（未细分）」），前端可直练

用法：
  python scripts/taxonomy/reclassify_points.py --dry-run            # 只出报告
  python scripts/taxonomy/reclassify_points.py --apply --batch-id v8-20261114
  python scripts/taxonomy/reclassify_points.py --apply --include-review --batch-id ...
  python scripts/taxonomy/reclassify_points.py --revert --batch-id v8-20261114
  python scripts/taxonomy/reclassify_points.py --dry-run --subject 1
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.taxonomy.classifier import classify, classify_cross  # noqa: E402

DB_PATH = ROOT / "data" / "question_bank.db"
OUT_DIR = ROOT.parent / "docs" / "design"


def load_questions(conn: sqlite3.Connection, subject: int | None, limit: int | None):
    sql = """SELECT qb.question_id, qb.subject_id, qb.sub_category_id AS sc_id,
                    qb.question_content, qb.options, qb.point_id AS old_point_id,
                    kp.point_name AS old_name, sc.name AS sc_name,
                    qg.shared_content AS group_content
             FROM question_bank qb
             LEFT JOIN knowledge_point kp ON kp.point_id = qb.point_id
             LEFT JOIN sub_categories sc ON sc.id = qb.sub_category_id
             LEFT JOIN question_groups qg ON qg.id = qb.group_id
             WHERE qb.status = 1"""
    args: list = []
    if subject:
        sql += " AND qb.subject_id = ?"
        args.append(subject)
    sql += " ORDER BY qb.question_id"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)
    return conn.execute(sql, args).fetchall()


def run(dry_run: bool, subject: int | None, limit: int | None,
        include_review: bool, batch_id: str, fix_subcategory: bool = False) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = load_questions(conn, subject, limit)

    stats = Counter()
    by_point = Counter()
    by_sc_tier = defaultdict(Counter)
    sc_fix = Counter()          # 知识点被纠正的题数（auto/review 分档）
    sc_pairs = Counter()        # (原知识点, 新知识点) 迁移流向
    samples: dict[str, list] = {"auto": [], "review": [], "unmatched": [], "sc_fix": []}
    plan: list[tuple] = []
    review_rows: list[tuple] = []

    for r in rows:
        if fix_subcategory:
            res = classify_cross(r["question_content"], r["subject_id"], r["sc_id"],
                                 options_text=r["options"], context_text=r["group_content"])
        else:
            res = classify(r["question_content"], r["sc_id"],
                           options_text=r["options"], subject_id=r["subject_id"],
                           context_text=r["group_content"])
        tier = res["tier"]
        stats[tier] += 1
        by_sc_tier[r["sc_name"] or "?"][tier] += 1
        if tier == "auto":
            by_point[res["name"]] += 1
            if len(samples["auto"]) < 12:
                samples["auto"].append({"qid": r["question_id"], "sc": r["sc_name"],
                                        "to": res["name"], "score": res["score"],
                                        "hits": res["hits"]})
        elif tier == "review" and len(samples["review"]) < 12:
            samples["review"].append({"qid": r["question_id"], "sc": r["sc_name"],
                                      "to": res["name"], "score": res["score"],
                                      "margin": res["margin"], "hits": res["hits"]})
        elif tier == "unmatched" and len(samples["unmatched"]) < 8:
            samples["unmatched"].append({"qid": r["question_id"], "sc": r["sc_name"],
                                         "head": (r["question_content"] or "")[:60]})

        # 知识点纠正只在 auto 档做：review 档本身低置信，
        # 再顺带改题目归属知识点会把误差放大一倍（一个错考点变成两处错数据）。
        new_sc = None
        if fix_subcategory and res.get("sc_changed") and tier == "auto":
            new_sc = res["sc_id"]
            sc_fix[tier] += 1
            sc_pairs[(r["sc_name"] or "?", res["name"])] += 1
            if len(samples["sc_fix"]) < 12:
                samples["sc_fix"].append({"qid": r["question_id"], "from_sc": r["sc_name"],
                                          "to_sc": new_sc, "to_point": res["name"],
                                          "score": res["score"], "margin": res["margin"],
                                          "head": (r["question_content"] or "")[:50],
                                          "hits": res["hits"]})

        if tier == "review" and res["point_id"] and res["point_id"] != r["old_point_id"]:
            review_rows.append((batch_id, r["question_id"], r["old_point_id"], res["point_id"],
                                res["score"], "review",
                                json.dumps({"hits": res["hits"], "margin": res["margin"]},
                                           ensure_ascii=False), r["sc_id"], None))

        actionable = tier == "auto" or (tier == "review" and include_review)
        # 已经是该考点的题不必再写审计，否则每跑一次就多一份噪声
        if actionable and res["point_id"] and (res["point_id"] != r["old_point_id"] or new_sc):
            reason = {"hits": res["hits"]}
            if new_sc:
                reason["sc_fix"] = {"from": r["sc_id"], "to": new_sc}
            plan.append((r["question_id"], r["old_point_id"], res["point_id"],
                         res["score"], tier, json.dumps(reason, ensure_ascii=False),
                         batch_id, r["sc_id"], new_sc))

    total = len(rows)
    covered = stats["auto"] + stats["review"]
    print(f"题目总数 {total} | auto {stats['auto']} | review {stats['review']} "
          f"| unmatched {stats['unmatched']}")
    if total:
        print(f"可定位率 (auto+review)/total = {covered / total:.1%}")
    if fix_subcategory:
        print(f"知识点纠正（auto 档）= {sc_fix['auto']} 题")
    print("按知识点分档：")
    for sc, c in sorted(by_sc_tier.items(), key=lambda x: -sum(x[1].values())):
        t = sum(c.values())
        print(f"  {sc:10s} n={t:5d} auto={c['auto']:5d} review={c['review']:4d} "
              f"unmatched={c['unmatched']:4d}")

    if dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "考点重分配_dryrun.json").write_text(json.dumps({
            "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "total": total, "stats": dict(stats),
            "by_sub_category": {k: dict(v) for k, v in by_sc_tier.items()},
            "top_points": by_point.most_common(30),
            "sc_fix": {"auto": sc_fix["auto"],
                       "pairs": [{"from": k[0], "to_point": k[1], "n": v}
                                 for k, v in sc_pairs.most_common(40)]},
            "samples": samples,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report -> {OUT_DIR / '考点重分配_dryrun.json'}")
    else:
        if not plan:
            print("没有可落库的分配，退出")
            conn.close()
            return
        if include_review:
            print("注意：本次包含 review 档（低置信），落库后需人工复核")
        with conn:
            conn.executemany(
                """INSERT INTO point_assign_audit
                   (batch_id, question_id, old_point_id, new_point_id, score, tier, reason,
                    old_sub_category_id, new_sub_category_id)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                [(b, q, o, n, s, t, rsn, osc, nsc)
                 for (q, o, n, s, t, rsn, b, osc, nsc) in plan])
            conn.executemany("UPDATE question_bank SET point_id=? WHERE question_id=?",
                             [(n, q) for (q, _o, n, _s, _t, _r, _b, _osc, _nsc) in plan])
            sc_rows = [(nsc, q) for (q, _o, _n, _s, _t, _r, _b, _osc, nsc) in plan if nsc]
            if sc_rows:
                conn.executemany(
                    "UPDATE question_bank SET sub_category_id=? WHERE question_id=?", sc_rows)
        # 复核队列按新方案重建：先作废与当前库状态不一致的旧提案，
        # 再写入本次 review 档，保证老师看到的就是「当前需要判断的题」。
        with conn:
            if review_rows:
                q_marks = ",".join("?" * len(review_rows))
                conn.execute(
                    f"DELETE FROM point_assign_audit WHERE review_status='pending' "
                    f"AND question_id IN ({q_marks})",
                    [row[1] for row in review_rows])
            conn.execute(
                """UPDATE point_assign_audit SET review_status='superseded'
                   WHERE review_status='pending' AND EXISTS (
                       SELECT 1 FROM question_bank qb
                       WHERE qb.question_id = point_assign_audit.question_id
                         AND (qb.point_id IS NULL OR qb.point_id != point_assign_audit.new_point_id))""")
            if review_rows:
                conn.executemany(
                    """INSERT INTO point_assign_audit
                       (batch_id, question_id, old_point_id, new_point_id, score, tier, reason,
                        old_sub_category_id, new_sub_category_id, review_status)
                       VALUES (?,?,?,?,?,?,?,?,?, 'pending')""",
                    [(b, q, o, n, s, t, rsn, osc, nsc) for (b, q, o, n, s, t, rsn, osc, nsc) in review_rows])
        pending = conn.execute(
            "SELECT COUNT(*) FROM point_assign_audit WHERE review_status='pending'").fetchone()[0]
        print(f"已落库 {len(plan)} 题，batch_id={batch_id}，其中纠正知识点 {len(sc_rows)} 题")
        print(f"复核队列已同步：待复核 {pending} 题（本次 review 档 {len(review_rows)}）")
    conn.close()


def revert(batch_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""SELECT question_id, old_point_id, old_sub_category_id,
                                  new_sub_category_id
                           FROM point_assign_audit
                           WHERE batch_id=? ORDER BY audit_id""", (batch_id,)).fetchall()
    if not rows:
        print(f"batch {batch_id} 无审计记录")
        conn.close()
        return
    with conn:
        conn.executemany("UPDATE question_bank SET point_id=? WHERE question_id=?",
                         [(r["old_point_id"], r["question_id"]) for r in rows])
        # 只还原本次真正改过知识点的题，避免把其它批次设的知识点抹成 NULL
        sc_rows = [(r["old_sub_category_id"], r["question_id"])
                   for r in rows if r["new_sub_category_id"] is not None]
        if sc_rows:
            conn.executemany(
                "UPDATE question_bank SET sub_category_id=? WHERE question_id=?", sc_rows)
    print(f"已回滚 {len(rows)} 题（batch {batch_id}，含知识点 {len(sc_rows)} 题）")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--include-review", action="store_true")
    ap.add_argument("--fix-subcategory", action="store_true",
                    help="跨知识点纠正：命中考点属于另一知识点时同步改 sub_category_id（仅 auto 档）")
    ap.add_argument("--subject", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch-id", default="v8-pilot")
    a = ap.parse_args()
    if a.revert:
        revert(a.batch_id)
    else:
        run(dry_run=not a.apply, subject=a.subject, limit=a.limit,
            include_review=a.include_review, batch_id=a.batch_id,
            fix_subcategory=a.fix_subcategory)
