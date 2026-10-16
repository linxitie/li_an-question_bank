"""
Obsidian 金句收藏功能测试
覆盖：
1. 数据库金句收藏/取消收藏
2. Obsidian 金句收藏/取消收藏
3. 未登录 401
4. 无效 obsidian_source 400
5. /news-favorites 合并返回 Obsidian 金句
6. /quote/daily 返回 obsidian_id/source_type
7. Obsidian 嵌套目录递归扫描
"""
import os
import tempfile
import pytest
from unittest.mock import patch

from app.models.models import EssayQuote, QuoteFavorite
from app.api.v1.community.quotes import _read_obsidian_quotes
from app.api.v1.personal.collection import _read_obsidian_quote_by_filename


@pytest.fixture
def db_quote(db_session):
    """创建一条数据库金句"""
    quote = EssayQuote(
        content="法者，天下之程式也，万事之仪表也。",
        source="管子",
        category="法治",
        author="管仲",
        status=1
    )
    db_session.add(quote)
    db_session.commit()
    db_session.refresh(quote)
    return quote


class TestDbQuoteFavorite:
    """数据库金句收藏"""

    def test_toggle_on_then_off(self, client, test_user, db_session, db_quote, auth_headers):
        # 收藏
        r = client.post(f"/api/quotes/{db_quote.quote_id}/favorite", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["favorited"] is True

        row = db_session.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == test_user.user_id,
            QuoteFavorite.quote_id == db_quote.quote_id
        ).first()
        assert row is not None

        # 取消收藏
        r = client.post(f"/api/quotes/{db_quote.quote_id}/favorite", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["favorited"] is False

        row = db_session.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == test_user.user_id,
            QuoteFavorite.quote_id == db_quote.quote_id
        ).first()
        assert row is None


class TestObsidianQuoteFavorite:
    """Obsidian 金句收藏"""

    OBSIDIAN_SOURCE = "2026-08-14-金句-050.md"

    def test_favorite_inserts_row_with_obsidian_source(self, client, test_user, db_session, auth_headers):
        r = client.post(f"/api/quotes/obsidian/{self.OBSIDIAN_SOURCE}/favorite", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["favorited"] is True

        row = db_session.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == test_user.user_id,
            QuoteFavorite.obsidian_source == self.OBSIDIAN_SOURCE
        ).first()
        assert row is not None
        assert row.quote_id is None  # Obsidian 金句无数据库 ID
        assert row.obsidian_source == self.OBSIDIAN_SOURCE

    def test_unfavorite_removes_row(self, client, test_user, db_session, auth_headers):
        db_session.add(QuoteFavorite(
            user_id=test_user.user_id,
            quote_id=None,
            obsidian_source=self.OBSIDIAN_SOURCE
        ))
        db_session.commit()

        r = client.post(f"/api/quotes/obsidian/{self.OBSIDIAN_SOURCE}/favorite", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["favorited"] is False

        row = db_session.query(QuoteFavorite).filter(
            QuoteFavorite.user_id == test_user.user_id,
            QuoteFavorite.obsidian_source == self.OBSIDIAN_SOURCE
        ).first()
        assert row is None

    def test_unauthenticated_returns_401(self, client):
        r = client.post(f"/api/quotes/obsidian/{self.OBSIDIAN_SOURCE}/favorite")
        assert r.status_code == 401

    def test_invalid_obsidian_source_returns_400(self, client, auth_headers):
        # 路径分隔符 / 违反正则
        r = client.post("/api/quotes/obsidian/..%2F..%2Fetc%2Fpasswd/favorite", headers=auth_headers)
        assert r.status_code in (400, 405)  # 路由层可能直接拦截
        # 不含斜杠但不符合 .md 后缀
        r = client.post("/api/quotes/obsidian/test.txt/favorite", headers=auth_headers)
        assert r.status_code == 400
        # 含空格
        r = client.post("/api/quotes/obsidian/bad%20name.md/favorite", headers=auth_headers)
        assert r.status_code == 400


class TestMergedFavorites:
    """收藏页合并返回"""

    def test_news_favorites_includes_obsidian_item(self, client, test_user, db_session, db_quote, auth_headers):
        # 数据库金句收藏
        db_session.add(QuoteFavorite(user_id=test_user.user_id, quote_id=db_quote.quote_id))
        # Obsidian 金句收藏
        db_session.add(QuoteFavorite(
            user_id=test_user.user_id,
            quote_id=None,
            obsidian_source="2026-08-14-金句-050.md"
        ))
        db_session.commit()

        with patch("app.api.v1.personal.collection._read_obsidian_quote_by_filename", return_value={
            "content": "忠诚是公安队伍代代相传的政治基因",
            "source": "人民公安报",
            "author": "",
            "topics": ["忠诚"],
        }):
            r = client.get("/api/collection/news-favorites?type=quote", headers=auth_headers)
            assert r.status_code == 200
            data = r.json()
            types = {item["source_type"] for item in data["items"]}
            assert "database" in types
            assert "obsidian" in types

            obs = [i for i in data["items"] if i["source_type"] == "obsidian"][0]
            assert obs["obsidian_source"] == "2026-08-14-金句-050.md"
            assert obs["obsidian_id"] == "obsidian_2026-08-14-金句-050.md"
            assert obs["quote_id"] == 0


class TestDailyQuote:
    """每日金句接口"""

    def test_daily_quote_returns_obsidian_fields(self, client, test_user, auth_headers):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "2026-08-14-金句-050.md"), "w", encoding="utf-8") as f:
            f.write(
                'quote: "忠诚是公安队伍代代相传的政治基因"\n'
                "status: 已审核\n"
                'source: "人民公安报"\n'
                'author: ""\n'
                "applicable_topics:\n"
                "  - 忠诚\n"
            )

        with patch("app.api.v1.community.quotes.OBSIDIAN_QUOTE_DIR", tmpdir):
            r = client.get("/api/quotes/quote/daily", headers=auth_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["source_type"] == "obsidian"
            assert data["obsidian_id"] == "obsidian_2026-08-14-金句-050.md"
            assert data["obsidian_source"] == "2026-08-14-金句-050.md"
            assert data["quote_id"] == 0
            assert data["favorited"] is False

    def test_daily_quote_reflects_favorite_state(self, client, test_user, db_session, auth_headers):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "2026-08-14-金句-050.md"), "w", encoding="utf-8") as f:
            f.write(
                'quote: "忠诚是公安队伍代代相传的政治基因"\n'
                "status: 已审核\n"
                'source: "人民公安报"\n'
                'author: ""\n'
            )
        db_session.add(QuoteFavorite(
            user_id=test_user.user_id,
            quote_id=None,
            obsidian_source="2026-08-14-金句-050.md"
        ))
        db_session.commit()

        with patch("app.api.v1.community.quotes.OBSIDIAN_QUOTE_DIR", tmpdir):
            r = client.get("/api/quotes/quote/daily", headers=auth_headers)
            assert r.status_code == 200
            assert r.json()["favorited"] is True


