"""MinIO/S3 兼容对象存储：path-style + AWS SigV4（零新增依赖）。

只实现 F3 需要的 PUT/GET/HEAD/DELETE/ListObjectsV2。密钥只从环境变量读取，
不落盘、不写日志。所有网络/认证/5xx 统一映射为 ObjectStoreUnavailable，
让 API 返回 503，而不是写出半条业务数据。
"""
from __future__ import annotations

import hashlib
import hmac
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import BinaryIO, Iterator

import httpx

from app.foundation.stores.object import (
    InvalidObjectKey,
    ObjectNotFound,
    ObjectStat,
    ObjectStoreUnavailable,
    StoreHealth,
    normalize_key,
)

_EMPTY_SHA = hashlib.sha256(b"").hexdigest()
_CHUNK = 256 * 1024


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _uri_encode(value: str, safe: str = "") -> str:
    return urllib.parse.quote(value, safe=safe)


class MinioObjectStore:
    backend = "minio"

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        region: str = "us-east-1",
        timeout: float = 5.0,
    ):
        raw = (endpoint or "").strip().rstrip("/")
        if raw.startswith("http://"):
            raw, secure = raw[len("http://"):], False
        elif raw.startswith("https://"):
            raw, secure = raw[len("https://"):], True
        if not raw or not bucket or not access_key or not secret_key:
            raise ObjectStoreUnavailable("MinIO 配置不完整（endpoint/bucket/access/secret）")
        self.endpoint = raw
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.region = region or "us-east-1"
        self.scheme = "https" if secure else "http"
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, follow_redirects=False)

    # ---------- 签名 ----------
    def _signed_headers(
        self, method: str, path: str, query: dict[str, str] | None,
        payload_hash: str, content_type: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = amz_date[:8]
        host = self.endpoint
        headers: dict[str, str] = {
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            headers["content-type"] = content_type
        if extra:
            for k, v in extra.items():
                headers[k.lower()] = v
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers))
        canonical_uri = _uri_encode(path, safe="/-_.~")
        items = []
        for k in sorted(query or {}):
            items.append(f"{_uri_encode(k)}={_uri_encode(query[k])}")
        canonical_query = "&".join(items)
        canonical_request = "\n".join([
            method,
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_names,
            payload_hash,
        ])
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ])
        k_date = _hmac(("AWS4" + self.secret_key).encode("utf-8"), date_stamp)
        k_region = _hmac(k_date, self.region)
        k_service = _hmac(k_region, "s3")
        k_signing = _hmac(k_service, "aws4_request")
        signature = hmac.new(
            k_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        headers["Authorization"] = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        )
        return headers

    def _url(self, key: str | None = None, query: dict[str, str] | None = None) -> str:
        path = f"/{_uri_encode(self.bucket)}"
        if key:
            path += "/" + _uri_encode(key, safe="/-_.~")
        url = f"{self.scheme}://{self.endpoint}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        return url

    def _call(
        self, method: str, *, key: str | None = None, query: dict[str, str] | None = None,
        content: BinaryIO | bytes | None = None, payload_hash: str = _EMPTY_SHA,
        content_type: str | None = None, extra: dict[str, str] | None = None,
        stream: bool = False, content_length: int | None = None,
    ) -> httpx.Response:
        path = f"/{self.bucket}" + (f"/{key}" if key else "")
        headers = self._signed_headers(
            method, path, query, payload_hash, content_type, extra
        )
        # 流式 BinaryIO 没有可靠的 len()，必须由调用方给出真实字节数；
        # SigV4 要求 Content-Length 与实际 body 一致，否则 MinIO 会拒绝 PUT。
        if content_length is None and isinstance(content, (bytes, bytearray)):
            content_length = len(content)
        headers["Content-Length"] = str(content_length or 0)
        try:
            req = self._client.build_request(
                method, self._url(key, query), headers=headers, content=content
            )
            resp = self._client.send(req, stream=stream)
        except httpx.HTTPError as exc:
            raise ObjectStoreUnavailable(f"MinIO 请求失败: {exc}") from exc
        if resp.status_code in (401, 403):
            if stream:
                resp.close()
            raise ObjectStoreUnavailable(
                f"MinIO 认证失败: HTTP {resp.status_code} {resp.text[:200]}"
            )
        if resp.status_code >= 500:
            if stream:
                resp.close()
            raise ObjectStoreUnavailable(f"MinIO 服务错误: HTTP {resp.status_code}")
        return resp

    # ---------- 写 ----------
    def put(
        self, key: str, source: BinaryIO, content_type: str,
        *, sha256: str, size: int,
    ) -> None:
        norm = normalize_key(key)
        if size < 0:
            raise InvalidObjectKey("size 不能为负数")
        resp = self._call(
            "PUT", key=norm, content=source, payload_hash=sha256,
            content_type=content_type, content_length=size,
        )
        if resp.status_code not in (200, 201):
            raise ObjectStoreUnavailable(f"MinIO PUT 失败: HTTP {resp.status_code} {resp.text[:200]}")

    # ---------- 读 ----------
    def open(self, key: str) -> BinaryIO:
        norm = normalize_key(key)
        resp = self._call("GET", key=norm)
        if resp.status_code == 404:
            raise ObjectNotFound(norm)
        if resp.status_code != 200:
            raise ObjectStoreUnavailable(f"MinIO GET 失败: HTTP {resp.status_code}")
        spool = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        for chunk in resp.iter_bytes(_CHUNK):
            spool.write(chunk)
        spool.seek(0)
        return spool

    def stream(
        self, key: str, start: int = 0, end: int | None = None
    ) -> Iterator[bytes]:
        norm = normalize_key(key)
        if start < 0 or (end is not None and end < start):
            raise ValueError(f"非法 Range: start={start} end={end}")
        extra = {}
        if start or end is not None:
            extra["Range"] = f"bytes={start}-{'' if end is None else end}"
        resp = self._call("GET", key=norm, extra=extra, stream=True)
        if resp.status_code == 404:
            resp.close()
            raise ObjectNotFound(norm)
        if resp.status_code not in (200, 206):
            resp.close()
            raise ObjectStoreUnavailable(f"MinIO GET 失败: HTTP {resp.status_code}")
        return self._iter_response(resp)

    @staticmethod
    def _iter_response(resp: httpx.Response) -> Iterator[bytes]:
        try:
            yield from resp.iter_bytes(_CHUNK)
        finally:
            resp.close()

    def stat(self, key: str) -> ObjectStat | None:
        norm = normalize_key(key)
        resp = self._call("HEAD", key=norm)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise ObjectStoreUnavailable(f"MinIO HEAD 失败: HTTP {resp.status_code}")
        size = int(resp.headers.get("content-length", "0"))
        return ObjectStat(key=norm, size=size, sha256=norm.split("/")[1])

    # ---------- 删/枚举/健康 ----------
    def delete(self, key: str) -> bool:
        norm = normalize_key(key)
        resp = self._call("DELETE", key=norm)
        if resp.status_code == 404:
            return False
        if resp.status_code not in (200, 204):
            raise ObjectStoreUnavailable(f"MinIO DELETE 失败: HTTP {resp.status_code}")
        return True

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        token: str | None = None
        while True:
            query = {"list-type": "2", "prefix": prefix}
            if token:
                query["continuation-token"] = token
            resp = self._call("GET", key="", query=query)
            if resp.status_code != 200:
                raise ObjectStoreUnavailable(f"MinIO LIST 失败: HTTP {resp.status_code}")
            root = ET.fromstring(resp.text)
            ns = {"s3": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
            for node in root.findall(".//s3:Contents/s3:Key", ns) if ns else root.findall(".//Contents/Key"):
                if node.text:
                    yield node.text
            truncated = root.findtext(".//s3:IsTruncated", "false", ns) if ns else root.findtext(".//IsTruncated", "false")
            if str(truncated).lower() != "true":
                return
            token = root.findtext(".//s3:NextContinuationToken", None, ns) if ns else root.findtext(".//NextContinuationToken")
            if not token:
                return

    def health(self) -> StoreHealth:
        try:
            resp = self._call("HEAD", key="")
            if resp.status_code in (200, 204, 301):
                return StoreHealth(backend=self.backend, ok=True, detail=f"bucket={self.bucket}")
            return StoreHealth(
                backend=self.backend, ok=False, degraded=True,
                detail=f"HTTP {resp.status_code} bucket={self.bucket}",
            )
        except ObjectStoreUnavailable as exc:
            return StoreHealth(backend=self.backend, ok=False, degraded=True, detail=str(exc))
