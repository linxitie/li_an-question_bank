# -*- coding: utf-8 -*-
"""
模块7 Phase3 - Obsidian 自生长知识库：图谱节点 + 审批入库 + Vault 工作流
流程：Obsidian 中编辑 Markdown（docs/knowledge-vault/）→ 提交为 pending 节点 → 审批通过（approved）→ 供 Agent 装配/检索
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import SysUser, KnowledgeNode, KnowledgeRelation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["联考小智-知识库"])

CATEGORIES = {
    "law": "法条",
    "recruit": "报考信息",
    "exam_point": "考点",
    "wrong": "错题经验",
}


class KnowledgeSubmitRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    category: str = Field(..., pattern="^(law|recruit|exam_point|wrong)$")
    content: str = Field(..., min_length=5)
    source: Optional[str] = Field(None, max_length=200)


@router.get("/categories", summary="知识库分类")
async def list_categories():
    return {"categories": [{"key": k, "name": v} for k, v in CATEGORIES.items()]}


@router.get("/nodes", summary="知识库节点列表")
async def list_nodes(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="分类过滤"),
    status: str = Query("approved", description="pending/approved/all"),
    limit: int = 50,
    offset: int = 0,
):
    q = db.query(KnowledgeNode)
    if category:
        q = q.filter(KnowledgeNode.category == category)
    if status == "pending":
        q = q.filter(KnowledgeNode.status == "pending")
    elif status == "approved":
        q = q.filter(KnowledgeNode.status == "approved")
    total = q.count()
    rows = (
        q.order_by(KnowledgeNode.update_time.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "node_id": n.node_id,
                "title": n.title,
                "category": n.category,
                "category_name": CATEGORIES.get(n.category, n.category),
                "content": n.content,
                "source": n.source,
                "status": n.status,
                "update_time": n.update_time.isoformat() if n.update_time else None,
            }
            for n in rows
        ],
    }


@router.post("/nodes", summary="提交新知识节点（待审批）")
async def submit_node(
    req: KnowledgeSubmitRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    node = KnowledgeNode(
        title=req.title.strip(),
        category=req.category,
        content=req.content.strip(),
        source=req.source,
        status="pending",
        submitter_id=current_user.user_id,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return {
        "node_id": node.node_id,
        "title": node.title,
        "status": node.status,
        "message": "已提交，等待审批通过后入库",
    }


@router.post("/nodes/{node_id}/approve", summary="审批通过并入库")
async def approve_node(
    node_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    node = db.query(KnowledgeNode).filter(KnowledgeNode.node_id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    if node.status == "approved":
        return {"node_id": node.node_id, "status": "approved", "message": "已是入库状态"}
    node.status = "approved"
    node.update_time = datetime.now()
    db.commit()
    return {"node_id": node.node_id, "status": "approved", "message": "已审批入库"}


@router.post("/nodes/{node_id}/reject", summary="驳回节点")
async def reject_node(
    node_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    node = db.query(KnowledgeNode).filter(KnowledgeNode.node_id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    node.status = "rejected"
    node.update_time = datetime.now()
    db.commit()
    return {"node_id": node.node_id, "status": "rejected"}


@router.get("/graph", summary="知识图谱（节点+关系）")
async def knowledge_graph(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nodes = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.status == "approved")
        .all()
    )
    rels = (
        db.query(KnowledgeRelation)
        .all()
    )
    return {
        "nodes": [
            {
                "node_id": n.node_id,
                "title": n.title,
                "category": n.category,
            }
            for n in nodes
        ],
        "relations": [
            {
                "from": r.from_node,
                "to": r.to_node,
                "type": r.rel_type,
            }
            for r in rels
        ],
    }


@router.get("/vault", summary="Obsidian Vault 工作流说明")
async def vault_info(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回 Vault 目录结构说明与如何用 Obsidian 扩充知识库"""
    vault_path = "docs/knowledge-vault"
    return {
        "vault_path": vault_path,
        "structure": {
            "law": "法条库（治安管理处罚法/人民警察法/刑法等核心条款）",
            "recruit": "报考信息库（联考公告/岗位/条件/时间线）",
            "exam_point": "考点库（行测/申论/公专高频考点）",
            "wrong": "错题经验库（典型错题与避坑笔记）",
        },
        "workflow": [
            "1. 用 Obsidian 打开项目 docs/knowledge-vault/ 目录作为 Vault",
            "2. 在对应分类目录新建 .md 笔记（首行 # 标题，正文用 Markdown）",
            "3. 通过本系统知识库页提交该笔记内容 → 生成 pending 节点",
            "4. 审批通过后节点进入 approved，Agent 对话时可按分类检索引用",
        ],
    }
