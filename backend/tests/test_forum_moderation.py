"""教师/管理员论坛管理 P3/P4 测试。"""
from app.core.security import create_access_token
from app.models.models import ForumComment, ForumModeration, ForumPost, SysUser


def _headers(user):
    token = create_access_token(data={"user_id": user.user_id, "user_no": user.user_no})
    return {"Authorization": f"Bearer {token}"}


def _student(db_session, user_no, class_name):
    user = SysUser(
        user_no=user_no,
        username=f"学生{user_no}",
        password="x",
        phone=f"139{user_no[-5:]}",
        user_type="student",
        role_level=0,
        status=1,
        class_name=class_name,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _post(db_session, author, title="不良帖子"):
    post = ForumPost(
        user_id=author.user_id,
        title=title,
        content="内容",
        share_type="DISCUSSION",
        status="NORMAL",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    return post


def _comment(db_session, post, author, content="不良评论"):
    comment = ForumComment(
        post_id=post.post_id,
        user_id=author.user_id,
        content=content,
        status=1,
    )
    db_session.add(comment)
    db_session.commit()
    db_session.refresh(comment)
    return comment


def test_teacher_hides_class_post_and_admin_approves(
    client, db_session, test_teacher, admin_headers
):
    student = _student(db_session, "mod001", "一班")
    post = _post(db_session, student)

    resp = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/hide",
        headers=_headers(test_teacher),
        json={"reason": "广告内容"},
    )
    assert resp.status_code == 200
    moderation_id = resp.json()["moderation_id"]

    row = db_session.query(ForumPost).filter_by(post_id=post.post_id).first()
    assert row.status == "BLOCKED"
    assert row.deleted_reason == "广告内容"

    approved = client.post(
        f"/api/admin/forum/moderation/{moderation_id}/approve",
        headers=admin_headers,
        json={"note": "确认删除"},
    )
    assert approved.status_code == 200
    db_session.expire_all()
    row = db_session.query(ForumPost).filter_by(post_id=post.post_id).first()
    assert row.status == "DELETED"


def test_teacher_cannot_hide_other_class_post(client, db_session, test_teacher):
    student = _student(db_session, "mod002", "二班")
    post = _post(db_session, student)
    resp = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/hide",
        headers=_headers(test_teacher),
        json={"reason": "跨班"},
    )
    assert resp.status_code == 403


def test_teacher_hide_comment_enters_review(client, db_session, test_teacher):
    student = _student(db_session, "mod003", "一班")
    post = _post(db_session, student)
    comment = _comment(db_session, post, student)

    resp = client.post(
        f"/api/teacher/forum/comments/{comment.comment_id}/hide",
        headers=_headers(test_teacher),
        json={"reason": "辱骂"},
    )
    assert resp.status_code == 200

    row = db_session.query(ForumComment).filter_by(comment_id=comment.comment_id).first()
    assert row.status == 2
    record = db_session.query(ForumModeration).filter_by(
        target_type="COMMENT", target_id=comment.comment_id
    ).first()
    assert record.status == "PENDING"


def test_admin_rejects_teacher_hide_and_restores(
    client, db_session, test_teacher, admin_headers
):
    student = _student(db_session, "mod004", "一班")
    post = _post(db_session, student)

    hide = client.post(
        f"/api/teacher/forum/posts/{post.post_id}/hide",
        headers=_headers(test_teacher),
        json={"reason": "误判"},
    )
    moderation_id = hide.json()["moderation_id"]

    rejected = client.post(
        f"/api/admin/forum/moderation/{moderation_id}/reject",
        headers=admin_headers,
        json={"note": "不构成违规"},
    )
    assert rejected.status_code == 200
    db_session.expire_all()
    row = db_session.query(ForumPost).filter_by(post_id=post.post_id).first()
    assert row.status == "NORMAL"


def test_admin_can_delete_teacher_post(client, db_session, test_teacher, admin_headers):
    post = _post(db_session, test_teacher)
    resp = client.delete(
        f"/api/admin/forum/posts/{post.post_id}",
        headers=admin_headers,
        params={"reason": "违规"},
    )
    assert resp.status_code == 200
    db_session.expire_all()
    row = db_session.query(ForumPost).filter_by(post_id=post.post_id).first()
    assert row.status == "DELETED"


def test_admin_recycle_and_restore(client, db_session, test_teacher, admin_headers):
    post = _post(db_session, test_teacher)
    client.delete(
        f"/api/admin/forum/posts/{post.post_id}",
        headers=admin_headers,
        params={"reason": "违规"},
    )

    recycle = client.get("/api/admin/forum/recycle", headers=admin_headers)
    assert recycle.status_code == 200
    assert any(p["id"] == post.post_id for p in recycle.json()["posts"])

    restored = client.post(
        f"/api/admin/forum/posts/{post.post_id}/restore", headers=admin_headers
    )
    assert restored.status_code == 200
    db_session.expire_all()
    row = db_session.query(ForumPost).filter_by(post_id=post.post_id).first()
    assert row.status == "NORMAL"


def test_recycle_audit_counts_and_logs(client, db_session, admin_headers):
    from app.services.forum_audit import collect_forum_recycle_stats, run_forum_recycle_audit

    student = _student(db_session, "mod005", "一班")
    post = _post(db_session, student)
    comment = _comment(db_session, post, student)
    post.status = "DELETED"
    comment.status = 2
    db_session.commit()

    stats = collect_forum_recycle_stats(db_session)
    assert stats["deleted_posts"] >= 1
    assert stats["hidden_comments"] >= 1

    run_forum_recycle_audit(db_session)
    from app.models.models import SysOperationLog

    log = (
        db_session.query(SysOperationLog)
        .filter(SysOperationLog.operation_type == "论坛回收站审计")
        .order_by(SysOperationLog.log_id.desc())
        .first()
    )
    assert log is not None
