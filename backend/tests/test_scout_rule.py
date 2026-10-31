"""R1 Scout 规则打分测试。"""
from app.models.models import ContentSource, EssayQuote, Topic
from app.services.kg_seed import seed_topics
from app.services.kg_service import create_edge, seed_relation_types
from app.services.scout_rule_service import score_quote, scout_quotes


def _quote(db, content, uid, *, author="", source="", trust=40, topic=False,
           review_status="pending", status=0, normalized_hash=None):
    quote = EssayQuote(
        content=content,
        author=author,
        source=source,
        quote_uid=uid,
        review_status=review_status,
        status=status,
        normalized_hash=normalized_hash,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)

    source_row = ContentSource(
        content_type="quote",
        content_id=quote.quote_id,
        source_type="manual",
        url="",
        publisher=source,
        trust_level=trust,
    )
    db.add(source_row)
    db.commit()
    quote.source_id = source_row.source_id
    db.commit()

    if topic:
        seed_relation_types(db)
        seed_topics(db)
        topic_row = db.query(Topic).filter(Topic.slug == "rule-of-law-thinking").one()
        create_edge(
            db,
            src_type="quote",
            src_id=quote.quote_id,
            dst_type="topic",
            dst_id=topic_row.topic_id,
            relation="has_topic",
        )
        db.commit()
    return quote


def test_good_quote_is_auto_approve_candidate(db_session):
    quote = _quote(
        db_session,
        "法者，天下之程式也，万事之仪表也。",
        "q_scout_good",
        author="管子",
        source="管子",
        trust=90,
        topic=True,
    )

    result = score_quote(db_session, quote)

    assert result.score >= 85
    assert result.decision == "auto_approve_candidate"


def test_weak_quote_is_rejected(db_session):
    quote = _quote(db_session, "太短", "q_scout_weak", trust=20)

    result = score_quote(db_session, quote)

    assert result.score < 60
    assert result.decision == "reject_candidate"
    assert "too_short" in result.reasons


def test_sensitive_and_placeholder_are_hard_risks(db_session):
    sensitive = _quote(
        db_session,
        "这是一段包含赌博内容的测试金句，长度足够用于评分。",
        "q_scout_sensitive",
        author="某人",
        source="某处",
        trust=90,
        topic=True,
    )
    placeholder = _quote(
        db_session,
        "这句话是示例文本，长度足够但是占位内容。",
        "q_scout_placeholder",
        author="某人",
        source="某处",
        trust=90,
        topic=True,
    )

    sensitive_result = score_quote(db_session, sensitive)
    placeholder_result = score_quote(db_session, placeholder)

    assert sensitive_result.decision == "reject_candidate"
    assert "sensitive" in sensitive_result.reasons
    assert sensitive_result.score <= 20
    assert "placeholder" in placeholder_result.reasons


def test_duplicate_is_penalized(db_session):
    first = _quote(
        db_session,
        "法者，天下之程式也，万事之仪表也。",
        "q_scout_dup1",
        author="管子",
        source="管子",
        trust=90,
        topic=True,
        normalized_hash="hash-dup",
    )
    second = _quote(
        db_session,
        "法者，天下之程式也，万事之仪表也。",
        "q_scout_dup2",
        author="管子",
        source="管子",
        trust=90,
        topic=True,
        normalized_hash="hash-dup",
    )

    first_result = score_quote(db_session, first)
    second_result = score_quote(db_session, second)

    assert first_result.score == second_result.score <= 90
    assert "duplicate" in first_result.reasons
    assert "duplicate" in second_result.reasons


def test_apply_writes_score_without_changing_review_state(db_session):
    quote = _quote(db_session, "法者，天下之程式也。", "q_scout_apply", trust=90, topic=True)

    report = scout_quotes(db_session, include_all=False, apply=True)

    assert report["apply"] is True
    db_session.refresh(quote)
    assert quote.quality_score is not None
    assert quote.review_status == "pending"
    assert quote.status == 0


def test_default_scope_only_pending_and_draft(db_session):
    _quote(db_session, "法者，天下之程式也。", "q_scout_pending", trust=90, topic=True)
    _quote(
        db_session,
        "天行健，君子以自强不息。",
        "q_scout_published",
        trust=90,
        topic=True,
        review_status="published",
        status=1,
    )

    report = scout_quotes(db_session, include_all=False)

    assert report["total"] == 1
    assert report["items"][0]["quote_uid"] == "q_scout_pending"
