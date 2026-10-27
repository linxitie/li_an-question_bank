"""从 SoT 生成图投影计划。

不写库；只把 knowledge_point / question_knowledge / question_bank 映射为
GraphNode/GraphEdge。回填脚本、对账与测试共用这一份口径。
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from sqlalchemy import text

from app.foundation.stores.graph import GraphEdge, GraphNode, GraphStore

KP_QUERY = text(
    """SELECT point_id, point_name, subject_id, sub_category_id, parent_id,
              level, sort_order, status
       FROM knowledge_point
       ORDER BY point_id"""
)
QUESTION_QUERY = text(
    """SELECT DISTINCT qb.question_id, qb.subject_id, qb.type_id,
              qb.status, qb.difficulty
       FROM question_knowledge qk
       JOIN question_bank qb ON qb.question_id = qk.question_id
       ORDER BY qb.question_id"""
)
QK_QUERY = text(
    "SELECT question_id, knowledge_point_id FROM question_knowledge "
    "ORDER BY question_id, knowledge_point_id"
)


@dataclass(frozen=True)
class GraphBuildPlan:
    nodes: list[GraphNode]
    edges: list[GraphEdge]

    def node_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in self.nodes:
            counts[node.label] = counts.get(node.label, 0) + 1
        return counts

    def edge_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for edge in self.edges:
            counts[edge.rel] = counts.get(edge.rel, 0) + 1
        return counts


def _limit_clause(limit: int | None) -> str:
    if limit is None:
        return ""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError(f"limit 必须是正整数或 None: {limit!r}")
    return f" LIMIT {int(limit)}"


def build_graph(session, *, limit: int | None = None) -> GraphBuildPlan:
    """生成节点/边计划；limit 同时限制知识点与题目，边只连已加载节点。"""
    kp_rows = session.execute(text(str(KP_QUERY) + _limit_clause(limit))).mappings().all()
    question_rows = session.execute(
        text(str(QUESTION_QUERY) + _limit_clause(limit))
    ).mappings().all()
    qk_rows = session.execute(QK_QUERY).mappings().all()

    kp_by_id: dict[int, dict[str, Any]] = {
        int(row["point_id"]): dict(row) for row in kp_rows
    }
    question_by_id: dict[int, dict[str, Any]] = {
        int(row["question_id"]): dict(row) for row in question_rows
    }

    nodes: list[GraphNode] = []
    for point_id, row in kp_by_id.items():
        nodes.append(GraphNode(
            label="KnowledgePoint",
            key=str(point_id),
            props={
                "pointId": point_id,
                "name": row["point_name"],
                "subjectId": row["subject_id"],
                "subCategoryId": row["sub_category_id"],
                "parentId": row["parent_id"],
                "level": row["level"],
                "sortOrder": row["sort_order"],
                "status": row["status"],
            },
        ))
    for question_id, row in question_by_id.items():
        nodes.append(GraphNode(
            label="Question",
            key=str(question_id),
            props={
                "questionId": question_id,
                "subjectId": row["subject_id"],
                "typeId": row["type_id"],
                "status": row["status"],
                "difficulty": row["difficulty"],
            },
        ))

    edges: list[GraphEdge] = []
    # 1) 层级：父 -> 子；父节点缺失或自指时跳过，并在计数上体现差异。
    for point_id, row in kp_by_id.items():
        parent_id = row["parent_id"]
        if not parent_id or int(parent_id) == 0 or int(parent_id) == point_id:
            continue
        if int(parent_id) not in kp_by_id:
            continue
        edges.append(GraphEdge(
            rel="PREREQUISITE_OF",
            src_label="KnowledgePoint", src_key=str(int(parent_id)),
            dst_label="KnowledgePoint", dst_key=str(point_id),
            props={"derivation": "hierarchy"},
        ))
    # 2) 同父兄弟：只对非根节点两两配对，规范化小 id -> 大 id，避免重复。
    siblings: dict[int, list[int]] = {}
    for point_id, row in kp_by_id.items():
        parent_id = row["parent_id"]
        if not parent_id or int(parent_id) == 0:
            continue
        siblings.setdefault(int(parent_id), []).append(point_id)
    for parent_id in sorted(siblings):
        group = sorted(siblings[parent_id])
        for left, right in combinations(group, 2):
            edges.append(GraphEdge(
                rel="PARALLEL_WITH",
                src_label="KnowledgePoint", src_key=str(left),
                dst_label="KnowledgePoint", dst_key=str(right),
                props={"derivation": "siblings", "parentId": parent_id},
            ))
    # 3) 题目 -> 知识点；只保留两端都已加载的边。
    for row in qk_rows:
        question_id = int(row["question_id"])
        point_id = int(row["knowledge_point_id"])
        if question_id not in question_by_id or point_id not in kp_by_id:
            continue
        edges.append(GraphEdge(
            rel="INSTANCE_OF",
            src_label="Question", src_key=str(question_id),
            dst_label="KnowledgePoint", dst_key=str(point_id),
            props={"derivation": "question_knowledge"},
        ))
    return GraphBuildPlan(nodes=nodes, edges=edges)


def apply_plan(store: GraphStore, plan: GraphBuildPlan, *, reset: bool = False) -> dict[str, int]:
    """把计划写入 GraphStore；reset=True 先清空图投影。"""
    if reset:
        store.clear()
    nodes_written = 0
    nodes_skipped = 0
    for node in plan.nodes:
        if store.upsert_node(node.label, node.key, node.props, version=node.version):
            nodes_written += 1
        else:
            nodes_skipped += 1
    edges_written = 0
    edges_skipped = 0
    for edge in plan.edges:
        if store.upsert_edge(
            edge.rel,
            (edge.src_label, edge.src_key),
            (edge.dst_label, edge.dst_key),
            edge.props,
        ):
            edges_written += 1
        else:
            edges_skipped += 1
    return {
        "nodes_written": nodes_written,
        "nodes_skipped": nodes_skipped,
        "edges_written": edges_written,
        "edges_skipped": edges_skipped,
    }
