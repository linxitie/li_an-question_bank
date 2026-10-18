"""跨域端到端流程测试（P2-81）。

覆盖三条非成就边与成就入口：

- **E11**：③ 练习提交 → ④ 练习记录可查（``POST /api/practice/batch-record``
  → ``GET /api/practice/records``）；
- **E12**：③ 答错 → ⑥ 错题集可查，且重复答错按次数累加、答对不误加
  （``GET /api/wrong-questions``）；
- **E13**：⑧ 薄弱点 → ⑤ 试卷推荐筛选（``GET /api/papers/list?recommend=true``）；
  无薄弱点时退化为全量且不报错；
- **10 类 trigger_type**（E1–E10，E5 两个字符串值，共 11 个）经事件消费者
  投递后，``achievement_judge`` 各收到一次，``badge_task`` 进度各 +1。

本文件只做跨域串联验证：E11/E12 复用 ``test_practice_transaction.py`` 的
判分事务口径，E13 复用 ``weakpoint_reader`` 与试卷列表推荐位；不修改产品代码，
不 import 其他域的 API 模块（HTTP 走客户端，判据走 service 层）。
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime

import pytest

from app.core import events
from app.core.trigger_types import ALL_TRIGGER_TYPES
from app.models.models import (
    ExamPaper,
    PaperQuestionRelation,
    PracticeRecord,
    QuestionBank,
    QuestionType,
    Task,
    UserTaskProgress,
    WrongQuestionPersonal,
)
from app.services import achievement_judge, event_consumer, practice_grading

#: E1–E10 十类事件与 trigger_type 字符串值的对照（E5 拆两个值，共 11 个）。
TRIGGER_CLASSES = {
    "practice.submit": "E1",
    "practice.record.created": "E2",
    "paper.completed": "E3",
    "wrong.reviewed": "E4",
    "note.created": "E5",
    "favorite.added": "E5",
    "forum.posted": "E6",
    "news.read": "E7",
    "material.opened": "E8",
    "shop.purchased": "E9",
    "checkin.done": "E10",
}


@pytest.fixture(autouse=True)
def _reset_event_state():
    """进程内去重窗口按用例重置，避免跨用例串扰。"""
    achievement_judge.reset_dedupe()
    practice_grading.reset_record_event_sessions()
    yield
    achievement_judge.reset_dedupe()
    practice_grading.reset_record_event_sessions()


@pytest.fixture
def question(db_session, test_subject, test_question_type, test_user):
    row = QuestionBank(
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        question_content="下列选项正确的是？",
        options=["A. 甲", "B. 乙", "C. 丙", "D. 丁"],
        answer="AC",
        creator_id=test_user.user_id,
        status=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_question(db_session, user, subject_id, type_id, content: str) -> QuestionBank:
    row = QuestionBank(
        subject_id=subject_id,
        type_id=type_id,
        question_content=content,
        options=["A. 甲", "B. 乙", "C. 丙", "D. 丁"],
        answer="A",
        creator_id=user.user_id,
        status=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _make_paper(db_session, user, subject_id, code: str) -> ExamPaper:
    paper = ExamPaper(
        paper_name=f"跨域试卷-{code}",
        paper_code=code,
        subject_id=subject_id,
        composition_method="MANUAL",
        creator_id=user.user_id,
        duration=60,
        total_score=100,
        paper_type="PUBLISHED",
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)
    return paper


def _link_question(db_session, paper, question, order: int = 1) -> None:
    db_session.add(
        PaperQuestionRelation(
            paper_id=paper.paper_id,
            question_id=question.question_id,
            question_order=order,
            question_score=5,
        )
    )
    db_session.commit()


# ---------------------------------------------------------------------------
# E11：③ 提交 → ④ 可查
# ---------------------------------------------------------------------------


def test_e11_submission_is_queryable_through_records_api(
    client, auth_headers, db_session, question
):
    response = client.post(
        "/api/practice/batch-record",
        headers=auth_headers,
        json={
            "records": [
                {
                    "question_id": question.question_id,
                    "user_answer": "AC",
                    "time_spent": 12,
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1

    listing = client.get(
        "/api/practice/records", headers=auth_headers, params={"limit": 50}
    )

    assert listing.status_code == 200, listing.text
    data = listing.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["question_id"] == question.question_id
    assert item["is_correct"] is True
    assert item["user_answer"] == "AC"
    assert item["practice_time"] is not None


# ---------------------------------------------------------------------------
# E12：③ 答错 → ⑥ 可查且幂等（按次累加，答对不误加）
# ---------------------------------------------------------------------------


def test_e12_wrong_answer_is_visible_in_wrongbook(
    client, auth_headers, db_session, question
):
    response = client.post(
        "/api/practice/batch-record",
        headers=auth_headers,
        json={"records": [{"question_id": question.question_id, "user_answer": "B"}]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_new_wrong"] is True
    assert body["wrong_question_stats"]["new"] == 1

    stored = db_session.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.question_id == question.question_id
    ).one()
    assert stored.error_count == 1

    listing = client.get("/api/wrong-questions", headers=auth_headers)

    assert listing.status_code == 200, listing.text
    data = listing.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["question_id"] == question.question_id
    assert item["error_count"] == 1


def test_e12_repeated_wrong_attempts_increment_once_each_and_correct_is_noop(
    client, auth_headers, db_session, question
):
    wrong_payload = {
        "records": [{"question_id": question.question_id, "user_answer": "B"}]
    }

    first = client.post(
        "/api/practice/batch-record", headers=auth_headers, json=wrong_payload
    )
    second = client.post(
        "/api/practice/batch-record", headers=auth_headers, json=wrong_payload
    )

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["wrong_question_stats"]["new"] == 1
    assert second.json()["wrong_question_stats"]["updated"] == 1

    db_session.expire_all()
    stored = db_session.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.question_id == question.question_id
    ).one()
    assert stored.error_count == 2
    assert stored.review_count == 2

    # 答对不触碰错题集：error_count 只随答错次数累加
    correct = client.post(
        "/api/practice/batch-record",
        headers=auth_headers,
        json={
            "records": [
                {"question_id": question.question_id, "user_answer": "AC"}
            ]
        },
    )

    assert correct.status_code == 200
    assert correct.json()["wrong_question_stats"] == {
        "new": 0,
        "updated": 0,
        "skipped": 0,
    }

    db_session.expire_all()
    stored = db_session.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.question_id == question.question_id
    ).one()
    assert stored.error_count == 2
    assert stored.review_count == 2

    listing = client.get("/api/wrong-questions", headers=auth_headers)
    item = listing.json()["items"][0]
    assert item["error_count"] == 2


# ---------------------------------------------------------------------------
# E13：⑧ 薄弱点 → ⑤ 推荐筛选
# ---------------------------------------------------------------------------


@pytest.fixture
def weak_type(db_session, test_subject):
    row = QuestionType(
        type_name="资料分析",
        type_code="ZILIAO",
        subject_id=test_subject.subject_id,
        is_objective=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _seed_weak_records(db_session, user, question, type_id: int, attempts: int = 5):
    """直接写入练习历史：题量达阈值且正确率低于薄弱线。"""
    for _ in range(attempts):
        db_session.add(
            PracticeRecord(
                user_id=user.user_id,
                question_id=question.question_id,
                subject_id=question.subject_id,
                type_id=type_id,
                is_correct=0,
                practice_date=date.today(),
                practice_time=datetime.now(),
            )
        )
    db_session.commit()


def test_e13_recommend_filters_papers_by_weak_question_type(
    client,
    auth_headers,
    db_session,
    test_user,
    test_subject,
    test_question_type,
    weak_type,
):
    weak_question = _make_question(
        db_session,
        test_user,
        test_subject.subject_id,
        weak_type.type_id,
        "资料分析薄弱题",
    )
    normal_question = _make_question(
        db_session,
        test_user,
        test_subject.subject_id,
        test_question_type.type_id,
        "普通单选题",
    )
    weak_paper = _make_paper(db_session, test_user, test_subject.subject_id, "X-E13-W")
    normal_paper = _make_paper(db_session, test_user, test_subject.subject_id, "X-E13-N")
    _link_question(db_session, weak_paper, weak_question)
    _link_question(db_session, normal_paper, normal_question)

    _seed_weak_records(db_session, test_user, weak_question, weak_type.type_id)

    response = client.get(
        "/api/papers/list",
        headers=auth_headers,
        params={"recommend": "true", "page_size": 50},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    paper_ids = [item["paper_id"] for item in body["items"]]
    assert body["total"] == 1
    assert paper_ids == [weak_paper.paper_id]
    assert normal_paper.paper_id not in paper_ids


def test_e13_recommend_without_weakpoints_returns_full_list(
    client,
    auth_headers,
    db_session,
    test_user,
    test_subject,
    test_question_type,
):
    first_question = _make_question(
        db_session,
        test_user,
        test_subject.subject_id,
        test_question_type.type_id,
        "题目一",
    )
    second_question = _make_question(
        db_session,
        test_user,
        test_subject.subject_id,
        test_question_type.type_id,
        "题目二",
    )
    first_paper = _make_paper(db_session, test_user, test_subject.subject_id, "X-E13-A")
    second_paper = _make_paper(db_session, test_user, test_subject.subject_id, "X-E13-B")
    _link_question(db_session, first_paper, first_question)
    _link_question(db_session, second_paper, second_question)

    response = client.get(
        "/api/papers/list",
        headers=auth_headers,
        params={"recommend": "true", "page_size": 50},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    paper_ids = {item["paper_id"] for item in body["items"]}
    assert body["total"] == 2
    assert paper_ids == {first_paper.paper_id, second_paper.paper_id}


# ---------------------------------------------------------------------------
# 10 类 trigger_type → achievement_judge
# ---------------------------------------------------------------------------


def _add_event_task(db_session, index: int, trigger_type: str) -> Task:
    task = Task(
        task_code=f"cross_evt_{index}",
        t_type="daily",
        title=f"跨域任务 {trigger_type}",
        metric=trigger_type,
        mode="event",
        threshold=1,
        reward_coins=0,
        reward_growth=0,
        sort_order=0,
        enabled=1,
    )
    db_session.add(task)
    return task


def test_all_trigger_types_dispatch_once_and_update_task_progress(
    monkeypatch, db_session, test_user
):
    # 事件目录：E1–E10 共 10 类，E5 拆成 note/favorite 两个值 → 11 个字符串值
    assert set(TRIGGER_CLASSES) == set(ALL_TRIGGER_TYPES)
    assert len(TRIGGER_CLASSES) == 11
    assert len(set(TRIGGER_CLASSES.values())) == 10

    tasks = {
        trigger: _add_event_task(db_session, index, trigger)
        for index, trigger in enumerate(ALL_TRIGGER_TYPES)
    }
    db_session.commit()
    task_ids = {trigger: task.task_id for trigger, task in tasks.items()}
    # ``_dispatch`` 会 close 会话；提前取出标量，避免对象被 detach 后失效
    user_id = test_user.user_id

    calls = []
    original_judge = achievement_judge.judge_action

    def spy_judge(user_id, trigger_type, db, session=None):
        result = original_judge(user_id, trigger_type, db, session=session)
        calls.append((trigger_type, result["duplicate"]))
        return result

    monkeypatch.setattr(achievement_judge, "judge_action", spy_judge)
    monkeypatch.setattr(event_consumer, "SessionLocal", lambda: db_session)

    for index, trigger_type in enumerate(ALL_TRIGGER_TYPES):
        asyncio.run(
            event_consumer._dispatch(
                events.Event(
                    name=events.EV_USER_ACTION,
                    payload={
                        "user_id": user_id,
                        "trigger_type": trigger_type,
                        "session": {"session_id": f"cross-domain-{index}"},
                    },
                )
            )
        )

    # 每个 trigger 均被接受一次，没有一条被判为重复
    assert [trigger for trigger, _ in calls] == list(ALL_TRIGGER_TYPES)
    assert all(duplicate is False for _, duplicate in calls)

    # badge_task（mode=event）按 trigger 各自累加 1
    db_session.expire_all()
    progress = {
        row.task_id: int(row.current or 0)
        for row in db_session.query(UserTaskProgress).all()
    }
    for trigger, task_id in task_ids.items():
        assert progress[task_id] == 1, trigger
