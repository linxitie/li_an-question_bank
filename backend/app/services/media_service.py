"""F3 媒体服务：写字节、写元数据、发 outbox、读/删的唯一业务边界。

事务纪律：本模块只 add/flush，不 commit。API 负责把 media_assets、outbox
和业务行放在同一个 Session 事务里提交；DB 失败只留下内容寻址孤儿字节。
"""
from __future__ import annotations

import hashlib
import logging
import re
import tempfile
import uuid
from datetime import datetime
from typing import BinaryIO, Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.foundation.outbox import emit
from app.foundation.stores.object import (
    ObjectNotFound,
    ObjectStoreUnavailable,
    build_object_store,
)
from app.models.media_asset import MediaAsset

logger = logging.getLogger(__name__)

KINDS = {"avatar", "forum", "material_image", "video"}
ASSET_ID_RE = re.compile(r"^[0-9a-f]{32}$")

_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_FORUM_TYPES = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_VIDEO_TYPES = {
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}


class MediaError(Exception):
    """媒体服务错误基类。"""


class MediaValidationError(MediaError):
    """kind/扩展名/大小等调用方错误，对应 HTTP 400。"""


class MediaTooLarge(MediaValidationError):
    """超过调用方上限。"""


class MediaNotFound(MediaError):
    """asset_id 不存在或已 tombstone，对应 HTTP 404。"""


class MediaBlobMissing(MediaError):
    """元数据存在但对象字节缺失；必须显式报错，不得回退旧路径。"""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def image_magic_ok(ext: str, content: bytes) -> bool:
    """按文件头校验常见图片格式，防止改扩展名绕过白名单。"""
    head = content[:12]
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".gif":
        return head.startswith(b"GIF87a") or head.startswith(b"GIF89a")
    if ext == ".webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    return False


def content_type_for(kind: str, original_name: str | None) -> str:
    """服务端按 kind+扩展名确定 Content-Type，不信客户端声明的值。"""
    if kind not in KINDS:
        raise MediaValidationError(f"未知媒体类型: {kind}")
    ext = _ext(original_name)
    table = {
        "avatar": _IMAGE_TYPES,
        "material_image": _IMAGE_TYPES,
        "forum": _FORUM_TYPES,
        "video": _VIDEO_TYPES,
    }[kind]
    mime = table.get(ext)
    if not mime:
        raise MediaValidationError(f"不支持的文件扩展名: {ext or '(空)'}")
    return mime


def _ext(name: str | None) -> str:
    if not name or "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[1].lower()


def _clean_name(name: str | None) -> str:
    raw = (name or "").replace(chr(92), "/").rsplit("/", 1)[-1]
    raw = "".join(c if c.isprintable() and c not in "\r\n" else "_" for c in raw)
    return raw[:255]


def store_bytes(
    session: Session,
    data: bytes,
    *,
    kind: str,
    original_name: str | None,
    content_type: str | None = None,
    created_by: int | None = None,
    trace_id: str | None = None,
    dedupe_key: str | None = None,
    max_bytes: int | None = None,
) -> MediaAsset:
    """小文件写入：算 sha -> 写对象 -> 写元数据 + outbox（不 commit）。"""
    if max_bytes is not None and len(data) > max_bytes:
        raise MediaTooLarge(f"文件超过上限 {max_bytes} 字节")
    return _store_stream(
        session,
        _BytesSource(data),
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        kind=kind,
        original_name=original_name,
        content_type=content_type,
        created_by=created_by,
        trace_id=trace_id,
        dedupe_key=dedupe_key,
    )


def store_file(
    session: Session,
    fileobj: BinaryIO,
    *,
    kind: str,
    original_name: str | None,
    content_type: str | None = None,
    created_by: int | None = None,
    trace_id: str | None = None,
    dedupe_key: str | None = None,
    max_bytes: int | None = None,
) -> MediaAsset:
    """流式写入：边读边算 sha，落临时 spool 后再进对象存储（不整文件进内存）。"""
    digest = hashlib.sha256()
    size = 0
    spool = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        while True:
            chunk = fileobj.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if max_bytes is not None and size > max_bytes:
                raise MediaTooLarge(f"文件超过上限 {max_bytes} 字节")
            digest.update(chunk)
            spool.write(chunk)
        spool.seek(0)
        return _store_stream(
            session,
            spool,
            size=size,
            sha256=digest.hexdigest(),
            kind=kind,
            original_name=original_name,
            content_type=content_type,
            created_by=created_by,
            trace_id=trace_id,
            dedupe_key=dedupe_key,
        )
    finally:
        spool.close()


class _BytesSource:
    """把 bytes 包装成最小 read() 接口，避免为小文件再复制一份。"""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = len(self._data) - self._pos
        chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


