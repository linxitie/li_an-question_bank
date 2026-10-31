"""F4 JSON-LD 文档构造测试。"""
from datetime import datetime

import pytest

from app.foundation.document_schema import (
    build_exam_resource,
    build_forum_content,
    build_import_snapshot,
)
from app.models.models import (
    ExamPaper,
    ForumComment,
    ForumPost,
    MaterialImportRecord,
    PaperQuestionRelation,
    QuestionImportRecord,
)


def _paper(db_session) -> ExamPaper:
    paper = ExamPaper(
        paper_name="2026 公安联考模拟卷",
        paper_code="P-2026-001",
        subject_id=1,
        composition_method="MANUAL",
        creator_id=1,
        duration=120,
        total_score=100,
        difficulty=4,
        question_count=2,
        exam_type="SIMULATION",
        paper_type="PUBLISHED",
        publish_target="mock_exam",
        description="测试卷",
        knowledge_range="刑法",
        shuffle_questions=1,
        shuffle_options=0,
        max_attempts=2,
        create_time=datetime(2026, 10, 1, 9, 0),
    )
    db_session.add(paper)
    db_session.flush()
    db_session.add_all([
        PaperQuestionRelation(
            paper_id=paper.paper_id, question_id=11, question_order=1, question_score=2.5
        ),
        PaperQuestionRelation(
            paper_id=paper.paper_id, question_id=12, question_order=2, question_score=3
        ),
    ])
    db_session.commit()
    return paper


def test_build_exam_resource_only_keeps_question_refs(db_session):
    paper = _paper(db_session)

    doc = build_exam_resource(db_session, paper.paper_id, version=7)

    assert doc["@type"] == "ExamPaper"
    assert doc["@id"] == f"urn:li-an:exam_resources:{paper.paper_id}"
    assert doc["version"] == 7
    assert doc["source"] == {"table": "exam_paper", "id": paper.paper_id}
    payload = doc["payload"]
    assert payload["name"] == "2026 公安联考模拟卷"
    assert payload["settings"] == {
        "shuffleQuestions": 1,
        "shuffleOptions": 0,
        "maxAttempts": 2,
    }
    assert payload["questionRefs"] == [
        {"questionId": 11, "score": 2.5},
        {"questionId": 12, "score": 3.0},
    ]
    serialized = str(doc)
    assert "question_content" not in serialized
    assert "options" not in serialized


def test_build_exam_resource_missing_returns_none(db_session):
    assert build_exam_resource(db_session, 999999) is None


def test_build_question_import_snapshot(db_session):
    record = QuestionImportRecord(
        user_id=1,
        original_filename="questions.docx",
        file_type="WORD",
        total_questions=10,
        success_count=9,
        failed_count=1,
        duplicate_count=2,
        import_status="PREVIEW",
        preview_data=[{"content": "题干"}],
        error_messages=["第 3 行格式错误"],
        progress_percent=100,
        current_phase="preview",
        import_time=datetime(2026, 10, 2, 10, 0),
        complete_time=datetime(2026, 10, 2, 10, 5),
    )
    db_session.add(record)
    db_session.commit()

    doc = build_import_snapshot(db_session, "question_import_record", record.import_id)

    assert doc["@id"].endswith(f"question_import_record:{record.import_id}")
    assert doc["payload"]["status"] == "PREVIEW"
    assert doc["payload"]["previewData"] == [{"content": "题干"}]
    assert doc["payload"]["errorMessages"] == ["第 3 行格式错误"]


def test_build_material_import_snapshot_waits_for_terminal_state(db_session):
    record = MaterialImportRecord(
        file_name="material.pdf",
        file_type="pdf",
        file_size=1024,
        parse_mode="async",
        parse_status="processing",
        parse_result='{"pages": [{"image": "_tmp/abc/page1.png"}]}',
        uploader_id=1,
    )
    db_session.add(record)
    db_session.commit()

    # 解析中不投影，避免把只有临时路径的半成品写进文档库。
    assert build_import_snapshot(db_session, "material_import_record", record.import_id) is None

    # 终态仍可能保留 _tmp 键（历史数据），投影时必须剥掉。
    record.parse_status = "success"
    record.parse_result = '{"_tmp": "C:/tmp/upload.pdf", "pages": [{"text": "已转存", "_tmp": "C:/tmp/a.png"}]}'
    db_session.commit()
    doc = build_import_snapshot(db_session, "material_import_record", record.import_id)
    assert doc["payload"]["parseResult"] == {"pages": [{"text": "已转存"}]}


def test_build_import_snapshot_rejects_unknown_source(db_session):
    with pytest.raises(ValueError):
        build_import_snapshot(db_session, "sys_user", 1)


def test_build_forum_content_includes_only_visible_comments(db_session):
    post = ForumPost(
        user_id=1,
        title="备考经验",
        content="正文",
        share_type="EXPERIENCE",
        tags="行测",
        status="NORMAL",
        like_count=3,
        comment_count=1,
        attachments=[{"name": "a.pdf", "url": "/media/a"}],
        create_time=datetime(2026, 10, 3, 9, 0),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add_all([
        ForumComment(post_id=post.post_id, user_id=2, content="可见", status=1),
        ForumComment(post_id=post.post_id, user_id=3, content="已隐藏", status=0),
    ])
    db_session.commit()

    doc = build_forum_content(db_session, post.post_id)

    assert doc["@type"] == "ForumThread"
    assert doc["payload"]["postId"] == post.post_id
    assert doc["payload"]["stats"]["likeCount"] == 3
    assert [row["content"] for row in doc["payload"]["comments"]] == ["可见"]


def test_build_forum_content_keeps_soft_deleted_status(db_session):
    post = ForumPost(
        user_id=1, title="已删", content="正文", status="DELETED",
        create_time=datetime(2026, 10, 3, 9, 0),
    )
    db_session.add(post)
    db_session.commit()

    doc = build_forum_content(db_session, post.post_id)

    assert doc["payload"]["status"] == "DELETED"
    assert doc["payload"]["comments"] == []


def test_build_forum_content_missing_returns_none(db_session):
    assert build_forum_content(db_session, 999999) is None
