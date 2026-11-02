"""R2.4 新闻图/向量投影（可重建，不参与业务事务）。"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.foundation import config as fcfg
from app.foundation.graph_schema import ensure_graph_schema
from app.foundation.ports.ai import EmbeddingError, EmbeddingPort, build_embedding_port
from app.foundation.stores.document import (
    DocumentStore,
    DocumentTooLarge,
    build_document_store,
)
from app.foundation.stores.graph import GraphStore, build_graph_store
from app.foundation.stores.local_vector import LocalVectorStore
from app.foundation.stores.object import ObjectStore, build_object_store
from app.foundation.stores.vector import VectorItem, VectorStore
from app.models.media_asset import MediaAsset
from app.models.models import NewsArticle, NewsImage
from app.services import media_service

NEWS_VECTOR_COLLECTION = "news_articles"
NEWS_DOCUMENT_COLLECTION = "news_contents"
_DEFAULT_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"


def _published(db: Session) -> list[NewsArticle]:
    return (
        db.query(NewsArticle)
        .filter(NewsArticle.status == 1, NewsArticle.review_status == "published")
        .order_by(NewsArticle.news_id)
        .all()
    )


def _date(value: datetime | None) -> str:
    return value.date().isoformat() if value else ""


def project_graph(db: Session, *, store: GraphStore | None = None, reset: bool = False) -> dict[str, Any]:
    if store is None:
        with sqlite3.connect(str(fcfg.sqlite_path())) as conn:
            ensure_graph_schema(conn)
        store = build_graph_store()
    if reset:
        store.clear()
    news_list = _published(db)
    nodes = 0
    edges = 0
    for news in news_list:
        store.upsert_node(
            "News", str(news.news_id),
            {
                "newsId": news.news_id,
                "title": news.title,
                "source": news.source,
                "category": news.category or "",
                "publishDate": _date(news.publish_date),
                "reviewStatus": news.review_status,
            },
            version=1,
        )
        nodes += 1
        if news.category_code or news.category:
            key = news.category_code or news.category or "uncategorized"
            store.upsert_node(
                "Topic", key,
                {"code": key, "name": news.category or key},
                version=1,
            )
            store.upsert_edge(
                "ABOUT", ("News", str(news.news_id)), ("Topic", key),
                {"derivation": "news_category"},
            )
            edges += 1
        if news.source:
            store.upsert_node(
                "Source", news.source,
                {"code": news.source, "name": news.source},
                version=1,
            )
            store.upsert_edge(
                "FROM_SOURCE", ("News", str(news.news_id)), ("Source", news.source),
                {"derivation": "news_source"},
            )
            edges += 1
        images = (
            db.query(NewsImage)
            .filter(NewsImage.news_id == news.news_id)
            .order_by(NewsImage.image_order)
            .all()
        )
        for image in images:
            store.upsert_node(
                "Media", image.image_path,
                {"path": image.image_path, "newsId": news.news_id},
                version=1,
            )
            store.upsert_edge(
                "HAS_MEDIA", ("News", str(news.news_id)), ("Media", image.image_path),
                {"derivation": "news_image", "order": image.image_order},
            )
            edges += 1
    return {
        "news": len(news_list),
        "nodes_written": nodes,
        "edges_written": edges,
        "backend": getattr(store, "backend", "unknown"),
    }


def _json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


def _image_info(
    image_path: str,
    upload_root: Path,
) -> dict[str, Any]:
    relative = image_path.replace("\\", "/")
    if relative.startswith("uploads/"):
        relative = relative[len("uploads/"):]
    path = Path(upload_root) / relative
    if not path.is_file():
        return {"imagePath": image_path, "missing": True}
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    return {
        "imagePath": image_path,
        "objectKey": f"{digest[:2]}/{digest}",
        "sha256": digest,
        "size": len(data),
        "contentType": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "data": data,
        "missing": False,
    }


def project_objects(
    db: Session,
    *,
    store: ObjectStore | None = None,
    upload_root: Path | str | None = None,
) -> dict[str, Any]:
    """把已发布新闻图片写入 F3 ObjectStore（内容寻址，幂等）。"""
    target = store or build_object_store()
    root = Path(upload_root) if upload_root else _DEFAULT_UPLOAD_ROOT
    news_list = _published(db)
    images = 0
    uploaded = 0
    existing = 0
    missing = 0
    errors: list[str] = []
    for news in news_list:
        rows = (
            db.query(NewsImage)
            .filter(NewsImage.news_id == news.news_id)
            .order_by(NewsImage.image_order)
            .all()
        )
        for image in rows:
            images += 1
            info = _image_info(image.image_path, root)
            if info["missing"]:
                missing += 1
                continue
            try:
                if target.stat(info["objectKey"]) is not None:
                    existing += 1
                    continue
                target.put(
                    info["objectKey"],
                    BytesIO(info["data"]),
                    info["contentType"],
                    sha256=info["sha256"],
                    size=info["size"],
                )
                uploaded += 1
            except Exception as exc:
                errors.append(f"news {news.news_id} {image.image_path}: {exc}")
    return {
        "news": len(news_list),
        "images": images,
        "uploaded": uploaded,
        "existing": existing,
        "missing": missing,
        "errors": errors[:10],
    }


def project_media_assets(
    db: Session,
    *,
    upload_root: Path | str | None = None,
) -> dict[str, Any]:
    """把已发布新闻图片登记到 F3 media_assets，并回填 news_image.media_asset_id。"""
    root = Path(upload_root) if upload_root else _DEFAULT_UPLOAD_ROOT
    news_list = _published(db)
    created = 0
    existing = 0
    linked = 0
    missing = 0
    errors: list[str] = []
    for news in news_list:
        rows = (
            db.query(NewsImage)
            .filter(NewsImage.news_id == news.news_id)
            .order_by(NewsImage.image_order)
            .all()
        )
        for image in rows:
            if image.media_asset_id:
                asset = db.get(MediaAsset, image.media_asset_id)
                if asset is not None and asset.status == "active":
                    existing += 1
                    linked += 1
                    continue
            info = _image_info(image.image_path, root)
            if info["missing"]:
                missing += 1
                continue
            try:
                asset = (
                    db.query(MediaAsset)
                    .filter(
                        MediaAsset.sha256 == info["sha256"],
                        MediaAsset.kind == "news_image",
                        MediaAsset.status == "active",
                    )
                    .first()
                )
                if asset is None:
                    asset = media_service.store_bytes(
                        db,
                        info["data"],
                        kind="news_image",
                        original_name=Path(image.image_path).name,
                        content_type=info["contentType"],
                        dedupe_key=f"news-image:{image.image_id}",
                        max_bytes=8 * 1024 * 1024,
                    )
                    created += 1
                else:
                    existing += 1
                image.media_asset_id = asset.asset_id
                linked += 1
            except Exception as exc:
                errors.append(f"news {news.news_id} {image.image_path}: {exc}")
    db.commit()
    return {
        "news": len(news_list),
        "created": created,
        "existing": existing,
        "linked": linked,
        "missing": missing,
        "errors": errors[:10],
    }


def project_documents(
    db: Session,
    *,
    store: DocumentStore | None = None,
    upload_root: Path | str | None = None,
) -> dict[str, Any]:
    """把已发布新闻正文/AI 结果/图片引用写入 F4 DocumentStore。"""
    target = store or build_document_store()
    root = Path(upload_root) if upload_root else _DEFAULT_UPLOAD_ROOT
    news_list = _published(db)
    written = 0
    errors: list[str] = []
    for news in news_list:
        rows = (
            db.query(NewsImage)
            .filter(NewsImage.news_id == news.news_id)
            .order_by(NewsImage.image_order)
            .all()
        )
        refs = []
        for image in rows:
            info = _image_info(image.image_path, root)
            refs.append({
                "imagePath": image.image_path,
                "mediaAssetId": image.media_asset_id,
                "objectKey": info.get("objectKey"),
                "sha256": info.get("sha256"),
                "size": info.get("size", 0),
                "missing": info["missing"],
            })
        doc = {
            "newsId": news.news_id,
            "title": news.title,
            "url": news.url,
            "source": news.source,
            "category": news.category or "",
            "categoryCode": news.category_code or "",
            "regionCode": news.region_code or "",
            "publishDate": news.publish_date.isoformat() if news.publish_date else "",
            "reviewStatus": news.review_status,
            "summary": news.summary or "",
            "content": news.content or "",
            "aiSummary": news.ai_summary or "",
            "aiExamPoints": _json_list(news.ai_exam_points),
            "aiEntities": _json_list(news.ai_entities),
            "aiRiskFlags": _json_list(news.ai_risk_flags),
            "images": refs,
            "projectedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        try:
            # 投影无业务版本号；用微秒时间戳保证重跑能覆盖旧文档。
            target.upsert(
                NEWS_DOCUMENT_COLLECTION,
                f"news:{news.news_id}",
                doc,
                version=int(datetime.now().timestamp() * 1_000_000),
            )
            written += 1
        except DocumentTooLarge as exc:
            errors.append(f"news {news.news_id}: {exc}")
        except Exception as exc:
            errors.append(f"news {news.news_id}: {exc}")
    return {"news": len(news_list), "written": written, "errors": errors[:10]}


def project_vectors(
    db: Session,
    *,
    embedding: EmbeddingPort | None = None,
    store: VectorStore | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    port = embedding or build_embedding_port()
    news_list = _published(db)
    if not news_list:
        return {"news": 0, "planned": 0, "written": 0, "provider": getattr(port, "provider", "unknown")}
    texts = [
        f"{n.title}\n{n.ai_summary or n.summary or ''}\n{(n.content or '')[:3000]}"
        for n in news_list
    ]
    vectors = port.embed(texts)
    if len(vectors) != len(news_list):
        raise ValueError("embedding 返回数量与新闻数不一致")
    target = store or LocalVectorStore(fcfg.vector_store_root(), dim=int(port.dim))
    if reset:
        target.clear(NEWS_VECTOR_COLLECTION)
    items = []
    for news, vector in zip(news_list, vectors):
        if len(vector) != int(port.dim):
            raise ValueError(f"embedding 维度 {len(vector)} != {port.dim}")
        items.append(VectorItem(
            id=str(news.news_id),
            vector=list(vector),
            meta={
                "newsId": news.news_id,
                "title": news.title,
                "category": news.category or "",
                "source": news.source,
                "provider": getattr(port, "provider", "unknown"),
                "contentHash": news.content_hash or "",
            },
        ))
    written = target.upsert_many(NEWS_VECTOR_COLLECTION, items)
    return {
        "news": len(news_list),
        "planned": len(items),
        "written": written,
        "provider": getattr(port, "provider", "unknown"),
        "degraded": bool(getattr(port, "degraded", False)),
        "collection": NEWS_VECTOR_COLLECTION,
    }


def project_vectors_safe(
    db: Session,
    *,
    provider: str = "auto",
    embedding: EmbeddingPort | None = None,
    store: VectorStore | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    """向量不可用时降级到 FTS/LIKE，不阻断新闻基础功能。"""
    port = embedding
    try:
        if port is None:
            if provider == "off":
                return {
                    "ok": False, "skipped": True, "fallback": "fts",
                    "provider": "off", "reason": "EMBEDDING_PROVIDER=off",
                }
            port = build_embedding_port(None if provider == "auto" else provider)
        actual_provider = getattr(port, "provider", "unknown")
        if actual_provider == "off":
            return {
                "ok": False, "skipped": True, "fallback": "fts",
                "provider": "off", "reason": "EMBEDDING_ENABLED=false 或 PROVIDER=off",
            }
        result = project_vectors(db, embedding=port, store=store, reset=reset)
        result["ok"] = True
        return result
    except (EmbeddingError, ValueError) as exc:
        return {
            "ok": False,
            "skipped": True,
            "fallback": "fts",
            "provider": getattr(port, "provider", provider),
            "reason": str(exc)[:300],
        }
