# -*- coding: utf-8 -*-
"""学生手动建卡（POST /api/materials/my/card）回归：

- 免审批：status 直接为 1，且立刻进公共列表
- 必填/长度/配图数量/图片格式四类校验
- 内容去重 409
- 分类法接口 /api/materials/taxonomy 形状
"""
import base64
import os
import uuid

import pytest

from app.models.models import StudyMaterial

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

IMG_DIR = os.path.join("uploads", "materials", "images")


def _new_user(client):
    uniq = uuid.uuid4().hex[:10]
    user_no = f"2026{uniq[:6]}"
    r = client.post("/api/auth/register", json={
        "username": user_no, "password": "Test123456",
        "phone": f"139{uniq[:8]}", "user_no": user_no, "user_type": "student"})
    assert r.status_code == 200, r.text
    uid = r.json().get("user_id")
    tok = client.post("/api/auth/login",
                      data={"username": user_no, "password": "Test123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, uid


def _form(**kw):
    data = {"subject": "xingce",
            "card_front": "资料分析 基期量" + uuid.uuid4().hex[:4],
            "card_back": "基期 = 现期 /（1 + 增长率）" + uuid.uuid4().hex[:4],
            "category": "", "point_id": ""}
    data.update(kw)
    return data


def _drop_images(*urls):
    for u in urls:
        if not u:
            continue
        p = os.path.join(IMG_DIR, os.path.basename(u))
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


class TestCreateCard:
    def test_publish_immediately_and_visible(self, client, db_session):
        hdr, uid = _new_user(client)
        data = _form()
        r = client.post("/api/materials/my/card", data=data, headers=hdr)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == 1, "学生建卡应免审批立即公开"
        assert body["subject"] == "xingce"
        mid = body["id"]

        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == mid).first()
        assert m is not None and m.creator_id == uid and m.type == "card"
        assert m.status == 1

        pub = client.get("/api/materials", params={"subject": "xingce", "type": "card"})
        assert pub.status_code == 200
        assert mid in [it["id"] for it in pub.json()["items"]], "公开卡应立即出现在列表"

    def test_one_image_becomes_cover(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post("/api/materials/my/card", data=_form(), headers=hdr,
                        files=[("images", ("a.png", PNG_1PX, "image/png"))])
        assert r.status_code == 200, r.text
        body = r.json()
        try:
            assert body["cover_image"].startswith("/uploads/materials/images/")
            assert len(body["images"]) == 1
            assert os.path.exists(os.path.join(IMG_DIR, os.path.basename(body["cover_image"])))
        finally:
            _drop_images(*body.get("images", []))

    def test_two_images_second_goes_to_content(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post(
            "/api/materials/my/card", data=_form(), headers=hdr,
            files=[("images", ("a.png", PNG_1PX, "image/png")),
                   ("images", ("b.png", PNG_1PX, "image/png"))])
        assert r.status_code == 200, r.text
        body = r.json()
        try:
            assert len(body["images"]) == 2
            detail = client.get(f"/api/materials/{body['id']}", headers=hdr).json()
            assert body["images"][1] in (detail.get("content") or "")
        finally:
            _drop_images(*body.get("images", []))

    def test_back_can_be_empty_when_image_present(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post("/api/materials/my/card", data=_form(card_back=""), headers=hdr,
                        files=[("images", ("a.png", PNG_1PX, "image/png"))])
        assert r.status_code == 200, r.text
        _drop_images(*r.json().get("images", []))

    def test_reject_when_no_back_and_no_image(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post("/api/materials/my/card", data=_form(card_back=""), headers=hdr)
        assert r.status_code == 400, r.text
        assert "背面" in r.json()["detail"]

    def test_front_required(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post("/api/materials/my/card", data=_form(card_front="  "), headers=hdr)
        assert r.status_code == 400, r.text

    def test_front_too_long(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post("/api/materials/my/card", data=_form(card_front="字" * 121), headers=hdr)
        assert r.status_code == 400, r.text
        assert "120" in r.json()["detail"]

    def test_image_count_limit(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post(
            "/api/materials/my/card", data=_form(), headers=hdr,
            files=[("images", (f"{i}.png", PNG_1PX, "image/png")) for i in range(3)])
        assert r.status_code == 400, r.text
        assert "2" in r.json()["detail"]

    def test_reject_fake_png_and_no_orphan_row(self, client, db_session):
        hdr, _ = _new_user(client)
        data = _form()
        before = db_session.query(StudyMaterial).count()
        r = client.post("/api/materials/my/card", data=data, headers=hdr,
                        files=[("images", ("evil.png", b"not-a-real-png", "image/png"))])
        assert r.status_code == 400, r.text
        assert db_session.query(StudyMaterial).count() == before, "图片校验失败不得落库"

    def test_duplicate_returns_409(self, client, db_session):
        hdr, _ = _new_user(client)
        data = _form()
        assert client.post("/api/materials/my/card", data=data, headers=hdr).status_code == 200
        r = client.post("/api/materials/my/card", data=data, headers=hdr)
        assert r.status_code == 409, r.text
        assert "重复" in r.json()["detail"]

    def test_invalid_subject(self, client, db_session):
        hdr, _ = _new_user(client)
        r = client.post("/api/materials/my/card", data=_form(subject="nope"), headers=hdr)
        assert r.status_code == 400, r.text

    def test_requires_login(self, client, db_session):
        r = client.post("/api/materials/my/card", data=_form())
        assert r.status_code in (401, 403), r.text


class TestMaterialTaxonomy:
    def test_shape(self, client):
        r = client.get("/api/materials/taxonomy", params={"subject": "xingce"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["subject"] == "xingce"
        assert isinstance(body["categories"], list)
        for c in body["categories"]:
            assert "name" in c and isinstance(c["points"], list)

    def test_invalid_subject(self, client):
        r = client.get("/api/materials/taxonomy", params={"subject": "nope"})
        assert r.status_code == 400

    def test_route_not_shadowed_by_material_id(self, client):
        """/taxonomy 必须声明在 /{material_id} 之前，否则会被整数路径参数吃掉返回 422。"""
        r = client.get("/api/materials/taxonomy", params={"subject": "shenlun"})
        assert r.status_code == 200, f"被 /{{material_id}} 吃掉：{r.status_code} {r.text}"
