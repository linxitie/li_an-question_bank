"""R1 每日金句预生成测试。"""
from datetime import date, timedelta

from app.models.models import DailyQuote, EssayQuote
from app.services.daily_quote_service import get_or_create_daily


def _quote(db, uid, content, status=1):
    quote = EssayQuote(content=content, quote_uid=uid, status=status, review_status="published")
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def test_daily_is_stable_and_persisted(db_session):
    quote = _quote(db_session, "q_daily_stable", "法者，天下之程式也。")

    first = get_or_create_daily(db_session)
    second = get_or_create_daily(db_session)

    assert first is not None and second is not None
    assert first[0].quote_date == second[0].quote_date
    assert first[1].quote_id == second[1].quote_id == quote.quote_id
    assert db_session.query(DailyQuote).count() == 1


def test_recent_quote_is_excluded(db_session):
    first = _quote(db_session, "q_daily_old", "法者，天下之程式也。")
    second = _quote(db_session, "q_daily_new", "天行健，君子以自强不息。")
    db_session.add(
        DailyQuote(
            quote_date=(date.today() - timedelta(days=1)).isoformat(),
            quote_id=first.quote_id,
        )
    )
    db_session.commit()

    result = get_or_create_daily(db_session)

    assert result is not None
    assert result[1].quote_id == second.quote_id


def test_falls_back_when_all_candidates_used(db_session):
    quote = _quote(db_session, "q_daily_only", "法者，天下之程式也。")
    db_session.add(
        DailyQuote(
            quote_date=(date.today() - timedelta(days=1)).isoformat(),
            quote_id=quote.quote_id,
        )
    )
    db_session.commit()

    result = get_or_create_daily(db_session)

    assert result is not None
    assert result[1].quote_id == quote.quote_id
    assert result[0].fallback_used == 1


def test_daily_api_returns_database_quote(client, db_session):
    quote = _quote(db_session, "q_daily_api", "法者，天下之程式也。")

    first = client.get("/api/quotes/quote/daily")
    second = client.get("/api/quotes/quote/daily")

    assert first.status_code == 200
    assert first.json()["source_type"] == "database"
    assert first.json()["quote_id"] == quote.quote_id
    assert second.json()["quote_id"] == first.json()["quote_id"]
