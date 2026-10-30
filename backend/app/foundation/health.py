"""foundation 健康快照：供 GET /health/foundation 使用（只读，不写库）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app.foundation.config import FOUNDATION_DISPATCH_MS, FOUNDATION_ENABLED
from app.foundation.projection import PROJECTION_NAME
from app.foundation.schema import FOUNDATION_TABLES

LAG_WARN_SECONDS = 300


def snapshot(engine, relay: dict | None = None) -> dict:
    if not FOUNDATION_ENABLED:
        return {"status": "disabled", "enabled": False, "projection": PROJECTION_NAME, "relay": relay}

    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = [t for t in FOUNDATION_TABLES if t not in tables]
        if missing:
            return {
                "status": "degraded", "enabled": True, "schema": "missing",
                "missing_tables": missing, "projection": PROJECTION_NAME,
            }

        pending = conn.execute(
            text("SELECT COUNT(*) FROM foundation_outbox WHERE status='pending'")
        ).scalar_one()
        dead = conn.execute(
            text("SELECT COUNT(*) FROM foundation_outbox WHERE status='dead'")
        ).scalar_one()
        oldest = conn.execute(
            text("SELECT MIN(occurred_at) FROM foundation_outbox WHERE status='pending'")
        ).scalar_one()
        cursor = conn.execute(
            text("SELECT last_outbox_id, updated_at FROM foundation_projection_cursor WHERE projection=:p"),
            {"p": PROJECTION_NAME},
        ).first()
        last_run = conn.execute(
            text("""SELECT status, finished_at FROM foundation_reconcile_run
                    ORDER BY started_at DESC LIMIT 1""")
        ).first()

    lag = _lag_seconds(oldest)
    healthy = dead == 0 and lag <= LAG_WARN_SECONDS
    return {
        "status": "ok" if healthy else "degraded",
        "enabled": True,
        "schema": "ok",
        "projection": PROJECTION_NAME,
        "pending": int(pending),
        "dead": int(dead),
        "lag_seconds": lag,
        "cursor": None if cursor is None else {
            "last_outbox_id": int(cursor[0]), "updated_at": cursor[1],
        },
        "last_reconcile": None if last_run is None else {
            "status": last_run[0], "finished_at": last_run[1],
        },
        "dispatch_interval_ms": FOUNDATION_DISPATCH_MS,
        "relay": relay,
        "document": _document_section(engine),
        "graph": _graph_section(engine),
        "vector": _vector_section(engine),
    }


def _graph_section(engine) -> dict:
    """图投影健康：图存储可用性 + 最近对账新鲜度/漂移。"""
    from app.foundation import config as cfg

    if not cfg.GRAPH_STORE_ENABLED:
        return {"enabled": False}
    section: dict = {
        "enabled": True,
        "backend": cfg.GRAPH_BACKEND,
        "ok": False,
        "degraded": True,
        "last_reconcile_at": None,
        "drift": None,
    }
    try:
        from app.foundation.stores.graph import build_graph_store

        health = build_graph_store().health()
        section["ok"] = bool(health.ok)
        section["degraded"] = bool(health.degraded)
        section["detail"] = health.detail
    except Exception as exc:  # noqa: BLE001 — 健康检查自身不能抛
        section["error"] = f"{type(exc).__name__}: {exc}"
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """SELECT finished_at, status FROM foundation_reconcile_run
                       WHERE scope='graph' ORDER BY finished_at DESC LIMIT 1"""
                )
            ).first()
        if row is not None:
            section["last_reconcile_at"] = row[0]
            section["drift"] = row[1] == "drift"
    except Exception as exc:  # noqa: BLE001
        section["reconcile_error"] = f"{type(exc).__name__}: {exc}"
    return section


def _vector_section(engine) -> dict:
    """向量投影健康：VectorStore 可用性 + Embedding 配置 + 最近对账。"""
    from app.foundation import config as cfg

    backend = (cfg.VECTOR_BACKEND or "off").strip().lower()
    if not cfg.VECTOR_STORE_ENABLED or backend == "off":
        return {"enabled": False, "backend": backend}
    section: dict = {
        "enabled": True,
        "backend": backend,
        "dim": cfg.VECTOR_DIM,
        "collection": cfg.VECTOR_COLLECTION,
        "ok": False,
        "degraded": True,
        "embedding": {
            "enabled": cfg.EMBEDDING_ENABLED,
            "provider": cfg.EMBEDDING_PROVIDER,
            "degraded": cfg.EMBEDDING_PROVIDER == "hash",
        },
        "last_reconcile_at": None,
        "drift": None,
    }
    try:
        from app.foundation.stores.vector import build_vector_store

        health = build_vector_store().health()
        section["ok"] = bool(health.ok)
        section["degraded"] = bool(health.degraded)
        section["detail"] = health.detail
    except Exception as exc:  # noqa: BLE001 — 健康检查自身不能抛
        section["error"] = f"{type(exc).__name__}: {exc}"
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """SELECT finished_at, status FROM foundation_reconcile_run
                       WHERE scope='vector' ORDER BY finished_at DESC LIMIT 1"""
                )
            ).first()
        if row is not None:
            section["last_reconcile_at"] = row[0]
            section["drift"] = row[1] == "drift"
    except Exception as exc:  # noqa: BLE001
        section["reconcile_error"] = f"{type(exc).__name__}: {exc}"
    return section


def _document_section(engine) -> dict:
    """文档投影健康：库可用性 + 最近对账新鲜度/漂移。"""
    from app.foundation import config as cfg

    if not cfg.DOC_STORE_ENABLED:
        return {"enabled": False}
    section: dict = {
        "enabled": True,
        "backend": cfg.DOC_STORE_BACKEND,
        "docs_root": str(cfg.document_store_root()),
        "ok": False,
        "degraded": True,
        "last_reconcile_at": None,
        "drift": None,
    }
    try:
        from app.foundation.stores.document import build_document_store

        health = build_document_store().health()
        section["ok"] = bool(health.ok)
        section["degraded"] = bool(health.degraded)
        section["detail"] = health.detail
    except Exception as exc:  # noqa: BLE001 — 健康检查自身不能抛
        section["error"] = f"{type(exc).__name__}: {exc}"
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """SELECT finished_at, status FROM foundation_reconcile_run
                       WHERE scope='document' ORDER BY finished_at DESC LIMIT 1"""
                )
            ).first()
        if row is not None:
            section["last_reconcile_at"] = row[0]
            section["drift"] = row[1] == "drift"
    except Exception as exc:  # noqa: BLE001
        section["reconcile_error"] = f"{type(exc).__name__}: {exc}"
    return section


def _lag_seconds(oldest: str | None) -> int:
    if not oldest:
        return 0
    try:
        started = datetime.fromisoformat(oldest)
        delta = datetime.now().astimezone() - started
        return max(0, int(delta.total_seconds()))
    except (TypeError, ValueError):
        return 0
