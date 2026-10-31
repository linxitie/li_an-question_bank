# -*- coding: utf-8 -*-
"""T1：管理员新建成就（词库自动命名）接口测试。

每个用例自建自删，保证 48 枚基线不被污染。
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def admin():
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/auth/login", data={"username": "cbrycc", "password": "cbrycc"})
    if r.status_code != 200:
        pytest.skip("无可用管理员账号")
    c.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return c


@pytest.fixture(scope="module")
def student():
    from app.main import app

    c = TestClient(app)
    r = c.post("/api/auth/login", data={"username": "202516001",
                                        "password": "test123456"})
    if r.status_code != 200:
        pytest.skip("无可用学生账号")
    c.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return c


@pytest.fixture()
def created(admin):
    """建一枚，用完删掉并把词库 used 复位。"""
    body = {"category": "数量", "condition_code": "total_questions",
            "threshold": 3000, "reward_coins": 30}
    r = admin.post("/api/achievements/admin", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    from app.core.database import SessionLocal
    from app.models.models import Achievement, BadgeNameBank, UserAchievement
    s = SessionLocal()
    try:
        s.query(UserAchievement).filter(
            UserAchievement.achievement_id == data["id"]).delete()
        s.query(Achievement).filter(
            Achievement.achievement_id == data["id"]).delete()
        s.query(BadgeNameBank).filter(
            BadgeNameBank.name == data["name"]).update({"used": 0})
        s.commit()
    finally:
        s.close()


class TestAchievementAdmin:
    def test_created_with_bank_name(self, created):
        assert created["named_from_bank"] is True
        assert created["name"], "必须从词库拿到名字"
        assert created["badge_tier"] in ("黑铁", "青铜", "白银", "黄金", "钻石")

    def test_tier_from_threshold(self, created):
        # 3000 题 → 黄金（与历史回填口径一致）
        assert created["badge_tier"] == "黄金"

    def test_bank_used_incremented(self, admin, created):
        d = admin.get("/api/achievements/name-bank/status").json()
        assert d["used"] >= 1
        assert d["left"] == d["total"] - d["used"]

    def test_duplicate_name_conflict(self, admin, created):
        r = admin.post("/api/achievements/admin", json={
            "name": created["name"], "category": "数量",
            "condition_code": "total_questions", "threshold": 3000})
        assert r.status_code == 409
        assert "已存在" in r.text

    def test_missing_required_field(self, admin):
        r = admin.post("/api/achievements/admin", json={"category": "数量"})
        assert r.status_code == 400

    def test_student_forbidden(self, student):
        r = student.post("/api/achievements/admin", json={
            "category": "数量", "condition_code": "total_questions",
            "threshold": 1000})
        assert r.status_code == 403

    def test_bank_status_requires_admin(self, student):
        assert student.get("/api/achievements/name-bank/status").status_code == 403
