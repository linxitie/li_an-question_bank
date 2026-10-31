"""R1 金句主题/关键词筛选 API 测试。"""
from app.models.models import EssayQuote, Topic
from app.services.kg_seed import seed_topics
from app.services.kg_service import create_edge, seed_relation_types


def _quote(db, content, uid):
    quote = EssayQuote(content=content, quote_uid=uid, status=1)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def test_filter_quotes_by_topic(client, db_session, auth_headers):
    seed_relation_types(db_session)
    seed_topics(db_session)
    topic = db_session.query(Topic).filter(Topic.slug == "rule-of-law-thinking").one()
    linked = _quote(db_session, "法者，天下之程式也。", "q_filter_linked")
    _quote(db_session, "天行健，君子以自强不息。", "q_filter_other")
    create_edge(
        db_session,
        src_type="quote",
        src_id=linked.quote_id,
        dst_type="topic",
        dst_id=topic.topic_id,
        relation="has_topic",
    )
    db_session.commit()

    response = client.get("/api/quotes", params={"topic": "rule-of-law-thinking"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["quote_id"] == linked.quote_id


def test_filter_quotes_by_keyword_and_unknown_topic(client, db_session, auth_headers):
    _quote(db_session, "法者，天下之程式也。", "q_filter_keyword")

    keyword = client.get("/api/quotes", params={"q": "程式"}, headers=auth_headers)
    assert keyword.status_code == 200
    assert keyword.json()["total"] == 1

    unknown = client.get("/api/quotes", params={"topic": "no-such-topic"}, headers=auth_headers)
    assert unknown.status_code == 200
    assert unknown.json()["total"] == 0
