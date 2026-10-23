"""反馈工单 P0 测试。

覆盖：工单号生成、详情权限、学生追加回复、截图数量上限。
"""
from app.models.models import FeedbackReply, SysUser, UserFeedback


def _create_feedback(client, auth_headers, **overrides):
    payload = {
        "category": "数据错误",
        "feedback_type": "answer",
        "content": "这道题答案不对",
        "question_id": 123,
    }
    payload.update(overrides)
    return client.post("/api/feedback", headers=auth_headers, json=payload)


def test_submit_feedback_returns_ticket_no(client, auth_headers):
    resp = _create_feedback(client, auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket_no"].startswith("FB")
    assert body["ticket_no"].endswith(str(body["feedback_id"]).zfill(6))


def test_feedback_detail_owner_and_staff(client, auth_headers, admin_headers, db_session):
    feedback_id = _create_feedback(client, auth_headers).json()["feedback_id"]

    owner = client.get(f"/api/feedback/{feedback_id}", headers=auth_headers)
    assert owner.status_code == 200
    assert owner.json()["ticket_no"].startswith("FB")

    staff = client.get(f"/api/feedback/{feedback_id}", headers=admin_headers)
    assert staff.status_code == 200

    other = SysUser(
        user_no="student900",
        username="其他学生",
        password="x",
        phone="13300133000",
        user_type="student",
        role_level=0,
        status=1,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    from app.core.security import create_access_token

    token = create_access_token(
        data={"user_id": other.user_id, "user_no": other.user_no}
    )
    denied = client.get(
        f"/api/feedback/{feedback_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 403


def test_student_can_append_reply(client, auth_headers, db_session):
    feedback_id = _create_feedback(client, auth_headers).json()["feedback_id"]

    resp = client.post(
        f"/api/feedback/{feedback_id}/reply",
        headers=auth_headers,
        json={"content": "补充：截图已上传"},
    )
    assert resp.status_code == 200
    rows = (
        db_session.query(FeedbackReply)
        .filter_by(feedback_id=feedback_id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].role == "student"


def test_feedback_attachments_limit(client, auth_headers, db_session):
    too_many = [{"name": f"{i}.png", "url": f"/uploads/{i}.png"} for i in range(6)]
    resp = _create_feedback(client, auth_headers, attachments=too_many)
    assert resp.status_code == 400

    ok = [{"name": f"{i}.png", "url": f"/uploads/{i}.png"} for i in range(5)]
    resp_ok = _create_feedback(client, auth_headers, attachments=ok)
    assert resp_ok.status_code == 200

    fb = db_session.query(UserFeedback).filter_by(feedback_id=resp_ok.json()["feedback_id"]).first()
    assert len(fb.attachments) == 5
