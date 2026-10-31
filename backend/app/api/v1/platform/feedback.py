"""
意见反馈 + 帮助中心 API
- 学生：提交反馈、查看我的反馈（含回复）
- 管理员/教师：查看全部反馈、回复反馈
- 帮助中心：静态务实 FAQ
"""
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ....core.database import get_db
from ....core.security import get_current_user, require_teacher_or_admin
from ....models.models import SysUser, UserFeedback, FeedbackReply

router = APIRouter(prefix="/api/feedback", tags=["意见反馈"])
admin_router = APIRouter(prefix="/api/admin/feedback", tags=["反馈管理"])

VALID_CATEGORIES = ["功能异常", "内容错误", "意见建议", "其他"]

# 务实 FAQ（帮助中心内容）
FAQ_ITEMS = [
    {"category": "账号与登录", "items": [
        {"q": "如何修改密码？", "a": "进入「我的 → 设置 → 个人设置」，点击修改密码，验证旧密码后设置新密码（至少6位）。"},
        {"q": "忘记密码怎么办？", "a": "请联系任课教师或管理员重置密码；重置后请尽快登录并修改为个人密码。"},
        {"q": "可以在多台设备登录吗？", "a": "可以，同一账号最多同时保持 3 台设备在线。可在「我的 → 设备管理」查看并移除不再使用的设备。"},
    ]},
    {"category": "刷题与错题", "items": [
        {"q": "做题记录会保存吗？", "a": "会。每次练习都会记录到「练习记录」和「学习数据」，错题自动收录进「错题集」，可随时复习。"},
        {"q": "错题如何复习？", "a": "进入「错题集」，按知识点/时间/科目选择复习队列；连续答对 3 次会自动「斩题」，10 天后自动清理。"},
        {"q": "答案解析为什么有时为空？", "a": "个别题目的解析在数据录入时缺失，已收录进内容整改计划。若遇到，可提交「内容错误」反馈，我们会尽快补全。"},
    ]},
    {"category": "金币与成就", "items": [
        {"q": "金币怎么获得？", "a": "每日签到获得 5 金币，连续签到满 7 天额外奖励 20 金币；完成成就也会获得对应金币奖励。"},
        {"q": "成就如何解锁？", "a": "完成对应条件自动解锁（如累计做题、连续学习、正确率达标等）。进入「我的 → 我的成就」查看全部 45 项成就与实时进度。"},
        {"q": "金币能做什么？", "a": "金币可用于兑换商城的学习资料与服务。具体商品以「金币购」页面为准。"},
    ]},
    {"category": "设备与安全", "items": [
        {"q": "如何保护账号安全？", "a": "请勿向他人透露账号密码；在公共设备登录后请及时退出，并可在「设备管理」中移除异常登录设备。"},
        {"q": "发现异常登录怎么办？", "a": "进入「我的 → 设备管理」，点击「退出所有设备」可强制下线所有设备，并尽快修改密码。"},
    ]},
    {"category": "反馈与联系", "items": [
        {"q": "如何反馈问题？", "a": "进入「我的 → 意见反馈」，选择分类并描述问题，提交后教师/管理员会查看并回复，你可在反馈列表中查看回复。"},
        {"q": "反馈多久会处理？", "a": "一般 1-3 个工作日内回复；涉及内容错误会进入题库整改流程，处理结果会回复到你的反馈中。"},
    ]},
]


@router.get("/faq", summary="帮助中心FAQ")
async def get_faq():
    return {"items": FAQ_ITEMS}


VALID_FEEDBACK_TYPES = {"question_content", "answer", "analysis", "function", "other"}
VALID_SOURCES = {"form", "forum", "practice"}
MAX_FEEDBACK_IMAGES = 5


def _validate_attachments(raw: Any) -> list:
    """反馈截图最多 5 张；只接受 {name,url,size,type} 结构。"""
    if not raw:
        return []
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="attachments 必须是数组")
    if len(raw) > MAX_FEEDBACK_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"反馈截图最多 {MAX_FEEDBACK_IMAGES} 张",
        )
    cleaned = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("url"):
            raise HTTPException(status_code=400, detail="附件格式错误")
        cleaned.append(
            {
                "name": str(item.get("name") or ""),
                "url": str(item.get("url")),
                "size": item.get("size"),
                "type": item.get("type"),
            }
        )
    return cleaned


@router.post("", summary="提交意见反馈")
async def submit_feedback(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    category = payload.get("category", "其他")
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="反馈内容不能为空")
    if len(content) > 1000:
        raise HTTPException(status_code=400, detail="反馈内容过长（最多1000字）")
    if category not in VALID_CATEGORIES:
        category = "其他"

    feedback_type = payload.get("feedback_type") or "other"
    if feedback_type not in VALID_FEEDBACK_TYPES:
        feedback_type = "other"
    source = payload.get("source") or "form"
    if source not in VALID_SOURCES:
        source = "form"

    fb = UserFeedback(
        user_id=current_user.user_id,
        category=category,
        content=content,
        contact=(payload.get("contact") or "").strip() or None,
        status="pending",
        feedback_type=feedback_type,
        question_id=payload.get("question_id"),
        practice_record_id=payload.get("practice_record_id"),
        attachments=_validate_attachments(payload.get("attachments")),
        priority=payload.get("priority") or "normal",
        source=source,
        forum_post_id=payload.get("forum_post_id"),
        subject_id=payload.get("subject_id"),
    )
    db.add(fb)
    db.flush()  # 先拿到 feedback_id，再生成可读工单号
    from datetime import datetime as _dt

    fb.ticket_no = f"FB{_dt.now().strftime('%Y%m%d')}-{fb.feedback_id:06d}"
    db.commit()
    db.refresh(fb)
    return {
        "feedback_id": fb.feedback_id,
        "ticket_no": fb.ticket_no,
        "message": "反馈已提交，感谢你的建议",
    }


