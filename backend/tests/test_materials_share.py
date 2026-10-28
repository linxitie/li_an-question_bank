# -*- coding: utf-8 -*-
"""B2 回归：分享 / 撤回 / 共享区 / 领取（复制语义 + 越权 + 幂等）。"""
import uuid

from app.models.models import StudyMaterial


def _card_body(**kw):
    b = {"subject": "xingce", "type": "card", "category": "方法技巧",
         "title": "分享测试卡 " + uuid.uuid4().hex[:6],
         "card_front": "正面 " + uuid.uuid4().hex[:6],
         "card_back": "①成分残缺 ②搭配不当",
         "badge": "技巧", "difficulty": 2}
    b.update(kw)
    return b


def _new_user(client, role="student"):
    uniq = uuid.uuid4().hex[:10]
    no = f"2027{uniq[:6]}"
    r = client.post("/api/auth/register", json={
        "username": no, "password": "Test123456",
        "phone": f"138{uniq[:8]}", "user_no": no, "user_type": role})
    assert r.status_code == 200, r.text
    uid = r.json()["user_id"]
    tok = client.post("/api/auth/login",
                      data={"username": no, "password": "Test123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, uid


def _create_card_public(client, hdr, **kw):
    """建卡并直接公开，返回 id。"""
    body = _card_body(publish=True, **kw)
    r = client.post("/api/materials/my", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["id"]


class TestShare:
    def test_non_owner_cannot_share(self, client, db_session):
        h1, _ = _new_user(client)
        h2, _ = _new_user(client)
        mid = _create_card_public(client, h1)
        r = client.post(f"/api/materials/{mid}/share", headers=h2)
        assert r.status_code == 403, r.text

    def test_owner_share_appears_in_shared_list(self, client, db_session):
        h1, uid1 = _new_user(client)
        h2, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]

        r = client.post(f"/api/materials/{mid}/share", headers=h1)
        assert r.status_code == 200, r.text

        m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).first()
        assert m.status == 1, "分享后应为公开"

        sh = client.get("/api/materials/shared", headers=h2)
        assert sh.status_code == 200, sh.text
        items = sh.json()["items"]
        hit = [i for i in items if i["id"] == mid]
        assert hit, "共享区应包含该卡"
        assert hit[0]["owner_id"] == uid1
        assert hit[0]["is_mine"] is False

    def test_shared_list_marks_own(self, client, db_session):
        h1, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        client.post(f"/api/materials/{mid}/share", headers=h1)
        mine = [i for i in client.get("/api/materials/shared", headers=h1).json()["items"]
                if i["id"] == mid]
        assert mine and mine[0]["is_mine"] is True


class TestAdopt:
    def test_adopt_copies_private_independent_card(self, client, db_session):
        h1, _ = _new_user(client)
        h2, uid2 = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        client.post(f"/api/materials/{mid}/share", headers=h1)

        r = client.post(f"/api/materials/{mid}/adopt", headers=h2)
        assert r.status_code == 200, r.text
        new_id = r.json()["id"]
        assert new_id != mid
        assert r.json()["source_material_id"] == mid

        new = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == new_id).first()
        assert new.creator_id == uid2
        assert new.status == 2, "领取后应进我的库（私有）"
        assert new.source_material_id == mid

        # 独立性：改自己的副本不影响源卡
        src_before = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).first().title
        up = client.put(f"/api/materials/my/{new_id}", json={"title": "我改过的副本"}, headers=h2)
        assert up.status_code == 200, up.text
        db_session.expire_all()
        src_after = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).first().title
        assert src_after == src_before, "副本修改不得影响源卡"

    def test_adopt_twice_conflicts(self, client, db_session):
        h1, _ = _new_user(client)
        h2, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        client.post(f"/api/materials/{mid}/share", headers=h1)

        assert client.post(f"/api/materials/{mid}/adopt", headers=h2).status_code == 200
        again = client.post(f"/api/materials/{mid}/adopt", headers=h2)
        assert again.status_code == 409, again.text

    def test_cannot_adopt_own(self, client, db_session):
        h1, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        client.post(f"/api/materials/{mid}/share", headers=h1)
        r = client.post(f"/api/materials/{mid}/adopt", headers=h1)
        assert r.status_code == 400, r.text

    def test_adopt_requires_login(self, client, db_session):
        h1, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        client.post(f"/api/materials/{mid}/share", headers=h1)
        r = client.post(f"/api/materials/{mid}/adopt")
        assert r.status_code == 401, r.text


class TestUnshare:
    def test_unshare_removes_from_shared_and_back_to_private(self, client, db_session):
        h1, _ = _new_user(client)
        h2, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        client.post(f"/api/materials/{mid}/share", headers=h1)

        r = client.post(f"/api/materials/{mid}/unshare", headers=h1)
        assert r.status_code == 200, r.text

        db_session.expire_all()
        m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).first()
        assert m.status == 2, "撤回后回私有"

        ids = [i["id"] for i in client.get("/api/materials/shared", headers=h2).json()["items"]]
        assert mid not in ids

        # 撤回后不可领取
        ad = client.post(f"/api/materials/{mid}/adopt", headers=h2)
        assert ad.status_code == 404, ad.text

    def test_non_owner_cannot_unshare(self, client, db_session):
        h1, _ = _new_user(client)
        h2, _ = _new_user(client)
        mid = client.post("/api/materials/my", json=_card_body(), headers=h1).json()["id"]
        client.post(f"/api/materials/{mid}/share", headers=h1)
        r = client.post(f"/api/materials/{mid}/unshare", headers=h2)
        assert r.status_code == 403, r.text
