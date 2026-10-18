"""笔记与收藏（E5）模块测试（P2-24 / P2-27）。

覆盖：创建笔记/收藏各发布一次对应 trigger_type；同一笔记重复提交（更新分支）
不重复发创建事件；编辑、删除、只读查询均不发布创建事件；新闻收藏与典题收藏
共用 ``favorite.added``。
"""
import pytest

from app.api.v1.personal import collection as collection_api
from app.api.v1.personal import notes as notes_api
from app.models.models import NewsArticle, QuestionBank


@pytest.fixture
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append({"user_id": user_id, "trigger_type": trigger_type})
        return True

    monkeypatch.setattr(notes_api, "record_user_action", fake_record)
    monkeypatch.setattr(collection_api, "record_user_action", fake_record)
    return events


@pytest.fixture
def question(db_session, test_subject, test_question_type, test_user):
    row = QuestionBank(
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        question_content="下列关于治安管理处罚的说法正确的是？",
        options=["A. 甲", "B. 乙", "C. 丙", "D. 丁"],
        answer="A",
        creator_id=test_user.user_id,
        status=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def news(db_session):
    row = NewsArticle(
        title="公安联考政策解读",
        url="https://example.com/news/1",
        source="cpd",
        category="政策",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _events(events, trigger_type):
    return [e for e in events if e["trigger_type"] == trigger_type]


def _create_question_note(client, auth_headers, question, text="第一次笔记"):
    return client.post(
        "/api/notes",
        headers=auth_headers,
        json={"type": "question", "id": question.question_id, "note_text": text},
    )


def test_create_question_note_publishes_once(
    client, auth_headers, question, published
):
    response = _create_question_note(client, auth_headers, question)

    assert response.status_code == 200
    assert response.json()["created"] is True
    events = _events(published, "note.created")
    assert len(events) == 1


def test_reposting_same_note_does_not_republish(
    client, auth_headers, question, published
):
    _create_question_note(client, auth_headers, question)
    second = _create_question_note(client, auth_headers, question, "修改后的笔记")

    assert second.status_code == 200
    assert second.json()["updated"] is True
    assert len(_events(published, "note.created")) == 1


def test_update_and_delete_do_not_republish(
    client, auth_headers, db_session, question, published
):
    created = _create_question_note(client, auth_headers, question).json()
    note_id = created["note_id"]

    updated = client.put(
        f"/api/notes/{note_id}",
        headers=auth_headers,
        json={"note_text": "编辑后的笔记"},
    )
    deleted = client.delete(f"/api/notes/{note_id}", headers=auth_headers)

    assert updated.status_code == 200
    assert deleted.status_code == 200
    assert len(_events(published, "note.created")) == 1


def test_create_news_note_publishes_once(
    client, auth_headers, news, published
):
    response = client.post(
        "/api/notes",
        headers=auth_headers,
        json={"type": "news", "id": news.news_id, "note_text": "新闻想法"},
    )

    assert response.status_code == 200
    assert response.json()["created"] is True
    assert len(_events(published, "note.created")) == 1


def test_question_favorite_add_publishes_then_toggle_off_does_not(
    client, auth_headers, question, published
):
    added = client.post(
        "/api/collection/favorite",
        headers=auth_headers,
        json={"type": "question", "id": question.question_id},
    )
    assert added.status_code == 200
    assert added.json()["favorited"] is True
    assert len(_events(published, "favorite.added")) == 1

    removed = client.post(
        "/api/collection/favorite",
        headers=auth_headers,
        json={"type": "question", "id": question.question_id},
    )
    assert removed.status_code == 200
    assert removed.json()["favorited"] is False
    assert len(_events(published, "favorite.added")) == 1


def test_news_favorite_add_publishes_favorite_added(
    client, auth_headers, news, published
):
    added = client.post(
        "/api/collection/favorite",
        headers=auth_headers,
        json={"type": "news", "id": news.news_id},
    )
    assert added.status_code == 200
    assert added.json()["favorited"] is True
    assert len(_events(published, "favorite.added")) == 1

    removed = client.post(
        "/api/collection/favorite",
        headers=auth_headers,
        json={"type": "news", "id": news.news_id},
    )
    assert removed.json()["favorited"] is False
    assert len(_events(published, "favorite.added")) == 1


def test_delete_favorite_does_not_republish(
    client, auth_headers, question, published
):
    fav_id = client.post(
        "/api/collection/favorite",
        headers=auth_headers,
        json={"type": "question", "id": question.question_id},
    ).json()["fav_id"]

    response = client.delete(f"/api/collection/{fav_id}", headers=auth_headers)

    assert response.status_code == 200
    assert len(_events(published, "favorite.added")) == 1


@pytest.mark.parametrize(
    "path",
    [
        "/api/notes",
        "/api/notes/stats",
        "/api/notes/news",
        "/api/notes/question",
        "/api/collection",
        "/api/collection/stats",
        "/api/collection/news-favorites",
        "/api/collection/question-favorites",
    ],
)
def test_read_endpoints_do_not_publish(
    client, auth_headers, question, published, path
):
    _create_question_note(client, auth_headers, question)
    published.clear()

    response = client.get(path, headers=auth_headers)

    assert response.status_code == 200
    assert published == []
