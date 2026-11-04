"""F4 JSON-LD 文档构造：只从 SoT 读取，不写任何表。

三个集合的字段是投影契约；新增字段只增不删。题目正文/选项不进入
exam_resources，避免把文档库变成第二事实源。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

CONTEXT = {"@vocab": "https://li-an.local/schema/"}
_SENSITIVE_KEYS = {"password", "password_hash", "token", "access_token", "jwt"}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _envelope(collection: str, key: str, doc_type: str, payload: dict[str, Any],
              *, source_table: str, source_id: Any, version: int,
              updated_at: str | None) -> dict[str, Any]:
    doc = {
        "@context": CONTEXT,
        "@id": f"urn:li-an:{collection}:{key}",
        "@type": doc_type,
        "version": int(version),
        "updatedAt": updated_at,
        "source": {"table": source_table, "id": source_id},
        "payload": payload,
    }
    assert_no_sensitive_fields(doc)
    return doc


def assert_no_sensitive_fields(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                raise ValueError(f"文档含敏感字段: {path}.{key}")
            assert_no_sensitive_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_sensitive_fields(item, f"{path}[{index}]")


def build_exam_resource(
    session: Session, paper_id: int, *, version: int = 1
) -> dict[str, Any] | None:
    from app.models.models import ExamPaper, PaperQuestionRelation

    paper = session.get(ExamPaper, int(paper_id))
    if paper is None:
        return None
    relations = (
        session.query(PaperQuestionRelation)
        .filter(PaperQuestionRelation.paper_id == paper.paper_id)
        .order_by(PaperQuestionRelation.question_order)
        .all()
    )
    question_refs = [
        {
            "questionId": int(row.question_id),
            "score": float(row.question_score or 0),
        }
        for row in relations
    ]
    payload = {
        "paperId": int(paper.paper_id),
        "name": paper.paper_name,
        "code": paper.paper_code,
        "subjectId": int(paper.subject_id) if paper.subject_id is not None else None,
        "compositionMethod": paper.composition_method,
        "duration": int(paper.duration or 0),
        "totalScore": float(paper.total_score or 0),
        "difficulty": int(paper.difficulty or 0),
        "questionCount": int(paper.question_count or len(question_refs)),
        "examType": paper.exam_type,
        "paperType": paper.paper_type,
        "publishTarget": paper.publish_target,
        "description": paper.description,
        "knowledgeRange": paper.knowledge_range,
        "settings": {
            "shuffleQuestions": int(paper.shuffle_questions or 0),
            "shuffleOptions": int(paper.shuffle_options or 0),
            "maxAttempts": int(paper.max_attempts or 1),
        },
        "questionRefs": question_refs,
    }
    return _envelope(
        "exam_resources",
        str(paper.paper_id),
        "ExamPaper",
        payload,
        source_table="exam_paper",
        source_id=int(paper.paper_id),
        version=version,
        updated_at=_iso(paper.update_time or paper.create_time),
    )


def build_import_snapshot(
    session: Session, source_table: str, import_id: int, *, version: int = 1
) -> dict[str, Any] | None:
    if source_table == "question_import_record":
        # 历史库存在枚举外的 PARTIAL（6 行），ORM 读取会直接抛 LookupError。
        # 投影只读快照，用 text() 读取原始值，避免一个遗留状态拖垮整批回填。
        from sqlalchemy import text

        row = session.execute(
            text(
                """SELECT import_id, import_status, original_filename, file_type,
                          total_questions, success_count, failed_count, duplicate_count,
                          preview_data, error_messages, import_time, complete_time,
                          progress_percent, current_phase
                   FROM question_import_record WHERE import_id=:import_id"""
            ),
            {"import_id": int(import_id)},
        ).first()
        if row is None:
            return None
        record = row._mapping
        payload = {
            "sourceTable": source_table,
            "importId": int(record["import_id"]),
            "status": record["import_status"],
            "originalFilename": record["original_filename"],
            "fileType": record["file_type"],
            "totalQuestions": int(record["total_questions"] or 0),
            "successCount": int(record["success_count"] or 0),
            "failedCount": int(record["failed_count"] or 0),
            "duplicateCount": int(record["duplicate_count"] or 0),
            "previewData": _json_value(record["preview_data"], {}),
            "errorMessages": _json_value(record["error_messages"], []),
            "importTime": _iso(record["import_time"]),
            "completeTime": _iso(record["complete_time"]),
            "progressPercent": int(record["progress_percent"] or 0),
            "currentPhase": record["current_phase"],
        }
        key = f"question_import_record:{record['import_id']}"
        return _envelope(
            "import_snapshots", key, "ImportSnapshot", payload,
            source_table=source_table, source_id=int(record["import_id"]),
            version=version,
            updated_at=_iso(record["complete_time"] or record["import_time"]),
        )

    if source_table == "material_import_record":
        from app.models.models import MaterialImportRecord

        record = session.get(MaterialImportRecord, int(import_id))
        if record is None:
            return None
        # 解析中/待解析的记录先不投影：此时 parse_result 只有临时文件路径，
        # 没有可复用的正文。等 success/failed 终态再写，且必须剥掉临时路径，
        # 避免把服务器本地目录写进文档库。
        if (record.parse_status or '').lower() in ('pending', 'processing'):
            return None
        parsed = _strip_tmp(_json_value(record.parse_result, None))
        payload = {
            "sourceTable": source_table,
            "importId": int(record.import_id),
            "status": record.parse_status,
            "fileName": record.file_name,
            "fileType": record.file_type,
            "fileSize": int(record.file_size or 0),
            "parseMode": record.parse_mode,
            "parseResult": parsed,
            "errorMessage": record.error_message,
            "uploaderId": int(record.uploader_id) if record.uploader_id else None,
            "createTime": _iso(record.create_time),
            "updateTime": _iso(record.update_time),
        }
        key = f"material_import_record:{record.import_id}"
        return _envelope(
            "import_snapshots", key, "ImportSnapshot", payload,
            source_table=source_table, source_id=int(record.import_id),
            version=version,
            updated_at=_iso(record.update_time or record.create_time),
        )

    raise ValueError(f"未知导入来源表: {source_table}")


def build_forum_content(
    session: Session, post_id: int, *, version: int = 1
) -> dict[str, Any] | None:
    from app.models.models import ForumComment, ForumPost

    post = session.get(ForumPost, int(post_id))
    if post is None:
        return None
    comments = (
        session.query(ForumComment)
        .filter(ForumComment.post_id == post.post_id, ForumComment.status == 1)
        .order_by(ForumComment.comment_id)
        .all()
    )
    payload = {
        "postId": int(post.post_id),
        "authorId": int(post.user_id) if post.user_id else None,
        "title": post.title,
        "content": post.content,
        "shareType": post.share_type,
        "tags": post.tags,
        "status": post.status,
        "stats": {
            "likeCount": int(post.like_count or 0),
            "commentCount": int(post.comment_count or 0),
            "viewCount": int(post.view_count or 0),
            "collectCount": int(post.collect_count or 0),
        },
        "attachments": _json_value(post.attachments, []),
        "comments": [
            {
                "commentId": int(row.comment_id),
                "userId": int(row.user_id) if row.user_id else None,
                "parentCommentId": (
                    int(row.parent_comment_id) if row.parent_comment_id else None
                ),
                "content": row.content,
                "likeCount": int(row.like_count or 0),
                "createTime": _iso(row.create_time),
            }
            for row in comments
        ],
    }
    return _envelope(
        "forum_contents", str(post.post_id), "ForumThread", payload,
        source_table="forum_post", source_id=int(post.post_id), version=version,
        updated_at=_iso(post.update_time or post.create_time),
    )


def _strip_tmp(value: Any) -> Any:
    """递归剥离临时路径：只删结构上的 _tmp 键，不改正文内容。"""
    if isinstance(value, dict):
        return {
            key: _strip_tmp(item)
            for key, item in value.items()
            if str(key).lower() != "_tmp"
        }
    if isinstance(value, list):
        return [_strip_tmp(item) for item in value]
    return value
