# -*- coding: utf-8 -*-
"""C1 回归（2026-11-08）：讲义大纲抽取 + 删除单份原件。

C1 要解决的问题：讲义在列表里只有一个标题，管理员看不出多长、分几章；抽屉也没有目录。
做法：上传/导入 docx 时抽 `{word_count, chapter_count, chapters[]}` 存 `study_material.doc_meta`。

删原件是 C2b 的补漏：验收时把 `模拟卷.pdf` 误挂到真题上，没有删除入口只能删整条资料。
"""
import io
from pathlib import Path

import pytest

from app.models.models import MaterialFile, StudyMaterial
from app.services import doc_outline, material_files


def _docx(paragraphs, styles=None):
    """生成 docx：paragraphs 是 [(text, style_name|None)]。"""
    from docx import Document
    doc = Document()
    for text, style in paragraphs:
        para = doc.add_paragraph(text)
        if style:
            para.style = doc.styles[style]
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestExtractOutline:
    def test_heading_styles_win(self):
        data = _docx([
            ("公专冲刺讲义", "Heading 1"),
            ("第一段正文。", None),
            ("1.1 传唤", "Heading 2"),
            ("传唤不是强制措施。", None),
            ("1.2 询问", "Heading 2"),
        ])
        tmp = Path("_outline_test.docx")
        tmp.write_bytes(data)
        try:
            meta = doc_outline.extract_docx_outline(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        assert meta is not None
        assert meta["chapter_count"] == 3
        assert [c["title"] for c in meta["chapters"]] == ["公专冲刺讲义", "1.1 传唤", "1.2 询问"]
        assert [c["level"] for c in meta["chapters"]] == [1, 2, 2]
        assert meta["word_count"] > 0

    def test_numbering_fallback_without_styles(self):
        data = _docx([
            ("第一章 治安管理处罚法", None),
            ("第一节 处罚种类", None),
            ("一、警告与罚款", None),
            ("正文内容。", None),
        ])
        tmp = Path("_outline_test2.docx")
        tmp.write_bytes(data)
        try:
            meta = doc_outline.extract_docx_outline(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        assert [c["level"] for c in meta["chapters"]] == [1, 2, 2], "章=1 节/中文序号=2"

    def test_no_headings_gives_word_count_only(self):
        data = _docx([("没有任何标题的一段话。", None), ("第二段。", None)])
        tmp = Path("_outline_test3.docx")
        tmp.write_bytes(data)
        try:
            meta = doc_outline.extract_docx_outline(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        assert meta is not None
        assert meta["chapters"] == [] and meta["chapter_count"] == 0
        assert meta["word_count"] == len("没有任何标题的一段话。") + len("第二段。")

    def test_broken_file_returns_none(self):
        tmp = Path("_outline_broken.docx")
        tmp.write_bytes(b"not a docx")
        try:
            assert doc_outline.extract_docx_outline(tmp) is None
        finally:
            tmp.unlink(missing_ok=True)

    def test_loads_tolerates_garbage(self):
        assert doc_outline.loads(None) is None
        assert doc_outline.loads("not json") is None
        assert doc_outline.loads('["a"]') is None
        assert doc_outline.loads('{"word_count": 10}') == {"word_count": 10}

    @pytest.mark.parametrize("n,expect", [
        (0, "—"), (None, "—"), (860, "860 字"), (8600, "8600 字"), (12345, "1.2 万字"),
    ])
    def test_human_word_count(self, n, expect):
        assert doc_outline.human_word_count(n) == expect


class TestOutlineOnUpload:
    def test_upload_docx_lecture_writes_doc_meta(self, client, admin_headers, db_session):
        data = _docx([("讲义标题", "Heading 1"), ("正文一。", None), ("1.1 小节", "Heading 2")])
        resp = client.post("/api/materials/admin/files/upload",
                           files={"file": ("大纲测试讲义.docx", data)},
                           data={"subject": "gongzhuan", "type": "lecture"},
                           headers=admin_headers)
        assert resp.status_code == 200, resp.text
        mid = resp.json()["material_id"]

        db_session.expire_all()
        m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
        assert m.doc_meta, "上传 docx 讲义后应写入大纲快照"
        meta = doc_outline.loads(m.doc_meta)
        assert meta["chapter_count"] == 2
        assert meta["word_count"] > 0

        pv = client.get(f"/api/materials/admin/{mid}/preview", headers=admin_headers).json()
        assert [c["title"] for c in pv["chapters"]] == ["讲义标题", "1.1 小节"]
        assert pv["doc"]["chapter_count"] == 2
        assert pv["doc"]["word_count_label"].endswith("字")

    def test_list_row_exposes_chapter_count_and_words(self, client, admin_headers, db_session):
        data = _docx([("第一章 X", None), ("正文。", None)])
        mid = client.post("/api/materials/admin/files/upload",
                          files={"file": ("列表大纲讲义.docx", data)},
                          data={"subject": "gongzhuan", "type": "lecture"},
                          headers=admin_headers).json()["material_id"]
        rows = client.get("/api/materials/admin/list", headers=admin_headers,
                          params={"type": "lecture"}).json()["items"]
        hit = [r for r in rows if r["id"] == mid][0]
        assert hit["chapter_count"] == 1
        assert hit["word_count"] and hit["word_count"] > 0

    def test_pdf_lecture_has_no_outline(self, client, admin_headers, db_session):
        pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
        mid = client.post("/api/materials/admin/files/upload",
                          files={"file": ("无大纲讲义.pdf", pdf)},
                          data={"subject": "gongzhuan", "type": "lecture"},
                          headers=admin_headers).json()["material_id"]
        db_session.expire_all()
        m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
        assert m.doc_meta is None, "PDF 没有样式信息，不硬抽目录"
        pv = client.get(f"/api/materials/admin/{mid}/preview", headers=admin_headers).json()
        assert pv["chapters"] == []
        assert pv["doc"]["word_count"] is None and pv["doc"]["word_count_label"] == "—"


def _mk_material_with_file(client, headers, db, name="删原件用例.docx"):
    data = _docx([("标题", "Heading 1"), ("正文。", None)])
    mid = client.post("/api/materials/admin/files/upload",
                      files={"file": (name, data)},
                      data={"subject": "gongzhuan", "type": "lecture"},
                      headers=headers).json()["material_id"]
    row = db.query(MaterialFile).filter(MaterialFile.material_id == mid).first()
    return mid, row


class TestDeleteFile:
    def test_delete_removes_row_and_physical_file(self, client, admin_headers, db_session):
        mid, row = _mk_material_with_file(client, admin_headers, db_session)
        path = material_files.resolve_abs_path(row)
        assert path.is_file()

        resp = client.delete(f"/api/materials/admin/{mid}/files/{row.file_id}",
                             headers=admin_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"]["physical_deleted"] is True
        assert body["files"] == []
        assert not path.exists(), "没有别的引用时应删物理文件"

        db_session.expire_all()
        assert db_session.query(MaterialFile).filter(
            MaterialFile.file_id == row.file_id).first() is None

    def test_content_addressed_file_kept_when_still_referenced(self, client, admin_headers,
                                                              db_session):
        mid_a, row_a = _mk_material_with_file(client, admin_headers, db_session, "共享内容.docx")
        # 同一份字节再挂到另一条资料（内容寻址 → 同一个物理文件）
        mid_b = client.post("/api/materials/admin/files/upload",
                            files={"file": ("共享内容.docx", _docx([("标题", "Heading 1"), ("正文。", None)]))},
                            data={"subject": "gongzhuan", "type": "lecture"},
                            headers=admin_headers).json()
        if mid_b.get("duplicate"):
            # 内容重复被拦（B2 的去重），直接手工建一条引用同一 sha 的记录
            m = StudyMaterial(subject="gongzhuan", type="lecture", title="引用同内容", status=0)
            db_session.add(m)
            db_session.commit()
            saved = material_files.save_from_path(
                db_session, m.material_id, material_files.resolve_abs_path(row_a),
                "共享内容.docx", role="primary", source="upload")
            db_session.commit()
            mid_b = {"material_id": m.material_id, "file_id": saved.file_id}

        path = material_files.resolve_abs_path(row_a)
        resp = client.delete(f"/api/materials/admin/{mid_a}/files/{row_a.file_id}",
                             headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["deleted"]["physical_deleted"] is False
        assert path.exists(), "还有别的资料引用同一内容时不能删物理文件"

    def test_wrong_material_or_file_is_404(self, client, admin_headers, db_session):
        mid, row = _mk_material_with_file(client, admin_headers, db_session)
        assert client.delete(f"/api/materials/admin/{mid + 999}/files/{row.file_id}",
                             headers=admin_headers).status_code == 404
        assert client.delete(f"/api/materials/admin/{mid}/files/99999999",
                             headers=admin_headers).status_code == 404

    def test_teacher_forbidden(self, client, admin_headers, teacher_headers, db_session):
        mid, row = _mk_material_with_file(client, admin_headers, db_session)
        assert client.delete(f"/api/materials/admin/{mid}/files/{row.file_id}",
                             headers=teacher_headers).status_code == 403
