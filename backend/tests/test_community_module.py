"""论坛社区（E6）模块测试（P2-31）。

覆盖：发帖上报一次 ``forum.posted``；同一帖子回帖/重复上报不再上报；
点赞等非创建行为不上报；历史帖子首条回帖上报一次；
金句收藏沿用既有 trigger_type 常量不回归。
"""
import pytest

from app.api.v1.community import forum, quotes
from app.core.trigger_types import TRIGGER_LEGACY_QUOTE_FAVORITE
from app.models.models import EssayQuote, ForumPost


@pytest.fixture(autouse=True)
def _reset_event_state():
    forum.reset_forum_posted_events()
    yield
    forum.reset_forum_posted_events()


@pytest.fixture
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append(
            {"user_id": user_id, "trigger_type": trigger_type, "session": session}
        )
        return True

    monkeypatch.setattr(forum, "record_user_action", fake_record)
    monkeypatch.setattr(quotes, "record_user_action", fake_record)
    return events


@pytest.fixture
def legacy_post(db_session, test_user):
    post = ForumPost(
        user_id=test_user.user_id,
        title="历史帖子",
        content="本次改造前已存在的帖子内容",
        share_type="EXPERIENCE",
        status="NORMAL",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    return post


def _forum_events(events):
    return [e for e in events if e["trigger_type"] == "forum.posted"]


def _create_post(client, auth_headers, title="备考经验分享", content="分享一下我的备考经验。"):
    return client.post(
        "/api/forum/posts",
        headers=auth_headers,
        data={"title": title, "content": content, "share_type": "EXPERIENCE"},
    )


def _add_comment(client, auth_headers, post_id, content="说得很有道理，感谢分享。"):
    return client.post(
        f"/api/forum/posts/{post_id}/comments",
        headers=auth_headers,
        data={"content": content},
    )


def test_create_post_publishes_once(client, auth_headers, published):
    response = _create_post(client, auth_headers)

    assert response.status_code == 200
    post_id = response.json()["id"]

    events = _forum_events(published)
    assert len(events) == 1
    assert events[0]["session"]["post_id"] == post_id
    assert events[0]["session"]["action"] == "created"


def test_comment_on_new_post_does_not_republish(client, auth_headers, published):
    post_id = _create_post(client, auth_headers).json()["id"]

    response = _add_comment(client, auth_headers, post_id)

    assert response.status_code == 200
    assert len(_forum_events(published)) == 1


def test_comment_on_legacy_post_publishes_once(
    client, auth_headers, legacy_post, published
):
    first = _add_comment(client, auth_headers, legacy_post.post_id)
    second = _add_comment(client, auth_headers, legacy_post.post_id, "再补充一句。")

    assert first.status_code == 200
    assert second.status_code == 200

    events = _forum_events(published)
    assert len(events) == 1
    assert events[0]["session"]["post_id"] == legacy_post.post_id
    assert events[0]["session"]["action"] == "commented"


def test_likes_do_not_publish_forum_event(client, auth_headers, published):
    post_id = _create_post(client, auth_headers).json()["id"]
    assert len(_forum_events(published)) == 1

    like_post = client.post(
        f"/api/forum/posts/{post_id}/like", headers=auth_headers
    )
    assert like_post.status_code == 200

    comment_id = _add_comment(client, auth_headers, post_id).json()["id"]
    like_comment = client.post(
        f"/api/forum/comments/{comment_id}/like", headers=auth_headers
    )
    assert like_comment.status_code == 200

    assert len(_forum_events(published)) == 1


def test_quote_favorite_keeps_legacy_trigger_constant(
    client, auth_headers, db_session, published
):
    quote = EssayQuote(content="为民者民必记之，惠民者民必感之。", status=1)
    db_session.add(quote)
    db_session.commit()
    db_session.refresh(quote)

    response = client.post(
        f"/api/quotes/{quote.quote_id}/favorite", headers=auth_headers
    )

    assert response.status_code == 200
    events = [e for e in published if e["trigger_type"] == TRIGGER_LEGACY_QUOTE_FAVORITE]
    assert len(events) == 1
    assert TRIGGER_LEGACY_QUOTE_FAVORITE == "quote_favorite"

    response = client.post(
        f"/api/quotes/{quote.quote_id}/favorite", headers=auth_headers
    )
    assert response.status_code == 200
    assert (
        len([e for e in published if e["trigger_type"] == TRIGGER_LEGACY_QUOTE_FAVORITE])
        == 1
    )


def test_question_share_type_is_accepted_and_filtered(client, auth_headers):
    """「答疑解惑」分类必须可发布，且列表能按该分类筛选。"""
    created = client.post(
        "/api/forum/posts",
        headers=auth_headers,
        data={
            "title": "求解答题思路",
            "content": "这道资料分析题怎么快速定位？",
            "share_type": "QUESTION",
        },
    )
    assert created.status_code == 200
    assert created.json()["shareType"] == "QUESTION"

    listed = client.get(
        "/api/forum/posts", params={"share_type": "QUESTION"}
    )
    assert listed.status_code == 200
    posts = listed.json()["posts"]
    assert posts
    assert all(p["shareType"] == "QUESTION" for p in posts)
