"""R0 Obsidian 导出测试：幂等、路径约束、vault 缺失。"""
import pytest

from app.models.models import EssayQuote, NewsArticle, RecruitmentInfo
from app.services.kg_seed import seed_topics
from app.services.kg_service import create_edge, seed_relation_types
from app.services.obsidian_export import _safe_path, export_all


def _prepare(db, vault):
    seed_relation_types(db)
    seed_topics(db)
    quote = EssayQuote(content="法者，天下之程式也。", source="管子", status=1)
    news = NewsArticle(title="公安要闻", url="https://example.com/n/1", source="cpd", category="理论")
    recruit = RecruitmentInfo(
        title="某省公务员招录",
        category="国考省考",
        url="https://example.com/r/1",
        status=1,
    )
    db.add_all([quote, news, recruit])
    db.commit()
    return quote


def test_export_is_idempotent(tmp_path, db_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    quote = _prepare(db_session, vault)

    first = export_all(db_session, vault)
    assert first["ok"] is True
    assert first["written"] >= 2
    assert (vault / "04-主题地图" / "loyalty-education.md").is_file()
    assert (vault / "01-金句" / f"q_{quote.quote_id:06d}.md").is_file()
    assert (vault / "02-新闻" / "index.md").is_file()
    assert (vault / "03-招考" / "index.md").is_file()
    assert (vault / "99-系统" / "导出清单.json").is_file()

    second = export_all(db_session, vault)
    assert second["written"] == 0
    assert second["skipped"] > 0


def test_missing_vault_returns_error(tmp_path):
    report = export_all(None, tmp_path / "not-exist")
    assert report["ok"] is False
    assert report["error"] == "vault_not_found"


def test_path_cannot_escape_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(ValueError):
        _safe_path(vault, "..", "escape.md")
