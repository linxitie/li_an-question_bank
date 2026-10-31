"""F3 /media 稳定读取契约：公开只读、ETag、Range、HEAD。

旧 /uploads 与 /static 挂载完全不动；本路由只服务 media_assets 的新资产。
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..foundation import media_health
from ..foundation.stores.object import ObjectStoreUnavailable
from ..services import media_service as ms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/media", tags=["媒体资产"])

_CACHE = "public, max-age=31536000, immutable"
# 浏览器原生可渲染、允许内联预览的类型（其余一律下载）
_INLINE_MIMES = {
    "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "text/plain",
}


def _etag(sha256: str) -> str:
    return f'"{sha256}"'


def _base_headers(asset, etag: str) -> dict:
    headers = {
        "ETag": etag,
        "Cache-Control": _CACHE,
        "Accept-Ranges": "bytes",
        "X-Content-Type-Options": "nosniff",
    }
    if asset.kind == "forum" and asset.original_name:
        # 2026-10-30：可预览类型走 inline（PDF/图片/文本），其余仍强制下载。
        # 平板/浏览器无内置阅读器时，前端会退化为下载（?download=1 也可强制下载）。
        name = quote(asset.original_name, safe="")
        headers["Content-Disposition"] = (
            "inline; filename*=UTF-8''" + name
            if asset.content_type in _INLINE_MIMES
            else "attachment; filename*=UTF-8''" + name
        )
    return headers


def _not_modified(request: Request, etag: str) -> bool:
    inm = request.headers.get("if-none-match")
    if not inm:
        return False
    return any(part.strip().removeprefix("W/") == etag for part in inm.split(","))


def _parse_range(header: str | None, size: int):
    """返回 (start,end)，None 表示整文件，'invalid' 表示 416。"""
    if not header:
        return None
    value = header.strip()
    if not value.startswith("bytes=") or "," in value:
        return "invalid"
    spec = value[len("bytes="):].strip()
    if "-" not in spec:
        return "invalid"
    left, right = spec.split("-", 1)
    try:
        if not left:
            suffix = int(right)
            if suffix <= 0:
                return "invalid"
            start = max(0, size - suffix)
            return start, size - 1
        start = int(left)
        end = int(right) if right else size - 1
    except ValueError:
        return "invalid"
    if start < 0 or start >= size or end < start:
        return "invalid"
    return start, min(end, size - 1)


def _range_416(size: int) -> Response:
    return Response(
        status_code=416,
        headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
    )


def _unavailable(exc: Exception) -> JSONResponse:
    logger.error("media 对象存储不可用: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "媒体存储暂时不可用，请稍后重试"},
        headers={"Retry-After": "5"},
    )


@router.api_route("/{asset_id}", methods=["GET", "HEAD"], summary="读取媒体资产")
def get_media(asset_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        asset = ms.get_asset(db, asset_id)
    except ms.MediaNotFound:
        return JSONResponse(status_code=404, content={"detail": "媒体不存在"})

    etag = _etag(asset.sha256)
    headers = _base_headers(asset, etag)
    # 2026-10-30：?download=1 强制下载（前端预览被拦截时的兜底）
    if request.query_params.get("download") == "1" and asset.original_name:
        headers["Content-Disposition"] = (
            "attachment; filename*=UTF-8''" + quote(asset.original_name, safe="")
        )
    if _not_modified(request, etag):
        return Response(status_code=304, headers=headers)

    if request.method == "HEAD":
        try:
            _, stat = ms.stat_blob(asset)
        except ms.MediaBlobMissing:
            media_health.mark_missing(asset_id)
            return JSONResponse(status_code=404, content={"detail": "媒体字节缺失"})
        except ObjectStoreUnavailable as exc:
            return _unavailable(exc)
        headers["Content-Length"] = str(stat.size)
        headers["Content-Type"] = asset.content_type
        return Response(status_code=200, headers=headers)

    size = asset.size_bytes
    if size <= 0:
        # 空对象不进入 Range/迭代逻辑，避免 start/end 反转。
        headers["Content-Length"] = "0"
        return Response(status_code=200, headers=headers)
    parsed = _parse_range(request.headers.get("range"), size)
    if parsed == "invalid":
        return _range_416(size)
    if parsed is None:
        start, end = 0, size - 1
        status_code = 200
    else:
        start, end = parsed
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    headers["Content-Length"] = str(max(0, end - start + 1))
    try:
        _, iterator = ms.iter_blob(asset, start, end)
    except ms.MediaBlobMissing:
        media_health.mark_missing(asset_id)
        return JSONResponse(status_code=404, content={"detail": "媒体字节缺失"})
    except ObjectStoreUnavailable as exc:
        return _unavailable(exc)

    return StreamingResponse(
        iterator,
        status_code=status_code,
        media_type=asset.content_type,
        headers=headers,
    )
