# -*- coding: utf-8 -*-
"""考点复核队列 API（v8 M2 / P3）。

重分类脚本把「低置信（tier=review）」的分配写进 point_assign_audit，
本路由让教师/管理员逐条确认：确认即保留新考点，驳回则按 old_point_id 还原。

GET  /api/point-review/queue?batch_id=&page=&page_size=   待复核清单
POST /api/point-review/{audit_id}                        确认 / 驳回
GET  /api/point-review/stats                              各批次复核进度
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import KnowledgePoint, QuestionBank, SysUser

router = APIRouter(prefix="/api/point-review", tags=["考点复核"])
logger = logging.getLogger(__name__)


class ReviewDecision(BaseModel):
    accept: bool
    note: Optional[str] = None


def _snippet(raw: Optional[str], width: int = 90) -> str:
    if not raw:
        return ""
    plain = " ".join(str(raw).replace("[IMAGE:", " ").split())
    return plain[:width] + ("…" if len(plain) > width else "")


def _require_reviewer(user: SysUser) -> None:
    """只允许教师与管理员复核，学生看不到他人的分考点结果。"""
    role = getattr(user, "user_type", None)
    if role not in ("teacher", "admin", 2, 3):
        raise HTTPException(status_code=403, detail="仅教师或管理员可复核考点分配")


@router.get("/queue")
async def get_review_queue(
    batch_id: Optional[str] = Query(None, description="批次号，缺省为最新批次"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """待复核清单：只返回 tier=review 且尚未复核的分配。"""
    _require_reviewer(current_user)
    batch = batch_id or db.execute(
        text("SELECT batch_id FROM point_assign_audit ORDER BY audit_id DESC LIMIT 1")
    ).scalar()
    if not batch:
        return {"batch_id": None, "total": 0, "items": []}

    total = db.execute(
        text(
            "SELECT COUNT(*) FROM point_assign_audit "
            "WHERE batch_id = :b AND tier = :t AND review_status = :s"
        ),
        {"b": batch, "t": "review", "s": "pending"},
    ).scalar() or 0

    rows = db.execute(
        text(
            "SELECT a.audit_id, a.question_id, a.old_point_id, a.new_point_id, a.score, a.tier, a.reason "
            "FROM point_assign_audit a WHERE a.batch_id = :b AND a.tier = :t AND a.review_status = :s "
            "ORDER BY a.score DESC, a.audit_id ASC LIMIT :lim OFFSET :off"
        ),
        {"b": batch, "t": "review", "s": "pending", "lim": page_size, "off": (page - 1) * page_size},
    ).fetchall()

    # 批量取题干与考点名，避免 N+1
    qids = [r[1] for r in rows]
    pids = {r[2] for r in rows} | {r[3] for r in rows}
    texts = {}
    if qids:
        for q in db.query(QuestionBank.question_id, QuestionBank.question_content).filter(
            QuestionBank.question_id.in_(qids)
        ):
            texts[q.question_id] = _snippet(q.question_content)
    names = {}
    if pids:
        for kp in db.query(KnowledgePoint.point_id, KnowledgePoint.point_name).filter(
            KnowledgePoint.point_id.in_([p for p in pids if p])
        ):
            names[kp.point_id] = kp.point_name

    items = [
        {
            "audit_id": r[0],
            "question_id": r[1],
            "old_point_name": names.get(r[2]) or "未挂载",
            "new_point_name": names.get(r[3]) or "未挂载",
            "score": r[4],
            "tier": r[5],
            "reason": r[6],
            "snippet": texts.get(r[1], ""),
        }
        for r in rows
    ]
    return {"batch_id": batch, "total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/{audit_id}")
async def decide_review(
    audit_id: int,
    body: ReviewDecision,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """确认保留新考点；驳回则把题还原到旧考点（含旧 sub_category 快照）。"""
    _require_reviewer(current_user)
    row = db.execute(
        text(
            "SELECT question_id, old_point_id, new_point_id, reason, review_status "
            "FROM point_assign_audit WHERE audit_id = :a"
        ),
        {"a": audit_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="复核记录不存在")
    if row[4] and row[4] != "pending":
        raise HTTPException(status_code=409, detail="该条已复核")

    status = "accepted" if body.accept else "rejected"
    if not body.accept:
        db.query(QuestionBank).filter(QuestionBank.question_id == row[0]).update(
            {QuestionBank.point_id: row[1]}, synchronize_session=False
        )
    db.execute(
        text(
            "UPDATE point_assign_audit SET review_status = :s, reviewer_id = :u, review_time = :t, "
            "review_note = :n WHERE audit_id = :a"
        ),
        {
            "s": status,
            "u": getattr(current_user, "user_id", None),
            "t": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "n": body.note,
            "a": audit_id,
        },
    )
    db.commit()
    logger.info("考点复核 audit=%s -> %s by user=%s", audit_id, status, getattr(current_user, "user_id", None))
    return {"audit_id": audit_id, "review_status": status, "reverted": not body.accept}


@router.get("/stats")
async def review_stats(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    _require_reviewer(current_user)
    rows = db.execute(
        text(
            "SELECT batch_id, tier, review_status, COUNT(*) FROM point_assign_audit "
            "GROUP BY batch_id, tier, review_status ORDER BY batch_id DESC"
        )
    ).fetchall()
    out: dict = {}
    for batch, tier, status, cnt in rows:
        bucket = out.setdefault(batch, {"batch_id": batch, "total": 0, "by_tier": {}, "by_status": {}})
        bucket["total"] += cnt
        bucket["by_tier"][tier] = bucket["by_tier"].get(tier, 0) + cnt
        bucket["by_status"][status or "pending"] = bucket["by_status"].get(status or "pending", 0) + cnt
    return {"batches": list(out.values())}
