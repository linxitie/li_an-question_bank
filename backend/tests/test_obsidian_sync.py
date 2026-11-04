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


def test_board_can_reject_published_quote(tmp_path, db_session):
    vault = tmp_path / "vault"
    board = vault / "00-收件箱" / "审核看板"
    board.mkdir(parents=True)
    quote = _pending(db_session, "q_board_reject")
    quote.review_status = "published"
    quote.status = 1
    db_session.commit()
    (board / "q_board_reject.md").write_text(
        "---\nuid: q_board_reject\nstatus: rejected\nreview_note: 来源不可信\n---\n正文\n",
        encoding="utf-8",
    )

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 1
    db_session.refresh(quote)
    assert quote.review_status == "rejected"
    assert quote.status == 0
    assert not (board / "q_board_reject.md").exists()
    assert list((vault / "07-归档" / "审核记录").glob("q_board_reject-*.md"))


def test_board_needs_human_is_skipped(tmp_path, db_session):
    vault = tmp_path / "vault"
    board = vault / "00-收件箱" / "审核看板"
    board.mkdir(parents=True)
    _pending(db_session, "q_board_wait")
    (board / "q_board_wait.md").write_text(
        "---\nuid: q_board_wait\nstatus: needs_human\n---\n正文\n",
        encoding="utf-8",
    )

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 0
    assert report["skipped"] == 1
    assert (board / "q_board_wait.md").exists()


def test_board_checkbox_reject_published_quote(tmp_path, db_session):
    vault = tmp_path / "vault"
    board = vault / "00-收件箱" / "审核看板" / "02-重点复核"
    board.mkdir(parents=True)
    quote = _pending(db_session, "q_board_checkbox")
    quote.review_status = "published"
    quote.status = 1
    db_session.commit()
    (board / "q_board_checkbox.md").write_text(
        "---\nuid: q_board_checkbox\nstatus: needs_human\n---\n正文\n\n"
        "- [x] 拒绝\n- [ ] 通过\n- [ ] 退回修改\n\n- 备注：来源不可信\n",
        encoding="utf-8",
    )

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 1
    db_session.refresh(quote)
    assert quote.review_status == "rejected"
    assert quote.status == 0


def test_board_multiple_checkboxes_are_rejected(tmp_path, db_session):
    vault = tmp_path / "vault"
    board = vault / "00-收件箱" / "审核看板" / "02-重点复核"
    board.mkdir(parents=True)
    quote = _pending(db_session, "q_board_multi")
    (board / "q_board_multi.md").write_text(
        "---\nuid: q_board_multi\nstatus: needs_human\n---\n正文\n\n"
        "- [x] 通过\n- [x] 拒绝\n- [ ] 退回修改\n",
        encoding="utf-8",
    )

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 0
    assert report["errors"]
    db_session.refresh(quote)
    assert quote.review_status == "pending"


def test_inbox_draft_projection_is_skipped(tmp_path, db_session):
    vault = tmp_path / "vault"
    inbox = vault / "00-收件箱" / "金句"
    inbox.mkdir(parents=True)
    quote = _pending(db_session, "q_inbox_draft")
    quote.review_status = "draft"
    quote.status = 0
    db_session.commit()
    (inbox / "q_inbox_draft.md").write_text(
        "---\nuid: q_inbox_draft\nstatus: draft\n---\n正文\n",
        encoding="utf-8",
    )

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 0
    assert report["skipped"] == 1
    assert (inbox / "q_inbox_draft.md").exists()


def test_note_without_uid_is_skipped(tmp_path, db_session):
    vault = tmp_path / "vault"
    board = vault / "00-收件箱" / "审核看板" / "抽样校准"
    board.mkdir(parents=True)
    (board / "抽样审核包.md").write_text(
        "# 抽样包\n\n- [x] 通过\n- [x] 拒绝\n",
        encoding="utf-8",
    )

    report = sync_review_inbox(db_session, vault)

    assert report["processed"] == 0
    assert report["errors"] == []
    assert report["skipped"] == 1
