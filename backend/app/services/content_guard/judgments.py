"""判定与仲裁：命中 → 证据链 → 分级处置 → 落库 → 人工复核。

原则：
- 阻断/打码是自动动作，但"为什么"必须写成证据链，而不是一个分数；
- 中低置信度不直接处置，转人工队列；
- 人工复核结果反哺词条置信度，形成主动学习闭环。
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ...models.content_guard import CgCase, CgJudgment, CgPolicy, CgTask, CgTerm
from . import audit, engine, graph, stats

DECISION_BY_LEVEL = {"blocked": "block", "masked": "mask", "reviewed": "review"}
LEVEL_BASE_CONFIDENCE = {"blocked": 0.90, "masked": 0.80, "reviewed": 0.55}
REVIEW_CONFIDENCE_FLOOR = 0.62
FP_DOWNGRADE_THRESHOLD = 3


def _policy_rows(db: Session, ids: list[int]) -> list[CgPolicy]:
    if not ids:
        return []
    return db.query(CgPolicy).filter(CgPolicy.clause_id.in_(ids)).all()


def _confidence(level: str, hits: list[dict]) -> float:
    if not hits:
        return 0.0
    top = max(float(h.get("confidence") or 0.0) for h in hits)
    score = 0.5 * top + 0.5 * LEVEL_BASE_CONFIDENCE.get(level, 0.5)
    score += 0.02 * min(len(hits), 5)
    if any(h.get("variant_id") for h in hits):
        score += 0.02
    return round(min(0.99, max(0.0, score)), 3)


def _build_evidence(
    db: Session,
    text: str,
    result: dict,
    level: str,
    confidence: float,
    policies: list[CgPolicy],
    decision: str,
    reason: str,
) -> list[dict]:
    return [
        {
            "step": "normalize",
            "detail": "NFKC 全半角归一 + 小写 + 去零宽/分隔符",
            "input_length": len(text or ""),
            "compact_length": len(result.get("compact") or ""),
        },
        {
            "step": "dfa_match",
            "hits": [
                {
                    "term_id": h.get("term_id"),
                    "term": h.get("term"),
                    "level": h.get("level"),
                    "category": h.get("category"),
                    "variant_kind": h.get("variant_kind"),
                }
                for h in result.get("hits", [])
            ],
        },
        {
            "step": "policy_map",
            "clauses": [
                {
                    "clause_id": p.clause_id,
                    "code": p.code,
                    "title": p.title,
                    "level": p.level,
                    "priority": p.priority,
                }
                for p in policies
            ],
        },
        {
            "step": "arbitration",
            "rule": "取最高等级；同等级按政策 priority 排序；置信度不足转人工",
            "level": level,
            "confidence": confidence,
            "engine_version": result.get("engine_version"),
            "engine_source": result.get("engine_source"),
        },
        {"step": "decision", "decision": decision, "reason": reason},
    ]


def _task_state(decision: str) -> str:
    return {"block": "auto_blocked", "mask": "auto_masked", "review": "pending"}.get(
        decision, "auto_masked"
    )


def record_judgment(
    db: Session,
    text: str,
    result: dict,
    *,
    scene: str,
    source_id: Optional[int],
    user_id: Optional[int],
) -> CgJudgment:
    level = result["level"]
    decision = result["decision"]
    hits = result.get("hits", [])
    policies = result.get("_policies", []) or []

    judgment = CgJudgment(
        scene=scene,
        source_id=source_id,
        user_id=user_id,
        content_hash=hashlib.sha256((text or "").encode("utf-8")).hexdigest(),
        content_snippet=result.get("snippet") or "",
        level=level,
        decision=decision,
        confidence=result.get("confidence", 0.0),
        hits=hits,
        policy_ids=result.get("policy_ids", []),
        evidence=result.get("evidence", []),
        engine_version=int(result.get("engine_version") or 0),
        latency_ms=float(result.get("latency_ms") or 0.0),
    )
    db.add(judgment)
    db.flush()

    now = datetime.now()
    for hit in hits:
        term_id = hit.get("term_id")
        if not term_id:
            continue
        term = db.query(CgTerm).filter(CgTerm.term_id == term_id).first()
        if not term:
            continue
        term.hit_count = (term.hit_count or 0) + 1
        term.last_hit_at = now
        if decision == "block":
            term.block_count = (term.block_count or 0) + 1
        elif decision == "mask":
            term.mask_count = (term.mask_count or 0) + 1
        else:
            term.review_count = (term.review_count or 0) + 1

    priority = max([p.priority for p in policies], default=50)
    task = CgTask(
        judgment_id=judgment.judgment_id,
        scene=scene,
        source_id=source_id,
        state=_task_state(decision),
        priority=priority,
        due_at=now + timedelta(hours=24) if decision == "review" else None,
        resolved_at=None if decision == "review" else now,
    )
    db.add(task)
    db.flush()

    for hit in hits:
        if hit.get("term_id"):
            graph.add_edge(db, "judgment", judgment.judgment_id, "triggers", "term", hit["term_id"])
    for policy_id in result.get("policy_ids", []):
        graph.add_edge(db, "judgment", judgment.judgment_id, "cites", "policy", policy_id)
    graph.add_edge(db, "task", task.task_id, "review_of", "judgment", judgment.judgment_id)

    stats.bump_daily(db, scene, decision)
    audit.record(
        db,
        f"judgment.{decision}",
        actor="content_guard",
        actor_role="agent",
        target_type="judgment",
        target_id=judgment.judgment_id,
        after={
            "level": level,
            "decision": decision,
            "confidence": judgment.confidence,
            "words": result.get("words", []),
        },
        payload={"scene": scene, "source_id": source_id, "task_id": task.task_id},
    )
    return judgment


def persist_result(
    db: Session,
    text: str,
    result: dict,
    *,
    scene: str,
    source_id: Optional[int],
    user_id: Optional[int],
) -> dict:
    """把包装层最终结论落成一条判定 + 一个任务，并写回 judgment_id / task_id。

    包装层为了合并政策/链接层，需要先拿到词库结论再定最终处置，因此统一在这里落库，
    避免同一条文本落两条判定。
    """
    judgment = record_judgment(
        db, text, result, scene=scene, source_id=source_id, user_id=user_id
    )
    task = (
        db.query(CgTask)
        .filter(CgTask.judgment_id == judgment.judgment_id)
        .order_by(desc(CgTask.task_id))
        .first()
    )
    result["judgment_id"] = judgment.judgment_id
    result["task_id"] = task.task_id if task else None
    result.pop("_policies", None)
    return result


def guard_text(
    db: Session,
    text: str,
    *,
    scene: str = "forum_post",
    source_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persist: bool = True,
) -> dict:
    """审核主入口：返回与旧 sensitive_filter 兼容的结果，并附带证据链。"""
    started = time.perf_counter()
    eng = engine.get_engine(db)
    result = eng.detect(text or "")
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)

    if not result["has_sensitive"]:
        result.update(
            {
                "decision": "pass",
                "confidence": 0.0,
                "policy_ids": [],
                "evidence": [{"step": "decision", "decision": "pass", "reason": "未命中词库"}],
                "policy_clauses": [],
                "judgment_id": None,
                "task_id": None,
            }
        )
        return result

    level = result["level"]
    hits = result.get("hits", [])
    confidence = _confidence(level, hits)
    policies = _policy_rows(db, result.get("policy_ids", []))
    policies.sort(key=lambda p: -(p.priority or 0))

    decision = DECISION_BY_LEVEL.get(level, "review")
    reason = f"命中 {len(hits)} 个{level}级词条"
    if decision in ("mask", "block") and confidence < REVIEW_CONFIDENCE_FLOOR:
        decision, reason = "review", f"置信度 {confidence} 低于自动处置阈值 {REVIEW_CONFIDENCE_FLOOR}"
    if level == "reviewed":
        decision = "review"
        reason = "reviewed 级词条只研判不自动处置"

    result["confidence"] = confidence
    result["decision"] = decision
    result["policy_clauses"] = [
        {"clause_id": p.clause_id, "code": p.code, "title": p.title, "priority": p.priority}
        for p in policies
    ]
    result["_policies"] = policies
    result["evidence"] = _build_evidence(db, text, result, level, confidence, policies, decision, reason)

    if not persist:
        result["judgment_id"] = None
        result["task_id"] = None
        return result

    judgment = record_judgment(
        db, text, result, scene=scene, source_id=source_id, user_id=user_id
    )
    task = (
        db.query(CgTask)
        .filter(CgTask.judgment_id == judgment.judgment_id)
        .order_by(desc(CgTask.task_id))
        .first()
    )
    result["judgment_id"] = judgment.judgment_id
    result["task_id"] = task.task_id if task else None
    result.pop("_policies", None)
    return result


def bind_source(db: Session, judgment_id: int, source_id: int) -> None:
    """发帖/评论创建成功后，把判定实例关联到真实业务主键。"""
    row = db.query(CgJudgment).filter(CgJudgment.judgment_id == judgment_id).first()
    if row is not None and row.source_id is None:
        row.source_id = source_id


def list_judgments(
    db: Session,
    *,
    scene: Optional[str] = None,
    decision: Optional[str] = None,
    human_override: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    query = db.query(CgJudgment)
    if scene:
        query = query.filter(CgJudgment.scene == scene)
    if decision:
        query = query.filter(CgJudgment.decision == decision)
    if human_override:
        query = query.filter(CgJudgment.human_override == human_override)
    total = query.count()
    rows = query.order_by(desc(CgJudgment.judgment_id)).offset(offset).limit(min(limit, 200)).all()
    return {"total": total, "items": [_serialize_judgment(r) for r in rows]}


def _serialize_judgment(row: CgJudgment) -> dict:
    return {
        "judgment_id": row.judgment_id,
        "scene": row.scene,
        "source_id": row.source_id,
        "user_id": row.user_id,
        "content_hash": row.content_hash,
        "content_snippet": row.content_snippet,
        "level": row.level,
        "decision": row.decision,
        "confidence": row.confidence,
        "hits": row.hits,
        "policy_ids": row.policy_ids,
        "evidence": row.evidence,
        "engine_version": row.engine_version,
        "latency_ms": row.latency_ms,
        "human_override": row.human_override,
        "overridden_by": row.overridden_by,
        "override_reason": row.override_reason,
        "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
    }


def get_judgment(db: Session, judgment_id: int) -> Optional[dict]:
    row = db.query(CgJudgment).filter(CgJudgment.judgment_id == judgment_id).first()
    if not row:
        return None
    data = _serialize_judgment(row)
    task = (
        db.query(CgTask)
        .filter(CgTask.judgment_id == judgment_id)
        .order_by(desc(CgTask.task_id))
        .first()
    )
    data["task"] = (
        {
            "task_id": task.task_id,
            "state": task.state,
            "priority": task.priority,
            "reviewer_id": task.reviewer_id,
            "note": task.note,
            "resolved_at": task.resolved_at.isoformat(timespec="seconds") if task.resolved_at else None,
        }
        if task
        else None
    )
    data["cases"] = [
        {"case_id": c.case_id, "title": c.title, "verdict": c.verdict}
        for c in db.query(CgCase).filter(CgCase.judgment_id == judgment_id).all()
    ]
    return data


def _upsert_case(
    db: Session,
    judgment: CgJudgment,
    *,
    verdict: str,
    reviewer_id: Optional[int],
    narrative: str,
) -> CgCase:
    case = db.query(CgCase).filter(CgCase.judgment_id == judgment.judgment_id).first()
    first_hit = (judgment.hits or [{}])[0] if judgment.hits else {}
    if case is None:
        case = CgCase(
            judgment_id=judgment.judgment_id,
            title=f"{first_hit.get('category', 'other')} / {first_hit.get('term', '未知')}",
            category=first_hit.get("category", "other"),
            level=judgment.level,
            verdict=verdict,
            narrative=narrative,
            tags=[h.get("term") for h in (judgment.hits or []) if h.get("term")],
            source="human" if reviewer_id else "auto",
            created_by=reviewer_id,
        )
        db.add(case)
        db.flush()
    else:
        case.verdict = verdict
        case.narrative = narrative
        case.created_by = reviewer_id
    graph.add_edge(db, "case", case.case_id, "derived_from", "judgment", judgment.judgment_id)
    return case


def override_judgment(
    db: Session,
    judgment_id: int,
    *,
    action: str,
    reviewer_id: Optional[int] = None,
    reason: str = "",
) -> dict:
    """人工复核：confirm 确认违规 / reject 判定误判 / modify 修改后通过。"""
    if action not in ("confirm", "reject", "modify"):
        raise ValueError("action 只支持 confirm/reject/modify")
    judgment = db.query(CgJudgment).filter(CgJudgment.judgment_id == judgment_id).first()
    if not judgment:
        raise ValueError("判定不存在")
    if judgment.human_override:
        raise ValueError(f"该判定已复核为 {judgment.human_override}，不能重复提交")

    judgment.human_override = action
    judgment.overridden_by = reviewer_id
    judgment.override_reason = (reason or "")[:500]
    judgment.overridden_at = datetime.now()

    task = (
        db.query(CgTask)
        .filter(CgTask.judgment_id == judgment_id)
        .order_by(desc(CgTask.task_id))
        .first()
    )
    if task:
        task.state = "rejected" if action == "reject" else "approved"
        task.reviewer_id = reviewer_id
        task.note = (reason or "")[:500]
        task.resolved_at = datetime.now()

    term_changes = []
    for hit in judgment.hits or []:
        term_id = hit.get("term_id")
        term = db.query(CgTerm).filter(CgTerm.term_id == term_id).first() if term_id else None
        if not term:
            continue
        if action == "reject":
            term.false_positive_count = (term.false_positive_count or 0) + 1
            term.confidence = round(max(0.1, float(term.confidence or 0.8) - 0.15), 3)
        else:
            term.confidence = round(min(0.99, float(term.confidence or 0.8) + 0.02), 3)
        term_changes.append(
            {
                "term_id": term.term_id,
                "term": term.term,
                "confidence": term.confidence,
                "false_positive_count": term.false_positive_count,
            }
        )

    if action == "reject":
        _upsert_case(
            db,
            judgment,
            verdict="false_positive",
            reviewer_id=reviewer_id,
            narrative=reason or "人工判定为误判，已下调词条置信度。",
        )
        stats.bump_daily(db, judgment.scene, "false_positive")
    else:
        _upsert_case(
            db,
            judgment,
            verdict="confirmed" if action == "confirm" else "overridden",
            reviewer_id=reviewer_id,
            narrative=reason or "人工确认命中，案例入库。",
        )

    engine.bump_version(db)
    audit.record(
        db,
        f"judgment.{action}",
        actor=f"user:{reviewer_id}" if reviewer_id else "human",
        actor_role="reviewer",
        target_type="judgment",
        target_id=judgment_id,
        before={"human_override": None},
        after={"human_override": action, "reason": reason, "terms": term_changes},
    )

    proposal = None
    if action == "reject":
        from . import proposals as proposal_service

        for item in term_changes:
            if item["false_positive_count"] >= FP_DOWNGRADE_THRESHOLD:
                term = db.query(CgTerm).filter(CgTerm.term_id == item["term_id"]).first()
                if not term or term.status != "active":
                    continue
                target_level = "reviewed" if term.level == "masked" else "deprecated"
                created = proposal_service.create_proposal(
                    db,
                    kind="update_level" if target_level != "deprecated" else "deprecate_term",
                    title=f"误判 {item['false_positive_count']} 次，建议处理词条「{term.term}」",
                    payload={
                        "term_id": term.term_id,
                        "level": target_level if target_level != "deprecated" else term.level,
                        "status": "deprecated" if target_level == "deprecated" else "active",
                    },
                    evidence=[
                        {"false_positive_count": item["false_positive_count"], "confidence": item["confidence"]},
                        {"source": "active_learning", "judgment_id": judgment_id},
                    ],
                    proposer="active_learning",
                    dedupe_key=f"fp:{term.term_id}:{judgment_id}",
                )
                proposal = created.proposal_id if created else None
    return {
        "judgment_id": judgment_id,
        "action": action,
        "task_state": task.state if task else None,
        "term_changes": term_changes,
        "proposal_id": proposal,
    }
