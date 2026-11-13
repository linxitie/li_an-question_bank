"""R0 知识图谱 API 测试。"""
from app.models.models import EssayQuote, Topic
from app.services.kg_seed import TOPIC_SEED, seed_topics
from app.services.kg_service import create_edge, seed_relation_types


def test_topics_endpoint(client, db_session):
    seed_topics(db_session)

    response = client.get("/api/kg/topics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(TOPIC_SEED)
    assert len(payload["items"]) == len(TOPIC_SEED)


def test_node_and_subgraph_endpoints(client, db_session):
    seed_relation_types(db_session)
    seed_topics(db_session)
    quote = EssayQuote(content="法者，天下之程式也。", source="管子", status=1)
    db_session.add(quote)
    db_session.commit()
    topic = db_session.query(Topic).filter(Topic.slug == "rule-of-law-thinking").one()
    create_edge(
        db_session,
        src_type="quote",
        src_id=quote.quote_id,
        dst_type="topic",
        dst_id=topic.topic_id,
        relation="has_topic",
    )
    db_session.commit()

    node_resp = client.get(f"/api/kg/nodes/quote/{quote.quote_id}")
    assert node_resp.status_code == 200
    assert node_resp.json()["node"]["type"] == "quote"
    assert len(node_resp.json()["edges"]) == 1

    assert client.get("/api/kg/nodes/quote/999999").status_code == 404

    sub_resp = client.get(
        "/api/kg/subgraph",
        params={"node_type": "quote", "node_id": quote.quote_id, "depth": 2},
    )
    assert sub_resp.status_code == 200
    node_ids = {(item["type"], item["id"]) for item in sub_resp.json()["nodes"]}
    assert ("topic", topic.topic_id) in node_ids


def test_search_endpoint(client, db_session):
    seed_topics(db_session)

    response = client.get("/api/kg/search", params={"q": "法治"})

    assert response.status_code == 200
    labels = [item["label"] for item in response.json()["items"]]
    assert "法治思维" in labels