@router.get("/{feedback_id}", summary="反馈工单详情")
async def get_feedback_detail(
    feedback_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fb = db.query(UserFeedback).filter(UserFeedback.feedback_id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")
    is_staff = current_user.user_type in ("teacher", "admin")
    if fb.user_id != current_user.user_id and not is_staff:
        raise HTTPException(status_code=403, detail="无权查看该反馈")

    data = _serialize_feedback(fb)
    replies = (
        db.query(FeedbackReply)
        .filter(FeedbackReply.feedback_id == feedback_id)
        .order_by(FeedbackReply.created_at.asc())
        .all()
    )
    data["replies"] = [
        {
            "reply_id": r.reply_id,
            "user_id": r.user_id,
            "role": r.role,
            "content": r.content,
            "attachments": r.attachments or [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in replies
    ]
    return data


@router.post("/{feedback_id}/reply", summary="学生追加反馈")
async def reply_own_feedback(
    feedback_id: int,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="回复内容不能为空")
    if len(content) > 1000:
        raise HTTPException(status_code=400, detail="回复内容过长（最多1000字）")

    fb = db.query(UserFeedback).filter(UserFeedback.feedback_id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")
    if fb.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="只能追加自己的反馈")

    db.add(
        FeedbackReply(
            feedback_id=feedback_id,
            user_id=current_user.user_id,
            role=current_user.user_type,
            content=content,
            attachments=_validate_attachments(payload.get("attachments")),
        )
    )
    db.commit()
    return {"success": True, "feedback_id": feedback_id}


@router.get("/my", summary="我的反馈列表")
async def my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(UserFeedback).filter(UserFeedback.user_id == current_user.user_id)
    total = query.count()
    items = query.order_by(desc(UserFeedback.created_at))\
        .offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [_serialize_feedback(f) for f in items],
    }


# ---------------- 管理员/教师端 ----------------

@admin_router.get("", summary="反馈列表（管理员/教师）")
async def list_all_feedback(
    status: Optional[str] = Query(None, description="筛选: pending/processing/replied/closed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
):
    query = db.query(UserFeedback)
    if status:
        query = query.filter(UserFeedback.status == status)
    total = query.count()
    items = query.order_by(desc(UserFeedback.created_at))\
        .offset((page - 1) * page_size).limit(page_size).all()

    # 附加提交人姓名
    result = []
    for f in items:
        data = _serialize_feedback(f)
        data["user_name"] = f.user.username if f.user else ""
        data["user_no"] = f.user.user_no if f.user else ""
        result.append(data)

    return {"total": total, "page": page, "page_size": page_size, "items": result}


@admin_router.post("/{feedback_id}/reply", summary="回复反馈")
async def reply_feedback(
    feedback_id: int,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db)
):
    reply = (payload.get("reply") or "").strip()
    if not reply:
        raise HTTPException(status_code=400, detail="回复内容不能为空")

    fb = db.query(UserFeedback).filter(UserFeedback.feedback_id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="反馈不存在")

    from datetime import datetime

    now = datetime.now()
    fb.reply = reply
    fb.reply_by = current_user.user_id
    fb.handler_id = fb.handler_id or current_user.user_id
    fb.status = "replied"
    fb.replied_at = now
    if not fb.first_response_at:
        fb.first_response_at = now
    db.add(
        FeedbackReply(
            feedback_id=feedback_id,
            user_id=current_user.user_id,
            role=current_user.user_type,
            content=reply,
        )
    )
    db.commit()
    return {"message": "回复成功", "feedback_id": feedback_id}


def _serialize_feedback(f: UserFeedback) -> Dict[str, Any]:
    return {
        "feedback_id": f.feedback_id,
        "ticket_no": f.ticket_no,
        "category": f.category,
        "feedback_type": f.feedback_type,
        "content": f.content,
        "contact": f.contact,
        "status": f.status,
        "priority": f.priority,
        "question_id": f.question_id,
        "practice_record_id": f.practice_record_id,
        "subject_id": f.subject_id,
        "attachments": f.attachments or [],
        "source": f.source,
        "forum_post_id": f.forum_post_id,
        "handler_id": f.handler_id,
        "claimed_at": f.claimed_at.isoformat() if f.claimed_at else None,
        "first_response_at": f.first_response_at.isoformat() if f.first_response_at else None,
        "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
        "merged_into": f.merged_into,
        "reply": f.reply,
        "replied_at": f.replied_at.isoformat() if f.replied_at else None,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }
