"""题库浏览（catalog）只读接口测试（P2-72 / P2-75）。

覆盖：
- 列表只返回 `status == 1` 的题目；
- 筛选参数（subject_id / difficulty / year / audit_status / keyword）与组合筛选；
- 服务端分页（page / page_size）与 total 口径；
- 参数校验（difficulty 1-5、page_size 1-100）；
- 详情读取、exam_frequency 自增、软删除 404。

本文件只验证既有只读端点，不新增端点、不修改路径。
"""
import pytest

from app.models.models import QuestionBank, QuestionSubject


@pytest.fixture
def make_question(db_session, test_user, test_subject, test_question_type):
    """构造题目行：默认 status=1 / difficulty=3 / year=2024。"""

    def _make(index: int, **overrides) -> QuestionBank:
        values = {
            "subject_id": test_subject.subject_id,
            "type_id": test_question_type.type_id,
            "question_content": f"行测题目内容 {index}",
            "options": [
                {"key": "A", "value": "选项 A"},
                {"key": "B", "value": "选项 B"},
                {"key": "C", "value": "选项 C"},
                {"key": "D", "value": "选项 D"},
            ],
            "answer": "A",
            "answer_analysis": "解析",
            "creator_id": test_user.user_id,
            "status": 1,
            "difficulty": 3,
            "year": 2024,
            "source": "公安联考真题",
            "tags": "测试标签",
            "audit_status": 1,
        }
        values.update(overrides)
        row = QuestionBank(**values)
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        return row

    return _make


@pytest.fixture
def other_subject(db_session):
    subject = QuestionSubject(
        subject_name="行测", subject_code="XINGCE", status=1
    )
    db_session.add(subject)
    db_session.commit()
    db_session.refresh(subject)
    return subject


def _ids(response) -> list:
    return [item["question_id"] for item in response.json()["items"]]


def test_list_returns_only_active_questions(client, make_question):
    first = make_question(1)
    make_question(2)
    deleted = make_question(3, status=0)

    response = client.get("/api/questions/")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert deleted.question_id not in _ids(response)
    assert first.question_id in _ids(response)


def test_list_filters_by_subject(client, make_question, other_subject):
    shenlun = make_question(1)
    xingce = make_question(2, subject_id=other_subject.subject_id)

    response = client.get(
        "/api/questions/", params={"subject_id": other_subject.subject_id}
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert _ids(response) == [xingce.question_id]
    assert shenlun.question_id not in _ids(response)


def test_list_filters_by_difficulty_and_year_and_audit_status(client, make_question):
    target = make_question(
        1, difficulty=5, year=2023, audit_status=0
    )
    make_question(2, difficulty=4, year=2023, audit_status=0)
    make_question(3, difficulty=5, year=2022, audit_status=0)
    make_question(4, difficulty=5, year=2023, audit_status=1)

    response = client.get(
        "/api/questions/",
        params={"difficulty": 5, "year": 2023, "audit_status": 0},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert _ids(response) == [target.question_id]


def test_list_filters_by_keyword_in_content_tags_or_source(client, make_question):
    content_hit = make_question(1, question_content="宪法基本原则是什么")
    tags_hit = make_question(2, tags="宪法")
    source_hit = make_question(3, source="宪法学讲义")
    make_question(4, question_content="刑法题目", tags="刑法", source="刑法讲义")

    response = client.get("/api/questions/", params={"keyword": "宪法"})

    assert response.status_code == 200
    assert response.json()["total"] == 3
    expected = {
        content_hit.question_id,
        tags_hit.question_id,
        source_hit.question_id,
    }
    assert set(_ids(response)) == expected


def test_list_pagination(client, make_question):
    rows = [make_question(i) for i in range(1, 6)]

    response = client.get(
        "/api/questions/", params={"page": 2, "page_size": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(rows)
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    # 列表按 create_time desc, question_id desc 排序；同批创建时以 id 倒序
    assert _ids(response) == [
        rows[2].question_id,
        rows[1].question_id,
    ]


@pytest.mark.parametrize("difficulty", [0, 6, -1])
def test_list_rejects_out_of_range_difficulty(client, difficulty):
    response = client.get(
        "/api/questions/", params={"difficulty": difficulty}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("page_size", [0, 101])
def test_list_rejects_out_of_range_page_size(client, page_size):
    response = client.get(
        "/api/questions/", params={"page_size": page_size}
    )
    assert response.status_code == 422


def test_list_rejects_page_zero(client):
    response = client.get("/api/questions/", params={"page": 0})
    assert response.status_code == 422


def test_detail_returns_question_and_increments_exam_frequency(client, make_question):
    row = make_question(1)

    first = client.get(f"/api/questions/{row.question_id}")
    assert first.status_code == 200
    assert first.json()["question_id"] == row.question_id
    assert first.json()["question_content"] == row.question_content
    assert first.json()["exam_frequency"] == 1

    second = client.get(f"/api/questions/{row.question_id}")
    assert second.status_code == 200
    assert second.json()["exam_frequency"] == 2


def test_detail_missing_returns_404(client):
    response = client.get("/api/questions/999999")
    assert response.status_code == 404


def test_detail_soft_deleted_returns_404(client, make_question):
    row = make_question(1, status=0)
    response = client.get(f"/api/questions/{row.question_id}")
    assert response.status_code == 404
