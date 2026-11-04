# -*- coding: utf-8 -*-
"""P3：图片 OCR 只做原位替换，不能改变前后文字与其它字段。"""
import json

from app.models.models import QuestionBank, QuestionGroup
from app.services.ocr_pipeline import (
    apply_group_decisions,
    apply_question_decisions,
    group_candidates,
    question_candidates,
)

PNG = ("data:image/png;base64,"
       "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")


def _make_question(db_session, subject, qtype, user):
    question = QuestionBank(
        subject_id=subject.subject_id,
        type_id=qtype.type_id,
        question_content=f'<p>替换前<img src="{PNG}">替换后</p>',
        options=json.dumps([
            {"key": "A", "value": f'<span>选项图<img src="{PNG}"></span>'},
            {"key": "B", "value": "纯文字"},
        ], ensure_ascii=False),
        answer="A",
        answer_analysis=f'<p>解析前<img src="{PNG}">解析后</p>',
        difficulty=1,
        score=2,
        creator_id=user.user_id,
        status=1,
        audit_status=1,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def test_candidates_cover_stem_option_analysis(db_session, test_subject, test_question_type, test_user):
    question = _make_question(db_session, test_subject, test_question_type, test_user)
    items = question_candidates(db_session, question, run_ocr=False)
    assert [item.location for item in items] == ["stem", "option:0", "analysis"]
    assert all(item.status == "resolved" for item in items)


def test_apply_only_selected_image_keeps_position(db_session, test_subject, test_question_type, test_user):
    question = _make_question(db_session, test_subject, test_question_type, test_user)
    report = apply_question_decisions(db_session, question, [
        {"location": "stem", "index": 0, "text": "增长 5%", "replace": True},
    ])
    db_session.refresh(question)
    assert report.replaced == 1
    assert question.question_content.startswith("<p>替换前")
    assert "增长 5%" in question.question_content
    assert "替换后" in question.question_content
    assert "<img" not in question.question_content
    # 选项和解析未被误改
    assert "<img" in question.answer_analysis
    assert "<img" in question.options


def test_group_apply_replaces_material_image(db_session):
    group = QuestionGroup(
        group_type="material",
        shared_content=f'<p>材料一<img src="{PNG}">后文</p>',
        title="测试材料",
        subject="申论",
    )
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    assert len(group_candidates(db_session, group, run_ocr=False)) == 1
    report = apply_group_decisions(db_session, group, [
        {"location": "group_content", "index": 0, "text": "材料文字", "replace": True},
    ])
    db_session.refresh(group)
    assert report.replaced == 1
    assert "材料文字" in group.shared_content
    assert "后文" in group.shared_content
