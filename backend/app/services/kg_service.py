"""R0 知识图谱服务：主题、边、节点解析、子图。

约定：
- 图谱只存 (type,id) 指针；展示时由 resolve_node 回查各业务表。
- create_edge 不 commit，由调用方统一提交；重复边返回已有记录。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..core.content_hub_schema import RELATION_SEED
from ..models.models import (
    ContentSource,
    EssayQuote,
    ExamCalendar,
    KgEdge,
    KgRelationType,
    KnowledgePoint,
    NewsArticle,
    QuestionSubject,
    RecruitmentInfo,
    Topic,
)

NODE_TYPES = frozenset(
    {"quote", "news", "recruitment", "topic", "knowledge_point", "source", "event", "subject", "media"}
)


def seed_relation_types(db: Session) -> int:
    """幂等种入关系类型注册表，返回新增数。"""
    existing = {row[0] for row in db.query(KgRelationType.relation).all()}
    created = 0
    for relation, description, directed, src_types, dst_types in RELATION_SEED:
        if relation in existing:
            continue
        db.add(
            KgRelationType(
                relation=relation,
                description=description,
                directed=directed,
                src_types=src_types,
                dst_types=dst_types,
            )
        )
        created += 1
    db.commit()
    return created


def create_edge(
    db: Session,
    *,
    src_type: str,
    src_id: int,
    dst_type: str,
    dst_id: int,
    relation: str,
    weight: float = 1.0,
    confidence: float = 1.0,
    origin: str = "rule",
) -> KgEdge:
    """创建边；重复 (src,dst,relation) 返回已有边。不提交事务。"""
    if src_type not in NODE_TYPES or dst_type not in NODE_TYPES:
        raise ValueError(f"unsupported node type: {src_type}->{dst_type}")
    if not db.query(KgRelationType).filter(KgRelationType.relation == relation).first():
        raise ValueError(f"unsupported relation: {relation}")

    existing = (
        db.query(KgEdge)
        .filter(
            KgEdge.src_type == src_type,
            KgEdge.src_id == src_id,
            KgEdge.dst_type == dst_type,
            KgEdge.dst_id == dst_id,
            KgEdge.relation == relation,
        )
        .first()
    )
    if existing:
        return existing

    edge = KgEdge(
        src_type=src_type,
        src_id=src_id,
        dst_type=dst_type,
        dst_id=dst_id,
        relation=relation,
        weight=weight,
        confidence=confidence,
        origin=origin,
    )
    db.add(edge)
    db.flush()
    return edge


def merge_topics(db: Session, source_id: int, target_id: int) -> int:
    """把 source 主题合并进 target：移动边/子主题，删除 source。返回移动边数。"""
    if source_id == target_id:
        return 0
    source = db.query(Topic).filter(Topic.topic_id == source_id).first()
    target = db.query(Topic).filter(Topic.topic_id == target_id).first()
    if not source or not target:
        raise ValueError("topic not found")

    # 子主题改挂到 target
    db.query(Topic).filter(Topic.parent_id == source_id).update(
        {Topic.parent_id: target_id}, synchronize_session=False
    )

    edges = (
        db.query(KgEdge)
        .filter(
            or_(
                and_(KgEdge.src_type == "topic", KgEdge.src_id == source_id),
                and_(KgEdge.dst_type == "topic", KgEdge.dst_id == source_id),
            )
        )
        .all()
    )
    moved = 0
    for edge in edges:
        new_src = target_id if edge.src_type == "topic" and edge.src_id == source_id else edge.src_id
        new_dst = target_id if edge.dst_type == "topic" and edge.dst_id == source_id else edge.dst_id
        if new_src == edge.src_id and new_dst == edge.dst_id:
            continue
        conflict = (
            db.query(KgEdge)
            .filter(
                KgEdge.src_type == edge.src_type,
                KgEdge.src_id == new_src,
                KgEdge.dst_type == edge.dst_type,
                KgEdge.dst_id == new_dst,
                KgEdge.relation == edge.relation,
            )
            .first()
        )
        if conflict:
            db.delete(edge)
            continue
        edge.src_id = new_src
        edge.dst_id = new_dst
        moved += 1

    db.delete(source)
    db.commit()
    return moved


def list_topics(db: Session, kind: str | None = None) -> list[Topic]:
    query = db.query(Topic).filter(Topic.status == 1)
    if kind:
        query = query.filter(Topic.kind == kind)
    return query.order_by(Topic.sort_order, Topic.topic_id).all()


def resolve_node(db: Session, node_type: str, node_id: int) -> dict[str, Any] | None:
    """按类型回查节点展示信息；不存在返回 None。"""
    if node_type == "topic":
        row = db.query(Topic).filter(Topic.topic_id == node_id).first()
        return {"type": node_type, "id": node_id, "label": row.name, "url": f"/topics/{row.slug}"} if row else None
    if node_type == "quote":
        row = db.query(EssayQuote).filter(EssayQuote.quote_id == node_id).first()
        if not row:
            return None
        label = " ".join((row.content or "").split())[:40]
        return {"type": node_type, "id": node_id, "label": label, "url": f"/quotes/{row.quote_id}"}
    if node_type == "news":
        row = db.query(NewsArticle).filter(NewsArticle.news_id == node_id).first()
        return {"type": node_type, "id": node_id, "label": row.title, "url": f"/news/{row.news_id}"} if row else None
    if node_type == "recruitment":
        row = db.query(RecruitmentInfo).filter(RecruitmentInfo.recruitment_id == node_id).first()
        return {
            "type": node_type,
            "id": node_id,
            "label": row.title,
            "url": f"/recruitment/{row.recruitment_id}",
        } if row else None
    if node_type == "knowledge_point":
        row = db.query(KnowledgePoint).filter(KnowledgePoint.point_id == node_id).first()
        return {
            "type": node_type,
            "id": node_id,
            "label": row.point_name,
            "url": f"/knowledge-points/{row.point_id}",
        } if row else None
    if node_type == "source":
        row = db.query(ContentSource).filter(ContentSource.source_id == node_id).first()
        if not row:
            return None
        label = row.publisher or row.url or f"source:{node_id}"
        return {"type": node_type, "id": node_id, "label": label, "url": row.url or ""}
    if node_type == "event":
        row = db.query(ExamCalendar).filter(ExamCalendar.event_id == node_id).first()
        return {
            "type": node_type,
            "id": node_id,
            "label": row.title,
            "url": f"/calendar/{row.event_id}",
        } if row else None
    if node_type == "subject":
        row = db.query(QuestionSubject).filter(QuestionSubject.subject_id == node_id).first()
        return {
            "type": node_type,
            "id": node_id,
            "label": row.subject_name,
            "url": f"/subjects/{row.subject_id}",
        } if row else None
    return None


def get_subgraph(db: Session, node_type: str, node_id: int, depth: int = 2) -> dict[str, Any]:
    """BFS 取子图；depth 限制 1-3，自环/环不会无限扩展。"""
    depth = max(1, min(int(depth), 3))
    visited: set[tuple[str, int]] = {(node_type, node_id)}
    frontier: list[tuple[str, int]] = [(node_type, node_id)]
    edges: dict[int, KgEdge] = {}

    for _ in range(depth):
        if not frontier:
            break
        conditions = []
        for current_type, current_id in frontier:
            conditions.append(and_(KgEdge.src_type == current_type, KgEdge.src_id == current_id))
            conditions.append(and_(KgEdge.dst_type == current_type, KgEdge.dst_id == current_id))
        rows = db.query(KgEdge).filter(or_(*conditions)).all()
        next_frontier: list[tuple[str, int]] = []
        for edge in rows:
            edges[edge.edge_id] = edge
            for node in ((edge.src_type, edge.src_id), (edge.dst_type, edge.dst_id)):
                if node not in visited:
                    visited.add(node)
                    next_frontier.append(node)
        frontier = next_frontier

    nodes = [node for nt, nid in visited if (node := resolve_node(db, nt, nid))]
    return {
        "nodes": nodes,
        "edges": [
            {
                "edge_id": edge.edge_id,
                "src_type": edge.src_type,
                "src_id": edge.src_id,
                "dst_type": edge.dst_type,
                "dst_id": edge.dst_id,
                "relation": edge.relation,
                "weight": edge.weight,
                "confidence": edge.confidence,
                "origin": edge.origin,
            }
            for edge in edges.values()
        ],
    }
