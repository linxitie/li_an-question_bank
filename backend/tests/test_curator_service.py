"""R1 Curator LLM 适配器测试。"""
from pathlib import Path

from app.models.models import EssayQuote
from app.services.curator_service import _extract_json, review_notes, review_quote_with_llm
from app.services.obsidian_sync import parse_note


def _quote(db, uid="q_curator_test"):
    quote = EssayQuote(
        content="法者，天下之程式也。",
        source="管子",
        author="管子",
        quote_uid=uid,
        quality_score=75.0,
        review_status="pending",
        status=0,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def _note(vault: Path, uid="q_curator_test"):
    board = vault / "00-收件箱" / "审核看板" / "02-重点复核"
    board.mkdir(parents=True)
    path = board / f"{uid}.md"
    path.write_text(
        "---\n"
        f"uid: {uid}\n"
        "type: quote\n"
        "status: needs_human\n"
        "score: 75.0\n"
        "---\n\n"
        "法者，天下之程式也。\n",
        encoding="utf-8",
    )
    return path


def test_extract_json_handles_code_fence():
    data = _extract_json('```json\n{"decision":"approve","confidence":0.9,"reasons":["ok"]}\n```')
    assert data["decision"] == "approve"


def test_review_note_with_fake_llm_does_not_change_status(tmp_path, db_session):
    quote = _quote(db_session)
    path = _note(tmp_path, quote.quote_uid)

    def fake(_prompt: str) -> str:
        return '{"decision":"approve","confidence":0.86,"reasons":["来源明确"]}'

    report = review_notes(db_session, tmp_path, limit=1, apply=True, client=fake)

    assert report["processed"] == 1
    fields, _body = parse_note(path.read_text(encoding="utf-8"))
    assert fields["curator_decision"] == "approve"
    assert fields["curator_confidence"] == "0.86"
    assert fields["status"] == "needs_human"
    db_session.refresh(quote)
    assert quote.review_status == "pending"


def test_invalid_decision_is_error(tmp_path, db_session):
    quote = _quote(db_session, "q_curator_invalid")
    _note(tmp_path, "q_curator_invalid")

    def fake(_prompt: str) -> str:
        return '{"decision":"maybe","confidence":0.5,"reasons":[]}'

    report = review_notes(db_session, tmp_path, limit=1, client=fake)

    assert report["processed"] == 0
    assert report["errors"]


def test_review_quote_with_llm_parses_openai_content(db_session):
    quote = _quote(db_session, "q_curator_parse")
    result = review_quote_with_llm(
        quote,
        client=lambda _p: '{"decision":"reject","confidence":1.5,"reasons":["来源不明"]}',
    )
    assert result.decision == "reject"
    assert result.confidence == 1.0
    assert result.reasons == ["来源不明"]
