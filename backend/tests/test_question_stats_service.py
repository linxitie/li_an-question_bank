"""QuestionStatsService 可见性口径测试"""
import pytest

from app.models.models import QuestionBank, SysUser
from app.services.question_stats import QuestionStatsService


@pytest.fixture
def teacher(db_session):
    user = SysUser(
        user_no="teacher_stats_001",
        username="统计教师",
        password="x",
        phone="13700137000",
        user_type="teacher",
        role_level=2,
        status=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed(db_session, subject_id, type_id, creator_id, status, audit_status,
          content):
    q = QuestionBank(
        subject_id=subject_id,
        type_id=type_id,
        question_content=content,
        options=[{"key": "A", "value": "1"}],
        answer="A",
        difficulty=1,
        score=2,
        creator_id=creator_id,
        status=status,
        audit_status=audit_status,
    )
    db_session.add(q)
    db_session.commit()
    return q


@pytest.fixture
def seeded(db_session, teacher, test_subject, test_question_type):
    for status, audit_status, content in [
        (1, 1, "visible"),
        (0, 1, "offline"),
        (1, 0, "pending"),
        (0, 0, "hidden"),
    ]:
        _seed(
            db_session,
            test_subject.subject_id,
            test_question_type.type_id,
            teacher.user_id,
            status,
            audit_status,
            content,
        )
    return db_session


def test_default_total_is_visible_for_all_roles(
    seeded, test_user, test_admin, teacher
):
    assert QuestionStatsService.get_stats(seeded, test_user)["total"] == 1
    assert QuestionStatsService.get_stats(seeded, test_admin)["total"] == 1
    assert QuestionStatsService.get_stats(seeded, teacher)["total"] == 1


def test_teacher_totals(seeded, teacher):
    stats = QuestionStatsService.get_stats(seeded, teacher)
    assert stats["my_total"] == 4
    assert stats["visible_total"] == 1
    assert QuestionStatsService.get_stats(seeded, teacher, mine=True)["total"] == 1


def test_admin_visibility_switches(seeded, test_admin):
    assert QuestionStatsService.get_stats(
        seeded, test_admin, include_offline=True
    )["total"] == 2
    assert QuestionStatsService.get_stats(
        seeded, test_admin, include_pending=True
    )["total"] == 2
    assert QuestionStatsService.get_stats(
        seeded, test_admin, include_offline=True, include_pending=True
    )["total"] == 4


def test_default_subject_distribution(seeded, test_admin):
    assert QuestionStatsService.get_stats(seeded, test_admin)["by_subject"] == {
        "申论": 1
    }
