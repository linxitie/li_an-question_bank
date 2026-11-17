# -*- coding: utf-8 -*-
"""解析 三层知识分类.drawio，得到权威的「科目 → 知识点 → 考点 → 细分」树（v9 M1）。

为什么必须解析这张图而不是照搬数据库
--------------------------------------
数据库里的层级是导入脚本按题干猜出来的，猜不准时就落到「其他」；而这张 drawio 是
人工整理的权威分类。用户要求「每个知识点下的考点分类准确、考点之下不再有『其他』」，
所以先把图变成结构化 JSON，再拿它反过来校准数据库。

图的画法是「括号式大纲」而不是嵌套容器——子节点不在父节点 bbox 内，而是排在父节点
下方一行、横向依次排开。所以父节点判定用几何规则：
  1) 父节点 y 更小（在上方）；
  2) 子节点左边界落在父节点横向范围内；
  3) 多个候选时取「最近的上方」（y 最大），并列时取更窄的（更深的层级）。

用法：
    python backend/scripts/taxonomy/drawio_tree.py --drawio "C:/.../三层知识分类.drawio" \
        --out docs/design/taxonomy_drawio_v9.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

# 横向容差：图上同一列的方框左边界并非像素级对齐（实测 -215 / -210 混用），
# 容差太小会让整棵子树变成孤儿，太大又会把相邻列并进来。
X_TOL = 24.0

DEFAULT_DRAWIO = r"C:/Users/21499/OneDrive/Desktop/三层知识分类.drawio"
DEFAULT_OUT = "docs/design/taxonomy_drawio_v9.json"
SUBJECT_NAMES = ("行测", "申论", "公专")


def _text(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = re.sub(r"<[^>]+>", "", raw)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(s.split())


def load_nodes(path: str) -> List[Dict[str, Any]]:
    root = ET.parse(path).getroot()
    nodes: List[Dict[str, Any]] = []
    for cell in root.findall(".//mxCell"):
        if cell.get("vertex") != "1":
            continue
        geo = cell.find("mxGeometry")
        if geo is None:
            continue
        try:
            x = float(geo.get("x") or 0)
            y = float(geo.get("y") or 0)
            w = float(geo.get("width") or 0)
            h = float(geo.get("height") or 0)
        except (TypeError, ValueError):
            continue
        label = _text(cell.get("value"))
        if not label:
            continue
        nodes.append({"id": cell.get("id"), "name": label, "x": x, "y": y, "w": w, "h": h})
    return nodes


def build_tree(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按「最近的上方 + 横向包含」挂父节点，返回森林。"""
    ordered = sorted(nodes, key=lambda n: (n["y"], n["x"]))
    for n in ordered:
        n["children"] = []
        n["parent"] = None

    for i, child in enumerate(ordered):
        best: Optional[Dict[str, Any]] = None
        for parent in ordered[:i]:
            # 父节点需在子节点上方，且横向覆盖子节点左边界（含 2px 容差）
            if parent["y"] >= child["y"]:
                continue
            if not (parent["x"] - X_TOL <= child["x"] <= parent["x"] + parent["w"] + X_TOL):
                continue
            # 每一层的框宽是稳定的（科目 1200+ / 知识点 550 / 考点 170 / 细分 80），
            # 所以「同列兄弟」可以用宽度区分：父节点必须明显更宽，否则就是同一层的兄弟。
            # 少了这条，纵向堆叠的知识点会互相认成父子，整棵树的层级会被压扁。
            if parent["w"] < child["w"] * 1.4:
                continue
            if best is None:
                best = parent
                continue
            if parent["y"] > best["y"]:
                best = parent
            elif parent["y"] == best["y"] and parent["w"] < best["w"]:
                best = parent
        if best is not None:
            child["parent"] = best["id"]
            best["children"].append(child)

    roots = [n for n in ordered if n["parent"] is None]
    return roots


def annotate_depth(roots: List[Dict[str, Any]]) -> None:
    def walk(node: Dict[str, Any], depth: int) -> None:
        node["depth"] = depth
        for c in node["children"]:
            walk(c, depth + 1)

    for r in roots:
        walk(r, 0)


def flatten(roots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def walk(node: Dict[str, Any], trail: List[str]) -> None:
        path = trail + [node["name"]]
        rows.append({
            "name": node["name"],
            "depth": node["depth"],
            "path": " / ".join(path),
            "subject": path[0] if path else "",
            "knowledge_point": path[1] if len(path) > 1 else "",
            "point": path[2] if len(path) > 2 else "",
            "detail": path[3] if len(path) > 3 else "",
            "x": node["x"], "y": node["y"], "w": node["w"],
        })
        for c in node["children"]:
            walk(c, path)

    for r in roots:
        walk(r, [])
    return rows


def summarize(roots: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_subject: Dict[str, Dict[str, int]] = {}
    for r in rows:
        if r["depth"] == 0:
            continue
        bucket = by_subject.setdefault(r["subject"], {"knowledge_point": 0, "point": 0, "detail": 0})
        if r["depth"] == 1:
            bucket["knowledge_point"] += 1
        elif r["depth"] == 2:
            bucket["point"] += 1
        elif r["depth"] >= 3:
            bucket["detail"] += 1
    others = [r["path"] for r in rows if r["name"] == "其他" and r["depth"] >= 2]
    return {
        "roots": [{"name": r["name"], "children": len(r["children"]), "depth_max": _max_depth(r)} for r in roots],
        "by_subject": by_subject,
        "total_nodes": len(rows),
        "other_nodes": len(others),
        "other_paths_sample": others[:20],
    }


def _max_depth(node: Dict[str, Any]) -> int:
    if not node["children"]:
        return node["depth"]
    return max(_max_depth(c) for c in node["children"])


def strip_internal(roots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去掉 id/parent/几何字段，只留名字与层级，便于人读与版本比对。"""
    out = []
    for r in roots:
        node = {"name": r["name"], "level": _level_name(r["depth"]), "children": strip_internal(r["children"])}
        out.append(node)
    return out


def _level_name(depth: int) -> str:
    return {0: "科目", 1: "知识点", 2: "考点"}.get(depth, "细分")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drawio", default=DEFAULT_DRAWIO)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.isfile(args.drawio):
        raise SystemExit("找不到 drawio 文件：" + args.drawio)
    nodes = load_nodes(args.drawio)
    roots = build_tree(nodes)
    annotate_depth(roots)
    rows = flatten(roots)
    payload = {
        "source": args.drawio,
        "summary": summarize(roots, rows),
        "tree": strip_internal(roots),
        "flat": rows,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    s = payload["summary"]
    print("节点数", s["total_nodes"], "根节点", [r["name"] for r in s["roots"]])
    print("各科目层级数量", json.dumps(s["by_subject"], ensure_ascii=False))
    print("名为「其他」的节点", s["other_nodes"], "→ 写入", args.out)


if __name__ == "__main__":
    main()
