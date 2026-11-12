"""警考雷达：资格卡、职位匹配、时间轴、待办、对比与考情。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, get_optional_user
from ....models.models import (
    JobHistoryStat,
    JobReminder,
    JobTimelineNode,
    PolicePost,
    RecruitmentInfo,
    SysUser,
    UserJobCompare,
    UserJobTask,
    UserProfile,
)
from ....services.recruitment_match_service import match_job

router = APIRouter(prefix="/api/recruitment", tags=["招考雷达"])

CORE_FIELDS = ("degree", "major_name", "fresh_grad", "political_status", "gender")
DEAD_SOURCE_HOSTS = {"www.rszk.net", "rszk.net"}



class EligibilityPayload(BaseModel):
    degree: str = ""
    major_name: str = ""
    major_category: str = ""
    graduation_year: int | None = None
    fresh_grad: int | None = None
    age: int | None = None
    political_status: str = ""
    gender: str = ""
    veteran: int = 0
    grassroots_years: int = 0
    physical_ok: int | None = None
    preferred_regions: list[str] = []
    preferred_categories: list[str] = []


class TaskPayload(BaseModel):
    title: str
    due_at: str = ""


class ReminderPayload(BaseModel):
    remind_at: str | None = None


def _profile(db: Session, user_id: int) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()


def _eligibility(profile: UserProfile | None) -> dict[str, Any]:
    if profile is None:
        return {
            "degree": "",
            "major_name": "",
            "major_category": "",
            "graduation_year": None,
            "fresh_grad": None,
            "age": None,
            "political_status": "",
            "gender": "",
            "veteran": 0,
            "grassroots_years": 0,
            "physical_ok": None,
            "preferred_regions": [],
            "preferred_categories": [],
            "completed": False,
            "missing": list(CORE_FIELDS),
        }
    data = {
        "degree": profile.degree or "",
        "major_name": profile.major_name or "",
        "major_category": profile.major_category or "",
        "graduation_year": profile.graduation_year,
        "fresh_grad": profile.fresh_grad,
        "age": profile.age,
        "political_status": profile.political_status or "",
        "gender": profile.gender or "",
        "veteran": profile.veteran or 0,
        "grassroots_years": profile.grassroots_years or 0,
        "physical_ok": profile.physical_ok,
        "preferred_regions": profile.preferred_regions or [],
        "preferred_categories": profile.preferred_categories or [],
    }
    missing = [field for field in CORE_FIELDS if data.get(field) in ("", None)]
    data["missing"] = missing
    data["completed"] = not missing
    return data


def _safe_official_url(value: str | None) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    if urlparse(url).netloc.lower() in DEAD_SOURCE_HOSTS:
        return ""
    return url


def _post_dict(post: PolicePost, profile: UserProfile | None = None) -> dict[str, Any]:
    match = match_job(profile, post)
    return {
        "post_id": post.post_id,
        "recruitment_id": post.recruitment_id,
        "job_name": post.job_name or post.region or "",
        "employer": post.employer or "",
        "province": post.province or "",
        "city": post.city or "",
        "category": post.category or "",
        "education_req": post.education_req or post.education or "",
        "major_req": post.major_req or post.profession or "",
        "political_req": post.political_req or "",
        "fresh_grad_req": post.fresh_grad_req or "",
        "grassroots_years": post.grassroots_years,
        "age_req": post.age_req or "",
        "physical_req": post.physical_req or "",
        "other_req": post.other_req or "",
        "plan_count": post.plan_count or 0,
        "ratio": post.ratio or "",
        "registration_start": post.registration_start or "",
        "registration_end": post.registration_end or "",
        "official_url": _safe_official_url(post.official_url),
        "match": match,
    }


def _parse_date(value: str | None) -> datetime | None:
    matches = re.findall(r"20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}", value or "")
    if not matches:
        return None
    digits = re.findall(r"\d+", matches[0])
    try:
        return datetime(int(digits[0]), int(digits[1]), int(digits[2]))
    except (IndexError, ValueError):
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    clean = value.strip().replace("/", "-").replace("年", "-").replace("月", "-").replace("日", "")
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        return _parse_date(clean)


def _deadline_for_post(db: Session, post: PolicePost) -> tuple[datetime | None, str]:
    """先读结构化截止日期，再从公告正文的报名截止句提取；不猜测。"""
    direct = _parse_date(post.registration_end)
    if direct:
        return direct, "registration_end"
    rec = (
        db.query(RecruitmentInfo)
        .filter(RecruitmentInfo.recruitment_id == post.recruitment_id)
        .first()
    )
    if rec is None:
        return None, ""
    text = f"{rec.content or ''}\n{rec.registration_start or ''}\n{rec.registration_end or ''}"
    for sentence in re.split(r"[。；;\n]", text):
        if any(term in sentence for term in ("报名截止", "截止时间", "截止日期", "报名结束")):
            found = _parse_date(sentence)
            if found:
                return found, "公告正文"
    return None, ""


@router.get("/eligibility")
async def get_eligibility(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _eligibility(_profile(db, current_user.user_id))


@router.put("/eligibility")
async def save_eligibility(
    body: EligibilityPayload,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _profile(db, current_user.user_id)
    if profile is None:
        profile = UserProfile(user_id=current_user.user_id)
        db.add(profile)
        db.flush()
    for field in (
        "degree",
        "major_name",
        "major_category",
        "graduation_year",
        "fresh_grad",
        "age",
        "political_status",
        "gender",
        "veteran",
        "grassroots_years",
        "physical_ok",
        "preferred_regions",
        "preferred_categories",
    ):
        setattr(profile, field, getattr(body, field))
    profile.eligibility_completed = 1 if not [
        f for f in CORE_FIELDS if getattr(profile, f) in ("", None)
    ] else 0
    profile.eligibility_updated_at = datetime.now()
    db.commit()
    return _eligibility(profile)


@router.get("/radar")
async def radar(
    province: str = Query("", max_length=50),
    education: str = Query("", max_length=30),
    major: str = Query("", max_length=100),
    political: str = Query("", max_length=30),
    match_level: str = Query("", pattern="^(|green|yellow|red)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: SysUser | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    profile = _profile(db, current_user.user_id) if current_user else None
    query = db.query(PolicePost).filter(
        PolicePost.status == 1,
        PolicePost.parse_status == "parsed",
    )
    if province.strip():
        query = query.filter(
            or_(
                PolicePost.province.like(f"%{province.strip()}%"),
                PolicePost.city.like(f"%{province.strip()}%"),
            )
        )
    if education.strip():
        query = query.filter(PolicePost.education_req.like(f"%{education.strip()}%"))
    if major.strip():
        query = query.filter(
            or_(
                PolicePost.major_req.like(f"%{major.strip()}%"),
                PolicePost.profession.like(f"%{major.strip()}%"),
            )
        )
    if political.strip():
        query = query.filter(PolicePost.political_req.like(f"%{political.strip()}%"))
    rows = query.order_by(PolicePost.post_id.desc()).all()
    items = [_post_dict(post, profile) for post in rows]
    if match_level:
        items = [item for item in items if item["match"]["level"] == match_level]
    total = len(items)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "profile": _eligibility(profile),
        "items": items[start : start + page_size],
    }


@router.get("/jobs/{post_id}")
async def job_detail(
    post_id: int,
    current_user: SysUser | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    post = db.query(PolicePost).filter(PolicePost.post_id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    profile = _profile(db, current_user.user_id) if current_user else None
    return _post_dict(post, profile)


@router.get("/jobs/{post_id}/timeline")
async def job_timeline(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = db.query(PolicePost).filter(PolicePost.post_id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    nodes = (
        db.query(JobTimelineNode)
        .filter(JobTimelineNode.post_id == post_id)
        .order_by(JobTimelineNode.start_at)
        .all()
    )
    if not nodes:
        fallback = []
        if post.registration_start:
            fallback.append(
                {"node_type": "registration_start", "title": "报名开始", "date": post.registration_start}
            )
        if post.registration_end:
            fallback.append(
                {"node_type": "registration_end", "title": "报名截止", "date": post.registration_end}
            )
        return {"source": "fallback", "nodes": fallback}
    return {
        "source": "parsed",
        "nodes": [
            {
                "node_type": node.node_type,
                "title": node.title,
                "start_at": node.start_at or "",
                "end_at": node.end_at or "",
                "evidence": node.evidence or "",
                "confidence": node.confidence or 0,
            }
            for node in nodes
        ],
    }


def _ensure_tasks(db: Session, user_id: int, post: PolicePost) -> list[UserJobTask]:
    tasks = (
        db.query(UserJobTask)
        .filter(UserJobTask.user_id == user_id, UserJobTask.post_id == post.post_id)
        .order_by(UserJobTask.task_id)
        .all()
    )
    if tasks:
        return tasks
    text = f"{post.other_req or ''} {post.major_req or ''}".lower()
    defaults = [
        ("registration_form", "准备报名表、身份证与证件照", post.registration_end or ""),
        ("education", "准备学信网学历/学籍证明", ""),
    ]
    if "党员" in text:
        defaults.append(("party", "准备党员/预备党员证明", ""))
    if "基层" in text:
        defaults.append(("grassroots", "准备基层工作经历证明", ""))
    if "体能" in text:
        defaults.append(("physical", "准备体能测试承诺书并完成自评", ""))
    for code, title, due in defaults:
        db.add(
            UserJobTask(
                user_id=user_id,
                post_id=post.post_id,
                task_code=code,
                title=title,
                due_at=due,
                source="auto",
            )
        )
    db.commit()
    return (
        db.query(UserJobTask)
        .filter(UserJobTask.user_id == user_id, UserJobTask.post_id == post.post_id)
        .all()
    )


@router.get("/jobs/{post_id}/tasks")
async def list_tasks(
    post_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(PolicePost).filter(PolicePost.post_id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    tasks = _ensure_tasks(db, current_user.user_id, post)
    return {
        "items": [
            {
                "task_id": task.task_id,
                "task_code": task.task_code,
                "title": task.title,
                "due_at": task.due_at or "",
                "status": task.status,
            }
            for task in tasks
        ]
    }


@router.post("/jobs/{post_id}/tasks")
async def add_task(
    post_id: int,
    body: TaskPayload,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(PolicePost).filter(PolicePost.post_id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    task = UserJobTask(
        user_id=current_user.user_id,
        post_id=post_id,
        task_code=f"manual_{int(datetime.now().timestamp())}",
        title=body.title,
        due_at=body.due_at,
        source="manual",
    )
    db.add(task)
    db.commit()
    return {"task_id": task.task_id, "title": task.title}


@router.patch("/tasks/{task_id}")
async def toggle_task(
    task_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(UserJobTask)
        .filter(UserJobTask.task_id == task_id, UserJobTask.user_id == current_user.user_id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="待办不存在")
    task.status = 0 if task.status else 1
    db.commit()
    return {"task_id": task.task_id, "status": task.status}


@router.get("/compare")
async def list_compare(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PolicePost)
        .join(UserJobCompare, UserJobCompare.post_id == PolicePost.post_id)
        .filter(UserJobCompare.user_id == current_user.user_id)
        .all()
    )
    profile = _profile(db, current_user.user_id)
    return {"items": [_post_dict(post, profile) for post in rows]}


@router.post("/compare/{post_id}")
async def add_compare(
    post_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(UserJobCompare).filter(UserJobCompare.user_id == current_user.user_id).count()
    if count >= 3:
        raise HTTPException(status_code=400, detail="对比篮最多 3 个职位")
    exists = (
        db.query(UserJobCompare)
        .filter(UserJobCompare.user_id == current_user.user_id, UserJobCompare.post_id == post_id)
        .first()
    )
    if exists is None:
        db.add(UserJobCompare(user_id=current_user.user_id, post_id=post_id))
        db.commit()
    return {"ok": True, "count": min(3, count + 1)}


@router.delete("/compare/{post_id}")
async def remove_compare(
    post_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(UserJobCompare).filter(
        UserJobCompare.user_id == current_user.user_id, UserJobCompare.post_id == post_id
    ).delete()
    db.commit()
    return {"ok": True}


@router.get("/jobs/{post_id}/history")
async def job_history(post_id: int, db: Session = Depends(get_db)):
    post = db.query(PolicePost).filter(PolicePost.post_id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    rows = (
        db.query(JobHistoryStat)
        .filter(
            or_(
                JobHistoryStat.post_id == post_id,
                JobHistoryStat.province == post.province,
            )
        )
        .order_by(JobHistoryStat.year.desc(), JobHistoryStat.stat_id)
        .limit(50)
        .all()
    )
    return {
        "items": [
            {
                "year": row.year,
                "job_name": row.job_name or "",
                "employer": row.employer or "",
                "min_score": row.min_score,
                "avg_score": row.avg_score,
                "applicants": row.applicants,
                "plan_count": row.plan_count,
                "ratio": row.ratio,
                "source_name": row.source_name or "",
                "source_url": row.source_url or "",
                "confidence": row.confidence,
            }
            for row in rows
        ],
        "note": "暂无历年数据" if not rows else "数据仅供参考，以官方公布为准",
    }


@router.get("/jobs/{post_id}/reminder-suggestion")
async def reminder_suggestion(post_id: int, db: Session = Depends(get_db)):
    post = db.query(PolicePost).filter(PolicePost.post_id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    deadline, source = _deadline_for_post(db, post)
    if deadline is None:
        return {
            "deadline_at": None,
            "suggested_at": None,
            "source": "",
            "message": "公告未写明确报名截止时间，请手动选择提醒日期",
        }
    suggested = deadline - timedelta(hours=24)
    if suggested <= datetime.now():
        suggested = datetime.now() + timedelta(hours=1)
    return {
        "deadline_at": deadline.isoformat(),
        "suggested_at": suggested.isoformat(),
        "source": source,
        "message": f"已识别报名截止时间（{source}），默认提前 24 小时提醒",
    }


@router.post("/jobs/{post_id}/remind")
async def create_reminder(
    post_id: int,
    body: ReminderPayload | None = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(PolicePost).filter(PolicePost.post_id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    supplied = _parse_datetime(body.remind_at if body else None)
    deadline, _source = _deadline_for_post(db, post)
    if supplied is not None:
        remind_at = supplied
    elif deadline is not None:
        remind_at = deadline - timedelta(hours=24)
    else:
        raise HTTPException(
            status_code=400,
            detail="该公告没有明确报名截止时间，请选择提醒日期",
        )
    if remind_at <= datetime.now():
        raise HTTPException(status_code=400, detail="提醒时间必须晚于当前时间")
    exists = (
        db.query(JobReminder)
        .filter(
            JobReminder.user_id == current_user.user_id,
            JobReminder.post_id == post_id,
            JobReminder.node_type == "registration_end",
        )
        .first()
    )
    if exists is None:
        db.add(
            JobReminder(
                user_id=current_user.user_id,
                post_id=post_id,
                node_type="registration_end",
                remind_at=remind_at,
                channel="notification",
                status="pending",
            )
        )
        db.commit()
    else:
        exists.remind_at = remind_at
        exists.status = "pending"
        exists.sent_at = None
        db.commit()
    return {"ok": True, "remind_at": remind_at.isoformat()}
