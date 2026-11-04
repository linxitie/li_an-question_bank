"""媒体资产健康快照：表、计数、对象存储可达性、近期缺字节告警。"""
from __future__ import annotations

import threading
import time

from sqlalchemy import text

from app.core.config import settings
from app.foundation.media_schema import MEDIA_TABLES
from app.foundation.stores.object import build_object_store

_MISSING_TTL_SECONDS = 300
_HEALTH_TTL_SECONDS = 30
_missing_lock = threading.Lock()
_missing: dict[str, float] = {}
_cache_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def mark_missing(asset_id: str) -> None:
    """记录一次元数据存在但对象缺失；供 /media 与健康快照共享。"""
    now = time.time()
    with _missing_lock:
        _missing[asset_id] = now
        for key, ts in list(_missing.items()):
            if now - ts > _MISSING_TTL_SECONDS:
                _missing.pop(key, None)
    _clear_cache()


def recent_missing() -> int:
    now = time.time()
    with _missing_lock:
        for key, ts in list(_missing.items()):
            if now - ts > _MISSING_TTL_SECONDS:
                _missing.pop(key, None)
        return len(_missing)


def _clear_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def reset_cache() -> None:
    """测试/运维用：强制下一次健康检查重新探测。"""
    _clear_cache()


def snapshot(engine, use_cache: bool = True) -> dict:
    global _cache
    now = time.time()
    if use_cache:
        with _cache_lock:
            if _cache is not None and now - _cache[0] < _HEALTH_TTL_SECONDS:
                return _cache[1]
    result = _snapshot_uncached(engine)
    with _cache_lock:
        _cache = (time.time(), result)
    return result


def _snapshot_uncached(engine) -> dict:
    enabled = bool(getattr(settings, "MEDIA_STORE_ENABLED", True))
    store = build_object_store()
    store_health = store.health()
    base = {
        "enabled": enabled,
        "backend": store.backend,
        "object_store": {
            "backend": store_health.backend,
            "ok": store_health.ok,
            "degraded": store_health.degraded,
            "detail": store_health.detail,
        },
        "missing_blob_recent": recent_missing(),
    }
    try:
        with engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing = [t for t in MEDIA_TABLES if t not in tables]
            if missing:
                return {
                    **base,
                    "status": "degraded",
                    "schema": "missing",
                    "missing_tables": missing,
                    "assets": None,
                }
            row = conn.execute(
                text(
                    "SELECT "
                    "SUM(CASE WHEN status='active' THEN 1 ELSE 0 END), "
                    "SUM(CASE WHEN status='deleted' THEN 1 ELSE 0 END), "
                    "COALESCE(SUM(CASE WHEN status='active' THEN size_bytes ELSE 0 END),0) "
                    "FROM media_assets"
                )
            ).one()
    except Exception as exc:  # noqa: BLE001 - 健康检查不得反向打挂进程
        return {**base, "status": "degraded", "schema": "error", "detail": str(exc)}

    active = int(row[0] or 0)
    deleted = int(row[1] or 0)
    bytes_active = int(row[2] or 0)
    healthy = enabled and store_health.ok and not store_health.degraded and recent_missing() == 0
    status = "disabled" if not enabled else ("ok" if healthy else "degraded")
    return {
        **base,
        "status": status,
        "schema": "ok",
        "assets": {"active": active, "deleted": deleted, "bytes_active": bytes_active},
    }