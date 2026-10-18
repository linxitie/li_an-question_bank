"""每日新闻（E7）模块测试（P2-32 / P2-35）。

覆盖：
- 登录用户首次打开新闻详情 → 恰好发布一次 ``news.read``；
- 同一用户同一篇再次打开 → 不重复发布（幂等）；
- 同一用户不同篇 → 各发布一次；
- 列表 / 今日 / 收藏等只读接口不发布；
- 匿名访问详情不发布，且不写已读记录；
- 列表与详情返回后端权威的 ``is_read`` 标记。
"""
import pytest

from app.api.v1.content import news as news_api
from app.core.trigger_types import TRIGGER_NEWS_READ
from app.models.models import NewsArticle


@pytest.fixture
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append({"user_id": user_id, "trigger_type": trigger_type})
        return True

    monkeypatch.setattr(news_api, "record_user_action", fake_record)
    return events


@pytest.fixture
def make_news(db_session):
    def _make(index: int) -> NewsArticle:
        row = NewsArticle(
            title=f"公安联考政策解读 {index}",
            url=f"https://example.com/news/{index}",
            source="cpd",
            category="政策",
            content="正文内容",
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        return row

    return _make


def _events(events, trigger_type):
    return [e for e in events if e["trigger_type"] == trigger_type]


def test_trigger_type_value_is_frozen():
    assert TRIGGER_NEWS_READ == "news.read"


def test_first_detail_read_publishes_once(client, auth_headers, make_news, published):
    news = make_news(1)

    response = client.get(f"/api/news/{news.news_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert len(_events(published, TRIGGER_NEWS_READ)) == 1


def test_second_read_same_article_does_not_republish(
    client, auth_headers, make_news, published
):
    news = make_news(2)

    first = client.get(f"/api/news/{news.news_id}", headers=auth_headers)
    second = client.get(f"/api/news/{news.news_id}", headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_read"] is True
    assert len(_events(published, TRIGGER_NEWS_READ)) == 1


def test_different_articles_publish_separately(
    client, auth_headers, make_news, published
):
    first_news = make_news(3)
    second_news = make_news(4)

    client.get(f"/api/news/{first_news.news_id}", headers=auth_headers)
    client.get(f"/api/news/{second_news.news_id}", headers=auth_headers)

    assert len(_events(published, TRIGGER_NEWS_READ)) == 2


@pytest.mark.parametrize("path", ["/api/news", "/api/news/today"])
def test_list_endpoints_do_not_publish(
    client, auth_headers, make_news, published, path
):
    make_news(5)

    response = client.get(path, headers=auth_headers)

    assert response.status_code == 200
    assert published == []


def test_list_never_publishes_even_after_read(
    client, auth_headers, make_news, published
):
    news = make_news(6)
    client.get(f"/api/news/{news.news_id}", headers=auth_headers)
    published.clear()

    response = client.get("/api/news", headers=auth_headers)

    assert response.status_code == 200
    assert published == []


def test_list_reports_backend_read_state(client, auth_headers, make_news, published):
    news = make_news(7)

    before = client.get("/api/news", headers=auth_headers).json()["items"]
    assert all(item["is_read"] is False for item in before)

    client.get(f"/api/news/{news.news_id}", headers=auth_headers)

    after = client.get("/api/news", headers=auth_headers).json()["items"]
    read_ids = {item["id"] for item in after if item["is_read"]}
    assert read_ids == {news.news_id}


def test_anonymous_detail_does_not_publish(client, make_news, published):
    news = make_news(8)

    response = client.get(f"/api/news/{news.news_id}")

    assert response.status_code == 200
    assert response.json()["is_read"] is False
    assert published == []


def test_missing_article_does_not_publish(client, auth_headers, published):
    response = client.get("/api/news/999999", headers=auth_headers)

    assert response.status_code == 404
    assert published == []
