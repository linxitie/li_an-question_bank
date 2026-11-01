"""R2.1 新闻 LocalStorage 测试。"""
from pathlib import Path

import pytest

from app.services.news_storage import LocalNewsStorage


def test_local_storage_hashes_and_dedupes(tmp_path):
    storage = LocalNewsStorage(tmp_path)
    data = b"fake-image-bytes"

    first = storage.save_image(data, ".jpg", "https://example.com/a.jpg")
    second = storage.save_image(data, ".jpg", "https://example.com/a.jpg")

    assert first == second
    assert first.startswith("uploads/news_images/")
    assert (Path(tmp_path) / "news_images" / Path(first).name).is_file()
    assert storage.public_url(first) == "/" + first


def test_local_storage_rejects_unknown_suffix(tmp_path):
    storage = LocalNewsStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.save_image(b"x", ".exe")
