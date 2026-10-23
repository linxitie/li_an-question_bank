"""论坛发帖/表情反应/个性化资料测试。

覆盖用户可见的关键路径：
- 发帖鉴权、空值、超长、敏感词、附件格式、XSS 原样存储
- 删除权限
- 帖子/评论的 6 种表情反应：设置、替换、取消、聚合
- 昵称/签名个性化与长度校验
"""
import pytest

from app.api.v1.community import forum
from app.core.security import create_access_token, get_password_hash
from app.models.models import ForumComment, ForumPost, SysUser
from app.services.sensitive_words import SensitiveLevel


def _create_post(client, headers, **overrides):
    payload = {
        "title": "备考经验分享",
        "content": "分享一下我的备考经验。",
        "share_type": "EXPERIENCE",
    }
    payload.update(overrides)
    return client.post("/api/forum/posts", headers=headers, data=payload)


def _second_user_headers(db_session):
    user = SysUser(
        user_no="test002",
        username="另一个用户",
        password=get_password_hash("password123"),
        phone="13800138001",
        user_type="student",
        role_level=1,
        status=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"user_id": user.user_id, "user_no": user.user_no})
    return {"Authorization": f"Bearer {token}"}, user


# ----------------------------- 发帖 -----------------------------

def test_create_post_requires_auth(client):
    response = client.post(
        "/api/forum/posts",
        data={"title": "标题", "content": "正文"},
    )
    assert response.status_code == 401


def test_create_post_rejects_blank_title_or_content(client, auth_headers):
    blank_title = _create_post(client, auth_headers, title="   ")
    blank_content = _create_post(client, auth_headers, content="   ")

    assert blank_title.status_code == 422
    assert blank_content.status_code == 422


def test_create_post_rejects_overlong_fields(client, auth_headers):
    long_title = _create_post(client, auth_headers, title="题" * 201)
    long_content = _create_post(client, auth_headers, content="文" * 10001)

    assert long_title.status_code == 422
    assert long_content.status_code == 422


