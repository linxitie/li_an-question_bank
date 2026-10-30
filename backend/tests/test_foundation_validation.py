"""F2 Step 6：写入守卫 6 类规则与端点 422 行为。"""
import pytest
from fastapi import HTTPException

from app.foundation.validation import (
    ReferenceCache, ValidationIssue, ensure_valid, validate_question,
)
from app.models.models import QuestionBank


def _refs() -> ReferenceCache:
    return ReferenceCache(
        subject_ids={1}, type_ids={1}, point_ids={10}, group_ids={20},
        type_names={1: '单选题'}, _loaded=True,
    )


def _valid(**overrides):
    data = {
        'subject_id': 1, 'type_id': 1, 'point_id': 10, 'group_id': 0,
        'question_content': '下列哪项是正确的？',
        'options': [{'key': 'A', 'value': '甲'}, {'key': 'B', 'value': '乙'}],
        'answer': 'A', 'answer_analysis': '解析', 'difficulty': 3,
        'score': 1.0, 'status': 1, 'audit_status': 1, 'tags': '',
    }
    data.update(overrides)
    return data


def _rules(data):
    return {i.rule for i in validate_question(data, _refs()) if i.severity == 'error'}


def test_valid_payload_has_no_error():
    assert _rules(_valid()) == set()


def test_long_content_rejected_short_passes():
    assert 'R-LONG' in _rules(_valid(question_content='字' * 50_001))
    assert _rules(_valid(question_content='字' * 50_000)) == set()


def test_empty_content_rejected():
    assert 'R-EMPTY' in _rules(_valid(question_content='   '))


def test_objective_without_options_rejected():
    assert 'R-EMPTY' in _rules(_valid(options=[]))


def test_enum_out_of_range_rejected():
    assert 'R-ENUM' in _rules(_valid(difficulty=9))
    assert 'R-ENUM' in _rules(_valid(status=7))
    assert 'R-ENUM' in _rules(_valid(score=-1))


def test_bad_json_rejected_good_json_passes():
    assert 'R-JSON' in _rules(_valid(options='["A",'))
    assert _rules(_valid(options='[{"key":"A","value":"甲"}]')) == set()


def test_fk_missing_rejected():
    assert 'R-FK' in _rules(_valid(subject_id=999))
    assert 'R-FK' in _rules(_valid(group_id=999))


def test_encoding_control_chars_rejected():
    assert 'R-ENCODING' in _rules(_valid(question_content='题目\x00注入'))
    assert 'R-ENCODING' in _rules(_valid(answer='\ud800'))


def test_replacement_char_only_warns():
    issues = validate_question(_valid(question_content='题目\ufffd'), _refs())
    assert [i for i in issues if i.severity == 'error'] == []
    assert any(i.severity == 'warning' for i in issues)


def test_partial_update_skips_missing_fields():
    assert _rules_partial({'answer': 'B'}) == set()
    assert 'R-ENUM' in _rules_partial({'difficulty': 0})


def _rules_partial(data):
    return {i.rule for i in validate_question(data, _refs(), partial=True, require_ids=False)
            if i.severity == 'error'}


def test_ensure_valid_raises_422_detail():
    with pytest.raises(HTTPException) as exc:
        ensure_valid(_valid(difficulty=9), None, cache=_refs())
    assert exc.value.status_code == 422
    assert isinstance(exc.value.detail, list)
    assert exc.value.detail[0]['field'] == 'difficulty'
    assert exc.value.detail[0]['rule'] == 'R-ENUM'


def test_switch_disables_validation(monkeypatch):
    monkeypatch.setenv('FOUNDATION_VALIDATION_ENABLED', 'false')
    assert ensure_valid(_valid(difficulty=9), None, cache=_refs()) == []


def test_create_endpoint_rejects_bad_payload_without_write(
        client, db_session, admin_headers, test_subject, test_question_type):
    before = db_session.query(QuestionBank).count()
    resp = client.post('/api/questions/', headers=admin_headers, json={
        'subject_id': test_subject.subject_id,
        'type_id': test_question_type.type_id,
        'question_content': '超长' * 30_000,
        'options': [{'key': 'A', 'value': '甲'}],
        'answer': 'A',
        'difficulty': 3,
        'score': 1.0,
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()['detail']
    assert any(d.get('rule') == 'R-LONG' for d in detail)
    assert db_session.query(QuestionBank).count() == before
