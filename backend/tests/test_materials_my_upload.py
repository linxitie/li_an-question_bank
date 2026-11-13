# -*- coding: utf-8 -*-
"""学生端 Excel 批量上传（POST /api/materials/my/upload）回归。

该通道与「逐张创建」并存：批量导入**进待审队列**（status=0），
逐张创建则免审直接公开（status=1）——两条链路的口径不能串。
"""
import io
import uuid

import pytest
from openpyxl import Workbook

from app.models.models import StudyMaterial


def _new_user(client):
    uniq = uuid.uuid4().hex[:10]
    user_no = f"2026{uniq[:6]}"
    r = client.post("/api/auth/register", json={
        "username": user_no, "password": "Test123456",
        "phone": f"139{uniq[:8]}", "user_no": user_no, "user_type": "student"})
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login",
                      data={"username": user_no, "password": "Test123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _xlsx(rows, headers=("正面", "背面")):
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestStudentExcelUpload:
    def test_xlsx_rows_enter_pending_queue(self, client, db_session):
        hdr = _new_user(client)
        tag = uuid.uuid4().hex[:4]
        data = _xlsx([
            (f"资料分析 基期量{tag}", "基期 = 现期 /（1 + 增长率）"),
            (f"资料分析 增长率{tag}", "增长率 = 增长量 / 基期量"),
        ])
        r = client.post(
            "/api/materials/my/upload", headers=hdr,
            params={"subject": "xingce"},
            files={"file": ("cards.xlsx", data,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["created"] == 2, body
        assert body["status"] == "pending_review"
        ids = body["material_ids"]
        rows = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id.in_(ids)).all()
        assert len(rows) == 2
        assert all(m.status == 0 for m in rows), "批量导入必须进待审队列"

        # 待审的行不出现在公开列表里
        pub = client.get("/api/materials", params={"subject": "xingce", "type": "card"})
        pub_ids = [it["id"] for it in pub.json()["items"]]
        assert not set(ids) & set(pub_ids), "待审卡片泄漏到公开列表"

    def test_csv_supported(self, client, db_session):
        hdr = _new_user(client)
        tag = uuid.uuid4().hex[:4]
        csv_text = f"正面,背面\n判断推理 三段论{tag},所有A是B；所有B是C → 所有A是C\n"
        r = client.post(
            "/api/materials/my/upload", headers=hdr,
            params={"subject": "xingce"},
            files={"file": ("cards.csv", csv_text.encode("utf-8"), "text/csv")})
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 1

    def test_missing_required_column_rejected(self, client, db_session):
        hdr = _new_user(client)
        # 表头缺「背面」→ 阻断级错误（E004），整单 400
        data = _xlsx([("只有正面",)], headers=("正面",))
        r = client.post(
            "/api/materials/my/upload", headers=hdr,
            params={"subject": "xingce"},
            files={"file": ("bad.xlsx", data,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code == 400, r.text
        assert "格式校验未通过" in r.json()["detail"]

    def test_invalid_subject_rejected(self, client, db_session):
        hdr = _new_user(client)
        data = _xlsx([("正面", "背面")])
        r = client.post(
            "/api/materials/my/upload", headers=hdr,
            params={"subject": "nope"},
            files={"file": ("a.xlsx", data,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code == 400

    def test_requires_login(self, client, db_session):
        data = _xlsx([("正面", "背面")])
        r = client.post(
            "/api/materials/my/upload",
            params={"subject": "xingce"},
            files={"file": ("a.xlsx", data,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        assert r.status_code in (401, 403), r.text


class TestBriefImageUrls:
    """列表 brief 必须给出 image_urls（封面 + 正文附图），否则前端「看全图」只有 1 张。"""

    def test_two_images_exposed_in_list(self, client, db_session):
        from tests.test_materials_my_card import PNG_1PX

        hdr = _new_user(client)
        front = f"申论归纳 三遍读法{uuid.uuid4().hex[:6]}"
        r = client.post(
            "/api/materials/my/card", headers=hdr,
            data={"subject": "shenlun", "card_front": front,
                  "card_back": "先总后分，再合并同类项。"},
            files=[("images", ("a.png", PNG_1PX, "image/png")),
                   ("images", ("b.png", PNG_1PX, "image/png"))])
        assert r.status_code == 200, r.text
        body = r.json()
        try:
            lst = client.get("/api/materials",
                             params={"subject": "shenlun", "type": "card", "page_size": 50}).json()
            hit = next((it for it in lst["items"] if it["id"] == body["id"]), None)
            assert hit is not None
            assert hit["image_urls"] == body["images"], hit["image_urls"]
            assert len(hit["image_urls"]) == 2
        finally:
            import os
            for u in body.get("images", []):
                p = os.path.join("uploads", "materials", "images", os.path.basename(u))
                if os.path.exists(p):
                    os.remove(p)

    def test_no_image_gives_empty_list(self, client, db_session):
        hdr = _new_user(client)
        client.post("/api/materials/my/card", headers=hdr,
                    data={"subject": "xingce", "card_front": f"无图卡{uuid.uuid4().hex[:5]}",
                          "card_back": "要点"})
        lst = client.get("/api/materials",
                         params={"subject": "xingce", "type": "card", "page_size": 50}).json()
        assert all(isinstance(it.get("image_urls"), list) for it in lst["items"])
