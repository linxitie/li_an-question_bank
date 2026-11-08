# -*- coding: utf-8 -*-
"""B2 后端回归（2026-11-07）：批量导入的单文件入口。

端点 `POST /api/materials/admin/files/upload`：
- 不带 `material_id` → 建一条资料（status=0）+ 原件 `primary`；
- 带 `material_id` → 只挂 `attachment`（双格式配对：docx 主文件 + pdf 附件）；
- 同内容（sha256）**不重复建**，返回 `duplicate=true` 与已存在资料 id；
- 扩展名 + magic bytes + 单文件 20MB 三重校验；非管理员 403。

为什么逐个文件而不是一次 50 个：见端点 docstring（进度/重试/跳过重复）。
"""
import io

import pytest

from app.models.models import MaterialFile, StudyMaterial
from app.services import material_files


def _docx_bytes(text="批量导入正文"):
    from docx import Document
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_bytes(text="PDF 原件"):
    """最小可识别 PDF（只校验 %PDF magic 与前缀，不要求结构完整）。"""
    body = (
        "%PDF-1.4\n"
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        f"% {text}\n"
        "trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    return body.encode("utf-8")


def _upload(client, headers, filename, content, **form):
    data = {"subject": "gongzhuan", "type": "lecture"}
    data.update({k: str(v) for k, v in form.items()})
    return client.post("/api/materials/admin/files/upload",
                       files={"file": (filename, content)},
                       data=data, headers=headers)


class TestCreateFromFile:
    def test_creates_unpublished_material_with_primary_file(
        self, client, admin_headers, db_session
    ):
        resp = _upload(client, admin_headers, "公专-讲义-第一章.docx",
                       _docx_bytes("第一章 职业素养"))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["duplicate"] is False
        assert body["created"] is True

        material = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == body["material_id"]).one()
        assert material.status == 0                     # 批量导入默认不上架
        assert material.type == "lecture"
        assert material.subject == "gongzhuan"
        assert material.title == "公专-讲义-第一章"      # 缺省用文件名（去扩展名）

        row = db_session.query(MaterialFile).filter(
            MaterialFile.material_id == material.material_id).one()
        assert row.role == "primary"
        assert row.source == "upload"
        assert material_files.resolve_abs_path(row).is_file()

    def test_type_and_category_respected(self, client, admin_headers, db_session):
        resp = _upload(client, admin_headers, "2019-北京公专.docx", _docx_bytes("试卷正文"),
                       type="paper", title="2019 北京公专", category="基础知识")
        assert resp.status_code == 200, resp.text
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == resp.json()["material_id"]).one()
        assert m.type == "paper"
        assert m.title == "2019 北京公专"
        assert m.category == "基础知识"

    def test_preview_lists_the_file(self, client, admin_headers, db_session):
        mid = _upload(client, admin_headers, "预览用讲义.docx", _docx_bytes()).json()["material_id"]
        pv = client.get(f"/api/materials/admin/{mid}/preview", headers=admin_headers).json()
        assert len(pv["files"]) == 1
        assert pv["files"][0]["file_name"] == "预览用讲义.docx"
        assert pv["files"][0]["role_label"] == "主文件"


class TestPairing:
    def test_attach_second_file_to_same_material(self, client, admin_headers, db_session):
        first = _upload(client, admin_headers, "2024-国考-题本.docx",
                        _docx_bytes("题本正文"))
        assert first.status_code == 200, first.text
        mid = first.json()["material_id"]

        second = _upload(client, admin_headers, "2024-国考-题本.pdf",
                         _pdf_bytes(), material_id=mid)
        assert second.status_code == 200, second.text
        assert second.json()["created"] is False
        assert second.json()["material_id"] == mid

        pv = client.get(f"/api/materials/admin/{mid}/preview", headers=admin_headers).json()
        roles = [(f["file_name"], f["role"], f["role_label"]) for f in pv["files"]]
        assert ("2024-国考-题本.docx", "primary", "主文件") in roles
        assert ("2024-国考-题本.pdf", "attachment", "附件") in roles
        # 主文件排前面
        assert pv["files"][0]["role"] == "primary"

    def test_attach_to_missing_material_is_404(self, client, admin_headers):
        resp = _upload(client, admin_headers, "孤儿附件.pdf", _pdf_bytes(),
                       material_id=99999999)
        assert resp.status_code == 404

    def test_attach_to_deleted_material_is_404(self, client, admin_headers, db_session):
        mid = _upload(client, admin_headers, "将删.docx", _docx_bytes("将删正文")).json()["material_id"]
        client.delete(f"/api/materials/admin/{mid}", headers=admin_headers)
        resp = _upload(client, admin_headers, "将删.pdf", _pdf_bytes(), material_id=mid)
        assert resp.status_code == 404

    def test_same_name_different_content_both_accepted(self, client, admin_headers,
                                                       db_session):
        a = _upload(client, admin_headers, "同名.docx", _docx_bytes("版本 A"))
        b = _upload(client, admin_headers, "同名.docx", _docx_bytes("版本 B"))
        assert a.status_code == 200 and b.status_code == 200
        assert a.json()["material_id"] != b.json()["material_id"]


