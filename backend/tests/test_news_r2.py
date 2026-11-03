"""R2 新闻分类与检索测试。"""

from datetime import datetime

from app.models.models import NewsArticle, NewsFavorite


def _article(db, title, category, content="", summary=""):
    article = NewsArticle(
        title=title,
        url=f"https://example.com/news/{title}",
        source="cpd",
        category=category,
        summary=summary,
        content=content,
        status=1,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def test_news_keyword_and_pagination(client, db_session):
    _article(db_session, "坚持和发展枫桥经验", "理论", content="基层治理")
    _article(db_session, "枫桥式公安派出所创建", "公安报", content="派出所建设")
    _article(db_session, "党史学习教育", "党史", content="理论学习")

    response = client.get("/api/news", params={"q": "枫桥", "page": 1, "page_size": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["has_more"] is True
    assert len(body["items"]) == 1


def test_news_category_filter_and_legacy_limit(client, db_session):
    _article(db_session, "理论文章", "理论")
    _article(db_session, "党史文章", "党史")

    response = client.get("/api/news", params={"category": "党史", "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "党史"
    assert body["page_size"] == 1


def test_news_categories_include_counts(client, db_session):
    _article(db_session, "理论一", "理论")
    _article(db_session, "理论二", "理论")
    _article(db_session, "党史一", "党史")

    response = client.get("/api/news/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    counts = {item["category"]: item["count"] for item in body["items"]}
    assert counts["理论"] == 2
    assert counts["党史"] == 1


def test_news_timeline_groups_published(client, db_session):
    article = _article(db_session, "时间线新闻", "理论")
    article.status = 1
    article.review_status = "published"
    db_session.commit()

    response = client.get("/api/news/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["date"] == "未分期"
    assert body["items"][0]["items"][0]["news_id"] == article.news_id


def test_news_digest_groups_day(client, db_session):
    article = _article(db_session, "日报新闻", "理论")
    article.publish_date = datetime(2026, 11, 2, 9, 0)
    article.review_status = "published"
    db_session.commit()

    response = client.get("/api/news/digest?day=2026-11-02")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-11-02"
    assert body["total"] == 1
    assert body["categories"][0]["count"] == 1
    assert body["items"][0]["news_id"] == article.news_id

    assert client.get("/api/news/digest?day=bad-date").status_code == 400


def test_timeline_and_digest_favorite_flag(client, db_session, test_user, auth_headers):
    article = _article(db_session, "收藏标记新闻", "理论")
    article.publish_date = datetime(2026, 11, 3, 9, 0)
    article.review_status = "published"
    db_session.add(NewsFavorite(user_id=test_user.user_id, news_id=article.news_id))
    db_session.commit()

    timeline = client.get("/api/news/timeline", headers=auth_headers)
    digest = client.get("/api/news/digest?day=2026-11-03", headers=auth_headers)

    assert timeline.status_code == 200
    assert digest.status_code == 200
    assert timeline.json()["items"][0]["items"][0]["is_favorited"] is True
    assert digest.json()["items"][0]["is_favorited"] is True

    toggled = client.post(f"/api/news/{article.news_id}/favorite", headers=auth_headers)
    assert toggled.status_code == 200
    assert toggled.json()["favorited"] is False
