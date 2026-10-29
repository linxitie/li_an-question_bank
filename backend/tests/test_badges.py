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

class TestBadgeWallAndSort:
    """S4：个人主页徽章墙（最近获得）+ 排序/截断 + 稀有度字段"""

    def test_wall_未登录被拒(self):
        from app.main import app

        r = TestClient(app).get("/api/badges/wall")
        assert r.status_code in (401, 403)

    def test_wall_只返回已获得且不超过limit(self, client_with_admin):
        r = client_with_admin.get("/api/badges/wall", params={"limit": 6})
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["items"]) <= 6
        assert all(i["owned"] is True for i in d["items"]), "徽章墙只能出现已获得徽章"
        assert "score" in d and "tier" in d

    def test_wall_含稀有度字段(self, client_with_admin):
        d = client_with_admin.get("/api/badges/wall", params={"limit": 6}).json()
        if not d["items"]:
            pytest.skip("该账号暂无已获得徽章")
        it = d["items"][0]
        assert it["owned_count"] >= 1
        assert 0 <= it["owned_percent"] <= 100

    def test_my_sort_recent_已获得排在前(self, client_with_admin):
        d = client_with_admin.get("/api/badges/my", params={"sort": "recent", "limit": 6}).json()
        assert d["returned"] == len(d["items"])
        if d["owned"]:
            assert d["items"][0]["owned"] is True, "recent 排序应让已获得徽章排在最前"

    def test_my_limit_截断生效(self, client_with_admin):
        d = client_with_admin.get("/api/badges/my", params={"limit": 3}).json()
        assert d["returned"] == 3
        assert len(d["items"]) == 3
        assert d["total"] >= 3, "total 仍应报告总数"

    def test_my_limit_0_表示不限制(self, client_with_admin):
        d = client_with_admin.get("/api/badges/my", params={"limit": 0}).json()
        assert d["returned"] == d["total"]

class TestSnapshotOnGrant:
    """S5：发放时写入「获得时档位快照」"""

    def test_新用户首次登录后快照非空(self):
        """登录会触发「初来乍到」成就；发放时应写入 tier_snapshot（中文档位）"""
        import uuid

        from app.main import app

        c = TestClient(app)
        no = "T9" + uuid.uuid4().hex[:8]
        reg = c.post("/api/auth/register", json={
            "username": no, "password": "Test123456",
            "phone": "139" + uuid.uuid4().hex[:8], "user_no": no, "user_type": "student"
        })
        if reg.status_code != 200:
            pytest.skip(f"注册不可用：{reg.status_code}")
        login = c.post("/api/auth/login", data={"username": no, "password": "Test123456"})
        if login.status_code != 200:
            pytest.skip("登录失败")
        c.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

        d = c.get("/api/badges/my", params={"only_owned": "true"}).json()
        assert d["owned"] >= 1, "首次登录应解锁「初来乍到」"
        owned = [i for i in d["items"] if i["owned"]]
        assert owned, "应有已获得徽章"
        snap = owned[0]["snapshot_tier"]
        assert snap in ("黑铁", "青铜", "白银", "黄金", "钻石"), f"快照应为中文档位，实际 {snap!r}"
