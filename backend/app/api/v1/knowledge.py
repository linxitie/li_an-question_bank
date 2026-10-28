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
            "3. 点击「📥 从 Vault 导入」→ 笔记自动扫描为 pending 节点（幂等）",
            "4. 审批通过后节点进入 approved，Agent 对话时可按分类检索引用",
        ],
    }


class VaultImportRequest(BaseModel):
    path: Optional[str] = Field(default=None, max_length=300, description="vault 目录，默认 docs/knowledge-vault（仅允许项目内路径）")


@router.post("/vault/import", summary="从 Obsidian Vault 导入笔记（自动生成待审批节点）")
async def vault_import(
    req: VaultImportRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """扫描 vault 目录 .md 笔记 → 按分类写入 KnowledgeNode(pending)，幂等（标题+正文指纹查重）。"""
    import os
    from pathlib import Path

    cwd = Path(os.getcwd()).resolve()
    if req.path:
        base = Path(req.path)
        if not base.is_absolute():
            base = cwd / base
        base = base.resolve()
        # 路径穿越防护：只允许项目目录内的 vault 路径
        if not (str(base) == str(cwd) or str(base).startswith(str(cwd) + os.sep)):
            raise HTTPException(status_code=400, detail="只允许导入项目内的 Vault 目录")
    else:
        # 默认路径探测：项目根 docs/knowledge-vault 或 backend 上一级的 docs/knowledge-vault
        candidates = [cwd / "docs/knowledge-vault"]
        if cwd.name == "backend":
            candidates.insert(0, cwd.parent / "docs/knowledge-vault")
        base = next((c for c in candidates if c.exists()), candidates[0])
        base = base.resolve()

    category_map = {"law": "law", "法条": "law", "recruit": "recruit", "报考": "recruit",
                    "exam_point": "exam_point", "考点": "exam_point", "wrong": "wrong", "错题": "wrong"}
    allowed_categories = {"law", "recruit", "exam_point", "wrong"}

    imported, skipped = 0, 0
    nodes = []
    if base.exists():
        for md in sorted(base.rglob("*.md")):
            if md.name.lower() in ("readme.md", "readme.markdown"):
                skipped += 1
                continue
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            title = (md.stem or "").strip()
            lines = text.splitlines()
            category = None
            # frontmatter 解析（--- 起止的 key: value）
            if len(lines) >= 3 and lines[0].strip() == "---":
                fm = {}
                for line in lines[1:]:
                    if line.strip() == "---":
                        break
                    if ":" in line:
                        k, _, v = line.partition(":")
                        fm[k.strip().lower()] = v.strip()
                category = fm.get("category") or fm.get("分类")
                if fm.get("title"):
                    title = fm["title"]
            else:
                # 首行 # 标题兜底
                for line in lines:
                    if line.strip().startswith("# "):
                        title = line.strip()[2:].strip()
                        break
            if category is None:
                # 按目录名推断分类
                parent = md.parent.name.lower()
                category = category_map.get(parent)
            if category not in allowed_categories:
                category = "exam_point"
            content = text.strip()
            if not content:
                skipped += 1
                continue
            # 幂等：标题+内容指纹查重
            fingerprint = (title + "|" + content[:80]).strip()
            dup = (
                db.query(KnowledgeNode)
                .filter(KnowledgeNode.title == title)
                .order_by(KnowledgeNode.create_time.desc())
                .first()
            )
            if dup and (dup.content or "")[:80] == content[:80]:
                skipped += 1
                continue
            source = (md.name + "（Obsidian Vault）")[:200]
            node = KnowledgeNode(
                title=title[:200],
                category=category,
                content=content,
                source=source,
                status="pending",
                submitter_id=current_user.user_id,
            )
            db.add(node)
            imported += 1
            nodes.append({"node_id": node.node_id, "title": node.title, "category": node.category, "status": node.status})
    db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "nodes": nodes[:20],
        "message": f"导入完成：新增 {imported} 条待审批笔记，跳过 {skipped} 条重复/空文件",
    }
