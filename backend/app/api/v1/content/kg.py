"""知识图谱只读查询 API（R0）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....services import kg_service

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])


@router.get("/topics", summary="主题列表")
def list_topics(
    kind: Optional[str] = Query(None, description="theme/exam_type"),
    db: Session = Depends(get_db),
):
    items = kg_service.list_topics_with_counts(db, kind)
    return {"items": items, "total": len(items)}


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
    items = kg_service.search_nodes(db, q, node_type, limit)
    return {"items": items, "total": len(items)}
