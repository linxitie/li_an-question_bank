"""R2.1 新闻图片存储抽象；一期只实现 Local。"""
from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path

from ..core.config import settings

_ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


class NewsStorage(ABC):
    """后续 MinIO/OSS 只需实现本接口。"""

    @abstractmethod
    def save_image(self, data: bytes, suffix: str, source_url: str = "") -> str:
        """返回数据库保存的相对路径（uploads/news_images/...）。"""

    def public_url(self, relative_path: str) -> str:
        return "/" + relative_path.lstrip("/")


class LocalNewsStorage(NewsStorage):
    def __init__(self, upload_root: str | Path | None = None):
        self.upload_root = Path(upload_root or settings.UPLOAD_DIR).resolve()

    def save_image(self, data: bytes, suffix: str, source_url: str = "") -> str:
        ext = (suffix or "").lower()
        if not ext.startswith("."):
            ext = "." + ext
        if ext not in _ALLOWED:
            raise ValueError(f"unsupported image suffix: {suffix}")
        digest = hashlib.sha256(data).hexdigest()
        name = f"{digest}{ext}"
        target_dir = self.upload_root / "news_images"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / name
        # 路径逃逸兜底
        if target_dir.resolve() not in target.resolve().parents and target.resolve() != target_dir.resolve():
            raise ValueError("invalid image path")
        if not target.exists():
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        return f"uploads/news_images/{name}"


def get_news_storage() -> NewsStorage:
    backend = (os.environ.get("NEWS_STORAGE_BACKEND") or "local").strip().lower()
    if backend != "local":
        raise ValueError(f"unsupported NEWS_STORAGE_BACKEND: {backend}")
    return LocalNewsStorage()
