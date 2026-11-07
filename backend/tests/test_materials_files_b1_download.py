# -*- coding: utf-8 -*-
"""B1 下载端点 HTTP 用例（2026-11-07）。

与 `test_materials_files_b1.py` 的分工：那边用纯函数/服务函数锁安全边界与存储逻辑，
这边只验**端点**真的把权限与文件正确串起来（6 条）。

注意事项（踩过的坑）：`FileResponse` 是流式响应，用例里必须把响应**读完并关闭**，
否则文件句柄留到下一个 app 生命周期，在 Windows 上会表现为下一条请求卡住。
这里统一用 `with client.stream(...)`。
"""
import io

from app.models.models import MaterialFile, StudyMaterial
from app.services import material_files


def _docx_bytes(paragraphs):
    from docx import Document
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _import_and_get_file(client, headers, filename, paragraphs):
    up = client.post("/api/materials/admin/import/upload",
                     files={"file": (filename, _docx_bytes(paragraphs))},
                     headers=headers)
    assert up.status_code == 200, up.text
    iid = up.json()["import_id"]
    resp = client.post(f"/api/materials/admin/import/{iid}/confirm",
                       json={"subject": "gongzhuan"}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["material_ids"][0]


def _dl(client, file_id, headers=None):
    """下载并读完即关（见模块 docstring）。返回 (status, headers, body_bytes)。"""
    with client.stream("GET", f"/api/materials/files/{file_id}/download",
                       headers=headers or {}) as resp:
        return resp.status_code, dict(resp.headers), resp.read()


def _file_of(db, material_id):
    return (db.query(MaterialFile)
            .filter(MaterialFile.material_id == material_id).one())


class TestDownloadEndpoint:
    def test_admin_download_returns_exact_bytes(self, client, admin_headers, db_session):
        mid = _import_and_get_file(client, admin_headers, "dl_admin.docx",
                                   ["下载验证正文", "管理员应能拿到原件。"])
        row = _file_of(db_session, mid)

        status, headers, body = _dl(client, row.file_id, admin_headers)
        assert status == 200
        assert body[:2] == b"PK"
        assert material_files.sha256_of_bytes(body) == row.sha256
        assert row.file_name in headers.get("content-disposition", "") or "attachment" in headers.get("content-disposition", "")
        assert headers.get("content-type", "").startswith(
            "application/vnd.openxmlformats")

    def test_student_blocked_when_unpublished(self, client, admin_headers,
                                              auth_headers, db_session):
        mid = _import_and_get_file(client, admin_headers, "dl_unpub.docx",
                                   ["未上架资料", "学生不可下载。"])
        row = _file_of(db_session, mid)
        assert db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == mid).one().status == 0

        status, _, body = _dl(client, row.file_id, auth_headers)
        assert status == 403
        assert "未上架".encode() in body

    def test_student_allowed_after_publish(self, client, admin_headers, auth_headers,
                                          db_session):
        mid = _import_and_get_file(client, admin_headers, "dl_pub.docx",
                                   ["上架后", "学生可下载。"])
        row = _file_of(db_session, mid)
        m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
        m.status = 1
        db_session.commit()

        status, _, body = _dl(client, row.file_id, auth_headers)
        assert status == 200
        assert body[:2] == b"PK"

    def test_anonymous_is_401(self, client, admin_headers, db_session):
        mid = _import_and_get_file(client, admin_headers, "dl_anon.docx",
                                   ["匿名", "必须 401。"])
        row = _file_of(db_session, mid)
        status, _, _ = _dl(client, row.file_id)
        assert status == 401

    def test_admin_can_still_download_after_soft_delete(self, client, admin_headers,
                                                        auth_headers, db_session):
        mid = _import_and_get_file(client, admin_headers, "dl_deleted.docx",
                                   ["软删后", "管理员仍可核对原件。"])
        row = _file_of(db_session, mid)
        client.delete(f"/api/materials/admin/{mid}", headers=admin_headers)

        assert _dl(client, row.file_id, admin_headers)[0] == 200
        assert _dl(client, row.file_id, auth_headers)[0] == 403

    def test_missing_and_tampered_paths_are_404(self, client, admin_headers, db_session):
        mid = _import_and_get_file(client, admin_headers, "dl_bad.docx",
                                   ["坏路径", "应当 404。"])
        row = _file_of(db_session, mid)

        assert _dl(client, 99999999, admin_headers)[0] == 404

        row.storage_path = "../../../../etc/passwd"
        db_session.commit()
        status, _, body = _dl(client, row.file_id, admin_headers)
        assert status == 404
        assert b"root:" not in body
