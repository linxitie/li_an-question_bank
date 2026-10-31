# -*- coding: utf-8 -*-
"""P3-03 收藏 / 我的喜欢 / 列表补字段。

约定：
- 收藏 = 五角星（forum_favorite 表）
- 喜欢 = 爱心（forum_like.reaction_code='like'）
"""
from app.core.security import create_access_token
from app.models.models import ForumFavorite, ForumPost, SysUser


def _create_post(client, headers, title="收藏测试帖", content="正文", **extra):
    data = {"title": title, "content": content, "share_type": "DISCUSSION"}
    data.update(extra)
    resp = client.post("/api/forum/posts", headers=headers, data=data)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _make_student(db_session, user_no, class_name=None):
    user = SysUser(
        user_no=user_no,
        username=user_no,
        password="x",
        phone="1300000000" + user_no[-1],
        user_type="student",
        role_level=1,
        status=1,
        class_name=class_name,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"user_id": user.user_id, "user_no": user.user_no})
    return user, {"Authorization": f"Bearer {token}"}


def test_favorite_toggle(client, auth_headers):
    post = _create_post(client, auth_headers)

    r1 = client.post(f"/api/forum/posts/{post['id']}/favorite", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["favorited"] is True
    assert r1.json()["favoriteCount"] == 1

    r2 = client.post(f"/api/forum/posts/{post['id']}/favorite", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["favorited"] is False
    assert r2.json()["favoriteCount"] == 0


def test_favorite_requires_login(client, auth_headers):
    post = _create_post(client, auth_headers)
    resp = client.post(f"/api/forum/posts/{post['id']}/favorite")
    assert resp.status_code in (401, 403), resp.text


def test_my_favorites_lists_only_mine(client, auth_headers, db_session):
    post = _create_post(client, auth_headers)
    client.post(f"/api/forum/posts/{post['id']}/favorite", headers=auth_headers)

    resp = client.get("/api/forum/my-favorites", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = [p["id"] for p in body["posts"]]
    assert post["id"] in ids

    # 另一个学生看不到我的收藏
    _, other_headers = _make_student(db_session, "stu900")
    resp2 = client.get("/api/forum/my-favorites", headers=other_headers)
    assert resp2.status_code == 200
    assert [p["id"] for p in resp2.json()["posts"]] == []


def test_my_likes_lists_liked_posts(client, auth_headers):
    post = _create_post(client, auth_headers)
    like = client.post(f"/api/forum/posts/{post['id']}/like", headers=auth_headers)
    assert like.status_code == 200, like.text

    resp = client.get("/api/forum/my-likes", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert post["id"] in [p["id"] for p in resp.json()["posts"]]


def test_list_contains_favorited_and_count(client, auth_headers):
    post = _create_post(client, auth_headers)
    client.post(f"/api/forum/posts/{post['id']}/favorite", headers=auth_headers)

    resp = client.get("/api/forum/posts", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    item = next(p for p in resp.json()["posts"] if p["id"] == post["id"])
    assert item["favorited"] is True
    assert item["favoriteCount"] == 1


def test_favorite_row_written(client, auth_headers, db_session, test_user):
    post = _create_post(client, auth_headers)
    client.post(f"/api/forum/posts/{post['id']}/favorite", headers=auth_headers)
    row = (
        db_session.query(ForumFavorite)
        .filter(ForumFavorite.post_id == post["id"], ForumFavorite.user_id == test_user.user_id)
        .first()
    )
    assert row is not None


def test_favorite_on_missing_post(client, auth_headers):
    resp = client.post("/api/forum/posts/999999/favorite", headers=auth_headers)
    assert resp.status_code in (404, 400), resp.text
