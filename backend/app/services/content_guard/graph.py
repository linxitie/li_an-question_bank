"""三层本体图谱：政策层 / 审核层 / 舆情层共用一套边表。

不引入 Neo4j 作为强依赖：cg_edge 是事实源，可按需投影到 foundation GraphStore；
图查询（邻居、子图、概览）都直接走 SQLite，规模在数十万边以内足够。
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...models.content_guard import CgCase, CgEdge, CgJudgment, CgPolicy, CgProposal, CgTask, CgTerm, CgVariant

NODE_TYPES = {
    "policy", "term", "variant", "judgment", "task", "proposal", "case", "category", "event",
}
RELATIONS = {
    "cites", "belongs_to", "triggers", "variant_of", "derived_from", "review_of",
    "proposed", "co_occurs", "overrides", "related_to",
}


def add_edge(
    db: Session,
    src_type: str,
    src_id: Any,
    rel: str,
    dst_type: str,
    dst_id: Any,
    *,
    weight: float = 1.0,
    props: Optional[dict] = None,
) -> Optional[CgEdge]:
    if src_type not in NODE_TYPES or dst_type not in NODE_TYPES or rel not in RELATIONS:
        return None
    src_s, dst_s = str(src_id), str(dst_id)
    existing = (
        db.query(CgEdge)
        .filter(
            CgEdge.src_type == src_type,
            CgEdge.src_id == src_s,
            CgEdge.rel == rel,
            CgEdge.dst_type == dst_type,
            CgEdge.dst_id == dst_s,
        )
        .first()
    )
    if existing:
        return existing
    edge = CgEdge(
        src_type=src_type,
        src_id=src_s,
        rel=rel,
        dst_type=dst_type,
        dst_id=dst_s,
        weight=weight,
        props=props or {},
    )
    db.add(edge)
    return edge


def node_label(db: Session, node_type: str, node_id: str) -> dict:
    label = f"{node_type}:{node_id}"
    meta: dict[str, Any] = {}
    try:
        if node_type == "term":
            row = db.query(CgTerm).filter(CgTerm.term_id == int(node_id)).first()
            if row:
                label, meta = row.term, {"level": row.level, "category": row.category, "status": row.status}
        elif node_type == "variant":
            row = db.query(CgVariant).filter(CgVariant.variant_id == int(node_id)).first()
            if row:
                label, meta = row.variant, {"kind": row.kind, "status": row.status}
        elif node_type == "policy":
            row = db.query(CgPolicy).filter(CgPolicy.clause_id == int(node_id)).first()
            if row:
                label, meta = f"{row.code} {row.title}", {"level": row.level, "priority": row.priority}
        elif node_type == "judgment":
            row = db.query(CgJudgment).filter(CgJudgment.judgment_id == int(node_id)).first()
            if row:
                label, meta = f"判定#{row.judgment_id}", {"decision": row.decision, "level": row.level}
        elif node_type == "task":
            row = db.query(CgTask).filter(CgTask.task_id == int(node_id)).first()
            if row:
                label, meta = f"任务#{row.task_id}", {"state": row.state}
        elif node_type == "proposal":
            row = db.query(CgProposal).filter(CgProposal.proposal_id == int(node_id)).first()
            if row:
                label, meta = row.title, {"status": row.status, "kind": row.kind}
        elif node_type == "case":
            row = db.query(CgCase).filter(CgCase.case_id == int(node_id)).first()
            if row:
                label, meta = row.title, {"level": row.level, "verdict": row.verdict}
    except (TypeError, ValueError):
        pass
    return {"type": node_type, "id": str(node_id), "label": label, "meta": meta}


def neighbors(
    db: Session,
    node_type: str,
    node_id: str,
    *,
    depth: int = 1,
    direction: str = "both",
    limit: int = 200,
) -> dict:
    if node_type not in NODE_TYPES:
        raise ValueError(f"未知节点类型: {node_type}")
    if depth < 1 or depth > 3:
        raise ValueError("depth 只支持 1-3")
    start = (node_type, str(node_id))
    visited = {start}
    queue = deque([(start, 0)])
    nodes = [node_label(db, *start)]
    edges: list[dict] = []
    seen_edges: set[int] = set()

    while queue and len(nodes) < limit:
        (current_type, current_id), d = queue.popleft()
        if d >= depth:
            continue
        query = db.query(CgEdge)
        if direction == "out":
            query = query.filter(CgEdge.src_type == current_type, CgEdge.src_id == current_id)
        elif direction == "in":
            query = query.filter(CgEdge.dst_type == current_type, CgEdge.dst_id == current_id)
        else:
            query = query.filter(
                or_(
                    (CgEdge.src_type == current_type) & (CgEdge.src_id == current_id),
                    (CgEdge.dst_type == current_type) & (CgEdge.dst_id == current_id),
                )
            )
        for edge in query.limit(limit).all():
            if edge.edge_id in seen_edges:
                continue
            seen_edges.add(edge.edge_id)
            edges.append(
                {
                    "edge_id": edge.edge_id,
                    "src": {"type": edge.src_type, "id": edge.src_id},
                    "rel": edge.rel,
                    "dst": {"type": edge.dst_type, "id": edge.dst_id},
                    "weight": edge.weight,
                }
            )
            for ntype, nid in ((edge.src_type, edge.src_id), (edge.dst_type, edge.dst_id)):
                if (ntype, nid) not in visited:
                    visited.add((ntype, nid))
                    nodes.append(node_label(db, ntype, nid))
                    queue.append(((ntype, nid), d + 1))
    return {"node": node_label(db, *start), "nodes": nodes, "edges": edges, "depth": depth}


def overview(db: Session) -> dict:
    edge_rows = db.query(CgEdge).all()
    by_rel = Counter(e.rel for e in edge_rows)
    by_src = Counter(e.src_type for e in edge_rows)
    by_dst = Counter(e.dst_type for e in edge_rows)
    degree: Counter[tuple[str, str]] = Counter()
    for edge in edge_rows:
        degree[(edge.src_type, edge.src_id)] += 1
        degree[(edge.dst_type, edge.dst_id)] += 1
    top = []
    for (ntype, nid), deg in degree.most_common(10):
        item = node_label(db, ntype, nid)
        item["degree"] = deg
        top.append(item)
    return {
        "edges": len(edge_rows),
        "by_relation": dict(by_rel),
        "by_src_type": dict(by_src),
        "by_dst_type": dict(by_dst),
        "top_nodes": top,
        "node_types": sorted(NODE_TYPES),
    }


def mermaid(db: Session, limit: int = 40) -> str:
    """导出可被 Obsidian 直接渲染的 Mermaid 图。"""
    lines = ["graph LR"]
    edges = db.query(CgEdge).order_by(CgEdge.edge_id.asc()).limit(limit).all()
    def _node_id(ntype: str, nid: str) -> str:
        safe = f"{ntype}_{nid}".replace("\"", "").replace("'", "")
        return safe or "node"

    for edge in edges:
        src = node_label(db, edge.src_type, edge.src_id)["label"].replace('"', "'")
        dst = node_label(db, edge.dst_type, edge.dst_id)["label"].replace('"', "'")
        lines.append(
            f'  {_node_id(edge.src_type, edge.src_id)}["{src}"] -->|{edge.rel}| '
            f'{_node_id(edge.dst_type, edge.dst_id)}["{dst}"]'
        )
    if len(lines) == 1:
        lines.append('  empty["暂无图谱关系"]')
    return "\n".join(lines)
