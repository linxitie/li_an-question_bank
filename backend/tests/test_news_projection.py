"""R2.4 新闻图/向量投影测试。"""
import hashlib
import sqlite3

from app.foundation.graph_schema import ensure_graph_schema
from app.foundation.ports.ai import EmbeddingUnavailable, HashEmbedding
from app.foundation.stores.local_document import LocalDocumentStore
from app.foundation.stores.local_graph import LocalGraphStore
from app.foundation.stores.local_object import LocalObjectStore
from app.foundation.stores.local_vector import LocalVectorStore
from app.models.media_asset import MediaAsset
from app.models.models import NewsArticle, NewsImage
from app.services import media_service
from app.services.news_projection import (
    NEWS_VECTOR_COLLECTION,
    project_documents,
    project_graph,
    project_media_assets,
    project_objects,
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


def test_project_objects_and_documents(tmp_path, db_session):
    _news(db_session)
    image_dir = tmp_path / "news_images"
    image_dir.mkdir()
    image_bytes = b"fake-news-image"
    (image_dir / "a.jpg").write_bytes(image_bytes)
    digest = hashlib.sha256(image_bytes).hexdigest()
    key = f"{digest[:2]}/{digest}"

    obj_store = LocalObjectStore(tmp_path / "objects")
    obj_report = project_objects(
        db_session, store=obj_store, upload_root=tmp_path
    )
    assert obj_report["uploaded"] == 1
    assert obj_store.stat(key) is not None

    doc_store = LocalDocumentStore(tmp_path / "docs")
    doc_report = project_documents(
        db_session, store=doc_store, upload_root=tmp_path
    )
    assert doc_report["written"] == 1
    doc = doc_store.get("news_contents", "news:1")
    assert doc["title"] == "新闻投影测试"
    assert doc["images"][0]["objectKey"] == key


def test_project_media_assets_links_and_dedupes(tmp_path, db_session, monkeypatch):
    _news(db_session)
    image_dir = tmp_path / "news_images"
    image_dir.mkdir()
    (image_dir / "a.jpg").write_bytes(b"fake-news-image")
    monkeypatch.setattr(
        media_service, "build_object_store",
        lambda: LocalObjectStore(tmp_path / "objects"),
    )
    monkeypatch.setattr(media_service.settings, "FOUNDATION_ENABLED", False)

    first = project_media_assets(db_session, upload_root=tmp_path)
    second = project_media_assets(db_session, upload_root=tmp_path)

    assert first["created"] == 1
    assert first["linked"] == 1
    assert second["created"] == 0
    assert second["existing"] == 1
    asset = db_session.query(MediaAsset).one()
    image = db_session.query(NewsImage).one()
    assert image.media_asset_id == asset.asset_id
    assert asset.kind == "news_image"
