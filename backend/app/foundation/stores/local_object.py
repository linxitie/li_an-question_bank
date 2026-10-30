"""local 对象存储：内容寻址目录 + 原子写。

路径：<root>/<sha[:2]>/<sha>。同一 sha 只存一份；写入先落同目录临时文件，
fsync 后 os.replace，保证读端永远看不到半个文件。
"""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import BinaryIO, Iterator

from app.foundation.stores.object import (
    InvalidObjectKey,
    ObjectNotFound,
    ObjectStat,
    StoreHealth,
    normalize_key,
)


logger = logging.getLogger(__name__)


class LocalObjectStore:
    backend = "local"

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ---------- 写 ----------
    def put(
        self,
        key: str,
        source: BinaryIO,
        content_type: str,
        *,
        sha256: str,
        size: int,
    ) -> None:
        norm = normalize_key(key)
        if norm.split("/")[1] != sha256:
            raise InvalidObjectKey("key 与传入 sha256 不一致")
        dest = self._path(norm)
        with self._lock_for(norm):
            self._put_locked(norm, dest, source, sha256, size)

    def _put_locked(self, norm: str, dest: Path, source: BinaryIO,
                    sha256: str, size: int) -> None:
        if dest.exists() and dest.stat().st_size == size:
            # 内容寻址天然幂等：已有同样大小的对象直接跳过，避免重复 IO。
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(dest.parent))
        try:
            digest = hashlib.sha256()
            written = 0
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    written += len(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if written != size:
                raise ValueError(f"对象大小不符: expected={size} actual={written}")
            if digest.hexdigest() != sha256:
                raise ValueError("对象 sha256 与声明不一致")
            try:
                os.replace(tmp, dest)
            except PermissionError:
                # Windows 下并发 replace 同一目标可能短暂拒绝访问；
                # 若目标已是完整同尺寸对象，视为成功，删除临时文件即可。
                if dest.exists() and dest.stat().st_size == size:
                    os.unlink(tmp)
                    return
                raise
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError as cleanup_exc:
                # 清理失败不能掩盖原始写入异常；留下 .tmp- 由 GC/人工处理。
                logger.debug("本地对象临时文件清理失败: %s", cleanup_exc)
            raise

    # ---------- 读 ----------
    def open(self, key: str) -> BinaryIO:
        path = self._path(normalize_key(key))
        try:
            return open(path, "rb")
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc

    def stream(
        self, key: str, start: int = 0, end: int | None = None
    ) -> Iterator[bytes]:
        # 必须先做存在性/大小检查再返回迭代器：生成器延迟执行会让缺文件
        # 在响应头已发出后才炸，HTTP 层无法再改成 404。
        path = self._path(normalize_key(key))
        try:
            total = path.stat().st_size
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc
        if start < 0 or (end is not None and end < start):
            raise ValueError(f"非法 Range: start={start} end={end}")
        if start >= total:
            return iter(())
        last = total - 1 if end is None else min(end, total - 1)
        return self._iter_file(path, start, last)

    @staticmethod
    def _iter_file(path: Path, start: int, last: int) -> Iterator[bytes]:
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = last - start + 1
            while remaining > 0:
                chunk = fh.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    def stat(self, key: str) -> ObjectStat | None:
        norm = normalize_key(key)
        path = self._path(norm)
        try:
            st = path.stat()
        except FileNotFoundError:
            return None
        return ObjectStat(key=norm, size=st.st_size, sha256=norm.split("/")[1])

    # ---------- 删/枚举/健康 ----------
    def delete(self, key: str) -> bool:
        try:
            self._path(normalize_key(key)).unlink()
            return True
        except FileNotFoundError:
            return False

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        if prefix and not all(c in "0123456789abcdef/" for c in prefix):
            raise InvalidObjectKey(f"非法 prefix: {prefix!r}")
        base = self.root
        if prefix:
            parts = [p for p in prefix.split("/") if p]
            for p in parts:
                if p in {".", ".."}:
                    raise InvalidObjectKey(f"非法 prefix: {prefix!r}")
            base = base.joinpath(*parts)
        if not base.exists():
            return
        for path in base.rglob("*"):
            if not path.is_file() or path.name.startswith(".tmp-"):
                continue
            rel = path.relative_to(self.root).as_posix()
            digest = path.name
            if len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
                yield rel

    def health(self) -> StoreHealth:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".health-probe"
            probe.write_bytes(b"")
            probe.unlink()
            return StoreHealth(backend=self.backend, ok=True, detail=str(self.root))
        except OSError as e:
            return StoreHealth(
                backend=self.backend, ok=False, degraded=True, detail=str(e)
            )

    def _lock_for(self, norm: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(norm)
            if lock is None:
                lock = threading.Lock()
                self._locks[norm] = lock
            return lock

    def _path(self, norm: str) -> Path:
        prefix, digest = norm.split("/")
        return self.root / prefix / digest