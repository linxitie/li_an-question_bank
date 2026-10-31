"""论坛举报与站内信 P0 测试。"""
from app.models.models import ForumPost, UserNotification


def _make_post(db_session, user):
    post = ForumPost(
        user_id=user.user_id,
        title="测试帖子",
        content="测试内容",
        share_type="DISCUSSION",
        status="NORMAL",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    return post


def test_duplicate_report_is_rejected(client, admin_headers, db_session, test_user):
    post = _make_post(db_session, test_user)

    first = client.post(
        "/api/forum/reports",
        headers=admin_headers,
        json={"target_type": "POST", "target_id": post.post_id, "reason_code": "spam"},
    )
    second = client.post(
        "/api/forum/reports",
        headers=admin_headers,
        json={"target_type": "POST", "target_id": post.post_id, "reason_code": "spam"},
    )
    assert first.status_code == 200
    assert second.status_code == 409


def test_cannot_report_own_content(client, auth_headers, db_session, test_user):
    post = _make_post(db_session, test_user)
    resp = client.post(
        "/api/forum/reports",
        headers=auth_headers,
        json={"target_type": "POST", "target_id": post.post_id, "reason_code": "spam"},
    )
    assert resp.status_code == 400


def test_notification_list_and_mark_read(client, admin_headers, db_session, test_admin):
    db_session.add(
        UserNotification(
            user_id=test_admin.user_id,
            type="system",
            title="欢迎",
            content="这是一条测试通知",
        )
    )
    db_session.commit()

    listed = client.get("/api/notifications", headers=admin_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert body["unread"] >= 1

    notification_id = body["items"][0]["notification_id"]
    read = client.put(
        f"/api/notifications/{notification_id}/read", headers=admin_headers
    )
    assert read.status_code == 200

    again = client.get("/api/notifications?unread_only=true", headers=admin_headers)
    assert again.status_code == 200
    assert all(item["is_read"] is False for item in again.json()["items"])


def test_notification_is_user_scoped(client, auth_headers, db_session, test_admin):
    db_session.add(
        UserNotification(
            user_id=test_admin.user_id,
            type="system",
            title="仅管理员可见",
        )
    )
    db_session.commit()

    listed = client.get("/api/notifications", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
