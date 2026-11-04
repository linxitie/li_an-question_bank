# -*- coding: utf-8 -*-
"""管理列表搜索（keyword）集成测试。

覆盖真接口全链路：管理员登录 → 建 2 张带唯一标记的卡 → 用 keyword 搜索命中 → 清理。
无可用管理员账号时自动 skip（不污染其他环境）。
"""
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def admin_client():
    from app.main import app

    c = TestClient(app)
    resp = c.post("/api/auth/login", data={"username": "cbrycc", "password": "cbrycc"})
    if resp.status_code != 200:
        pytest.skip("无可用管理员测试账号（cbrycc），跳过搜索集成测试")
    token = resp.json().get("access_token")
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


@pytest.fixture()
def tagged_cards(admin_client):
    """建 2 张标题带唯一标记的卡，测试结束删除。"""
    tag = "ZZ" + uuid.uuid4().hex[:8]
    ids = []
    for title in (f"搜索专用-判断推理-{tag}", f"搜索专用-职业素养-{tag}"):
        body = {
            "subject": "xingce",
            "type": "card",
            "title": title,
            "card_front": f"正面-{tag}",
            "card_back": f"背面-{tag}",
            "category": "知觉速度与准确性",
            "publish": False,
        }
        r = admin_client.post("/api/materials/admin", json=body)
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    yield tag, ids
    for mid in ids:
        admin_client.delete(f"/api/materials/admin/{mid}")


class TestAdminListSearch:
    def test_keyword_hits_only_matching(self, admin_client, tagged_cards):
        tag, ids = tagged_cards
        r = admin_client.get("/api/materials/admin/list",
                             params={"keyword": tag, "page_size": 100})
        assert r.status_code == 200
        data = r.json()
        got = [i["id"] for i in data["items"]]
        assert sorted(got) == sorted(ids), f"应只命中新建的 2 张卡，实际 {got}"
        assert data["total"] == 2

    def test_keyword_by_category(self, admin_client, tagged_cards):
        """分类也应参与匹配（实现为 title OR category LIKE）"""
        tag, _ = tagged_cards
        r = admin_client.get("/api/materials/admin/list",
                             params={"keyword": "知觉速度与准确性", "page_size": 100})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(tag in (i.get("title") or "") for i in items), "分类匹配结果里应含刚建的卡"

    def test_keyword_no_match_returns_empty(self, admin_client):
        r = admin_client.get("/api/materials/admin/list",
                             params={"keyword": "ZZ绝不可能命中" + uuid.uuid4().hex})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_empty_keyword_returns_more_than_zero(self, admin_client):
        r = admin_client.get("/api/materials/admin/list", params={"keyword": ""})
        assert r.status_code == 200
        assert r.json()["total"] > 0, "空关键词不应过滤掉全部结果"

    def test_student_forbidden(self):
        """权限：非管理员访问管理列表应 403"""
        from app.main import app

        c = TestClient(app)
        login = c.post("/api/auth/login",
                       data={"username": "202516001", "password": "test123456"})
        if login.status_code != 200:
            pytest.skip("无可用学生测试账号")
        c.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
        r = c.get("/api/materials/admin/list", params={"keyword": "x"})
        assert r.status_code == 403
