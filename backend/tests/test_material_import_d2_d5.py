# -*- coding: utf-8 -*-
"""D2/D4/D5 回归：导入 confirm 的 publish / skipped / invalid_rows，以及 preview 回传表头。

背景：
- D2 导入一律 status=0，必须逐条手工上线 → 现在支持 body.publish=true 直接上线
- D4 重复内容静默跳过（created=0 仍返回 200）→ 现在返回 skipped 明细
- D5 行级空值静默丢弃 → 现在返回 invalid_rows
- D3 经复核为误判：parse_xlsx 已把表头拆进 headers，故这里断言 preview 能拿到 headers
"""
import io

from app.models.models import StudyMaterial


def _xlsx_bytes(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, headers, filename, content):
    return client.post("/api/materials/admin/import/upload",
                       files={"file": (filename, content)}, headers=headers)


def _confirm(client, headers, import_id, **extra):
    body = {"subject": "xingce", "category": "方法技巧",
            "column_mapping": {"front": 0, "back": 1, "category": 2}}
    body.update(extra)
    return client.post(f"/api/materials/admin/import/{import_id}/confirm",
                       json=body, headers=headers)


CARDS = [
    ["正面", "背面", "分类"],
    ["语句表达·病句辨析", "①成分残缺 ②搭配不当 ③语序不当 ④句式杂糅", "方法技巧"],
    ["类比推理·逻辑关系", "先定关系类型：近义/反义、种属、功能、因果", "方法技巧"],
]


class TestPublishFlag:
    """D2：publish 决定导入后是否直接上线。"""

    def test_publish_true_creates_online_cards(self, client, admin_headers, db_session):
        up = _upload(client, admin_headers, "d2_publish.xlsx", _xlsx_bytes(CARDS))
        assert up.status_code == 200, up.text
        iid = up.json()["import_id"]

        resp = _confirm(client, admin_headers, iid, publish=True)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["published"] is True, data
        assert len(data["material_ids"]) == 2, data

        rows = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id.in_(data["material_ids"])).all()
        assert {r.status for r in rows} == {1}, [r.status for r in rows]

    def test_publish_default_keeps_offline(self, client, admin_headers, db_session):
        up = _upload(client, admin_headers, "d2_default.xlsx", _xlsx_bytes(CARDS))
        iid = up.json()["import_id"]
        resp = _confirm(client, admin_headers, iid)
        data = resp.json()
        assert data["published"] is False, data
        rows = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id.in_(data["material_ids"])).all()
        assert {r.status for r in rows} == {0}


class TestInvalidRows:
    """D5：正面或背面为空的行必须被回报，而不是静默丢弃。"""

    def test_invalid_rows_reported(self, client, admin_headers, db_session):
        rows = [
            ["正面", "背面", "分类"],
            ["有正有背", "正常内容", "方法技巧"],
            ["只有正面", "", "方法技巧"],          # 无效：缺背面
            ["", "只有背面", "方法技巧"],          # 无效：缺正面
        ]
        up = _upload(client, admin_headers, "d5_invalid.xlsx", _xlsx_bytes(rows))
        iid = up.json()["import_id"]
        resp = _confirm(client, admin_headers, iid)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["created"] == 1, data
        assert data["invalid_rows"] == [2, 3], data
        assert data["skipped_count"] == 2, data


class TestDuplicateSkipped:
    """D4：重复导入必须回报被跳过的行，而不是 created=0 静默成功。"""

    def test_duplicate_import_reports_skipped(self, client, admin_headers, db_session):
        payload = _xlsx_bytes(CARDS)
        up1 = _upload(client, admin_headers, "d4_first.xlsx", payload)
        r1 = _confirm(client, admin_headers, up1.json()["import_id"])
        assert r1.json()["created"] == 2, r1.text

        up2 = _upload(client, admin_headers, "d4_second.xlsx", payload)
        r2 = _confirm(client, admin_headers, up2.json()["import_id"])
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert data["created"] == 0, data
        assert data["skipped"], data
        assert all(s["reason"] == "duplicate" for s in data["skipped"]), data


class TestPreviewHeaders:
    """D3 澄清：表头由 parse_xlsx 拆进 headers，preview 应能看到。"""

    def test_preview_returns_headers_and_row_count(self, client, admin_headers):
        up = _upload(client, admin_headers, "d3_header.xlsx", _xlsx_bytes(CARDS))
        iid = up.json()["import_id"]
        resp = client.get(f"/api/materials/admin/import/{iid}/preview",
                          headers=admin_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["headers"] == ["正面", "背面", "分类"], body
        assert body["row_count"] == 2, body
