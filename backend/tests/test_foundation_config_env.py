"""foundation 配置必须像 Pydantic 一样读取 backend/.env。"""
import os

from app.foundation.config import load_env_files


def test_foundation_loads_env_file(tmp_path, monkeypatch):
    for key in (
        "EMBEDDING_ENABLED", "EMBEDDING_PROVIDER", "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL", "EMBEDDING_DIM",
    ):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "EMBEDDING_ENABLED=true\n"
        "EMBEDDING_PROVIDER=http\n"
        "EMBEDDING_BASE_URL=https://embed.example/v1\n"
        "EMBEDDING_MODEL=test-embed\n"
        "EMBEDDING_DIM=512\n",
        encoding="utf-8",
    )

    load_env_files((env_file,))

    assert os.environ["EMBEDDING_ENABLED"] == "true"
    assert os.environ["EMBEDDING_PROVIDER"] == "http"
    assert os.environ["EMBEDDING_BASE_URL"] == "https://embed.example/v1"
    assert os.environ["EMBEDDING_MODEL"] == "test-embed"
    assert os.environ["EMBEDDING_DIM"] == "512"
