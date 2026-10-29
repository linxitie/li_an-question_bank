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

# 关系类型中文名（图谱图例与详情展示用；复用既有三类型，不新增表字段）
REL_TYPE_NAMES = {
    "related": "关联对照",
    "contains": "包含归属",
    "leads_to": "前置延伸",
}

# 图谱分类配色（与前端卡片配色保持一致）
CATEGORY_COLORS = {
    "law": "#2a6bb8",
    "recruit": "#2e8b57",
    "exam_point": "#c98a2b",
    "wrong": "#c0392b",
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
                "category_name": CATEGORIES.get(n.category, n.category),
                "color": CATEGORY_COLORS.get(n.category, "#1a2a4a"),
                "summary": (n.content or "").strip().replace("\n", " ")[:80],
            }
            for n in nodes
        ],
        "relations": [
            {
                "from": r.from_node,
                "to": r.to_node,
                "type": r.rel_type,
                "type_name": REL_TYPE_NAMES.get(r.rel_type, r.rel_type),
            }
            for r in rels
        ],
    }


@router.get("/stats", summary="知识图谱统计（分类计数/关系类型分布/待审批数）")
async def knowledge_stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    approved = db.query(KnowledgeNode).filter(KnowledgeNode.status == "approved").all()
    pending = db.query(KnowledgeNode).filter(KnowledgeNode.status == "pending").count()
    rels = db.query(KnowledgeRelation).all()
    by_cat = {k: 0 for k in CATEGORIES}
    for n in approved:
        by_cat[n.category] = by_cat.get(n.category, 0) + 1
    by_type = {k: 0 for k in REL_TYPE_NAMES}
    for r in rels:
        by_type[r.rel_type] = by_type.get(r.rel_type, 0) + 1
    return {
        "node_total": len(approved),
        "pending_total": pending,
        "relation_total": len(rels),
        "by_category": [
            {"key": k, "name": CATEGORIES[k], "count": v,
             "color": CATEGORY_COLORS[k]}
            for k, v in by_cat.items()
        ],
        "by_relation_type": [
            {"key": k, "name": v, "count": by_type.get(k, 0)}
            for k, v in REL_TYPE_NAMES.items()
        ],
    }


@router.get("/nodes/{node_id}/detail", summary="节点详情（含邻居关系）")
async def node_detail(
    node_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    node = db.query(KnowledgeNode).filter(KnowledgeNode.node_id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    # 出边 + 入边邻居（含对端标题与关系名）
    neighbor_map = {}
    out_rels = db.query(KnowledgeRelation).filter(KnowledgeRelation.from_node == node_id).all()
    in_rels = db.query(KnowledgeRelation).filter(KnowledgeRelation.to_node == node_id).all()
    neighbors = []
    for r in out_rels:
        target = db.get(KnowledgeNode, r.to_node)
        neighbors.append({
            "dir": "out",
            "rel_id": r.rel_id,
            "node_id": r.to_node,
            "title": target.title if target else f"节点{r.to_node}",
            "type": r.rel_type,
            "type_name": REL_TYPE_NAMES.get(r.rel_type, r.rel_type),
        })
    for r in in_rels:
        source = db.get(KnowledgeNode, r.from_node)
        neighbors.append({
            "dir": "in",
            "rel_id": r.rel_id,
            "node_id": r.from_node,
            "title": source.title if source else f"节点{r.from_node}",
            "type": r.rel_type,
            "type_name": REL_TYPE_NAMES.get(r.rel_type, r.rel_type),
        })
    return {
        "node_id": node.node_id,
        "title": node.title,
        "category": node.category,
        "category_name": CATEGORIES.get(node.category, node.category),
        "color": CATEGORY_COLORS.get(node.category, "#1a2a4a"),
        "content": node.content or "",
        "source": node.source,
        "status": node.status,
        "create_time": node.create_time.isoformat() if node.create_time else None,
        "update_time": node.update_time.isoformat() if node.update_time else None,
        "neighbors": neighbors,
    }


# ==================== 知识图谱关系管理（自生长：手动建边 + 自动推荐） ====================


class RelationCreate(BaseModel):
    from_node: int
    to_node: int
    rel_type: str = "related"


@router.post("/relation", summary="手动建立知识关系（幂等）")
async def create_relation(
    req: RelationCreate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.from_node == req.to_node:
        raise HTTPException(status_code=400, detail="不能建立自环关系")
    nodes = db.query(KnowledgeNode).filter(
        KnowledgeNode.node_id.in_([req.from_node, req.to_node]),
        KnowledgeNode.status == "approved",
    ).count()
    if nodes != 2:
        raise HTTPException(status_code=404, detail="关系节点不存在或未入库")
    if req.rel_type not in ("related", "contains", "leads_to"):
        raise HTTPException(status_code=400, detail="关系类型不合法")
    dup = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.from_node == req.from_node,
        KnowledgeRelation.to_node == req.to_node,
    ).first()
    if dup:
        return {"created": 0, "rel_id": dup.rel_id, "message": "关系已存在"}
    rel = KnowledgeRelation(from_node=req.from_node, to_node=req.to_node, rel_type=req.rel_type)
    db.add(rel)
    db.commit()
    return {"created": 1, "rel_id": rel.rel_id, "message": "关系已建立"}


@router.get("/relations", summary="关系列表（含节点标题）")
async def list_relations(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rels = db.query(KnowledgeRelation).order_by(KnowledgeRelation.create_time.desc()).limit(200).all()
    out = []
    for r in rels:
        src = db.get(KnowledgeNode, r.from_node)
        dst = db.get(KnowledgeNode, r.to_node)
        out.append({
            "rel_id": r.rel_id,
            "from": r.from_node,
            "to": r.to_node,
            "from_title": src.title if src else f"节点{r.from_node}",
            "to_title": dst.title if dst else f"节点{r.to_node}",
            "type": r.rel_type,
            "create_time": r.create_time.strftime("%Y-%m-%d %H:%M") if r.create_time else "",
        })
    return {"total": len(out), "items": out}


@router.delete("/relation/{rel_id}", summary="删除关系")
async def delete_relation(
    rel_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rel = db.get(KnowledgeRelation, rel_id)
    if not rel:
        raise HTTPException(status_code=404, detail="关系不存在")
    db.delete(rel)
    db.commit()
    return {"deleted": 1, "message": "关系已删除"}


@router.post("/relation/suggest", summary="自动推荐关系（标题相似/关键词共现，零 LLM）")
async def suggest_relations(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """已入库节点两两打分：同分类 + 标题/内容关键词共现 → 推荐 top10 未建关系。"""
    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.status == "approved").all()
    existing = set(
        (r.from_node, r.to_node) for r in db.query(KnowledgeRelation).all()
    )
    existing |= set((b, a) for a, b in existing)  # 无向去重

    def tokens(text: str):
        return set(str(text or "").replace("（", "").replace("）", "").replace("，", " ").replace("、", " ").split())

    cands = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            if (a.node_id, b.node_id) in existing:
                continue
            score = 0
            if a.category == b.category:
                score += 1
            ta, tb = tokens(a.title), tokens(b.title)
            inter = ta & tb
            score += min(len(inter), 3)
            if score >= 2:
                cands.append((score, a, b))
    cands.sort(key=lambda x: -x[0])
    return {
        "total": len(cands[:10]),
        "items": [
            {
                "from": a.node_id,
                "to": b.node_id,
                "from_title": a.title,
                "to_title": b.title,
                "type": "related",
                "score": s,
            }
            for s, a, b in cands[:10]
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
