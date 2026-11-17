# -*- coding: utf-8 -*-
"""用 drawio 权威分类校准数据库的三层结构（v9 M1）。

数据库真实结构（实测，2026-11-14）：
    科目 question_subject
      └─ 知识点 sub_categories（16 行：行测 7 + 科学推理，申论 5，公专 3）
           └─ 考点 knowledge_point.level=2（parent_id=0，sub_category_id 指向知识点）
                └─ 细分 knowledge_point.level=3（parent_id 指向考点）

drawio（三层知识分类.drawio）给出同一套三层的权威命名，本脚本把两边的名字做差集，
输出「缺考点 / 缺细分 / DB 独有 / 「其他」节点」四张表；--apply 时只做加法（补建缺失节点），
不删、不改名、不重挂任何历史行 —— 历史练习记录依赖 point_id 取名，删改会造成二次断链。

用法（必须在 backend 目录下运行，否则 SQLite 相对路径会连到空库）：
    cd backend
    PYTHONIOENCODING=utf-8 python scripts/taxonomy/verify_tree.py
    PYTHONIOENCODING=utf-8 python scripts/taxonomy/verify_tree.py --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import KnowledgePoint  # noqa: E402
from sqlalchemy import text  # noqa: E402

SUBJECT_BY_NAME = {"行测": 1, "申论": 2, "公专": 3}
DEFAULT_TREE = "../docs/design/taxonomy_drawio_v9.json"
DEFAULT_REPORT = "../docs/design/taxonomy_diff_v9.json"
OTHER_NAMES = {"其他", "其他（未细分）", "未分类", "未细分"}


def load_tree(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_sub_categories(db) -> List[Dict[str, Any]]:
    rows = db.execute(text("select id, subject_id, name from sub_categories order by subject_id, sort_order, id")).fetchall()
    return [{"id": int(r[0]), "subject_id": int(r[1]), "name": (r[2] or "").strip()} for r in rows]


def load_points(db) -> List[Dict[str, Any]]:
    rows = db.query(KnowledgePoint).filter(KnowledgePoint.level.in_([2, 3])).all()
    return [
        {
            "id": int(r.point_id),
            "name": (r.point_name or "").strip(),
            "subject_id": int(r.subject_id or 0),
            "parent_id": int(r.parent_id or 0),
            "sub_category_id": int(r.sub_category_id or 0),
            "level": int(r.level or 0),
        }
        for r in rows
    ]


def compare(tree: Dict[str, Any], db) -> Dict[str, Any]:
    flat = tree.get("flat", [])
    scs = load_sub_categories(db)
    points = load_points(db)
    sc_by_subject: Dict[int, List[Dict[str, Any]]] = {}
    for sc in scs:
        sc_by_subject.setdefault(sc["subject_id"], []).append(sc)
    l2_by_sc: Dict[int, List[Dict[str, Any]]] = {}
    for p in points:
        if p["level"] == 2:
            l2_by_sc.setdefault(p["sub_category_id"], []).append(p)
    l3_by_parent: Dict[int, List[Dict[str, Any]]] = {}
    for p in points:
        if p["level"] == 3:
            l3_by_parent.setdefault(p["parent_id"], []).append(p)

    report: Dict[str, Any] = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "subjects": {}}

    for subject_name, subject_id in SUBJECT_BY_NAME.items():
        rows = [r for r in flat if r["subject"] == subject_name]
        want_kp = []
        for r in rows:
            if r["depth"] == 1 and r["name"] not in want_kp:
                want_kp.append(r["name"])

        db_kp = {s["name"]: s for s in sc_by_subject.get(subject_id, [])}
        subject_report = {
            "db_knowledge_points": len(db_kp),
            "want_knowledge_points": len(want_kp),
            "missing_knowledge_point": [n for n in want_kp if n not in db_kp],
            "db_only_knowledge_point": [n for n in db_kp if n not in want_kp],
            "points": {},
            "questions": int(db.execute(text("select count(*) from question_bank where subject_id=:s"), {"s": subject_id}).scalar() or 0),
        }

        for kp_name in want_kp:
            want_points: List[str] = []
            for r in rows:
                if r["depth"] == 2 and r["knowledge_point"] == kp_name and r["name"] not in want_points:
                    want_points.append(r["name"])
            sc = db_kp.get(kp_name)
            have = l2_by_sc.get(sc["id"], []) if sc else []
            have_names = [p["name"] for p in have]
            detail_want = sum(1 for r in rows if r["depth"] >= 3 and r["knowledge_point"] == kp_name)
            detail_have = sum(len(l3_by_parent.get(p["id"], [])) for p in have)
            subject_report["points"][kp_name] = {
                "sub_category_id": sc["id"] if sc else None,
                "db_points": len(have),
                "want_points": len(want_points),
                "missing_points": [n for n in want_points if n not in have_names],
                "db_only_points": [n for n in have_names if n not in want_points],
                "db_other_points": [n for n in have_names if n in OTHER_NAMES],
                "detail_db": detail_have,
                "detail_want": detail_want,
                "question_count": sum(
                    int(db.execute(text("select count(*) from question_bank where point_id=:p"), {"p": p["id"]}).scalar() or 0)
                    for p in have
                ),
            }
        report["subjects"][subject_name] = subject_report
    return report


def _best_point(name: str, candidates: List[str], detail_names: Dict[str, List[str]]) -> str:
    """把一个 drawio 里不存在的考点名，归到最接近的 drawio 考点。

    先看是否互为子串（「中国特色社会主义理论体系」→「习近平新时代中国特色社会主义思想」不会命中，
    但「二十大精神」→「党的二十大精神」会命中），再用 difflib 相似度兜底，
    比较对象包含该考点自己的细分名，避免只看考点名而错配。
    """
    from difflib import SequenceMatcher

    best, best_score = "", 0.0
    for cand in candidates:
        pool = [cand] + detail_names.get(cand, [])
        score = 0.0
        for item in pool:
            if name and (name in item or item in name):
                score = max(score, 0.95)
            score = max(score, SequenceMatcher(None, name, item).ratio())
        if score > best_score:
            best, best_score = cand, score
    return best or (candidates[0] if candidates else "")


def _merge_into(db, src_id: int, dst_id: int) -> int:
    """把 src 节点上的题目改挂到 dst，然后删除 src（合并同名兄弟节点）。

    唯一约束 (subject_id, sub_category_id, parent_id, point_name) 不允许同一父级下出现两个同名节点，
    历史导入留下的同名「其他」在改 parent 时会直接撞约束，所以必须「先合并同名、再改挂」。
    """
    moved = db.execute(
        text("update question_bank set point_id=:d where point_id=:s"), {"d": dst_id, "s": src_id}
    ).rowcount or 0
    for sql in (
        "update question_knowledge set point_id=:d where point_id=:s",
        "update point_assign_audit set new_point_id=:d where new_point_id=:s",
        "update point_assign_audit set old_point_id=:d where old_point_id=:s",
    ):
        try:
            db.execute(text(sql), {"d": dst_id, "s": src_id})
        except Exception:
            pass
    try:
        db.execute(text("update knowledge_point set parent_id=:d where parent_id=:s"), {"d": dst_id, "s": src_id})
    except Exception:
        pass
    db.execute(text("delete from knowledge_point where point_id=:s"), {"s": src_id})
    return int(moved)


def _demote(db, node_id: int, target_id: int, want_level: int = 3) -> str:
    """把节点挂到 target 下（默认 level=3）；同名兄弟已存在则合并。"""
    node = db.query(KnowledgePoint).filter(KnowledgePoint.point_id == node_id).first()
    if node is None:
        return "gone"
    dup = db.query(KnowledgePoint).filter(
        KnowledgePoint.parent_id == target_id,
        KnowledgePoint.level == want_level,
        KnowledgePoint.point_name == node.point_name,
        KnowledgePoint.point_id != node_id,
    ).first()
    if dup is not None:
        _merge_into(db, int(node.point_id), int(dup.point_id))
        return "merged"
    node.parent_id = target_id
    node.level = want_level
    db.flush()
    return "moved"


def apply_tree(tree: Dict[str, Any], db) -> Dict[str, Any]:
    """按 drawio 校准：补建缺失考点、把 drawio 之外的平铺考点下沉为细分。

    规则（可回滚，备份见 data/backups/question_bank_pre_v9tree_*.db）：
      1) drawio 有的考点/细分，DB 没有就新建；
      2) drawio 没有、但 DB 存在的考点（含大量「其他」）下沉为 level=3 细分并挂到最接近的 drawio 考点；
      3) 下沉节点的既有子节点一并改挂到同一考点；同名冲突走合并（题目先迁移再删节点）；
      4) 题目 point_id 只在合并时迁移，其余不动：题量由考点汇总子节点得出，历史练习记录不失效。
    """
    flat = tree.get("flat", [])
    stats = {"knowledge_point": 0, "point": 0, "detail": 0, "demoted": 0, "reparented": 0, "merged": 0, "moved_questions": 0}

    for subject_name, subject_id in SUBJECT_BY_NAME.items():
        rows = [r for r in flat if r["subject"] == subject_name]
        scs = {s["name"]: s for s in load_sub_categories(db) if s["subject_id"] == subject_id}

        for kp_name, sc in scs.items():
            want_points: List[str] = []
            detail_names: Dict[str, List[str]] = {}
            for r in rows:
                if r["depth"] == 2 and r["knowledge_point"] == kp_name:
                    if r["name"] not in want_points:
                        want_points.append(r["name"])
                        detail_names[r["name"]] = []
                elif r["depth"] >= 3 and r["knowledge_point"] == kp_name:
                    detail_names.setdefault(r["point"], []).append(r["name"])
            if not want_points:
                continue

            points = load_points(db)
            existing = [p for p in points if p["level"] == 2 and p["sub_category_id"] == sc["id"]]
            by_name = {p["name"]: p for p in existing}
            for name in want_points:
                if name in by_name:
                    continue
                obj = KnowledgePoint(
                    point_name=name, subject_id=subject_id, sub_category_id=sc["id"],
                    parent_id=0, level=2, description="", sort_order=0, status=1,
                )
                db.add(obj)
                db.flush()
                stats["point"] += 1
                by_name[name] = {"id": int(obj.point_id), "name": name, "level": 2,
                                 "parent_id": 0, "sub_category_id": sc["id"], "subject_id": subject_id}

            for p in existing:
                if p["name"] in want_points:
                    continue
                target = _best_point(p["name"], want_points, detail_names)
                if not target:
                    continue
                target_id = by_name[target]["id"]
                kids = [
                    int(k.point_id)
                    for k in db.query(KnowledgePoint).filter(
                        KnowledgePoint.level == 3, KnowledgePoint.parent_id == p["id"]
                    ).all()
                ]
                result = _demote(db, p["id"], target_id)
                if result == "merged":
                    stats["merged"] += 1
                    stats["moved_questions"] += 0
                elif result == "moved":
                    stats["demoted"] += 1
                for kid_id in kids:
                    r2 = _demote(db, kid_id, target_id)
                    if r2 == "merged":
                        stats["merged"] += 1
                    elif r2 == "moved":
                        stats["reparented"] += 1
            db.commit()

            for pt_name, details in detail_names.items():
                parent = by_name.get(pt_name)
                if parent is None:
                    continue
                have = {
                    (r.point_name or "").strip()
                    for r in db.query(KnowledgePoint).filter(
                        KnowledgePoint.level == 3, KnowledgePoint.parent_id == parent["id"]
                    ).all()
                }
                for dname in details:
                    if dname in have:
                        continue
                    db.add(KnowledgePoint(
                        point_name=dname, subject_id=subject_id, sub_category_id=sc["id"],
                        parent_id=parent["id"], level=3, description="", sort_order=0, status=1,
                    ))
                    have.add(dname)
                    stats["detail"] += 1
            db.commit()
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default=DEFAULT_TREE)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    tree = load_tree(args.tree)
    db = SessionLocal()
    try:
        report = compare(tree, db)
        os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        for name, s in report["subjects"].items():
            print(
                "==",
                name,
                "| 知识点 DB/drawio = %d/%d" % (s["db_knowledge_points"], s["want_knowledge_points"]),
                "| 缺考点",
                sum(len(v["missing_points"]) for v in s["points"].values()),
                "| 缺细分",
                sum(max(0, v["detail_want"] - v["detail_db"]) for v in s["points"].values()),
                "| DB 独有考点",
                sum(len(v["db_only_points"]) for v in s["points"].values()),
                "| 「其他」考点",
                sum(len(v["db_other_points"]) for v in s["points"].values()),
            )
        print("差异报告 →", args.report)
        if args.apply:
            print("落库：", json.dumps(apply_tree(tree, db), ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