def test_create_post_blocks_sensitive_content(client, auth_headers, monkeypatch):
    def fake_detect(text):
        return {"level": SensitiveLevel.BLOCKED, "words": ["违规词"], "masked_text": text}

    monkeypatch.setattr(forum.sensitive_filter, "detect", fake_detect)
    response = _create_post(client, auth_headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SENSITIVE_CONTENT_BLOCKED"


def test_create_post_masks_sensitive_content(client, auth_headers, monkeypatch):
    def fake_detect(text):
        return {"level": SensitiveLevel.MASKED, "words": ["敏感"], "masked_text": "已屏蔽内容"}

    monkeypatch.setattr(forum.sensitive_filter, "detect", fake_detect)
    response = _create_post(client, auth_headers)

    assert response.status_code == 200
    assert response.json()["content"] == "已屏蔽内容"


def test_create_post_rejects_invalid_attachments(client, auth_headers):
    response = _create_post(client, auth_headers, attachments="not-json")

    assert response.status_code == 422


def test_create_post_keeps_xss_as_plain_text(client, auth_headers):
    payload = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    response = _create_post(client, auth_headers, content=payload)

    assert response.status_code == 200
    assert response.json()["content"] == payload
    # 响应是 JSON，不是 text/html，浏览器不会执行
    assert response.headers["content-type"].startswith("application/json")


def test_delete_post_requires_owner_or_admin(client, auth_headers, db_session):
    post_id = _create_post(client, auth_headers).json()["id"]
    other_headers, _ = _second_user_headers(db_session)

    denied = client.delete(f"/api/forum/posts/{post_id}", headers=other_headers)
    allowed = client.delete(f"/api/forum/posts/{post_id}", headers=auth_headers)

    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"
    assert allowed.status_code == 200


# ----------------------------- 表情反应 -----------------------------

def test_post_reaction_set_switch_and_cancel(client, auth_headers, db_session):
    post_id = _create_post(client, auth_headers).json()["id"]

    first = client.post(
        f"/api/forum/posts/{post_id}/reactions/love", headers=auth_headers
    )
    assert first.status_code == 200
    assert first.json()["myReaction"] == "love"
    assert first.json()["reactions"] == {"love": 1}
    assert first.json()["reactionCount"] == 1

    switched = client.post(
        f"/api/forum/posts/{post_id}/reactions/haha", headers=auth_headers
    )
    assert switched.status_code == 200
    assert switched.json()["myReaction"] == "haha"
    assert switched.json()["reactions"] == {"haha": 1}
    assert switched.json()["reactionCount"] == 1

    cancelled = client.delete(
        f"/api/forum/posts/{post_id}/reactions", headers=auth_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["myReaction"] is None
    assert cancelled.json()["reactions"] == {}
    assert cancelled.json()["reactionCount"] == 0


def test_post_reaction_aggregates_multiple_users(client, auth_headers, db_session):
    post_id = _create_post(client, auth_headers).json()["id"]
    other_headers, _ = _second_user_headers(db_session)

    client.post(f"/api/forum/posts/{post_id}/reactions/like", headers=auth_headers)
    client.post(f"/api/forum/posts/{post_id}/reactions/like", headers=other_headers)
    client.post(f"/api/forum/posts/{post_id}/reactions/wow", headers=other_headers)

    detail = client.get(f"/api/forum/posts/{post_id}", headers=auth_headers)
    body = detail.json()

    assert body["reactions"] == {"like": 1, "wow": 1}
    assert body["myReaction"] == "like"
    assert body["likeCount"] == 2


def test_post_reaction_rejects_unknown_code(client, auth_headers):
    post_id = _create_post(client, auth_headers).json()["id"]
    response = client.post(
        f"/api/forum/posts/{post_id}/reactions/fire", headers=auth_headers
    )

    assert response.status_code == 422


def test_comment_reaction_and_nested_reply(client, auth_headers, db_session):
    post_id = _create_post(client, auth_headers).json()["id"]
    parent = client.post(
        f"/api/forum/posts/{post_id}/comments",
        headers=auth_headers,
        data={"content": "父评论"},
    ).json()
    other_headers, other_user = _second_user_headers(db_session)
    reply = client.post(
        f"/api/forum/posts/{post_id}/comments",
        headers=other_headers,
        data={"content": "楼中楼回复", "parent_comment_id": parent["id"]},
    )

    assert reply.status_code == 200
    assert reply.json()["parentCommentId"] == parent["id"]

    reacted = client.post(
        f"/api/forum/comments/{parent['id']}/reactions/love", headers=auth_headers
    )
    assert reacted.status_code == 200
    assert reacted.json()["myReaction"] == "love"

    comments = client.get(
        f"/api/forum/posts/{post_id}/comments", headers=auth_headers
    ).json()["comments"]
    parent_row = next(c for c in comments if c["id"] == parent["id"])
    assert parent_row["reactions"] == {"love": 1}


def test_comment_rejects_empty_content(client, auth_headers):
    post_id = _create_post(client, auth_headers).json()["id"]
    response = client.post(
        f"/api/forum/posts/{post_id}/comments",
        headers=auth_headers,
        data={"content": "   "},
    )

    assert response.status_code == 422


# ----------------------------- 表情包 -----------------------------

def test_sticker_upload_list_and_delete(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr(forum.settings, "UPLOAD_DIR", str(tmp_path))

    upload = client.post(
        "/api/forum/stickers",
        headers=auth_headers,
        files={"file": ("cat.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
        data={"name": "猫猫"},
    )
    assert upload.status_code == 200
    sticker = upload.json()
    assert sticker["name"] == "猫猫"
    assert sticker["url"].startswith("/uploads/stickers/")

    listed = client.get("/api/forum/stickers", headers=auth_headers)
    assert listed.status_code == 200
    assert any(s["id"] == sticker["id"] for s in listed.json()["stickers"])

    deleted = client.delete(
        f"/api/forum/stickers/{sticker['id']}", headers=auth_headers
    )
    assert deleted.status_code == 200

    listed_after = client.get("/api/forum/stickers", headers=auth_headers)
    assert all(s["id"] != sticker["id"] for s in listed_after.json()["stickers"])


def test_sticker_rejects_unsupported_format(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr(forum.settings, "UPLOAD_DIR", str(tmp_path))
    response = client.post(
        "/api/forum/stickers",
        headers=auth_headers,
        files={"file": ("bad.svg", b"<svg/>", "image/svg+xml")},
    )

    assert response.status_code == 422


def test_sticker_delete_rejects_other_user(client, auth_headers, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(forum.settings, "UPLOAD_DIR", str(tmp_path))
    sticker = client.post(
        "/api/forum/stickers",
        headers=auth_headers,
        files={"file": ("cat.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    ).json()

    other_headers, _ = _second_user_headers(db_session)
    response = client.delete(
        f"/api/forum/stickers/{sticker['id']}", headers=other_headers
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


# ----------------------------- 个性化资料 -----------------------------

def test_profile_nickname_and_signature(client, auth_headers):
    response = client.put(
        "/api/auth/profile",
        headers=auth_headers,
        json={"nickname": "砺安小助手", "signature": "每天进步一点点"},
    )

    assert response.status_code == 200
    user = response.json()["user"]
    assert user["nickname"] == "砺安小助手"
    assert user["signature"] == "每天进步一点点"


def test_profile_rejects_overlong_nickname(client, auth_headers):
    response = client.put(
        "/api/auth/profile",
        headers=auth_headers,
        json={"nickname": "名" * 21},
    )

    assert response.status_code == 400


def test_forum_post_uses_nickname_fallback(client, auth_headers, db_session):
    client.put(
        "/api/auth/profile",
        headers=auth_headers,
        json={"nickname": "砺安小助手"},
    )
    response = _create_post(client, auth_headers)

    assert response.status_code == 200
    assert response.json()["user"]["nickname"] == "砺安小助手"


# ----------------------------- 排序 -----------------------------

def _create_post_with_metrics(client, auth_headers, db_session, title, **metrics):
    post_id = _create_post(client, auth_headers, title=title, content=f"{title}正文").json()["id"]
    row = db_session.query(ForumPost).filter(ForumPost.post_id == post_id).one()
    for field, value in metrics.items():
        setattr(row, field, value)
    db_session.commit()
    return post_id


def test_forum_posts_sort_by_metrics(client, auth_headers, db_session):
    _create_post_with_metrics(
        client, auth_headers, db_session, "低热度",
        like_count=1, comment_count=5, view_count=100,
    )
    _create_post_with_metrics(
        client, auth_headers, db_session, "高赞",
        like_count=3, comment_count=2, view_count=50,
    )
    _create_post_with_metrics(
        client, auth_headers, db_session, "高评论",
        like_count=2, comment_count=8, view_count=10,
    )

    def titles(**params):
        response = client.get("/api/forum/posts", params={"limit": 10, **params})
        assert response.status_code == 200
        return [p["title"] for p in response.json()["posts"]]

    assert titles(sort_by="likes", order="desc") == ["高赞", "高评论", "低热度"]
    assert titles(sort_by="likes", order="asc") == ["低热度", "高评论", "高赞"]
    assert titles(sort_by="comments", order="desc") == ["高评论", "低热度", "高赞"]
    assert titles(sort_by="views", order="desc") == ["低热度", "高赞", "高评论"]
    assert titles(sort_by="time", order="desc") == ["高评论", "高赞", "低热度"]


def test_forum_posts_keep_pinned_first(client, auth_headers, db_session):
    _create_post_with_metrics(
        client, auth_headers, db_session, "旧置顶",
        like_count=0, comment_count=0, view_count=0,
    )
    pinned = db_session.query(ForumPost).filter(ForumPost.title == "旧置顶").one()
    pinned.is_top = 1
    db_session.commit()

    _create_post_with_metrics(
        client, auth_headers, db_session, "新高赞",
        like_count=99, comment_count=0, view_count=0,
    )

    response = client.get(
        "/api/forum/posts", params={"sort_by": "likes", "order": "desc", "limit": 10}
    )
    assert response.status_code == 200
    assert response.json()["posts"][0]["title"] == "旧置顶"


def test_comments_sort_by_likes_replies_and_time(client, auth_headers, db_session):
    from datetime import datetime

    post_id = _create_post(client, auth_headers).json()["id"]

    def add_comment(content, parent_comment_id=None):
        response = client.post(
            f"/api/forum/posts/{post_id}/comments",
            headers=auth_headers,
            data={"content": content, "parent_comment_id": parent_comment_id}
            if parent_comment_id
            else {"content": content},
        )
        assert response.status_code == 200
        return response.json()["id"]

    parent_a = add_comment("A")
    parent_b = add_comment("B")
    parent_c = add_comment("C")
    add_comment("A-1", parent_a)
    add_comment("A-2", parent_a)
    add_comment("B-1", parent_b)

    rows = {
        row.comment_id: row
        for row in db_session.query(ForumComment)
        .filter(ForumComment.post_id == post_id)
        .all()
    }
    rows[parent_a].like_count = 1
    rows[parent_b].like_count = 3
    rows[parent_c].like_count = 2
    by_content = {row.content: row for row in rows.values()}
    for index, content in enumerate(["A", "A-1", "A-2", "B", "B-1", "C"], start=1):
        by_content[content].create_time = datetime(2026, 1, 1, 0, 0, index)
    db_session.commit()

    def comments(**params):
        response = client.get(
            f"/api/forum/posts/{post_id}/comments",
            params={"limit": 100, **params},
        )
        assert response.status_code == 200
        return response.json()["comments"]

    by_likes_desc = comments(sort_by="likes", order="desc")
    assert [c["content"] for c in by_likes_desc if c["parentCommentId"] is None] == ["B", "C", "A"]

    by_replies_desc = comments(sort_by="replies", order="desc")
    roots = [c for c in by_replies_desc if c["parentCommentId"] is None]
    assert [c["content"] for c in roots] == ["A", "B", "C"]
    assert roots[0]["replyCount"] == 2
    assert roots[1]["replyCount"] == 1
    assert roots[2]["replyCount"] == 0

    by_time_desc = comments(sort_by="time", order="desc")
    assert [c["content"] for c in by_time_desc] == ["C", "B-1", "B", "A-2", "A-1", "A"]
    by_time_asc = comments(sort_by="time", order="asc")
    assert [c["content"] for c in by_time_asc] == ["A", "A-1", "A-2", "B", "B-1", "C"]
