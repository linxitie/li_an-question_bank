# -*- coding: utf-8 -*-
"""P3-02 结构测试：forum_favorite 表与 forum_post 可见范围列。

不测接口（接口在 P3-03），只保证：
1) 模型注册进 metadata（应用启动 create_all 能建表）
2) 字段类型/默认值符合设计
3) 未填 visibility 的帖子默认 = ALL（向后兼容）
4) 收藏唯一约束生效（同一用户不可重复收藏同一帖）
"""
import pytest
from sqlalchemy import inspect, text

from app.core.database import Base
from app.models.models import ForumFavorite, ForumPost, SysUser


def test_forum_favorite_registered_in_metadata():
    assert "forum_favorite" in Base.metadata.tables
    cols = {c.name for c in ForumFavorite.__table__.columns}
    assert {"favorite_id", "post_id", "user_id", "create_time"} <= cols


def test_forum_post_has_visibility_columns():
    cols = {c.name for c in ForumPost.__table__.columns}
    assert "visibility" in cols
    assert "visible_classes" in cols


def test_tables_created_in_db(db_session):
    insp = inspect(db_session.get_bind())
    tables = set(insp.get_table_names())
    assert "forum_favorite" in tables

    post_cols = {c["name"] for c in insp.get_columns("forum_post")}
    assert {"visibility", "visible_classes"} <= post_cols


def test_default_visibility_is_all(db_session, test_user):
    """不传 visibility 时落库应为 ALL（学生默认 CLASSES 由接口层决定，不动表默认值）。"""
    post = ForumPost(
        user_id=test_user.user_id,
        title="结构测试帖",
        content="正文",
        share_type="DISCUSSION",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    assert post.visibility == "ALL"
    assert post.visible_classes is None


def test_favorite_unique_constraint(db_session, test_user):
    post = ForumPost(
        user_id=test_user.user_id,
        title="收藏约束测试帖",
        content="正文",
        share_type="DISCUSSION",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    db_session.add(ForumFavorite(post_id=post.post_id, user_id=test_user.user_id))
    db_session.commit()

    db_session.add(ForumFavorite(post_id=post.post_id, user_id=test_user.user_id))
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_visibility_can_be_classes(db_session, test_user):
    post = ForumPost(
        user_id=test_user.user_id,
        title="本班可见帖",
        content="正文",
        share_type="DISCUSSION",
        visibility="CLASSES",
        visible_classes=["一班", "二班"],
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    assert post.visibility == "CLASSES"
    assert post.visible_classes == ["一班", "二班"]
