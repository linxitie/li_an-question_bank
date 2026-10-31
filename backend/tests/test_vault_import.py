"""R1 原始 vault 导入测试。"""
from pathlib import Path

from app.models.models import ContentSource, EssayQuote, KgEdge, Topic
from app.services.vault_import_service import import_vault


def _write(path: Path, quote: str, status: str, topic: str = "政治建设"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "type: 金句\n"
        "date: 2026-08-15\n"
        f'quote: "{quote}"\n'
        "source: 权威官方文件\n"
        'author: ""\n'
        "applicable_topics:\n"
        f"  - {topic}\n"
        "status: " + status + "\n"
        "---\n",
        encoding="utf-8-sig",
    )


def _vault(tmp_path: Path) -> Path:
    library = tmp_path / "vault" / "01-金句素材库" / "01-政治类"
    _write(library / "20260815-0001.md", "以政治建设铸魂，以思想建设立根。", "已审核")
    _write(library / "20260815-0002.md", "责任链条拧得紧，学习教育抓得实。", "已审核")
    _write(library / "20260815-0003.md", "待审金句内容，长度足够用于导入测试。", "待审核")
    _write(library / "20260815-0004.md", "已拒绝的内容不应入库。", "已拒绝")
    return tmp_path / "vault"


def test_import_inserts_approved_and_pending_skips_rejected(tmp_path, db_session):
    report = import_vault(db_session, _vault(tmp_path), limit=None, apply=True)

    assert report["inserted"] == 3
    assert report["skipped_status"] == 1
    assert db_session.query(EssayQuote).count() == 3
    pending = db_session.query(EssayQuote).filter(EssayQuote.quote_uid == "20260815-0003").one()
    assert pending.review_status == "pending"
    assert pending.status == 0
    assert db_session.query(ContentSource).count() == 3
    assert db_session.query(KgEdge).count() == 6
    assert db_session.query(Topic).filter(Topic.name == "政治建设").count() == 1


def test_import_is_idempotent(tmp_path, db_session):
    vault = _vault(tmp_path)

    first = import_vault(db_session, vault, limit=None, apply=True)
    second = import_vault(db_session, vault, limit=None, apply=True)

    assert first["inserted"] == 3
    assert second["inserted"] == 0
    assert second["updated"] == 3
    assert second["sources_created"] == 0
    assert second["edges_created"] == 0
    assert second["duplicates"] == 0


def test_dry_run_does_not_write(tmp_path, db_session):
    report = import_vault(db_session, _vault(tmp_path), limit=None, apply=False)

    assert report["inserted"] == 0
    assert report["apply"] is False
    assert db_session.query(EssayQuote).count() == 0
    assert all(item["action"].startswith("would_") for item in report["items"])


def test_colliding_filenames_get_unique_uids(tmp_path, db_session):
    root = tmp_path / "vault" / "01-金句素材库" / "01-政治类"
    _write(root / "subA" / "20260815-0001.md", "同文件名金句甲，内容长度足够用于测试。", "已审核")
    _write(root / "subB" / "20260815-0001.md", "同文件名金句乙，内容长度足够用于测试。", "已审核")

    report = import_vault(db_session, tmp_path / "vault", limit=None, apply=True)

    assert report["inserted"] == 2
    rows = db_session.query(EssayQuote).all()
    assert len({row.quote_uid for row in rows}) == 2
    assert {row.content for row in rows} == {
        "同文件名金句甲，内容长度足够用于测试。",
        "同文件名金句乙，内容长度足够用于测试。",
    }
