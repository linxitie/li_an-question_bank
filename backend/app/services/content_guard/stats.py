"""看板聚合：词库规模、今日判定、待办与趋势。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.content_guard import (
    CgAuditEvent,
    CgCase,
    CgJudgment,
    CgProposal,
    CgRedteamSample,
    CgStatDaily,
    CgTask,
    CgTerm,
    CgVariant,
)
from . import engine


def bump_daily(db: Session, scene: str, decision: str) -> None:
    """同时累计场景行与 all 汇总行；看板只读 all，避免扫明细表。"""
    today = date.today()
    scenes = ("all",) if scene == "all" else (scene, "all")
    for scene_key in scenes:
        row = (
            db.query(CgStatDaily)
            .filter(CgStatDaily.stat_date == today, CgStatDaily.scene == scene_key)
            .first()
        )
        if row is None:
            row = CgStatDaily(stat_date=today, scene=scene_key)
            db.add(row)
        row.total = (row.total or 0) + 1
        if decision == "block":
            row.blocked = (row.blocked or 0) + 1
        elif decision == "mask":
            row.masked = (row.masked or 0) + 1
        elif decision == "review":
            row.reviewed = (row.reviewed or 0) + 1
        elif decision == "pass":
            row.passed = (row.passed or 0) + 1
        elif decision == "false_positive":
            row.false_positive = (row.false_positive or 0) + 1
    db.flush()


def overview(db: Session) -> dict:
    today = date.today()
    term_total = db.query(func.count(CgTerm.term_id)).scalar() or 0
    by_level = dict(
        db.query(CgTerm.level, func.count(CgTerm.term_id)).group_by(CgTerm.level).all()
    )
    by_status = dict(
        db.query(CgTerm.status, func.count(CgTerm.term_id)).group_by(CgTerm.status).all()
    )
    variant_total = db.query(func.count(CgVariant.variant_id)).scalar() or 0
    judgment_total = db.query(func.count(CgJudgment.judgment_id)).scalar() or 0
    today_row = (
        db.query(CgStatDaily)
        .filter(CgStatDaily.stat_date == today, CgStatDaily.scene == "all")
        .first()
    )
    pending_tasks = (
        db.query(func.count(CgTask.task_id)).filter(CgTask.state == "pending").scalar() or 0
    )
    pending_proposals = (
        db.query(func.count(CgProposal.proposal_id))
        .filter(CgProposal.status == "pending")
        .scalar()
        or 0
    )
    undetected = (
        db.query(func.count(CgRedteamSample.sample_id))
        .filter(CgRedteamSample.detected.is_(False))
        .scalar()
        or 0
    )
    return {
        "terms": {"total": term_total, "by_level": by_level, "by_status": by_status},
        "variants": variant_total,
        "judgments": judgment_total,
        "today": {
            "total": today_row.total if today_row else 0,
            "blocked": today_row.blocked if today_row else 0,
            "masked": today_row.masked if today_row else 0,
            "reviewed": today_row.reviewed if today_row else 0,
            "false_positive": today_row.false_positive if today_row else 0,
        },
        "pending_tasks": pending_tasks,
        "pending_proposals": pending_proposals,
        "redteam_undetected": undetected,
        "cases": db.query(func.count(CgCase.case_id)).scalar() or 0,
        "audit_events": db.query(func.count(CgAuditEvent.event_id)).scalar() or 0,
        "engine_version": engine.read_version(db),
    }


def trend(db: Session, days: int = 14) -> list[dict]:
    days = max(1, min(days, 90))
    start = date.today() - timedelta(days=days - 1)
    rows = (
        db.query(CgStatDaily)
        .filter(CgStatDaily.stat_date >= start, CgStatDaily.scene == "all")
        .order_by(CgStatDaily.stat_date.asc())
        .all()
    )
    buckets: dict[str, dict] = {}
    for offset in range(days):
        key = (start + timedelta(days=offset)).isoformat()
        buckets[key] = {
            "date": key,
            "total": 0,
            "blocked": 0,
            "masked": 0,
            "reviewed": 0,
            "false_positive": 0,
        }
    for row in rows:
        key = row.stat_date.isoformat() if row.stat_date else None
        if key not in buckets:
            continue
        bucket = buckets[key]
        for field in ("total", "blocked", "masked", "reviewed", "false_positive"):
            bucket[field] += getattr(row, field) or 0
    return list(buckets.values())


def top_terms(db: Session, limit: int = 10, since: Optional[datetime] = None) -> list[dict]:
    query = db.query(CgTerm).filter(CgTerm.hit_count > 0)
    if since:
        query = query.filter(CgTerm.last_hit_at >= since)
    rows = query.order_by(CgTerm.hit_count.desc()).limit(max(1, min(limit, 50))).all()
    return [
        {
            "term_id": r.term_id,
            "term": r.term,
            "level": r.level,
            "category": r.category,
            "status": r.status,
            "hit_count": r.hit_count,
            "false_positive_count": r.false_positive_count,
            "confidence": r.confidence,
            "last_hit_at": r.last_hit_at.isoformat(timespec="seconds") if r.last_hit_at else None,
        }
        for r in rows
    ]
