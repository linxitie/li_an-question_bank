# -*- coding: utf-8 -*-
"""A2 回归（2026-11-07）：管理列表的「上传时间 / 发布者 / 最近 7·30 天 / 排序」。

口径来自裁定 D37：对外叫「上传时间」，实现取**入库时间** `study_material.create_time`（零迁移），
对外补 `+08:00`；「最近 N 天」是**滚动窗口**（`create_time >= now - N 天`），不是「本周一」。
"""
from datetime import datetime, timedelta

from app.models.models import StudyMaterial


def _mk(db, creator_id, days_ago, title, status=1):
    """造一条资料，create_time 显式回拨到 N 天前（默认值 datetime.now 不够可控）。"""
    m = StudyMaterial(
        subject="gongzhuan", type="card", title=title,
        card_front="正面", card_back="背面",
        status=status, creator_id=creator_id,
        create_time=datetime.now() - timedelta(days=days_ago),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _list(client, headers, **params):
    r = client.get("/api/materials/admin/list", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


class TestUploadTime:
    def test_item_has_created_at_in_cn_offset(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, test_admin.user_id, 3, "三天前的资料")
        data = _list(client, admin_headers)
        item = data["items"][0]
        assert "created_at" in item
        # 带 +08:00，前端拿到就能直接格式化，不需要猜时区
        assert item["created_at"].endswith("+08:00"), item["created_at"]
        assert item["created_at"][:10] == (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    def test_student_list_also_has_created_at(self, client, db_session, test_admin):
        """学生端列表同源（`_item_brief`），也应带 created_at（增字段、不改旧字段）。"""
        _mk(db_session, test_admin.user_id, 1, "学生可见资料")
        r = client.get("/api/materials", params={"subject": "gongzhuan"})
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert items and items[0]["created_at"].endswith("+08:00")


class TestPublisher:
    def test_publisher_comes_from_creator_id(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, test_admin.user_id, 2, "管理员发的")
        item = _list(client, admin_headers)["items"][0]
        pub = item["publisher"]
        assert pub["id"] == test_admin.user_id
        assert pub["name"] == test_admin.username     # 无 nickname 时回退 username
        assert pub["role"] == "admin"
        assert pub["role_label"] == "管理员"

    def test_missing_creator_is_none_not_crash(self, client, db_session, test_admin, admin_headers):
        """creator_id 为空（历史数据/系统导入）不能 500，前端显示 —。"""
        _mk(db_session, None, 2, "无发布者")
        item = _list(client, admin_headers)["items"][0]
        assert item["creator_id"] is None
        assert item["publisher"] is None

    def test_filter_by_publisher(self, client, db_session, test_admin, test_teacher, admin_headers):
        _mk(db_session, test_admin.user_id, 1, "管理员的资料")
        _mk(db_session, test_teacher.user_id, 1, "教师的资料")
        data = _list(client, admin_headers, publisher_id=test_teacher.user_id)
        assert data["total"] == 1
        assert data["items"][0]["title"] == "教师的资料"


class TestCreatedWithin:
    """滚动窗口：7d / 30d。"""

    def test_7d_only_recent(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, test_admin.user_id, 3, "3 天前")
        _mk(db_session, test_admin.user_id, 20, "20 天前")
        _mk(db_session, test_admin.user_id, 40, "40 天前")
        data = _list(client, admin_headers, created_within="7d")
        assert data["total"] == 1
        assert data["items"][0]["title"] == "3 天前"

    def test_30d_includes_20_but_not_40(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, test_admin.user_id, 3, "3 天前")
        _mk(db_session, test_admin.user_id, 20, "20 天前")
        _mk(db_session, test_admin.user_id, 40, "40 天前")
        data = _list(client, admin_headers, created_within="30d")
        titles = {i["title"] for i in data["items"]}
        assert titles == {"3 天前", "20 天前"}

    def test_no_param_returns_all(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, test_admin.user_id, 3, "3 天前")
        _mk(db_session, test_admin.user_id, 40, "40 天前")
        assert _list(client, admin_headers)["total"] == 2

    def test_invalid_value_is_422(self, client, db_session, test_admin, admin_headers):
        r = client.get("/api/materials/admin/list", headers=admin_headers,
                       params={"created_within": "5d"})
        assert r.status_code == 422


class TestOrder:
    def test_default_is_newest_first(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, test_admin.user_id, 5, "较旧")
        _mk(db_session, test_admin.user_id, 1, "较新")
        items = _list(client, admin_headers)["items"]
        assert [i["title"] for i in items] == ["较新", "较旧"]

    def test_created_asc_is_oldest_first(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, test_admin.user_id, 5, "较旧")
        _mk(db_session, test_admin.user_id, 1, "较新")
        items = _list(client, admin_headers, order="created_asc")["items"]
        assert [i["title"] for i in items] == ["较旧", "较新"]

    def test_invalid_order_is_422(self, client, db_session, test_admin, admin_headers):
        """非法排序值 → 422（`order` 是白名单 pattern，不是自由字符串）。

        2026-11-08 更新：`id_desc` 现在是**合法默认值**（ID 方案 A），
        所以拿它当"非法样本"已经过时 —— 换成真正不存在的 `relevance`。
        """
        r = client.get("/api/materials/admin/list", headers=admin_headers,
                       params={"order": "relevance"})
        assert r.status_code == 422

    def test_id_desc_is_accepted(self, client, db_session, test_admin, admin_headers):
        """`id_desc` 是默认排序键（列表时间倒序），必须 200 而不是 422。"""
        _mk(db_session, test_admin.user_id, 1, "随便一条")
        r = client.get("/api/materials/admin/list", headers=admin_headers,
                       params={"order": "id_desc"})
        assert r.status_code == 200, r.text
        assert r.json()["items"][0]["seq"] == r.json()["total"]


class TestPermission:
    def test_student_cannot_list_admin(self, client, db_session, auth_headers):
        r = client.get("/api/materials/admin/list", headers=auth_headers)
        assert r.status_code == 403
