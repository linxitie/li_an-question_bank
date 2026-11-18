# -*- coding: utf-8 -*-
"""v8 P0：导出三层分类基线快照（科目 → 知识点 → 考点）与对照表。

只读：不写数据库，只在 docs/design/ 下产出两个文件。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "data" / "question_bank.db"
OUT_DIR = Path(__file__).resolve().parents[3] / "docs" / "design"

# 5 处命名漂移：库内旧名 → drawio 规范名。只做映射不改名，避免破坏题点引用。
NAME_DRIFT = {
    "定义推理": "定义判断",
    "逻辑推理": "逻辑判断",
    "事务写作": "事务文书",
    "策论文": "策论文",
    "政策文": "政论文",
    "政治敏锐性能够与鉴别力": "政治敏锐性与鉴别力",
}


def main() -> none:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)  # noqa: F841
    conn.row_factory = sqlite3.Row
    subjects = [dict(r) for r in conn.execute(
        "SELECT subject_id, subject_name FROM question_subject ORDER BY subject_id")]
    tree = []
    for subj in subjects:
        subs = []
        for sc in conn.execute(
            "SELECT id, name, subject_id FROM sub_categories WHERE subject_id=? ORDER BY id",
            (subj["subject_id"],),
        ):
            points = []
            for kp in conn.execute(
                """SELECT point_id, point_name, level, status, alias_of, sort_order
                   FROM knowledge_point
                   WHERE sub_category_id=? AND level=2 AND status=1 AND alias_of IS NULL
                   ORDER BY sort_order, point_id""",
                (sc["id"],),
            ):
                n = conn.execute(
                    "SELECT count(*) FROM question_bank WHERE point_id=?",
                    (kp["point_id"],),
                ).fetchone()[0]
                n_kids = conn.execute(
                    """SELECT count(*) FROM question_bank q
                       JOIN knowledge_point k ON k.point_id=q.point_id
                       WHERE k.parent_id=? AND k.status=1""",
                    (kp["point_id"],),
                ).fetchone()[0]
                points.append({
                    "point_id": kp["point_id"],
                    "name": NAME_DRIFT.get(kp["point_name"], kp["point_name"]),
                    "raw_name": kp["point_name"],
                    "direct_questions": n,
                    "child_questions": n_kids,
                })
            fallback = [r["point_id"] for r in conn.execute(
                """SELECT point_id FROM knowledge_point
                   WHERE sub_category_id=? AND level=3 AND status=1 AND alias_of IS NULL
                     AND point_name LIKE '其他%'""",
                (sc["id"],),
            )]
            subs.append({
                "sub_category_id": sc["id"],
                "name": sc["name"],
                "exam_points": points,
                "fallback_point_ids": fallback,
            })
        tree.append({"subject_id": subj["subject_id"], "name": subj["subject_name"],
                     "sub_categories": subs})
    conn.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "三层分类基线_v1.json").write_text(
        json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 三层分类对照表 v1（科目 → 知识点 → 考点）", "",
             "> 由 `backend/scripts/taxonomy/export_baseline.py` 实测生成，勿手改。",
             "> 「直挂题量」= 题目 point_id 直接指向该考点；「子级题量」= 挂在该考点下三级子节点的题量。",
             ""]
    for subj in tree:
        lines.append(f"## {subj['name']}（subject {subj['subject_id']}）")
        lines.append("")
        lines.append("| 知识点 | 考点 | 直挂题量 | 子级题量 | 收容节点数 |")
        lines.append("|---|---|---|---|---|")
        for sc in subj["sub_categories"]:
            if not sc["exam_points"]:
                lines.append(f"| {sc['name']} | （无） | 0 | 0 | {len(sc['fallback_point_ids'])} |")
            for i, p in enumerate(sc["exam_points"]):
                head = sc["name"] if i == 0 else ""
                lines.append(
                    f"| {head} | {p['name']} | {p['direct_questions']} | {p['child_questions']} "
                    f"| {len(sc['fallback_point_ids']) if i == 0 else ''} |")
        lines.append("")
    (OUT_DIR / "三层分类对照表_v1.md").write_text("\n".join(lines), encoding="utf-8")
    total = sum(len(s["exam_points"]) for subj in tree for s in subj["sub_categories"])
    print(f"OK subjects={len(tree)} exam_points={total}")
    print(f"wrote {(OUT_DIR / '三层分类基线_v1.json')}")
    print(f"wrote {(OUT_DIR / '三层分类对照表_v1.md')}")


if __name__ == "__main__":
    main()
