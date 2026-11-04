"""R0 回填 CLI 测试：dry-run 不写库、apply 幂等、覆盖率。"""
from app.models.models import ContentSource, EssayQuote, KgEdge, NewsArticle, RecruitmentInfo, Topic
from scripts.content_hub.backfill_kg import QUOTE_CATEGORY_TO_TOPIC, backfill


def test_legacy_quote_category_alias():
    assert QUOTE_CATEGORY_TO_TOPIC["民心"] == "民生保障"


def _seed_content(db):
    db.add_all(
        [
            EssayQuote(content="天行健，君子以自强不息。", category="哲理", status=1),
            EssayQuote(content="法者，天下之程式也。", category="法治", status=1),
            NewsArticle(
                title="公安要闻一则",
                url="https://example.com/news/1",
                source="cpd",
                category="理论",
            ),
            RecruitmentInfo(
                title="某省 2026 年公务员招录",
                category="国考省考",
                url="https://example.com/recruit/1",
                status=1,
            ),
        ]
    )
    db.commit()


def test_backfill_dry_run_does_not_write(db_session):
    _seed_content(db_session)
    before = (
        db_session.query(KgEdge).count(),
        db_session.query(ContentSource).count(),
        db_session.query(Topic).count(),
    )

    report = backfill(db_session, apply=False)

    assert report["edges_created"] == 0
    assert report["sources_created"] == 0
    assert report["coverage"] == {"quote": 1.0, "news": 1.0, "recruitment": 1.0}
    after = (
        db_session.query(KgEdge).count(),
        db_session.query(ContentSource).count(),
        db_session.query(Topic).count(),
    )
    assert before == after


def test_backfill_apply_is_idempotent(db_session):
    _seed_content(db_session)

    report = backfill(db_session, apply=True)

    assert report["quotes"] == {"total": 2, "linked": 2, "skipped": 0}
    assert report["news"] == {"total": 1, "linked": 1, "skipped": 0}
    assert report["recruitment"] == {"total": 1, "linked": 1, "skipped": 0}
    assert report["edges_created"] == 8
    assert report["sources_created"] == 4
    assert db_session.query(KgEdge).count() == 8
    assert db_session.query(ContentSource).count() == 4

    db_session.expire_all()
    quote = db_session.query(EssayQuote).filter(EssayQuote.category == "法治").one()
    assert quote.quote_uid
    assert quote.normalized_hash
    assert quote.source_id is not None

    again = backfill(db_session, apply=True)
    assert again["edges_created"] == 0
    assert again["sources_created"] == 0
