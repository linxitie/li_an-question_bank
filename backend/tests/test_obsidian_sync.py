"""R1 Obsidian 审核收件箱回写测试。"""
from app.models.models import EssayQuote
from app.services.obsidian_export import export_all
from app.services.obsidian_sync import sync_review_inbox


def _pending(db, uid):
    quote = EssayQuote(
        content="法者，天下之程式也。",
        source="管子",
        quote_uid=uid,
        review_status="pending",
        status=0,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def test_export_pending_and_approve_from_obsidian(tmp_path, db_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    quote = _pending(db_session, "q_sync_approve")

    export_all(db_session, vault)
    inbox_file = vault / "00-收件箱" / "金句" / "q_sync_approve.md"
    assert inbox_file.is_file()
    assert not (vault / "01-金句" / "q_sync_approve.md").exists()

    text = inbox_file.read_text(encoding="utf-8")
    text = text.replace("status: pending", "status: published")
    text = text.replace('review_note: ""', 'review_note: "来源可核验"')
    inbox_file.write_text(text, encoding="utf-8")

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 1
    assert report["errors"] == []
    db_session.refresh(quote)
    assert quote.review_status == "published"
    assert quote.status == 1
    assert not inbox_file.exists()
    assert list((vault / "07-归档" / "审核记录").glob("q_sync_approve-*.md"))


def test_reject_without_note_is_kept_for_human(tmp_path, db_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    quote = _pending(db_session, "q_sync_reject")
    export_all(db_session, vault)
    inbox_file = vault / "00-收件箱" / "金句" / "q_sync_reject.md"

    text = inbox_file.read_text(encoding="utf-8").replace("status: pending", "status: rejected")
    inbox_file.write_text(text, encoding="utf-8")

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 0
    assert report["errors"]
    db_session.refresh(quote)
    assert quote.review_status == "pending"
    assert inbox_file.exists()


def test_conflict_is_moved_aside(tmp_path, db_session):
    vault = tmp_path / "vault"
    vault.mkdir()
    quote = _pending(db_session, "q_sync_conflict")
    quote.review_status = "published"
    quote.status = 1
    db_session.commit()
    inbox_dir = vault / "00-收件箱" / "金句"
    inbox_dir.mkdir(parents=True)
    (inbox_dir / "q_sync_conflict.md").write_text(
        "---\nuid: q_sync_conflict\nstatus: published\n---\n正文\n",
        encoding="utf-8",
    )

    report = sync_review_inbox(db_session, vault)

    assert report["moved"] == 1
    assert not (inbox_dir / "q_sync_conflict.md").exists()
    assert list((vault / "00-收件箱" / "冲突").glob("q_sync_conflict-*.md"))
