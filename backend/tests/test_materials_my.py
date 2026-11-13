# -*- coding: utf-8 -*-
"""B1 回归：个人库（status=2）+ 三角色建卡 + 越权防护 + R-1 去重修正。"""
import uuid

from app.models.models import StudyMaterial


def _card_body(**kw):
    body = {"subject": "xingce", "type": "card", "category": "方法技巧",
            "title": "病句辨析要点", "card_front": "语句表达·病句辨析",
            "card_back": "①成分残缺 ②搭配不当 ③语序不当 ④句式杂糅",
            "badge": "技巧", "difficulty": 2}
    body.update(kw)
    return body


def _new_user(client, role="student"):
    """注册并登录一个唯一用户，返回 headers 与 user_id。"""
    uniq = uuid.uuid4().hex[:10]
    user_no = f"2026{uniq[:6]}"
    r = client.post("/api/auth/register", json={
        "username": user_no, "password": "Test123456",
        "phone": f"139{uniq[:8]}", "user_no": user_no, "user_type": role})
    assert r.status_code == 200, r.text
    uid = r.json().get("user_id")
    tok = client.post("/api/auth/login",
                      data={"username": user_no, "password": "Test123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, uid


class TestMyLibraryCreate:
    """学生可建卡，默认进私有库。"""

    def test_student_creates_private_card(self, client, db_session):
        hdr, uid = _new_user(client)
        r = client.post("/api/materials/my", json=_card_body(), headers=hdr)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == 2, data
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == data["id"]).first()
        assert m is not None
        assert m.creator_id == uid
        assert m.status == 2
        assert m.type == "card"

    def test_private_card_not_in_public_list(self, client, db_session, admin_headers):
        hdr, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=hdr).json()["id"]

        pub = client.get("/api/materials", params={"subject": "xingce", "type": "card"})
        assert pub.status_code == 200
        ids = [it["id"] for it in pub.json()["items"]]
        assert mid not in ids, "私有卡泄漏到公共列表"

        # 本人 /my 能看到
        mine = client.get("/api/materials/my", headers=hdr)
        assert mid in [it["id"] for it in mine.json()["items"]]

    def test_publish_true_makes_it_public(self, client, db_session):
        hdr, _ = _new_user(client)
        body = _card_body(title="公开卡" + uuid.uuid4().hex[:6])
        r = client.post("/api/materials/my", json=body, headers=hdr)
        assert r.status_code == 200
        mid = r.json()["id"]

        up = client.put(f"/api/materials/my/{mid}", json={"publish": True}, headers=hdr)
        assert up.status_code == 200, up.text
        assert up.json()["status"] == 1

        pub = client.get("/api/materials", params={"subject": "xingce", "type": "card"})
        assert mid in [it["id"] for it in pub.json()["items"]]


class TestMyLibraryPermission:
    """越权防护：他人不可改/删。"""

    def test_other_user_cannot_update(self, client, db_session):
        h1, _ = _new_user(client)
        h2, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]

        r = client.put(f"/api/materials/my/{mid}", json={"title": "被篡改"}, headers=h2)
        assert r.status_code == 403, r.text
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == mid).first()
        assert m.title != "被篡改"

    def test_other_user_cannot_delete(self, client, db_session):
        h1, _ = _new_user(client)
        h2, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]

        r = client.delete(f"/api/materials/my/{mid}", headers=h2)
        assert r.status_code == 403, r.text

    def test_admin_can_update_any(self, client, db_session, admin_headers):
        h1, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        r = client.put(f"/api/materials/my/{mid}", json={"title": "管理员改名"},
                       headers=admin_headers)
        assert r.status_code == 200, r.text
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == mid).first()
        assert m.title == "管理员改名"

    def test_owner_delete_is_soft(self, client, db_session):
        h1, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        r = client.delete(f"/api/materials/my/{mid}", headers=h1)
        assert r.status_code == 200, r.text
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == mid).first()
        assert m.status == -1, "应为软删(status=-1)"
        mine = client.get("/api/materials/my", headers=h1)
        assert mid not in [it["id"] for it in mine.json()["items"]]


class TestDedupWithPrivateCards:
    """R-1：他人的私有卡不得阻塞我创建相同内容。"""

    def test_other_users_private_card_does_not_block(self, client, db_session):
        h1, _ = _new_user(client)
        h2, _ = _new_user(client)
        same = _card_body(title="同一内容卡" + uuid.uuid4().hex[:6],
                          card_front="相同正面" + uuid.uuid4().hex[:6],
                          card_back="相同背面内容" + uuid.uuid4().hex[:6])

        r1 = client.post("/api/materials/my", json=same, headers=h1)
        assert r1.status_code == 200, r1.text

        r2 = client.post("/api/materials/my", json=same, headers=h2)
        assert r2.status_code == 200, f"他人私有卡不应阻塞我建卡: {r2.text}"
        assert r2.json()["id"] != r1.json()["id"]
