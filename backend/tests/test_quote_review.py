"""R1 金句审核状态机 API 测试。"""
from app.models.models import EssayQuote, QuoteReview


def _pending_quote(db, uid="q_r1_test"):
    quote = EssayQuote(
        content="法者，天下之程式也。",
        source="管子",
        category="法治",
        quote_uid=uid,
        review_status="pending",
        status=0,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def test_approve_publishes_and_logs(client, db_session, test_admin, admin_headers):
    quote = _pending_quote(db_session)

    response = client.post(
        f"/api/admin/quotes/{quote.quote_uid}/review",
        json={"action": "approve", "reason": "来源可核验"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    db_session.refresh(quote)
    assert quote.review_status == "published"
    assert quote.status == 1
    log = db_session.query(QuoteReview).filter(QuoteReview.quote_id == quote.quote_id).one()
    assert log.action == "approve"
    assert log.reviewer_id == test_admin.user_id


def test_reject_requires_reason(client, db_session, admin_headers):
    quote = _pending_quote(db_session, uid="q_r1_reject")

    empty = client.post(
        f"/api/admin/quotes/{quote.quote_uid}/review",
        json={"action": "reject", "reason": ""},
        headers=admin_headers,
    )
    assert empty.status_code == 400

    rejected = client.post(
        f"/api/admin/quotes/{quote.quote_uid}/review",
        json={"action": "reject", "reason": "来源不可信"},
        headers=admin_headers,
    )
    assert rejected.status_code == 200
    db_session.refresh(quote)
    assert quote.review_status == "rejected"
    assert quote.status == 0


def test_request_changes_returns_to_draft(client, db_session, admin_headers):
    quote = _pending_quote(db_session, uid="q_r1_changes")

    response = client.post(
        f"/api/admin/quotes/{quote.quote_uid}/review",
        json={"action": "request_changes", "reason": "补来源"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    db_session.refresh(quote)
    assert quote.review_status == "draft"
    assert quote.status == 0


def test_invalid_transition_is_rejected(client, db_session, admin_headers):
    quote = _pending_quote(db_session, uid="q_r1_invalid")
    quote.review_status = "published"
    quote.status = 1
    db_session.commit()

    response = client.post(
        f"/api/admin/quotes/{quote.quote_id}/review",
        json={"action": "approve", "reason": ""},
        headers=admin_headers,
    )

    assert response.status_code == 400


def test_non_admin_forbidden_and_anonymous_unauthorized(client, db_session, auth_headers):
    quote = _pending_quote(db_session, uid="q_r1_auth")
    url = f"/api/admin/quotes/{quote.quote_uid}/review"

    assert client.post(url, json={"action": "approve", "reason": ""}).status_code == 401
    assert client.post(
        url,
        json={"action": "approve", "reason": ""},
        headers=auth_headers,
    ).status_code == 403


def test_candidates_lists_pending(client, db_session, admin_headers):
    _pending_quote(db_session, uid="q_r1_pending_a")
    _pending_quote(db_session, uid="q_r1_pending_b")

    response = client.get("/api/admin/quotes/candidates", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2
