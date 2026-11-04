"""R2.1 通用新闻采集器测试。"""
from app.core.news_sources import NewsSourceConfig
from app.models.models import NewsArticle, NewsImage
from app.services import news_collector
from app.services.news_storage import LocalNewsStorage

LIST_HTML = """
<html><body>
<a href="/a/1.html">坚持和发展新时代枫桥经验 推动基层治理现代化</a>
<a href="/a/2.html">公安部部署夏季治安打击整治行动</a>
<a href="/login">登录</a>
</body></html>
"""

ARTICLE_HTML = """
<html><head><title>坚持和发展新时代枫桥经验</title>
<meta property="og:title" content="坚持和发展新时代枫桥经验"></head>
<body><h1>坚持和发展新时代枫桥经验</h1>
<div class="article-content">坚持和发展新时代枫桥经验，是基层社会治理的重要实践。
要依靠群众、服务群众，把矛盾化解在基层，把平安建设落到实处。
要坚持党建引领，把党的政治优势、组织优势转化为治理效能，形成共建共治共享的基层治理格局。</div>
<img src="/img/1.jpg" />
<img src="/template/logo.png" />
</body></html>
"""


def test_parse_article_filters_template_images():
    article = news_collector.parse_article(ARTICLE_HTML, "https://example.com/a/1.html")
    assert article.images == ["https://example.com/img/1.jpg"]


def _source():
    return NewsSourceConfig(
        "beijing", "北京市公安局", "https://example.com", "https://example.com/list",
        category_code="police_news", category="公安要闻", region_code="110000",
    )


def test_collect_source_inserts_and_dedupes(tmp_path, db_session, monkeypatch):
    storage = LocalNewsStorage(tmp_path)
    html = {
        "https://example.com/list": LIST_HTML,
        "https://example.com/a/1.html": ARTICLE_HTML,
    }
    monkeypatch.setattr(
        news_collector, "_download_image",
        lambda url, _storage, timeout=15: "uploads/news_images/fake.jpg",
    )

    first = news_collector.collect_source(
        db_session, _source(), limit=1, dry_run=False,
        fetcher=lambda url: html[url], storage=storage,
    )
    second = news_collector.collect_source(
        db_session, _source(), limit=1, dry_run=False,
        fetcher=lambda url: html[url], storage=storage,
    )

    assert first["inserted"] == 1
    assert first["images"] == 1
    assert second["duplicates"] == 1
    article = db_session.query(NewsArticle).one()
    assert article.review_status == "pending"
    assert article.status == 0
    assert db_session.query(NewsImage).count() == 1


def test_collect_source_dry_run_does_not_write(tmp_path, db_session):
    html = {"https://example.com/list": LIST_HTML, "https://example.com/a/1.html": ARTICLE_HTML}
    report = news_collector.collect_source(
        db_session, _source(), limit=1, dry_run=True,
        fetcher=lambda url: html[url], storage=LocalNewsStorage(tmp_path),
    )

    assert report["inserted"] == 1
    assert db_session.query(NewsArticle).count() == 0
