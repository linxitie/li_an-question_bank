"""论坛 P1 编辑/置顶/删除/筛选测试。"""
from app.core.security import create_access_token
from app.models.models import ForumComment, ForumPost, SysUser


def _create_post(client, auth_headers, title="P1 测试帖", content="正文内容"):
    resp = client.post(
        "/api/forum/posts",
        headers=auth_headers,
        data={
            "title": title,
            "content": content,
            "share_type": "DISCUSSION",
            "title_color": "gold",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _add_comment(client, auth_headers, post_id, content="一条评论"):
    resp = client.post(
        f"/api/forum/posts/{post_id}/comments",
        headers=auth_headers,
        data={"content": content},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _second_student(db_session):
    student = SysUser(
        user_no="p1_student_2",
        username="另一学生",
        password="x",
        phone="13000130000",
        user_type="student",
        role_level=0,
        status=1,
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    token = create_access_token(
        data={"user_id": student.user_id, "user_no": student.user_no}
    )
    return student, {"Authorization": f"Bearer {token}"}


def test_author_can_edit_within_30_minutes(client, auth_headers):
    post = _create_post(client, auth_headers)
    resp = client.put(
        f"/api/forum/posts/{post['id']}",
        headers=auth_headers,
        json={"title": "新标题", "content": "新正文", "title_color": "gold"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "新标题"
    assert body["titleColor"] == "gold"


def test_other_user_cannot_edit(client, auth_headers, db_session):
    post = _create_post(client, auth_headers)
    _, other_headers = _second_student(db_session)
    resp = client.put(
        f"/api/forum/posts/{post['id']}",
        headers=other_headers,
        json={"title": "篡改"},
    )
    assert resp.status_code == 400


def test_invalid_title_color_falls_back(client, auth_headers):
    post = _create_post(client, auth_headers)
    resp = client.put(
        f"/api/forum/posts/{post['id']}",
        headers=auth_headers,
        json={"title_color": "#fff"},
    )
    assert resp.status_code == 200
    assert resp.json()["titleColor"] == "default"


def test_post_author_can_pin_comment(client, auth_headers, db_session):
    post = _create_post(client, auth_headers)
    comment = _add_comment(client, auth_headers, post["id"])

    resp = client.put(
        f"/api/forum/comments/{comment['id']}/pin",
        headers=auth_headers,
        json={"pinned": True},
    )
    assert resp.status_code == 200
    assert resp.json()["isPinned"] is True

    row = db_session.query(ForumComment).filter_by(comment_id=comment["id"]).first()
    assert row.is_pinned == 1


def test_other_user_cannot_pin(client, auth_headers, db_session):
    post = _create_post(client, auth_headers)
    comment = _add_comment(client, auth_headers, post["id"])
    _, other_headers = _second_student(db_session)

    resp = client.put(
        f"/api/forum/comments/{comment['id']}/pin",
        headers=other_headers,
        json={"pinned": True},
    )
    assert resp.status_code == 400


def test_delete_comment_is_soft(client, auth_headers, db_session):
    post = _create_post(client, auth_headers)
    comment = _add_comment(client, auth_headers, post["id"])

    resp = client.delete(
        f"/api/forum/comments/{comment['id']}", headers=auth_headers
    )
    assert resp.status_code == 200

    row = db_session.query(ForumComment).filter_by(comment_id=comment["id"]).first()
    assert row.status == 0

    post_row = db_session.query(ForumPost).filter_by(post_id=post["id"]).first()
    assert post_row.comment_count == 0


def test_locked_post_rejects_comment(client, auth_headers, db_session):
    post = _create_post(client, auth_headers)
    row = db_session.query(ForumPost).filter_by(post_id=post["id"]).first()
    row.is_locked = 1
    db_session.commit()

    resp = client.post(
        f"/api/forum/posts/{post['id']}/comments",
        headers=auth_headers,
        data={"content": "还能评论吗"},
    )
    assert resp.status_code == 400


def test_keyword_filter(client, auth_headers):
    _create_post(client, auth_headers, title="独一无二的关键词ABC", content="内容")
    resp = client.get(
        "/api/forum/posts", params={"keyword": "关键词ABC", "limit": 50}
    )
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()["posts"]]
    assert "独一无二的关键词ABC" in titles