def _store_stream(
    session: Session,
    source: BinaryIO,
    *,
    size: int,
    sha256: str,
    kind: str,
    original_name: str | None,
    content_type: str | None,
    created_by: int | None,
    trace_id: str | None,
    dedupe_key: str | None,
) -> MediaAsset:
    mime = content_type_for(kind, original_name)
    if content_type and content_type.split(";")[0].strip().lower() != mime:
        # 客户端声明与扩展名不一致：以服务端映射为准，仅记录不阻断。
        logger.info(
            "media content_type 纠正 kind=%s ext=%s declared=%s actual=%s",
            kind, _ext(original_name), content_type, mime,
        )
    store = build_object_store()
    object_key = f"{sha256[:2]}/{sha256}"
    try:
        store.put(object_key, source, mime, sha256=sha256, size=size)
    except ObjectStoreUnavailable:
        raise
    except OSError as exc:
        logger.error("media 对象写入失败 key=%s: %s", object_key, exc)
        raise ObjectStoreUnavailable(str(exc)) from exc

    asset = MediaAsset(
        asset_id=uuid.uuid4().hex,
        sha256=sha256,
        object_key=object_key,
        size_bytes=size,
        content_type=mime,
        kind=kind,
        original_name=_clean_name(original_name),
        created_by=created_by,
        status="active",
        created_at=_now(),
    )
    session.add(asset)
    session.flush()
    if getattr(settings, "FOUNDATION_ENABLED", True):
        emit(
            session,
            event_name="media.asset.created.v1",
            aggregate_type="media_asset",
            aggregate_id=asset.asset_id,
            payload={
                "asset_id": asset.asset_id,
                "sha256": sha256,
                "size": size,
                "content_type": mime,
                "kind": kind,
                "created_by": created_by,
            },
            producer="media_service",
            trace_id=trace_id,
            dedupe_key=dedupe_key,
        )
    logger.info(
        "media 写入 asset_id=%s kind=%s sha=%s size=%s backend=%s",
        asset.asset_id, kind, sha256[:12], size, store.backend,
    )
    return asset


def get_asset(session: Session, asset_id: str) -> MediaAsset:
    if not ASSET_ID_RE.fullmatch(asset_id or ""):
        raise MediaNotFound(asset_id)
    asset = session.get(MediaAsset, asset_id)
    if asset is None or asset.status != "active":
        raise MediaNotFound(asset_id)
    return asset


def open_asset(session: Session, asset_id: str) -> tuple[MediaAsset, BinaryIO]:
    return open_blob(get_asset(session, asset_id))


def open_blob(asset: MediaAsset) -> tuple[MediaAsset, BinaryIO]:
    try:
        return asset, build_object_store().open(asset.object_key)
    except ObjectNotFound as exc:
        raise MediaBlobMissing(asset.asset_id) from exc


def stream_asset(
    session: Session, asset_id: str, start: int = 0, end: int | None = None
) -> tuple[MediaAsset, Iterator[bytes]]:
    return iter_blob(get_asset(session, asset_id), start, end)


def iter_blob(
    asset: MediaAsset, start: int = 0, end: int | None = None
) -> tuple[MediaAsset, Iterator[bytes]]:
    try:
        return asset, build_object_store().stream(asset.object_key, start, end)
    except ObjectNotFound as exc:
        raise MediaBlobMissing(asset.asset_id) from exc


def stat_asset(session: Session, asset_id: str):
    """HEAD 用：确认字节存在并返回存储侧大小（应为 asset.size_bytes）。"""
    return stat_blob(get_asset(session, asset_id))


def stat_blob(asset: MediaAsset):
    try:
        stat = build_object_store().stat(asset.object_key)
    except ObjectNotFound as exc:
        raise MediaBlobMissing(asset.asset_id) from exc
    if stat is None:
        raise MediaBlobMissing(asset.asset_id)
    return asset, stat


def asset_path(asset: MediaAsset) -> str:
    return f"/media/{asset.asset_id}"


def media_asset_id_from_url(url: str | None) -> str | None:
    if not url or not url.startswith("/media/"):
        return None
    candidate = url[len("/media/"):].split("?", 1)[0]
    return candidate if ASSET_ID_RE.fullmatch(candidate) else None


def retire_url(session: Session, old_url: str | None) -> None:
    """头像替换：只退休 /media/ 旧资产；/uploads/ 旧文件原样保留。"""
    asset_id = media_asset_id_from_url(old_url)
    if asset_id:
        try:
            delete_asset(session, asset_id)
        except Exception as exc:  # noqa: BLE001 - 旧资产清理失败不得阻断新头像
            logger.warning("media 旧资产退休失败 asset_id=%s: %s", asset_id, exc)


def delete_asset(session: Session, asset_id: str) -> bool:
    """tombstone；同 sha 无其他 active 行时才删字节。不 commit。"""
    asset = get_asset(session, asset_id)
    asset.status = "deleted"
    asset.deleted_at = _now()
    session.flush()
    remaining = session.execute(
        text(
            "SELECT COUNT(*) FROM media_assets "
            "WHERE sha256=:sha AND status='active' AND asset_id<>:aid"
        ),
        {"sha": asset.sha256, "aid": asset.asset_id},
    ).scalar_one()
    if remaining == 0:
        try:
            build_object_store().delete(asset.object_key)
        except Exception as exc:  # noqa: BLE001 - 删除字节失败留给 GC 对账
            logger.warning("media 字节删除失败 key=%s: %s", asset.object_key, exc)
    return True