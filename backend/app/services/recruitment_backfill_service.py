"""把现有招考公告回填为雷达职位（MVP，不覆盖已有 police_post）。"""

from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy.orm import Session

from ..models.models import JobTimelineNode, PolicePost, RecruitmentInfo


def _first(pattern: str, text: str) -> str:
    match = re.search(pattern, text or "")
    return match.group(0) if match else ""


def backfill_police_posts(db: Session) -> dict[str, int]:
    created = 0
    timelines = 0
    for rec in db.query(RecruitmentInfo).filter(RecruitmentInfo.status == 1).all():
        exists = (
            db.query(PolicePost)
            .filter(PolicePost.recruitment_id == rec.recruitment_id)
            .first()
        )
        if exists:
            continue
        text = f"{rec.title or ''}\n{rec.requirements or ''}\n{rec.content or ''}"
        education = ""
        for value in ("博士", "硕士", "研究生", "本科", "大专"):
            if value in text:
                education = value
                break
        post = PolicePost(
            recruitment_id=rec.recruitment_id,
            job_name=rec.title[:200],
            employer=(rec.organization or "")[:200],
            province=(rec.region or "")[:50],
            city=(rec.region or "")[:50],
            category=(rec.category or "")[:50],
            education_req=education or None,
            major_req=_first(r"(?:专业|学科)(?:要求|：|:)?[^。；\n]{0,120}", text) or None,
            political_req="党员" if "党员" in text else None,
            fresh_grad_req="应届" if "应届" in text else None,
            registration_start=rec.registration_start or None,
            registration_end=rec.registration_end or rec.deadline or None,
            official_url=rec.url or None,
            source=rec.source_name or "历史公告",
            status=1,
            parse_status="manual",
            parse_confidence=0.5,
            evidence_json=json.dumps(
                {"source": "recruitment_info", "title": rec.title}, ensure_ascii=False
            ),
            updated_at=datetime.now(),
        )
        db.add(post)
        db.flush()
        created += 1
        nodes = []
        if rec.registration_start:
            nodes.append(("registration_start", "报名开始", rec.registration_start))
        if rec.registration_end or rec.deadline:
            nodes.append(("registration_end", "报名截止", rec.registration_end or rec.deadline))
        for node_type, title, date_value in nodes:
            db.add(
                JobTimelineNode(
                    recruitment_id=rec.recruitment_id,
                    post_id=post.post_id,
                    node_type=node_type,
                    title=title,
                    start_at=date_value,
                    end_at=date_value,
                    evidence="recruitment_info",
                    confidence=0.5,
                )
            )
            timelines += 1
    db.commit()
    return {"posts_created": created, "timeline_nodes": timelines}
