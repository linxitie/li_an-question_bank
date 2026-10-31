"""R1 Scout 决策落库与审核看板导出测试。"""
from pathlib import Path

from app.models.models import EssayQuote, QuoteReview
from app.services.review_board_export import export_review_board
from app.services.scout_apply_service import apply_scout_decisions


def _quote(db, uid, score, review_status="pending", status=0):
    quote = EssayQuote(
        content="法者，天下之程式也。",
        quote_uid=uid,
        quality_score=score,
        review_status=review_status,
        status=status,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def test_apply_scout_decisions(db_session):
    high = _quote(db_session, "q_apply_high", 90, "pending", 0)
    middle = _quote(db_session, "q_apply_mid", 70, "pending", 0)
    low = _quote(db_session, "q_apply_low", 50, "published", 1)

    report = apply_scout_decisions(db_session)

    assert report["approved"] == 1
    assert report["rejected"] == 1
    db_session.refresh(high)
    db_session.refresh(middle)
    db_session.refresh(low)
    assert high.review_status == "published" and high.status == 1
    assert middle.review_status == "pending" and middle.status == 0
    assert low.review_status == "rejected" and low.status == 0
    assert db_session.query(QuoteReview).count() == 2


def test_review_board_contains_middle_and_pending(tmp_path, db_session):
    _quote(db_session, "q_board_high", 90, "published", 1)
    _quote(db_session, "q_board_mid", 70, "published", 1)
    _quote(db_session, "q_board_low", 50, "rejected", 0)
    _quote(db_session, "q_board_pending", 75, "pending", 0)
    vault = tmp_path / "vault"
    vault.mkdir()

    report = export_review_board(db_session, vault)

    assert report["candidates"] == 2
    board = Path(report["board"])
    assert (board / "index.md").is_file()
    assert (board / "02-重点复核" / "q_board_mid.md").is_file()
    assert (board / "02-重点复核" / "q_board_pending.md").is_file()
    assert "q_board_high" not in (board / "index.md").read_text(encoding="utf-8")


def test_review_board_splits_into_three_buckets(tmp_path, db_session):
    _quote(db_session, "q_bucket_high", 82, "published", 1)
    _quote(db_session, "q_bucket_mid", 72, "published", 1)
    _quote(db_session, "q_bucket_low", 62, "pending", 0)
    vault = tmp_path / "vault"
    vault.mkdir()

    report = export_review_board(db_session, vault)

    assert report["buckets"] == {
        "01-优先通过": 1,
        "02-重点复核": 1,
        "03-建议拒绝": 1,
    }
    board = Path(report["board"])
    assert (board / "01-优先通过" / "q_bucket_high.md").is_file()
    assert (board / "02-重点复核" / "q_bucket_mid.md").is_file()
    assert (board / "03-建议拒绝" / "q_bucket_low.md").is_file()
