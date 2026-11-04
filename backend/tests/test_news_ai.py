"""R2.2 新闻 AI 处理与 Obsidian 导出测试。"""
from app.models.models import NewsArticle
from app.services.news_ai_service import process_news
from app.services.news_obsidian_export import export_news_board


def _news(db, title="公安新闻", content="这是一篇用于测试的公安新闻正文。" * 5, status="pending"):
    news = NewsArticle(
        title=title,
        url="https://example.com/news/1",
        source="mps",
        category="公安要闻",
        category_code="police_news",
        summary="摘要",
        content=content,
        status=0,
        review_status=status,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


def test_ai_process_with_fake_client(db_session):
    news = _news(db_session)

    def fake(_prompt):
        return (
            '{"summary":"公安新闻摘要","exam_points":["坚持和发展新时代枫桥经验"],'
            '"official_phrases":["坚持和发展新时代枫桥经验"],'
            '"entities":[{"type":"organization","name":"公安部"}],'
            '"risk_flags":[],"confidence":0.9}'
        )

    report = process_news(db_session, limit=5, client=fake)

    db_session.refresh(news)
    assert report["processed"] == 1
    assert news.ai_summary == "公安新闻摘要"
    assert "枫桥经验" in news.ai_exam_points
    assert news.ai_status == "ok"
    assert news.review_status == "pending"


def test_ai_rule_blocks_high_risk(db_session):
    news = _news(db_session, title="测试暴恐内容")
    report = process_news(
        db_session,
        limit=5,
        client=lambda _p: '{"summary":"测试","exam_points":[],"entities":[],"risk_flags":[],"confidence":0.8}',
    )
    db_session.refresh(news)
    assert report["high_risk"] == 1
    assert news.review_status == "high_risk"
    assert "暴恐" in news.ai_risk_flags


def test_export_news_board(tmp_path, db_session):
    news = _news(db_session)
    process_news(
        db_session,
        limit=5,
        client=lambda _p: '{"summary":"摘要","exam_points":["考点"],"entities":[],"risk_flags":[],"confidence":0.9}',
    )
    vault = tmp_path / "vault"
    vault.mkdir()

    report = export_news_board(db_session, vault)

    assert report["written"] == 1
    assert (vault / "00-收件箱" / "新闻" / "时效性看板.md").is_file()
    assert any((vault / "00-收件箱" / "新闻").rglob("news_*.md"))
