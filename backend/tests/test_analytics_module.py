"""P2-57 / P2-58 / P2-61 / P2-62：成绩分析域与 E13 读链路。"""
from pathlib import Path

from app.core.security import create_access_token, get_password_hash
from app.models.models import (
    ExamPaper,
    KnowledgePoint,
    PaperQuestionRelation,
    PracticeRecord,
    QuestionBank,
    QuestionType,
    SysUser,
)
from app.services import weakpoint_reader


def _headers(user: SysUser) -> dict:
    token = create_access_token(
        data={"user_id": user.user_id, "user_no": user.user_no}
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_type(
    db_session,
    user,
    *,
    code: str,
    name: str,
    point_name: str,
    total: int,
    correct: int,
):
    subject_id = 1
    qtype = QuestionType(
        type_name=name,
        type_code=code,
        subject_id=subject_id,
        is_objective=1,
    )
    point = KnowledgePoint(point_name=point_name, subject_id=subject_id)
    db_session.add_all([qtype, point])
    db_session.commit()
    db_session.refresh(qtype)
    db_session.refresh(point)

    question = QuestionBank(
        subject_id=subject_id,
        type_id=qtype.type_id,
        point_id=point.point_id,
        question_content=f"{name} 示例题",
        answer="A",
        creator_id=user.user_id,
        status=1,
        audit_status=1,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    for index in range(total):
        db_session.add(
            PracticeRecord(
                user_id=user.user_id,
                question_id=question.question_id,
                subject_id=subject_id,
                type_id=qtype.type_id,
                answer="A",
                is_correct=1 if index < correct else 0,
            )
        )
    db_session.commit()
    return qtype, question


def _seed_paper(db_session, user, question, *, code: str, name: str) -> ExamPaper:
    paper = ExamPaper(
        paper_name=name,
        paper_code=code,
        subject_id=1,
        composition_method="MANUAL",
        creator_id=user.user_id,
        duration=60,
        total_score=100,
        question_count=1,
        paper_type="PUBLISHED",
        exam_type="PRACTICE",
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)
    db_session.add(
        PaperQuestionRelation(
            paper_id=paper.paper_id,
            question_id=question.question_id,
            question_order=1,
            question_score=2,
        )
    )
    db_session.commit()
    return paper


def test_weakpoint_reader_structure_is_stable(db_session, test_user):
    _seed_type(
        db_session,
        test_user,
        code="WEAK",
        name="薄弱题型",
        point_name="薄弱考点",
        total=10,
        correct=3,
    )
    _seed_type(
        db_session,
        test_user,
        code="STRONG",
        name="优势题型",
        point_name="优势考点",
        total=10,
        correct=9,
    )

    result = weakpoint_reader.get_weakpoints(db_session, test_user.user_id)

    assert len(result) == 1
    assert set(result[0]) == {"knowledge_point", "accuracy", "total", "correct"}
    assert result[0]["knowledge_point"] == "薄弱考点"
    assert result[0]["accuracy"] == 30.0
    assert result[0]["total"] == 10
    assert result[0]["correct"] == 3


def test_weakpoint_reader_returns_empty_without_records(db_session):
    assert weakpoint_reader.get_weakpoints(db_session, None) == []
    assert weakpoint_reader.get_weakpoint_type_ids(db_session, 999999) == []


def test_weakpoint_reader_does_not_import_api_modules():
    source = Path(__file__).resolve().parents[1] / "app" / "services" / "weakpoint_reader.py"
    assert "api.v1" not in source.read_text(encoding="utf-8")


def test_dashboard_exposes_weakpoints(client, db_session, test_user, auth_headers):
    _seed_type(
        db_session,
        test_user,
        code="WEAK",
        name="薄弱题型",
        point_name="薄弱考点",
        total=10,
        correct=2,
    )

    response = client.get("/api/stats/dashboard", headers=auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "weakPoints" in payload
    assert payload["weakPoints"][0]["knowledge_point"] == "薄弱考点"
    assert payload["weakPoints"][0]["accuracy"] == 20.0


def test_paper_recommendation_filters_by_weakpoint(
    client, db_session, test_user, auth_headers
):
    weak_type, weak_question = _seed_type(
        db_session,
        test_user,
        code="WEAK",
        name="薄弱题型",
        point_name="薄弱考点",
        total=10,
        correct=3,
    )
    _, strong_question = _seed_type(
        db_session,
        test_user,
        code="STRONG",
        name="优势题型",
        point_name="优势考点",
        total=10,
        correct=10,
    )
    weak_paper = _seed_paper(
        db_session, test_user, weak_question, code="REC-WEAK", name="薄弱推荐卷"
    )
    strong_paper = _seed_paper(
        db_session, test_user, strong_question, code="REC-STRONG", name="优势卷"
    )

    response = client.get(
        "/api/papers/list?recommend=true&page_size=50", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    ids = {item["paper_id"] for item in response.json()["items"]}
    assert weak_paper.paper_id in ids
    assert strong_paper.paper_id not in ids
    assert weak_type.type_id in weakpoint_reader.get_weakpoint_type_ids(
        db_session, test_user.user_id
    )


def test_paper_recommendation_falls_back_without_weakpoints(
    client, db_session, test_user
):
    _, question = _seed_type(
        db_session,
        test_user,
        code="NO_WEAK",
        name="普通题型",
        point_name="普通考点",
        total=4,
        correct=4,
    )
    paper = _seed_paper(
        db_session, test_user, question, code="REC-ALL", name="全量卷"
    )

    newcomer = SysUser(
        user_no="analytics_new",
        username="新用户",
        password=get_password_hash("password123"),
        phone="13600136000",
        user_type="student",
        role_level=1,
        status=1,
    )
    db_session.add(newcomer)
    db_session.commit()
    db_session.refresh(newcomer)

    response = client.get(
        "/api/papers/list?recommend=true&page_size=50", headers=_headers(newcomer)
    )

    assert response.status_code == 200, response.text
    ids = {item["paper_id"] for item in response.json()["items"]}
    assert paper.paper_id in ids
