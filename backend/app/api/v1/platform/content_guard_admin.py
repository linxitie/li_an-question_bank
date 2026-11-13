"""管理员端：敏感词自生长知识库运营接口。

权限：require_admin（role_level >= 2）。Agent 无此入口，只有服务层提案能力。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import require_admin
from ....models.content_guard import CgPolicy, CgTask, CgTerm, CgVariant
from ....models.models import SysUser
from ....services.content_guard import (
    audit,
    engine,
    graph,
    guard_text,
    judgments,
    normalizer,
    obsidian,
    proposals,
    reconcile,
    redteam,
    seed_defaults,
    stats,
)
from .content_guard_console import CONSOLE_HTML

router = APIRouter(prefix="/api/v1/admin/content-guard", tags=["内容安全知识库"])

@router.get("/console", response_class=HTMLResponse, include_in_schema=False)
async def content_guard_console() -> HTMLResponse:
    """管理员端图形化运营台（登录后 token 走 localStorage）。"""
    return HTMLResponse(CONSOLE_HTML)

LEVELS = {"blocked", "masked", "reviewed"}
TERM_STATUS = {"active", "candidate", "deprecated"}


class TermCreate(BaseModel):
    term: str = Field(..., min_length=1, max_length=200)
    level: str = Field("reviewed")
    category: str = Field("other", max_length=40)
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    policy_clause_id: Optional[int] = None
    note: Optional[str] = Field(None, max_length=500)


class TermUpdate(BaseModel):
    level: Optional[str] = None
    category: Optional[str] = Field(None, max_length=40)
    status: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    note: Optional[str] = Field(None, max_length=500)


class VariantCreate(BaseModel):
    variant: str = Field(..., min_length=1, max_length=200)
    kind: str = Field("homophone", max_length=20)


class PolicyCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    title: str = Field(..., min_length=1, max_length=200)
    category: str = Field("other", max_length=40)
    level: str = Field("reviewed")
    severity: int = Field(2, ge=1, le=5)
    priority: int = Field(20, ge=0, le=1000)
    legal_basis: Optional[str] = None
    content: Optional[str] = None


class OverrideBody(BaseModel):
    action: str = Field(..., pattern="^(confirm|reject|modify)$")
    reason: str = Field("", max_length=500)


class ReviewBody(BaseModel):
    reason: str = Field("", max_length=500)


class ProposalCreate(BaseModel):
    kind: str = Field(..., max_length=30)
    title: str = Field(..., min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Any] = Field(default_factory=list)


class DetectBody(BaseModel):
    text: str = Field(..., max_length=20000)
    scene: str = Field("precheck", max_length=40)
    persist: bool = False


class RedteamBody(BaseModel):
    limit: int = Field(30, ge=1, le=200)
    create_proposals: bool = True


class ObsidianBody(BaseModel):
    vault: Optional[str] = None
    dry_run: bool = False


def _actor(user: SysUser) -> str:
    return f"user:{user.user_id}:{user.username}"


def _term_dict(row: CgTerm) -> dict:
    return {
        "term_id": row.term_id,
        "term": row.term,
        "normalized": row.normalized,
        "level": row.level,
        "category": row.category,
        "status": row.status,
        "source": row.source,
        "confidence": row.confidence,
        "weight": row.weight,
        "policy_clause_id": row.policy_clause_id,
        "hit_count": row.hit_count,
        "block_count": row.block_count,
        "mask_count": row.mask_count,
        "review_count": row.review_count,
        "false_positive_count": row.false_positive_count,
        "last_hit_at": row.last_hit_at.isoformat(timespec="seconds") if row.last_hit_at else None,
        "note": row.note,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
    }


def _policy_dict(row: CgPolicy) -> dict:
    return {
        "clause_id": row.clause_id,
        "code": row.code,
        "title": row.title,
        "category": row.category,
        "level": row.level,
        "severity": row.severity,
        "priority": row.priority,
        "status": row.status,
        "legal_basis": row.legal_basis,
    }


@router.get("/overview", summary="知识库总览")
async def overview(
    db: Session = Depends(get_db), _: SysUser = Depends(require_admin)
):
    data = stats.overview(db)
    data["top_terms"] = stats.top_terms(db, 10)
    data["trend"] = stats.trend(db, 14)
    data["graph"] = graph.overview(db)
    data["audit"] = audit.verify_chain(db)
    return data


@router.post("/sync-lexicon", summary="从 Obsidian 词表同步敏感词")
async def sync_lexicon(
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from ....core.config import settings
    from ....services.content_guard.vault_sync import sync_vault_lexicons

    vault = str(getattr(settings, "MODERATION_VAULT_DIR", "") or "")
    if not vault:
        raise HTTPException(status_code=400, detail="未配置 MODERATION_VAULT_DIR")
    return sync_vault_lexicons(db, vault)


@router.get("/terms", summary="词条列表")
async def list_terms(
    query: Optional[str] = Query(None, max_length=100),
    level: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    q = db.query(CgTerm)
    if query:
        like = f"%{query.strip()}%"
        q = q.filter(or_(CgTerm.term.like(like), CgTerm.normalized.like(like)))
    if level:
        q = q.filter(CgTerm.level == level)
    if category:
        q = q.filter(CgTerm.category == category)
    if status:
        q = q.filter(CgTerm.status == status)
    total = q.count()
    rows = q.order_by(desc(CgTerm.hit_count), CgTerm.term_id.asc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_term_dict(r) for r in rows]}


@router.post("/terms", summary="新增词条")
async def create_term(
    body: TermCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    if body.level not in LEVELS:
        raise HTTPException(status_code=400, detail=f"level 只支持 {sorted(LEVELS)}")
    norm = normalizer.normalize(body.term)
    if not norm:
        raise HTTPException(status_code=400, detail="词条归一化后为空")
    if db.query(CgTerm).filter(CgTerm.normalized == norm).first():
        raise HTTPException(status_code=409, detail="词条已存在")
    policy = None
    if body.policy_clause_id:
        policy = db.query(CgPolicy).filter(CgPolicy.clause_id == body.policy_clause_id).first()
    if policy is None:
        policy = (
            db.query(CgPolicy)
            .filter(CgPolicy.category == body.category, CgPolicy.status == "active")
            .order_by(CgPolicy.priority.desc())
            .first()
        )
    row = CgTerm(
        term=body.term.strip(),
        normalized=norm,
        level=body.level,
        category=body.category,
        weight=body.confidence,
        confidence=body.confidence,
        status="active",
        source="manual",
        policy_clause_id=policy.clause_id if policy else None,
        created_by=user.user_id,
        updated_by=user.user_id,
        note=body.note,
        first_seen_at=datetime.now(),
    )
    db.add(row)
    db.flush()
    graph.add_edge(db, "term", row.term_id, "belongs_to", "category", body.category)
    if policy:
        graph.add_edge(db, "term", row.term_id, "cites", "policy", policy.clause_id)
    engine.bump_version(db)
    audit.record(
        db,
        "term.create",
        actor=_actor(user),
        actor_role="admin",
        target_type="term",
        target_id=row.term_id,
        after=_term_dict(row),
        ip="",
    )
    db.commit()
    db.refresh(row)
    return _term_dict(row)


@router.patch("/terms/{term_id}", summary="修改词条")
async def update_term(
    term_id: int,
    body: TermUpdate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    row = db.query(CgTerm).filter(CgTerm.term_id == term_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="词条不存在")
    before = _term_dict(row)
    if body.level is not None:
        if body.level not in LEVELS:
            raise HTTPException(status_code=400, detail="非法 level")
        row.level = body.level
    if body.category is not None:
        row.category = body.category
    if body.status is not None:
        if body.status not in TERM_STATUS:
            raise HTTPException(status_code=400, detail="非法 status")
        row.status = body.status
    if body.confidence is not None:
        row.confidence = body.confidence
    if body.note is not None:
        row.note = body.note
    row.updated_by = user.user_id
    row.version = (row.version or 1) + 1
    engine.bump_version(db)
    audit.record(
        db,
        "term.update",
        actor=_actor(user),
        actor_role="admin",
        target_type="term",
        target_id=term_id,
        before=before,
        after=_term_dict(row),
    )
    db.commit()
    db.refresh(row)
    return _term_dict(row)


@router.get("/terms/{term_id}/variants", summary="词条变体列表")
async def list_variants(
    term_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    rows = db.query(CgVariant).filter(CgVariant.term_id == term_id).all()
    return {
        "total": len(rows),
        "items": [
            {
                "variant_id": r.variant_id,
                "term_id": r.term_id,
                "variant": r.variant,
                "normalized": r.normalized,
                "kind": r.kind,
                "status": r.status,
                "hit_count": r.hit_count,
            }
            for r in rows
        ],
    }


@router.post("/terms/{term_id}/variants", summary="新增变体")
async def create_variant(
    term_id: int,
    body: VariantCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    term = db.query(CgTerm).filter(CgTerm.term_id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    vnorm = normalizer.normalize(body.variant)
    if not vnorm or vnorm == term.normalized:
        raise HTTPException(status_code=400, detail="变体为空或与原词相同")
    if db.query(CgVariant).filter(CgVariant.term_id == term_id, CgVariant.normalized == vnorm).first():
        raise HTTPException(status_code=409, detail="变体已存在")
    variant = CgVariant(
        term_id=term_id,
        variant=body.variant.strip(),
        normalized=vnorm,
        kind=body.kind,
        status="active",
        created_by=user.user_id,
    )
    db.add(variant)
    db.flush()
    graph.add_edge(db, "variant", variant.variant_id, "variant_of", "term", term_id)
    engine.bump_version(db)
    audit.record(
        db,
        "variant.create",
        actor=_actor(user),
        actor_role="admin",
        target_type="variant",
        target_id=variant.variant_id,
        after={"term_id": term_id, "variant": body.variant, "kind": body.kind},
    )
    db.commit()
    return {"variant_id": variant.variant_id, "term_id": term_id, "variant": variant.variant}


@router.delete("/variants/{variant_id}", summary="停用变体")
async def deprecate_variant(
    variant_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    row = db.query(CgVariant).filter(CgVariant.variant_id == variant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="变体不存在")
    row.status = "deprecated" if row.status == "active" else "active"
    engine.bump_version(db)
    audit.record(
        db,
        "variant.toggle",
        actor=_actor(user),
        actor_role="admin",
        target_type="variant",
        target_id=variant_id,
        after={"status": row.status},
    )
    db.commit()
    return {"variant_id": variant_id, "status": row.status}


@router.get("/policies", summary="政策条款列表")
async def list_policies(
    db: Session = Depends(get_db), _: SysUser = Depends(require_admin)
):
    rows = db.query(CgPolicy).order_by(CgPolicy.priority.desc(), CgPolicy.clause_id).all()
    return {"total": len(rows), "items": [_policy_dict(r) for r in rows]}


@router.post("/policies", summary="新增政策条款（提案审批落库）")
async def create_policy(
    body: PolicyCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    if db.query(CgPolicy).filter(CgPolicy.code == body.code).first():
        raise HTTPException(status_code=409, detail="条款编号已存在")
    policy = CgPolicy(
        code=body.code,
        title=body.title,
        category=body.category,
        level=body.level,
        severity=body.severity,
        priority=body.priority,
        status="active",
        legal_basis=body.legal_basis,
        content=body.content,
        effective_from=datetime.now(),
    )
    db.add(policy)
    db.flush()
    engine.bump_version(db)
    audit.record(
        db,
        "policy.create",
        actor=_actor(user),
        actor_role="admin",
        target_type="policy",
        target_id=policy.clause_id,
        after=_policy_dict(policy),
    )
    db.commit()
    return _policy_dict(policy)


@router.get("/judgments", summary="判定列表")
async def list_judgments(
    scene: Optional[str] = None,
    decision: Optional[str] = None,
    human_override: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    return judgments.list_judgments(
        db,
        scene=scene,
        decision=decision,
        human_override=human_override,
        limit=limit,
        offset=offset,
    )


@router.get("/judgments/{judgment_id}", summary="判定详情与证据链")
async def get_judgment(
    judgment_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    data = judgments.get_judgment(db, judgment_id)
    if not data:
        raise HTTPException(status_code=404, detail="判定不存在")
    return data


@router.post("/judgments/{judgment_id}/override", summary="人工复核判定")
async def override_judgment(
    judgment_id: int,
    body: OverrideBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    try:
        result = judgments.override_judgment(
            db,
            judgment_id,
            action=body.action,
            reviewer_id=user.user_id,
            reason=body.reason,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tasks", summary="审核任务队列")
async def list_tasks(
    state: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    q = db.query(CgTask)
    if state:
        q = q.filter(CgTask.state == state)
    total = q.count()
    rows = q.order_by(desc(CgTask.priority), CgTask.task_id.asc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "task_id": r.task_id,
                "judgment_id": r.judgment_id,
                "scene": r.scene,
                "source_id": r.source_id,
                "state": r.state,
                "priority": r.priority,
                "assignee_id": r.assignee_id,
                "reviewer_id": r.reviewer_id,
                "due_at": r.due_at.isoformat(timespec="seconds") if r.due_at else None,
                "created_at": r.created_at.isoformat(timespec="seconds") if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/tasks/{task_id}/resolve", summary="处理审核任务")
async def resolve_task(
    task_id: int,
    body: OverrideBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    task = db.query(CgTask).filter(CgTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.state != "pending":
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.state}")
    try:
        result = judgments.override_judgment(
            db,
            task.judgment_id,
            action=body.action,
            reviewer_id=user.user_id,
            reason=body.reason,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/proposals", summary="知识变更提案列表")
async def list_proposals(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    return proposals.list_proposals(db, status=status, kind=kind, limit=limit, offset=offset)


@router.post("/proposals", summary="提交知识变更提案")
async def create_proposal(
    body: ProposalCreate,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    try:
        row = proposals.create_proposal(
            db,
            kind=body.kind,
            title=body.title,
            payload=body.payload,
            evidence=body.evidence,
            proposer="human",
        )
        db.commit()
        return {"proposal_id": row.proposal_id, "status": row.status}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/proposals/{proposal_id}/approve", summary="通过提案并写入知识库")
async def approve_proposal(
    proposal_id: int,
    body: ReviewBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    try:
        result = proposals.approve_proposal(
            db, proposal_id, reviewer_id=user.user_id, note=body.reason
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/proposals/{proposal_id}/reject", summary="拒绝提案")
async def reject_proposal(
    proposal_id: int,
    body: ReviewBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    try:
        result = proposals.reject_proposal(
            db, proposal_id, reviewer_id=user.user_id, note=body.reason
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/audit", summary="审计事件")
async def list_audit(
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    return {"items": audit.recent(db, limit=limit, action=action)}


@router.get("/audit/verify", summary="校验审计哈希链")
async def verify_audit(
    db: Session = Depends(get_db), _: SysUser = Depends(require_admin)
):
    return audit.verify_chain(db)


@router.get("/graph", summary="图谱邻居/子图")
async def get_graph(
    node_type: str = Query(..., max_length=30),
    node_id: str = Query(..., max_length=60),
    depth: int = Query(2, ge=1, le=3),
    direction: str = Query("both", pattern="^(both|out|in)$"),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    try:
        return graph.neighbors(db, node_type, node_id, depth=depth, direction=direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/stats/trend", summary="审核趋势")
async def get_trend(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    return {"days": days, "items": stats.trend(db, days), "top_terms": stats.top_terms(db, 10)}


@router.post("/detect", summary="检测文本（调试，不落判定）")
async def detect_text(
    body: DetectBody,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    # 运营台检测必须与发帖闸门同源，否则会出现"运营台 pass、发帖 mask"的假象
    result = guard_text(db, body.text, scene=body.scene, persist=body.persist)
    result.pop("_policies", None)
    return result


@router.post("/redteam/run", summary="运行红队规避测试")
async def run_redteam(
    body: RedteamBody,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    result = redteam.run(db, limit=body.limit, create_proposals=body.create_proposals)
    db.commit()
    return result


@router.get("/redteam/samples", summary="红队样本")
async def list_redteam(
    detected: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    return redteam.list_samples(db, limit=limit, detected=detected)


@router.post("/obsidian/export", summary="导出 Obsidian 投影")
async def export_obsidian(
    body: ObsidianBody,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    return obsidian.export_all(
        db, vault=body.vault or None, dry_run=body.dry_run
    )


@router.post("/obsidian/import", summary="导入 Obsidian 审阅结果")
async def import_obsidian(
    body: ObsidianBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_admin),
):
    return obsidian.import_reviews(
        db,
        vault=body.vault or None,
        dry_run=body.dry_run,
        reviewer_id=user.user_id,
    )


@router.post("/reconcile", summary="跨层一致性对账")
async def run_reconcile(
    body: ObsidianBody,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_admin),
):
    result = reconcile.run(db, vault=body.vault or None)
    db.commit()
    return result


@router.post("/seed", summary="幂等补种知识库目录")
async def seed_catalog(
    db: Session = Depends(get_db), _: SysUser = Depends(require_admin)
):
    report = seed_defaults(db)
    db.commit()
    return report


@router.post("/reload", summary="热加载词库引擎")
async def reload_engine(
    db: Session = Depends(get_db), user: SysUser = Depends(require_admin)
):
    from ....services.content_guard import reload_engine as _reload

    result = _reload(db, actor=_actor(user))
    db.commit()
    return result
