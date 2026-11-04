"""R2.3 新闻审核状态机与 Obsidian 回写测试。"""
from pathlib import Path

from app.models.models import NewsArticle, NewsReview
from app.services.news_obsidian_sync import sync_news_review
from app.services.news_review_service import NewsReviewError, review_news


def _news(db, status="pending"):
    news = NewsArticle(
        title="新闻审核测试", url="https://example.com/n/1", source="mps",
        category="公安要闻", category_code="police_news", content="正文" * 20,
        status=0, review_status=status,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


def test_review_publish_and_reject_requires_reason(db_session):
    news = _news(db_session)

    published, log = review_news(db_session, news_id=news.news_id, action="publish")
    assert published.review_status == "published"
    assert published.status == 1
    assert log.to_status == "published"
    assert db_session.query(NewsReview).count() == 1

    try:
        review_news(db_session, news_id=news.news_id, action="reject", reason="")
    except NewsReviewError:
        pass
    else:
        raise AssertionError("reject without reason should fail")


def test_obsidian_news_checkbox_sync(tmp_path, db_session):
    news = _news(db_session)
    card = tmp_path / "00-收件箱" / "新闻" / "2026-11-01" / "news_000001.md"
    card.parent.mkdir(parents=True)
    card.write_text(
        "---\nnews_id: %s\nstatus: pending\n---\n\n"
        "- [x] 通过\n- [ ] 拒绝\n- [ ] 退回修改\n\n- 备注：人工确认\n"
        % news.news_id,
        encoding="utf-8",
    )

    report = sync_news_review(db_session, tmp_path)

    assert report["processed"] == 1
    db_session.refresh(news)
    assert news.review_status == "published"
    assert not card.exists()
    assert list((tmp_path / "07-归档" / "新闻审核").glob("*.md"))
