# -*- coding: utf-8 -*-
"""P3-03 可见范围：学生默认本班、可改全校；教师/管理员不过滤。

决策来源：docs/plans/论坛与个人主页增强_总方案_v1.7.md §9（用户 2026-10-26 批复）
"""
from datetime import datetime

from app.core.security import create_access_token
from app.models.models import ForumPost, SysUser


def _make_student(db_session, user_no, class_name):
    user = SysUser(
        user_no=user_no,
        username=user_no,
        password="x",
        phone="1390000000" + user_no[-1],
        user_type="student",
        role_level=1,
        status=1,
        class_name=class_name,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"user_id": user.user_id, "user_no": user.user_no})
    return user, {"Authorization": f"Bearer {token}"}


def _create_post(client, headers, title="可见范围测试帖", **extra):
    data = {"title": title, "content": "正文", "share_type": "DISCUSSION"}
    data.update(extra)
    resp = client.post("/api/forum/posts", headers=headers, data=data)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _titles(client, headers, **params):
    resp = client.get("/api/forum/posts", headers=headers, params=params)
    assert resp.status_code == 200, resp.text
    return [p["title"] for p in resp.json()["posts"]]


def test_student_default_is_classes(client, db_session):
    stu, headers = _make_student(db_session, "s101", "一班")
    post = _create_post(client, headers, title="默认本班帖")
    assert post["visibility"] == "CLASSES"
    assert post["visibleClasses"] == ["一班"]

    row = db_session.query(ForumPost).filter(ForumPost.post_id == post["id"]).first()
    assert row.visibility == "CLASSES"
    assert row.visible_classes == ["一班"]


def test_other_class_cannot_see(client, db_session):
    a, ha = _make_student(db_session, "s102", "一班")
    b, hb = _make_student(db_session, "s103", "二班")
    _create_post(client, ha, title="一班专属帖")

    assert "一班专属帖" in _titles(client, ha)
    assert "一班专属帖" not in _titles(client, hb)


def test_student_can_post_all(client, db_session):
    a, ha = _make_student(db_session, "s104", "一班")
    b, hb = _make_student(db_session, "s105", "二班")
    post = _create_post(client, ha, title="全校帖", visibility="ALL")
    assert post["visibility"] == "ALL"
    assert "全校帖" in _titles(client, hb)


def test_teacher_sees_all(client, db_session, teacher_headers):
    a, ha = _make_student(db_session, "s106", "一班")
    _create_post(client, ha, title="教师应可见的本班帖")
    assert "教师应可见的本班帖" in _titles(client, teacher_headers)


def test_guest_sees_only_all(client, db_session):
    a, ha = _make_student(db_session, "s107", "一班")
    _create_post(client, ha, title="游客不该看到的本班帖")
    guest_titles = [p["title"] for p in client.get("/api/forum/posts").json()["posts"]]
    assert "游客不该看到的本班帖" not in guest_titles


def test_date_range_filter(client, db_session):
    a, ha = _make_student(db_session, "s108", "一班")
    post = _create_post(client, ha, title="日期过滤测试帖", visibility="ALL")

    row = db_session.query(ForumPost).filter(ForumPost.post_id == post["id"]).first()
    row.create_time = datetime(2026, 1, 15, 12, 0, 0)
    db_session.commit()

    assert "日期过滤测试帖" in _titles(
        client, ha, date_from="2026-01-15", date_to="2026-01-15"
    )
    assert "日期过滤测试帖" not in _titles(client, ha, date_from="2026-02-01")
    assert "日期过滤测试帖" not in _titles(client, ha, date_to="2026-01-14")


def test_invalid_visibility_falls_back(client, db_session):
    a, ha = _make_student(db_session, "s109", "一班")
    post = _create_post(client, ha, title="非法可见范围帖", visibility="WHATEVER")
    assert post["visibility"] in ("CLASSES", "ALL")
    assert post["visibility"] != "WHATEVER"
