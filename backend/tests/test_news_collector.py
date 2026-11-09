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
<header><img src="/img/header-logo.png" alt="logo"></header>
<div class="article-content">坚持和发展新时代枫桥经验，是基层社会治理的重要实践。
要依靠群众、服务群众，把矛盾化解在基层，把平安建设落到实处。
要坚持党建引领，把党的政治优势、组织优势转化为治理效能，形成共建共治共享的基层治理格局。
<img src="/img/1.jpg" alt="新闻现场" />
<img src="/img/qrcode.png" alt="二维码" />
<img src="/img/photo.jpg" alt="logo" />
</div>
<div class="sidebar"><img src="/img/sidebar.jpg" alt="相关新闻" /></div>
<img src="/template/logo.png" />
</body></html>
"""


def test_parse_article_filters_only_content_images():
    article = news_collector.parse_article(ARTICLE_HTML, "https://example.com/a/1.html")
    assert article.images == ["https://example.com/img/1.jpg"]


def test_image_size_filter_rejects_icons_and_tiny_squares():
    from io import BytesIO

    from PIL import Image

    def png(width: int, height: int) -> bytes:
        buffer = BytesIO()
        Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
        return buffer.getvalue()

    assert not news_collector._is_acceptable_image(png(80, 80))
    assert not news_collector._is_acceptable_image(png(120, 120))
    assert news_collector._is_acceptable_image(png(320, 180))
    assert news_collector._is_acceptable_image(png(400, 400))


def test_image_url_and_alt_noise_filter():
    assert news_collector._is_noise_image("https://example.com/assets/qrcode.png")
    assert news_collector._is_noise_image(
        "https://example.com/photo.jpg", {"alt": "新华网客户端下载二维码"}
    )
    assert news_collector._is_noise_image("https://example.com/ad/banner.jpg")
    assert not news_collector._is_noise_image("https://example.com/news/road.jpg")


def test_clean_title_strips_feed_metadata():
    raw = "把加强党性修养作为终身课题 2026-11-04 09:10:40 来源：新华网 分享： - 标准 +"
    assert news_collector._clean_title(raw) == "把加强党性修养作为终身课题"


def test_clean_article_text_removes_duplicate_title_and_tail():
    raw = (
        "测试标题\n\n测试标题\n\n第一段完整内容，包含句号。\n\n"
        "第二段完整内容，继续说明。\n\n相关阅读\n\n推荐链接\n\n"
        "版权所有：测试单位\n\n京ICP备000000号"
    )
    assert news_collector.clean_article_text("测试标题", raw) == (
        "第一段完整内容，包含句号。\n\n第二段完整内容，继续说明。"
    )


def _source():
    return NewsSourceConfig(
        "beijing",
        "北京市公安局",
        "https://example.com",
        "https://example.com/list",
        category_code="police_news",
        category="公安要闻",
        region_code="110000",
    )


def test_collect_source_inserts_and_dedupes(tmp_path, db_session, monkeypatch):
    storage = LocalNewsStorage(tmp_path)
    html = {
        "https://example.com/list": LIST_HTML,
        "https://example.com/a/1.html": ARTICLE_HTML,
    }
    monkeypatch.setattr(
        news_collector,
        "_download_image",
        lambda url, _storage, timeout=15: "uploads/news_images/fake.jpg",
    )

    first = news_collector.collect_source(
        db_session,
        _source(),
        limit=1,
        dry_run=False,
        fetcher=lambda url: html[url],
        storage=storage,
    )
    second = news_collector.collect_source(
        db_session,
        _source(),
        limit=1,
        dry_run=False,
        fetcher=lambda url: html[url],
        storage=storage,
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
        db_session,
        _source(),
        limit=1,
        dry_run=True,
        fetcher=lambda url: html[url],
        storage=LocalNewsStorage(tmp_path),
    )

    assert report["inserted"] == 1
    assert db_session.query(NewsArticle).count() == 0


def test_daily_limit_blocks_source_after_five(db_session):
    for index in range(5):
        db_session.add(
            NewsArticle(
                title=f"今日来源文章{index}",
                url=f"https://example.com/{index}",
                source="beijing",
                content="正文" * 50,
                status=0,
                review_status="pending",
            )
        )
    db_session.commit()

    report = news_collector.collect_source(
        db_session,
        _source(),
        limit=5,
        daily_limit=5,
        dry_run=True,
    )

    assert report["daily_used"] == 5
    assert report["daily_remaining"] == 0
    assert report["daily_skipped"] is True
    assert report["inserted"] == 0