class TestObsidianRecursiveScan:
    """Obsidian 金句嵌套目录递归扫描"""

    NESTED_CONTENT = (
        'quote: "忠诚是公安队伍代代相传的政治基因"\n'
        "status: 已审核\n"
        'source: "人民公安报"\n'
        'author: ""\n'
    )

    def _create_nested_quote(self, tmp_path):
        """在 tmp_path 下创建 01-政治类/党建引领/test-nested.md"""
        nested_dir = tmp_path / "01-政治类" / "党建引领"
        nested_dir.mkdir(parents=True)
        (nested_dir / "test-nested.md").write_text(self.NESTED_CONTENT, encoding="utf-8")

    def test_read_obsidian_quotes_recursive(self, tmp_path):
        """嵌套子目录中的金句文件应被递归扫描到"""
        self._create_nested_quote(tmp_path)

        with patch("app.api.v1.community.quotes.OBSIDIAN_QUOTE_DIR", str(tmp_path)):
            quotes = _read_obsidian_quotes()

        assert len(quotes) == 1
        assert quotes[0]["filename"] == "test-nested.md"
        assert quotes[0]["content"] == "忠诚是公安队伍代代相传的政治基因"

    def test_obsidian_quote_by_filename_nested(self, tmp_path):
        """仅传文件名（不含路径）应能找到嵌套目录中的金句"""
        self._create_nested_quote(tmp_path)

        with patch("app.api.v1.community.quotes.OBSIDIAN_QUOTE_DIR", str(tmp_path)):
            quote = _read_obsidian_quote_by_filename("test-nested.md")

        assert quote is not None
        assert quote["content"] == "忠诚是公安队伍代代相传的政治基因"

    def test_get_daily_quote_nested(self, client, test_user, auth_headers, tmp_path):
        """嵌套目录中的金句应被每日金句接口选中"""
        self._create_nested_quote(tmp_path)

        with patch("app.api.v1.community.quotes.OBSIDIAN_QUOTE_DIR", str(tmp_path)):
            with patch("app.api.v1.community.quotes.get_random_int", return_value=0):
                r = client.get("/api/quotes/quote/daily", headers=auth_headers)

        assert r.status_code == 200
        assert r.json()["source_type"] == "obsidian"