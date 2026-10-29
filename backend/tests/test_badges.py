# -*- coding: utf-8 -*-
"""S2 测试：档位判定 / 进度 / 累计积分 / 形状映射 / 徽章接口。

覆盖用户批复的阈值：<200 黑铁 ｜ 200–399 青铜 ｜ 400–599 白银 ｜ 600–799 黄金 ｜ ≥800 钻石
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import badge_service  # noqa: E402


class TestTierOf:
    @pytest.mark.parametrize("score,code,label", [
        (0, "iron", "黑铁"),
        (199, "iron", "黑铁"),
        (200, "bronze", "青铜"),
        (399, "bronze", "青铜"),
        (400, "silver", "白银"),
        (599, "silver", "白银"),
        (600, "gold", "黄金"),
        (799, "gold", "黄金"),
        (800, "diamond", "钻石"),
        (99999, "diamond", "钻石"),
    ])
    def test_边界值(self, score, code, label):
        info = badge_service.tier_of(score)
        assert info["code"] == code, f"{score} 应为 {code}，实际 {info['code']}"
        assert info["label"] == label

    def test_负数按0处理(self):
        assert badge_service.tier_of(-50)["label"] == "黑铁"

    def test_钻石不封顶(self):
        info = badge_service.tier_of(5000)
        assert info["maxed"] is True
        assert info["next_threshold"] is None

    def test_中间档有下一档(self):
        info = badge_service.tier_of(780)
        assert info["label"] == "黄金"
        assert info["next_label"] == "钻石"
        assert info["next_threshold"] == 800


class TestProgress:
    def test_780到钻石还差20分(self):
        p = badge_service.progress_to_next(780)
        assert p["need"] == 20
        assert p["maxed"] is False
        assert 89.0 <= p["percent"] <= 91.0, f"780/黄金段应约 90%，实际 {p['percent']}"

    def test_钻石档进度100且maxed(self):
        p = badge_service.progress_to_next(1200)
        assert p["maxed"] is True
        assert p["percent"] == 100.0

    def test_刚进档进度为0(self):
        p = badge_service.progress_to_next(400)
        assert p["percent"] == 0.0
        assert p["need"] == 200


class TestShape:
    @pytest.mark.parametrize("category,shape", [
        ("社交", "ribbon"),
        ("成长", "ribbon"),
        ("坚持", "shield"),
        ("数量", "shield"),
        ("正确率", "shield"),
        ("错题", "shield"),
        ("综合", "shield"),
    ])
    def test_类别映射(self, category, shape):
        assert badge_service.shape_of(category) == shape

    def test_未知类别默认盾牌(self):
        assert badge_service.shape_of("不存在的类别") == "shield"
        assert badge_service.shape_of(None) == "shield"


class TestSnapshotLabel:
    @pytest.mark.parametrize("idx,label", [
        (0, "黑铁"), (1, "青铜"), (2, "白银"), (3, "黄金"), (4, "钻石"),
    ])
    def test_索引转中文(self, idx, label):
        assert badge_service.tier_label_by_index(idx) == label

    def test_非法索引返回None(self):
        assert badge_service.tier_label_by_index(None) is None
        assert badge_service.tier_label_by_index(9) is None
        assert badge_service.tier_label_by_index("x") is None


@pytest.fixture(scope="module")
def client_with_admin():
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/auth/login", data={"username": "cbrycc", "password": "cbrycc"})
    if r.status_code != 200:
        pytest.skip("无可用管理员账号")
    c.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return c


class TestBadgeApi:
    def test_未登录被拒(self):
        from app.main import app

        r = TestClient(app).get("/api/badges/catalog")
        assert r.status_code in (401, 403)

    def test_目录含成就与称号(self, client_with_admin):
        r = client_with_admin.get("/api/badges/catalog")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 51, f"应至少 48 成就 + 3 称号，实际 {data['total']}"
        kinds = {i["kind"] for i in data["items"]}
        assert kinds == {"achievement", "title"}
        shapes = {i["shape"] for i in data["items"]}
        assert shapes <= {"shield", "ribbon"}, shapes

    def test_概览返回五档与积分(self, client_with_admin):
        r = client_with_admin.get("/api/badges/summary")
        assert r.status_code == 200
        d = r.json()
        assert d["score"] >= 0
        assert d["tier"]["label"] in ("黑铁", "青铜", "白银", "黄金", "钻石")
        assert len(d["tiers"]) == 5
        assert [t["threshold"] for t in d["tiers"]] == [0, 200, 400, 600, 800]
        assert "percent" in d["progress"]

    def test_我的徽章含获得状态(self, client_with_admin):
        r = client_with_admin.get("/api/badges/my")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 51
        assert isinstance(d["owned"], int)
        sample = d["items"][0]
        for k in ("kind", "name", "shape", "owned", "current_tier"):
            assert k in sample, f"缺字段 {k}"
        assert any(i["owned"] for i in d["items"]), "测试账号应至少拥有 1 枚成就徽章"

    def test_按类别过滤(self, client_with_admin):
        r = client_with_admin.get("/api/badges/catalog", params={"category": "坚持"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert items, "坚持类应有徽章"
        assert all(i["category"] == "坚持" for i in items)
