"""知识变更提案：Agent 只提案，人工确认后才生效。

审批动作与写入在同一事务内完成：提案状态、词条/变体、图谱边、审计事件
要么全部提交，要么全部回滚，避免"提案已批但词库没变"。
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ...models.content_guard import CgPolicy, CgProposal, CgTerm, CgVariant
from . import audit, engine, graph, normalizer

VALID_LEVELS = {"blocked", "masked", "reviewed"}
VALID_KINDS = {
    "add_term", "add_variant", "update_level", "deprecate_term",
    "new_policy", "merge_terms", "consistency",
}


def create_proposal(
    db: Session,
    *,
    kind: str,
    title: str,
    payload: dict,
    evidence: Optional[list] = None,
    proposer: str = "agent",
    dedupe_key: Optional[str] = None,
) -> Optional[CgProposal]:
    if kind not in VALID_KINDS:
        raise ValueError(f"未知提案类型: {kind}")
    key = dedupe_key or hashlib.sha256(
        (kind + "|" + title + "|" + str(sorted(payload.items()))).encode("utf-8")
    ).hexdigest()[:160]
    existing = db.query(CgProposal).filter(CgProposal.dedupe_key == key).first()
    if existing:
        return existing
    proposal = CgProposal(
        kind=kind,
        title=title[:200],
        payload=payload,
        evidence=evidence or [],
        proposer=proposer,
        status="pending",
        dedupe_key=key,
    )
    db.add(proposal)
    db.flush()
    audit.record(
        db,
        "proposal.create",
        actor=proposer,
        actor_role="agent",
        target_type="proposal",
        target_id=proposal.proposal_id,
        after={"kind": kind, "title": title, "payload": payload},
    )
    return proposal


def _policy_for(db: Session, category: str) -> Optional[CgPolicy]:
    rows = (
        db.query(CgPolicy)
        .filter(CgPolicy.category == category, CgPolicy.status == "active")
        .order_by(CgPolicy.priority.desc())
        .all()
    )
    return rows[0] if rows else None


def _ensure_term(db: Session, payload: dict, proposer: str) -> CgTerm:
    word = str(payload.get("term") or "").strip()
    if not word:
        raise ValueError("add_term 缺少 term")
    norm = normalizer.normalize(word)
    if not norm:
        raise ValueError("term 归一化后为空")
    level = str(payload.get("level") or "reviewed")
    if level not in VALID_LEVELS:
        raise ValueError(f"非法 level: {level}")
    category = str(payload.get("category") or "other")
    term = db.query(CgTerm).filter(CgTerm.normalized == norm).first()
    if term is None:
        policy = _policy_for(db, category)
        term = CgTerm(
            term=word,
            normalized=norm,
            level=level,
            category=category,
            weight=float(payload.get("confidence") or 0.7),
            confidence=float(payload.get("confidence") or 0.7),
            status="active",
            source=proposer if proposer in ("redteam", "active_learning", "manual") else "auto",
            policy_clause_id=policy.clause_id if policy else None,
            created_by=None,
            first_seen_at=datetime.now(),
            note=(payload.get("note") or "")[:500],
        )
        db.add(term)
        db.flush()
    else:
        term.level = level
        term.category = category
        term.status = "active"
        term.confidence = max(float(term.confidence or 0.0), float(payload.get("confidence") or 0.7))
        if not term.policy_clause_id:
            policy = _policy_for(db, category)
            term.policy_clause_id = policy.clause_id if policy else None
    policy = _policy_for(db, category)
    if policy:
        graph.add_edge(db, "term", term.term_id, "cites", "policy", policy.clause_id)
    graph.add_edge(db, "term", term.term_id, "belongs_to", "category", category)

    for item in payload.get("variants") or []:
        text = str(item.get("variant") if isinstance(item, dict) else item).strip()
        if not text:
            continue
        vnorm = normalizer.normalize(text)
        if not vnorm or vnorm == term.normalized:
            continue
        exists = (
            db.query(CgVariant)
            .filter(CgVariant.term_id == term.term_id, CgVariant.normalized == vnorm)
            .first()
        )
        if exists:
            continue
        variant = CgVariant(
            term_id=term.term_id,
            variant=text,
            normalized=vnorm,
            kind=(item.get("kind") if isinstance(item, dict) else None) or "homophone",
            status="active",
            created_by=None,
        )
        db.add(variant)
        db.flush()
        graph.add_edge(db, "variant", variant.variant_id, "variant_of", "term", term.term_id)
    return term


def _apply(db: Session, proposal: CgProposal) -> dict:
    payload = proposal.payload or {}
    kind = proposal.kind
    result: dict[str, Any] = {"kind": kind}
    if kind in ("add_term", "consistency"):
        if kind == "add_term":
            term = _ensure_term(db, payload, proposal.proposer)
            result["term_id"] = term.term_id
            proposal.applied_ref_type = "term"
            proposal.applied_ref_id = term.term_id
    elif kind == "add_variant":
        term_id = int(payload.get("term_id") or 0)
        term = db.query(CgTerm).filter(CgTerm.term_id == term_id).first()
        if not term:
            raise ValueError("词条不存在")
        text = str(payload.get("variant") or "").strip()
        vnorm = normalizer.normalize(text)
        if not vnorm:
            raise ValueError("变体归一化后为空")
        if vnorm == term.normalized:
            raise ValueError("变体与原词相同")
        existing = (
            db.query(CgVariant)
            .filter(CgVariant.term_id == term_id, CgVariant.normalized == vnorm)
            .first()
        )
        if existing is None:
            existing = CgVariant(
                term_id=term_id,
                variant=text,
                normalized=vnorm,
                kind=str(payload.get("kind") or "homophone"),
                status="active",
                created_by=None,
            )
            db.add(existing)
            db.flush()
            graph.add_edge(db, "variant", existing.variant_id, "variant_of", "term", term_id)
        result["variant_id"] = existing.variant_id
        proposal.applied_ref_type = "variant"
        proposal.applied_ref_id = existing.variant_id
    elif kind in ("update_level", "deprecate_term"):
        term_id = int(payload.get("term_id") or 0)
        term = db.query(CgTerm).filter(CgTerm.term_id == term_id).first()
        if not term:
            raise ValueError("词条不存在")
        if kind == "update_level":
            level = str(payload.get("level") or term.level)
            if level not in VALID_LEVELS:
                raise ValueError(f"非法 level: {level}")
            term.level = level
            if "confidence" in payload:
                term.confidence = max(0.1, min(0.99, float(payload["confidence"])))
            if payload.get("status") in ("active", "deprecated"):
                term.status = payload["status"]
        else:
            term.status = "deprecated"
        result["term_id"] = term.term_id
        proposal.applied_ref_type = "term"
        proposal.applied_ref_id = term.term_id
    elif kind == "new_policy":
        code = str(payload.get("code") or "").strip()
        if not code:
            raise ValueError("new_policy 缺少 code")
        policy = db.query(CgPolicy).filter(CgPolicy.code == code).first()
        if policy is None:
            policy = CgPolicy(
                code=code,
                title=str(payload.get("title") or code),
                category=str(payload.get("category") or "other"),
                level=str(payload.get("level") or "reviewed"),
                severity=int(payload.get("severity") or 2),
                priority=int(payload.get("priority") or 20),
                status="active",
                legal_basis=payload.get("legal_basis"),
                content=payload.get("content"),
                effective_from=datetime.now(),
            )
            db.add(policy)
            db.flush()
        result["policy_id"] = policy.clause_id
        proposal.applied_ref_type = "policy"
        proposal.applied_ref_id = policy.clause_id
    elif kind == "merge_terms":
        source = db.query(CgTerm).filter(CgTerm.term_id == int(payload.get("source_term_id") or 0)).first()
        target = db.query(CgTerm).filter(CgTerm.term_id == int(payload.get("target_term_id") or 0)).first()
        if not source or not target:
            raise ValueError("合并词条不存在")
        for variant in db.query(CgVariant).filter(CgVariant.term_id == source.term_id).all():
            duplicate = (
                db.query(CgVariant)
                .filter(CgVariant.term_id == target.term_id, CgVariant.normalized == variant.normalized)
                .first()
            )
            if duplicate:
                db.delete(variant)
            else:
                variant.term_id = target.term_id
        source.status = "deprecated"
        result["source_term_id"] = source.term_id
        result["target_term_id"] = target.term_id
        proposal.applied_ref_type = "term"
        proposal.applied_ref_id = target.term_id
    return result


def approve_proposal(
    db: Session,
    proposal_id: int,
    *,
    reviewer_id: Optional[int] = None,
    note: str = "",
) -> dict:
    proposal = db.query(CgProposal).filter(CgProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise ValueError("提案不存在")
    if proposal.status != "pending":
        raise ValueError(f"提案状态为 {proposal.status}，不能重复审批")
    result = _apply(db, proposal)
    proposal.status = "applied"
    proposal.reviewer_id = reviewer_id
    proposal.review_note = (note or "")[:500]
    proposal.reviewed_at = datetime.now()
    if result.get("term_id"):
        graph.add_edge(db, "proposal", proposal.proposal_id, "proposed", "term", result["term_id"])
    engine.bump_version(db)
    audit.record(
        db,
        "proposal.approve",
        actor=f"user:{reviewer_id}" if reviewer_id else "human",
        actor_role="reviewer",
        target_type="proposal",
        target_id=proposal.proposal_id,
        before={"status": "pending"},
        after={"status": "applied", "result": result, "note": note},
    )
    return {"proposal_id": proposal_id, "status": "applied", "result": result}


def reject_proposal(
    db: Session,
    proposal_id: int,
    *,
    reviewer_id: Optional[int] = None,
    note: str = "",
) -> dict:
    proposal = db.query(CgProposal).filter(CgProposal.proposal_id == proposal_id).first()
    if not proposal:
        raise ValueError("提案不存在")
    if proposal.status != "pending":
        raise ValueError(f"提案状态为 {proposal.status}，不能重复审批")
    proposal.status = "rejected"
    proposal.reviewer_id = reviewer_id
    proposal.review_note = (note or "")[:500]
    proposal.reviewed_at = datetime.now()
    audit.record(
        db,
        "proposal.reject",
        actor=f"user:{reviewer_id}" if reviewer_id else "human",
        actor_role="reviewer",
        target_type="proposal",
        target_id=proposal.proposal_id,
        before={"status": "pending"},
        after={"status": "rejected", "note": note},
    )
    return {"proposal_id": proposal_id, "status": "rejected"}


def list_proposals(
    db: Session,
    *,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    query = db.query(CgProposal)
    if status:
        query = query.filter(CgProposal.status == status)
    if kind:
        query = query.filter(CgProposal.kind == kind)
    total = query.count()
    rows = query.order_by(desc(CgProposal.proposal_id)).offset(offset).limit(min(limit, 200)).all()
    return {
        "total": total,
        "items": [
            {
                "proposal_id": r.proposal_id,
                "kind": r.kind,
                "title": r.title,
                "payload": r.payload,
                "evidence": r.evidence,
                "proposer": r.proposer,
                "status": r.status,
                "reviewer_id": r.reviewer_id,
                "review_note": r.review_note,
                "created_at": r.created_at.isoformat(timespec="seconds") if r.created_at else None,
            }
            for r in rows
        ],
    }
