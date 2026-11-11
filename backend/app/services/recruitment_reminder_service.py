"""招考截止提醒：把到期 JobReminder 写入站内信。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..models.models import JobReminder, PolicePost, UserNotification


def dispatch_job_reminders(db: Session) -> dict[str, int]:
    now = datetime.now()
    rows = (
        db.query(JobReminder)
        .filter(JobReminder.status == "pending", JobReminder.remind_at <= now)
        .order_by(JobReminder.remind_at)
        .limit(100)
        .all()
    )
    sent = 0
    failed = 0
    for reminder in rows:
        post = db.query(PolicePost).filter(PolicePost.post_id == reminder.post_id).first()
        if post is None:
            reminder.status = "skipped"
            continue
        try:
            db.add(
                UserNotification(
                    user_id=reminder.user_id,
                    type="system",
                    title=f"招考提醒：{post.job_name or post.employer or '招考职位'}",
                    content=(
                        f"{post.job_name or post.employer or '招考职位'} 的报名截止时间："
                        f"{post.registration_end or '请查看公告'}。请及时完成报名/缴费。"
                    ),
                    link=f"/recruitment/radar?post_id={post.post_id}",
                    related_type="job_reminder",
                    related_id=reminder.reminder_id,
                    is_read=0,
                )
            )
            reminder.sent_at = now
            reminder.status = "sent"
            sent += 1
        except Exception:
            reminder.status = "failed"
            failed += 1
    db.commit()
    return {"due": len(rows), "sent": sent, "failed": failed}
