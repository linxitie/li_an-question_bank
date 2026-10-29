"""R0 图谱服务测试：种子、边去重、主题合并、节点解析、子图。"""
import pytest

from app.models.models import EssayQuote, KgEdge, NewsArticle, Topic
from app.services.kg_seed import TOPIC_SEED, seed_topics
from app.services.kg_service import (
    create_edge,
    get_subgraph,
    list_topics,
    merge_topics,
    resolve_node,
    seed_relation_types,
)


def _bootstrap(db):
    seed_relation_types(db)
    seed_topics(db)


def test_seed_topics_is_idempotent(db_session):
    assert seed_topics(db_session) == len(TOPIC_SEED)
    assert seed_topics(db_session) == 0
    assert db_session.query(Topic).count() == len(TOPIC_SEED)
    assert len(list_topics(db_session, "exam_type")) == 6


def test_create_edge_dedupes_and_validates(db_session):
    _bootstrap(db_session)
    topic = db_session.query(Topic).first()

    first = create_edge(
        db_session,
        src_type="quote",
        src_id=1,
        dst_type="topic",
        dst_id=topic.topic_id,
        relation="has_topic",
    )
    second = create_edge(
        db_session,
        src_type="quote",
        src_id=1,
        dst_type="topic",
        dst_id=topic.topic_id,
        relation="has_topic",
    )
    assert first.edge_id == second.edge_id
    db_session.commit()
    assert db_session.query(KgEdge).count() == 1

    with pytest.raises(ValueError):
        create_edge(
            db_session,
            src_type="quote",
            src_id=1,
            dst_type="topic",
            dst_id=topic.topic_id,
            relation="not_a_relation",
        )
    with pytest.raises(ValueError):
        create_edge(
            db_session,
            src_type="unknown",
            src_id=1,
            dst_type="topic",
            dst_id=topic.topic_id,
            relation="has_topic",
        )


def test_merge_topics_moves_edges(db_session):
    _bootstrap(db_session)
    source = Topic(name="待合并", slug="merge-source", kind="theme")
    target = Topic(name="目标主题", slug="merge-target", kind="theme")
    db_session.add_all([source, target])
    db_session.commit()

    create_edge(
        db_session,
        src_type="quote",
        src_id=1,
        dst_type="topic",
        dst_id=source.topic_id,
        relation="has_topic",
    )
    db_session.commit()

    assert merge_topics(db_session, source.topic_id, target.topic_id) == 1
    edge = db_session.query(KgEdge).one()
    assert edge.dst_id == target.topic_id
    assert db_session.get(Topic, source.topic_id) is None


def test_resolve_node_and_subgraph(db_session):
    _bootstrap(db_session)
    quote = EssayQuote(content="法者，天下之程式也。", source="管子", status=1)
    news = NewsArticle(title="公安要闻", url="https://example.com/n/1", source="cpd")
    db_session.add_all([quote, news])
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
    create_edge(
        db_session,
        src_type="news",
        src_id=news.news_id,
        dst_type="topic",
        dst_id=topic.topic_id,
        relation="has_topic",
    )
    db_session.commit()

    node = resolve_node(db_session, "quote", quote.quote_id)
    assert node is not None
    assert node["label"].startswith("法者")

    subgraph = get_subgraph(db_session, "quote", quote.quote_id, depth=2)
    node_ids = {(item["type"], item["id"]) for item in subgraph["nodes"]}
    assert ("quote", quote.quote_id) in node_ids
    assert ("news", news.news_id) in node_ids
    assert len(subgraph["edges"]) == 2
