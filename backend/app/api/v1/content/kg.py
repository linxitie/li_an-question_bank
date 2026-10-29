"""知识图谱只读查询 API（R0）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....models.models import EssayQuote, KgEdge, NewsArticle, RecruitmentInfo, Topic
from ....services import kg_service

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])


@router.get("/topics", summary="主题列表")
def list_topics(
    kind: Optional[str] = Query(None, description="theme/exam_type"),
    db: Session = Depends(get_db),
):
    topics = kg_service.list_topics(db, kind)
    counts = dict(
        db.query(KgEdge.dst_id, func.count(KgEdge.edge_id))
        .filter(KgEdge.dst_type == "topic")
        .group_by(KgEdge.dst_id)
        .all()
    )
    return {
        "items": [
            {
                "topic_id": topic.topic_id,
                "name": topic.name,
                "slug": topic.slug,
                "kind": topic.kind,
                "parent_id": topic.parent_id,
                "count": counts.get(topic.topic_id, 0),
            }
            for topic in topics
        ],
        "total": len(topics),
    }


@router.get("/nodes/{node_type}/{node_id}", summary="节点与一跳邻居")
def get_node(
    node_type: str,
    node_id: int,
    db: Session = Depends(get_db),
):
    node = kg_service.resolve_node(db, node_type, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    subgraph = kg_service.get_subgraph(db, node_type, node_id, depth=1)
    return {"node": node, "edges": subgraph["edges"]}


@router.get("/subgraph", summary="子图查询")
def get_subgraph(
    node_type: str = Query(..., description="节点类型"),
    node_id: int = Query(..., description="节点 ID"),
    depth: int = Query(2, ge=1, le=3, description="扩展深度 1-3"),
    db: Session = Depends(get_db),
):
    if not kg_service.resolve_node(db, node_type, node_id):
        raise HTTPException(status_code=404, detail="节点不存在")
    return kg_service.get_subgraph(db, node_type, node_id, depth=depth)


@router.get("/search", summary="节点检索")
def search_nodes(
    q: str = Query(..., min_length=1, description="关键词"),
    node_type: Optional[str] = Query(None, description="限定节点类型"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    pattern = f"%{q}%"
    items: list[dict] = []

    if node_type in (None, "topic"):
        rows = (
            db.query(Topic)
            .filter(or_(Topic.name.like(pattern), Topic.slug.like(pattern)))
            .limit(limit)
            .all()
        )
        items.extend(
            {
                "type": "topic",
                "id": row.topic_id,
                "label": row.name,
                "url": f"/topics/{row.slug}",
            }
            for row in rows
        )

    if node_type in (None, "quote"):
        rows = db.query(EssayQuote).filter(EssayQuote.content.like(pattern)).limit(limit).all()
        items.extend(filter(None, (kg_service.resolve_node(db, "quote", row.quote_id) for row in rows)))

    if node_type in (None, "news"):
        rows = db.query(NewsArticle).filter(NewsArticle.title.like(pattern)).limit(limit).all()
        items.extend(filter(None, (kg_service.resolve_node(db, "news", row.news_id) for row in rows)))

    if node_type in (None, "recruitment"):
        rows = (
            db.query(RecruitmentInfo)
            .filter(RecruitmentInfo.title.like(pattern))
            .limit(limit)
            .all()
        )
        items.extend(
            filter(None, (kg_service.resolve_node(db, "recruitment", row.recruitment_id) for row in rows))
        )

    deduped: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for item in items:
        key = (item["type"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break

    return {"items": deduped, "total": len(deduped)}