class TestDuplicate:
    def test_same_bytes_returns_duplicate_without_new_material(
        self, client, admin_headers, db_session
    ):
        payload = _docx_bytes("完全相同的讲义")
        first = _upload(client, admin_headers, "重复讲义.docx", payload)
        assert first.status_code == 200, first.text
        mid = first.json()["material_id"]
        before = db_session.query(StudyMaterial).count()

        again = _upload(client, admin_headers, "重复讲义-副本.docx", payload)
        assert again.status_code == 200, again.text
        body = again.json()
        assert body["duplicate"] is True
        assert body["created"] is False
        assert body["material_id"] == mid
        assert db_session.query(StudyMaterial).count() == before, "重复内容不该再建资料"

    def test_duplicate_of_soft_deleted_material_is_allowed(
        self, client, admin_headers, db_session
    ):
        payload = _docx_bytes("删掉后重传")
        mid = _upload(client, admin_headers, "删掉重传.docx", payload).json()["material_id"]
        client.delete(f"/api/materials/admin/{mid}", headers=admin_headers)

        again = _upload(client, admin_headers, "删掉重传.docx", payload)
        assert again.status_code == 200, again.text
        assert again.json()["duplicate"] is False
        assert again.json()["material_id"] != mid


class TestValidation:
    def test_teacher_forbidden(self, client, teacher_headers):
        resp = _upload(client, teacher_headers, "越权.docx", _docx_bytes())
        assert resp.status_code == 403

    @pytest.mark.parametrize("filename,content,expect", [
        ("错扩展名.txt", b"hello", "仅支持"),
        ("假 docx.docx", b"not-a-zip", "格式与扩展名不符"),
        ("空.docx", b"", "空文件"),
    ])
    def test_bad_files_rejected(self, client, admin_headers, filename, content, expect):
        resp = _upload(client, admin_headers, filename, content)
        assert resp.status_code == 400, resp.text
        assert expect in resp.text

    def test_invalid_subject_and_type(self, client, admin_headers):
        bad_subject = client.post("/api/materials/admin/files/upload",
                                  files={"file": ("a.docx", _docx_bytes())},
                                  data={"subject": "yuwen", "type": "lecture"},
                                  headers=admin_headers)
        assert bad_subject.status_code == 400
        bad_type = _upload(client, admin_headers, "b.docx", _docx_bytes(), type="card")
        assert bad_type.status_code == 400
        assert "article / lecture / paper" in bad_type.text

    def test_xlsx_accepted_as_file(self, client, admin_headers, db_session):
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.append(["正面", "背面"])
        wb.active.append(["题", "答"])
        buf = io.BytesIO()
        wb.save(buf)
        resp = _upload(client, admin_headers, "卡片表.xlsx", buf.getvalue(), type="article")
        assert resp.status_code == 200, resp.text
        row = db_session.query(MaterialFile).filter(
            MaterialFile.material_id == resp.json()["material_id"]).one()
        assert row.file_ext == "xlsx"

class TestAttachRoleAuto:
    """C2b：给「还没有原件」的资料补档时，这一份要落成主文件，而不是附件。"""

    def test_first_file_becomes_primary(self, client, admin_headers, db_session):
        # 建一条没有原件的试卷资料，再挂一份 pdf
        from app.models.models import StudyMaterial
        m = StudyMaterial(subject="gongzhuan", type="paper", title="无原件的试卷", status=0)
        db_session.add(m)
        db_session.commit()

        resp = _upload(client, admin_headers, "补的原卷.pdf", _pdf_bytes(),
                       type="paper", material_id=m.material_id)
        assert resp.status_code == 200, resp.text
        row = db_session.query(MaterialFile).filter(
            MaterialFile.material_id == m.material_id).one()
        assert row.role == "primary", "补档的第一份必须是主文件"

    def test_second_file_becomes_attachment(self, client, admin_headers, db_session):
        from app.models.models import StudyMaterial
        m = StudyMaterial(subject="gongzhuan", type="paper", title="已有原件的试卷", status=0)
        db_session.add(m)
        db_session.commit()
        _upload(client, admin_headers, "第一份.pdf", _pdf_bytes("v1"),
                type="paper", material_id=m.material_id)
        _upload(client, admin_headers, "第二份.docx", _docx_bytes("第二份正文"),
                type="paper", material_id=m.material_id)

        roles = {r.role for r in db_session.query(MaterialFile).filter(
            MaterialFile.material_id == m.material_id).all()}
        assert roles == {"primary", "attachment"}

class TestPaperCodeFromFileName:
    """C2a 接线（2026-11-08）：试卷上传时按文件名生成编号，不能只靠补录/改信息生成。

    验收时发现：`2024国考·公专题本.docx` 走 B2 上传后编号为空（material 127）。
    """

    def test_upload_paper_gets_code_from_file_name(self, client, admin_headers, db_session):
        resp = _upload(client, admin_headers, "2024国考·公专题本.docx",
                       _docx_bytes("2024 国考题本"), type="paper")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == body["material_id"]).one()
        assert m.paper_code == "GZ-2024-GK-T"
        assert m.badge == "GZ-2024-GK-T", "列表副标题取 badge"

        # 预览侧：编号/年份/地区/卷别 都能出，题量等留空（没有可作答卷）
        pv = client.get(f"/api/materials/admin/{m.material_id}/preview",
                        headers=admin_headers).json()
        assert pv["paper"]["paper_code"] == "GZ-2024-GK-T"
        assert pv["paper"]["year"] == 2024
        assert pv["paper"]["region_name"] == "国考"
        assert pv["paper"]["book_kind_label"] == "题本"
        assert pv["paper"]["question_count"] is None
        assert pv["paper"]["exam_paper_id"] is None

    def test_unparseable_paper_name_gets_no_code(self, client, admin_headers, db_session):
        resp = _upload(client, admin_headers, "扫描件_001.pdf", _pdf_bytes(), type="paper")
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == resp.json()["material_id"]).one()
        assert m.paper_code is None and m.badge is None, "解析不出就留空，不编造"

    def test_lecture_upload_has_no_paper_code(self, client, admin_headers, db_session):
        resp = _upload(client, admin_headers, "2019北京讲义.docx", _docx_bytes("讲义"), type="lecture")
        m = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == resp.json()["material_id"]).one()
        assert m.paper_code is None
