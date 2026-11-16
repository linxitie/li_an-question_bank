"""论坛回收站：软删除 / 回收站列表 / 恢复 / 批量删除。"""
from datetime import datetime, timedelta

from app.models.models import ForumPost


def _create_post(client, auth_headers, title):
    resp = client.post(
        "/api/forum/posts",
        headers=auth_headers,
        data={"title": title, "content": "正常的正文内容，用于回收站测试"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_delete_goes_to_recycle_bin_and_restore(client, db_session, auth_headers):
    body = _create_post(client, auth_headers, "回收站测试帖")
    post_id = body.get("post_id") or body.get("id")

    deleted = client.delete(f"/api/forum/posts/{post_id}", headers=auth_headers)
    assert deleted.status_code == 200

    db_session.expire_all()
    post = db_session.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    assert post.status == "DELETED"
    assert post.deleted_at is not None
    assert post.deleted_by is not None

    # 普通列表看不到，回收站列表能看到
    normal = client.get("/api/forum/my-posts", headers=auth_headers).json()
    assert all(p["id"] != post_id for p in normal["posts"])
    trash = client.get(
        "/api/forum/my-posts?include_deleted=true", headers=auth_headers
    ).json()
    assert any(p["id"] == post_id and p.get("deletedAt") for p in trash["posts"])

    restored = client.post(f"/api/forum/posts/{post_id}/restore", headers=auth_headers)
    assert restored.status_code == 200
    db_session.expire_all()
    post = db_session.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    assert post.status == "NORMAL"
    assert post.deleted_at is None


def test_restore_rejected_after_30_days(client, db_session, auth_headers):
    body = _create_post(client, auth_headers, "过期回收站帖")
    post_id = body.get("post_id") or body.get("id")
    post = db_session.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    post.status = "DELETED"
    post.deleted_at = datetime.now() - timedelta(days=31)
    db_session.commit()

    resp = client.post(f"/api/forum/posts/{post_id}/restore", headers=auth_headers)
    assert resp.status_code in (400, 422)
    assert "30 天" in resp.text


def test_batch_delete_own_posts(client, db_session, auth_headers):
    ids = []
    for i in range(2):
        body = _create_post(client, auth_headers, f"批量删除测试{i}")
        ids.append(body.get("post_id") or body.get("id"))
    resp = client.post(
        "/api/forum/posts/batch-delete", headers=auth_headers, json={"post_ids": ids}
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2
    db_session.expire_all()
    rows = db_session.query(ForumPost).filter(ForumPost.post_id.in_(ids)).all()
    assert all(r.status == "DELETED" for r in rows)
