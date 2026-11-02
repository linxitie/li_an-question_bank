"""R2.4 新闻图/向量投影测试。"""
import sqlite3

from app.foundation.graph_schema import ensure_graph_schema
from app.foundation.ports.ai import EmbeddingUnavailable, HashEmbedding
from app.foundation.stores.local_graph import LocalGraphStore
from app.foundation.stores.local_vector import LocalVectorStore
from app.models.models import NewsArticle, NewsImage
from app.services.news_projection import (
    NEWS_VECTOR_COLLECTION,
    project_graph,
    project_vectors,
    project_vectors_safe,
)


def _news(db):
    news = NewsArticle(
        title="新闻投影测试", url="https://example.com/p/1", source="mps",
        category="公安要闻", category_code="police_news",
        content="公安新闻投影正文" * 10, status=1, review_status="published",
    )
    db.add(news)
    db.flush()
    db.add(NewsImage(news_id=news.news_id, image_path="uploads/news_images/a.jpg", image_order=0))
    db.commit()
    db.refresh(news)
    return news


def test_project_graph_news_topic_source_media(tmp_path, db_session):
    db_path = tmp_path / "graph.db"
    with sqlite3.connect(db_path) as conn:
        ensure_graph_schema(conn)
    store = LocalGraphStore(db_path)
    _news(db_session)

    report = project_graph(db_session, store=store)

    assert report["news"] == 1
    assert report["nodes_written"] == 1
    assert store.get_node("News", "1") is not None
    assert store.get_node("Topic", "police_news") is not None
    assert store.get_node("Source", "mps") is not None
    assert store.get_node("Media", "uploads/news_images/a.jpg") is not None
    assert store.counts()["edges"] == 3


def test_project_vectors_with_hash_provider(tmp_path, db_session):
    _news(db_session)
    embedding = HashEmbedding(32)
    store = LocalVectorStore(tmp_path, dim=32)

    report = project_vectors(db_session, embedding=embedding, store=store)

    assert report["written"] == 1
    assert report["degraded"] is True
    assert store.count(NEWS_VECTOR_COLLECTION) == 1
    hits = store.search(NEWS_VECTOR_COLLECTION, embedding.embed(["公安新闻"])[0], top_k=3)
    assert hits and hits[0].id == "1"


class _FailingEmbedding:
    provider = "http"
    dim = 32
    degraded = False

    def embed(self, texts):
        raise EmbeddingUnavailable("provider unavailable")


def test_projection_degrades_when_embedding_off(tmp_path, db_session):
    _news(db_session)
    store = LocalVectorStore(tmp_path, dim=32)

    report = project_vectors_safe(db_session, provider="off", store=store)

    assert report["skipped"] is True
    assert report["fallback"] == "fts"
    assert store.count(NEWS_VECTOR_COLLECTION) == 0


def test_projection_degrades_when_embedding_fails(tmp_path, db_session):
    _news(db_session)
    store = LocalVectorStore(tmp_path, dim=32)

    report = project_vectors_safe(
        db_session, embedding=_FailingEmbedding(), store=store
    )

    assert report["skipped"] is True
    assert report["fallback"] == "fts"
    assert "provider unavailable" in report["reason"]
