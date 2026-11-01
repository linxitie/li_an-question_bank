# -*- coding: utf-8 -*-
"""T2/T4/T5 接口测试：精选徽章、墙顺序、金币字段、快照估算标记。

用学生账号（202516001）跑真实接口；账号无已获得徽章时自动 skip。
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def stu():
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/auth/login", data={"username": "202516001",
                                        "password": "test123456"})
    if r.status_code != 200:
        pytest.skip("无可用学生账号")
    c.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return c


@pytest.fixture()
def owned_ids(stu):
    r = stu.get("/api/badges/my", params={"only_owned": True, "kind": "achievement"})
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"] if i.get("owned")]
    if len(ids) < 2:
        pytest.skip("该账号已获得徽章不足 2 枚")
    return ids


class TestBadgeTop:
    def test_set_order_then_wall(self, stu, owned_ids):
        pick = owned_ids[:2][::-1]
        r = stu.put("/api/badges/top", json={
            "items": [{"kind": "achievement", "id": x} for x in pick]})
        assert r.status_code == 200, r.text
        assert [i["id"] for i in r.json()["items"]] == pick

        wall = stu.get("/api/badges/wall", params={"limit": 6}).json()
        assert [i["id"] for i in wall["items"][:2]] == pick, "墙应按精选顺序排列"
        assert all(i.get("pinned") for i in wall["items"][:2])
        assert any(not i.get("pinned") for i in wall["items"][2:]) or len(wall["items"]) <= 2

    def test_clear_top(self, stu):
        r = stu.put("/api/badges/top", json={"items": []})
        assert r.status_code == 200
        assert r.json()["count"] == 0
        assert stu.get("/api/badges/top").json()["items"] == []

    def test_unowned_rejected(self, stu):
        r = stu.put("/api/badges/top", json={
            "items": [{"kind": "achievement", "id": 999999}]})
        assert r.status_code == 400
        assert "尚未获得" in r.text

    def test_more_than_six_rejected(self, stu):
        r = stu.put("/api/badges/top", json={
            "items": [{"kind": "achievement", "id": i} for i in range(1, 8)]})
        assert r.status_code == 400
        assert "最多精选" in r.text

    def test_bad_id_type_rejected(self, stu):
        r = stu.put("/api/badges/top", json={"items": [{"kind": "achievement", "id": "x"}]})
        assert r.status_code == 400

    def test_my_exposes_pinned_flag(self, stu, owned_ids):
        """回归：/api/badges/my 必须回 pinned，否则前端星标与「取消精选」永远不出现。"""
        pick = owned_ids[:2]
        assert stu.put("/api/badges/top", json={
            "items": [{"kind": "achievement", "id": x} for x in pick]}).status_code == 200
        try:
            mine = stu.get("/api/badges/my").json()["items"]
            flags = {i["id"]: i.get("pinned") for i in mine if i.get("kind") == "achievement"}
            for bid in pick:
                assert flags.get(bid) is True, f"精选徽章 {bid} 的 pinned 应为 True"
            others = [i["id"] for i in mine
                      if i.get("kind") == "achievement" and i.get("owned") and i["id"] not in pick]
            for bid in others:
                assert flags.get(bid) is False, f"未精选徽章 {bid} 的 pinned 应为 False"
        finally:
            # 还原现场（保持原来 2 枚精选，顺序不变）
            stu.put("/api/badges/top", json={
                "items": [{"kind": "achievement", "id": x} for x in pick]})


class TestBadgeSummaryFields:
    def test_coins_present(self, stu):
        d = stu.get("/api/badges/summary").json()
        assert isinstance(d.get("coins"), int)
        assert d["coins"] >= 0

    def test_snapshot_estimated_flag(self, stu):
        items = stu.get("/api/badges/my", params={"only_owned": True}).json()["items"]
        assert items, "账号应至少拥有 1 枚徽章"
        for it in items:
            assert "snapshot_estimated" in it
            assert isinstance(it["snapshot_estimated"], bool)
