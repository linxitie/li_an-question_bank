# -*- coding: utf-8 -*-
"""导入质量报告（v8 M4 / P5）。

GET /api/import/records/{import_id}/report

回答教师最关心的三个问题：
1. 这份卷子解析出来多少题、丢了多少（成功/重复/失败）；
2. 每题的质量分分布（低于 60 分即「待修正」）；
3. 具体哪些题有问题、问题是什么（题干过短/选项待补充/缺解析/配图缺失）。
"""
from __future__ import annotations

import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import QuestionImportRecord, SysUser
from ....services.question_ingest.quality import PASS_SCORE, score_question

router = APIRouter(prefix="/api/import", tags=["题目导入"])
logger = logging.getLogger(__name__)


def _items_of(record: QuestionImportRecord) -> list:
    """preview_data 兼容 list 与 {questions:[...]} 两种历史写法。"""
    data = record.preview_data or []
    if isinstance(data, dict):
        for key in ("questions", "items", "list", "preview"):
            if isinstance(data.get(key), list):
                return data[key]
        return []
    return data if isinstance(data, list) else []


@router.get("/records/{import_id}/report")
async def get_import_report(
    import_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    record = db.query(QuestionImportRecord).filter(
        QuestionImportRecord.import_id == import_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="导入记录不存在")

    items = _items_of(record)
    scored = []
    flag_counter: Counter = Counter()
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        payload = item.get("data") if isinstance(item.get("data"), dict) else item
        res = score_question(payload)
        for f in res["flags"]:
            flag_counter[f] += 1
        if not res["pass"]:
            raw = str(payload.get("question_content") or "")
            scored.append({
                "index": idx + 1,
                "snippet": " ".join(raw.split())[:80],
                "score": res["score"],
                "flags": res["flags"],
            })

    buckets = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = item.get("data") if isinstance(item.get("data"), dict) else item
        s = score_question(payload)["score"]
        if s >= 90:
            buckets["excellent"] += 1
        elif s >= 75:
            buckets["good"] += 1
        elif s >= PASS_SCORE:
            buckets["fair"] += 1
        else:
            buckets["poor"] += 1

    return {
        "import_id": import_id,
        "original_filename": record.original_filename,
        "file_type": record.file_type,
        "import_status": record.import_status,
        "import_time": record.import_time.strftime("%Y-%m-%d %H:%M:%S") if record.import_time else None,
        "counts": {
            "total": record.total_questions or 0,
            "success": record.success_count or 0,
            "failed": record.failed_count or 0,
            "duplicate": record.duplicate_count or 0,
        },
        "quality": {"buckets": buckets, "pass_line": PASS_SCORE, "need_fix": len(scored)},
        "flag_summary": dict(flag_counter.most_common()),
        "need_fix_items": scored[:50],
    }