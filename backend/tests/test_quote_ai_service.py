from app.models.models import EssayQuote, QuoteReview
from app.services.quote_ai_service import review_quotes


def test_quote_ai_review_isolates_low_quality(db_session):
    low = EssayQuote(content="没有出处的完整句子", source=None, author=None, status=1)
    good = EssayQuote(
        content="法者，天下之程式也，万事之仪表也。", source="管子", author="管仲", status=1
    )
    db_session.add_all([low, good])
    db_session.commit()

    def fake_client(prompt: str) -> str:
        assert "法者" in prompt
        return '{"quality":"approved","score":92,"reason":"经典出处明确，表达完整"}'

    report = review_quotes(db_session, limit=10, apply=True, client=fake_client)
    db_session.refresh(low)
    db_session.refresh(good)

    assert report["total"] == 2
    assert report["rejected"] == 1
    assert report["approved"] == 1
    assert low.status == 0
    assert low.review_status == "rejected"
    assert low.ai_quality_reason == "缺少作者与出处"
    assert good.status == 1
    assert good.review_status == "published"
    assert good.quality_score == 92.0
    assert db_session.query(QuoteReview).count() == 2
