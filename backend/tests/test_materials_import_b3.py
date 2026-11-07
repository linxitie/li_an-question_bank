# -*- coding: utf-8 -*-
"""B3 回归（2026-11-07）：讲义落 card 的修复 + 重复导入拦截。

两条缺陷（都实测过）：
1. **P1 讲义落 card**：`import_confirm` 只接受 `type=article`，却在建行时用
   `classifier.classify()` 的结果覆盖了它；而 `_classify_document` 把「字数 < 500 的文档」
   一律判成 `card`。于是短讲义被塞进卡片区（实测样本 `04_讲义_正常.docx` 两次导入 → 121/122 都是 card）。
2. **重复导入不拦**：上传阶段没有文件指纹；confirm 阶段算出了 `dup_check` 却只记指标、照样建行
   ——同一个文件导两次就有两份资料。

现在锁死的行为：
- 文档类 `type` 白名单 = article / lecture，**不传默认 lecture**，显式选择优先于分类器；
- 分类器对文档只可能返回 lecture（文档永远不是 card）；
- 同名同大小同 sha256 的文件二次上传 → 409，且消息里带旧记录号；`force=true` 可放行；
- 同内容（不同文件）二次 confirm → 409，`force=true` 可放行，并写一条去重记录。
"""
import io

import pytest

from app.models.models import StudyMaterial
from app.services.material_classifier import MaterialClassifier


def _docx_bytes(paragraphs):
    from docx import Document
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _upload(client, headers, filename, content, force=False):
    data = {"force": "true"} if force else None
    return client.post("/api/materials/admin/import/upload",
                       files={"file": (filename, content)},
                       data=data, headers=headers)


def _confirm(client, headers, import_id, **body):
    payload = {"subject": "gongzhuan"}
    payload.update(body)
    return client.post(f"/api/materials/admin/import/{import_id}/confirm",
                       json=payload, headers=headers)


SHORT_DOC = ["一、公安专业科目考试说明", "本讲义共三章，覆盖职业素养、基础知识、基本能力。"]


class TestDocumentTypeWhitelist:
    def test_default_type_is_lecture(self, client, admin_headers, db_session):
        """不传 type → 讲义（原来会落 card）。"""
        up = _upload(client, admin_headers, "b3_short_lecture.docx",
                     _docx_bytes(SHORT_DOC))
        assert up.status_code == 200, up.text
        iid = up.json()["import_id"]

        resp = _confirm(client, admin_headers, iid)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["type"] == "lecture", data
        mid = data["material_ids"][0]
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == mid).one()
        assert row.type == "lecture"
        assert row.card_front is None and row.card_back is None

    def test_explicit_article_is_honored(self, client, admin_headers, db_session):
        """显式选「作为文章」→ 文章（不允许分类器改回去）。"""
        up = _upload(client, admin_headers, "b3_as_article.docx",
                     _docx_bytes(SHORT_DOC + ["这是时评类短文，不是讲义。"]))
        iid = up.json()["import_id"]
        resp = _confirm(client, admin_headers, iid, type="article")
        assert resp.status_code == 200, resp.text
        assert resp.json()["type"] == "article"
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == resp.json()["material_ids"][0]).one()
        assert row.type == "article"

    def test_explicit_lecture(self, client, admin_headers, db_session):
        up = _upload(client, admin_headers, "b3_as_lecture.docx",
                     _docx_bytes(SHORT_DOC + ["第二章 基础知识。"]))
        iid = up.json()["import_id"]
        resp = _confirm(client, admin_headers, iid, type="lecture")
        assert resp.status_code == 200, resp.text
        assert resp.json()["type"] == "lecture"

    @pytest.mark.parametrize("bad", ["card", "video_intro", "paper", "ARTICLE"])
    def test_other_types_rejected(self, client, admin_headers, bad):
        up = _upload(client, admin_headers, f"b3_bad_{bad}.docx",
                     _docx_bytes(SHORT_DOC + [f"类型 {bad} 不允许。"]))
        iid = up.json()["import_id"]
        resp = _confirm(client, admin_headers, iid, type=bad)
        assert resp.status_code == 400, resp.text
        assert "article" in resp.text and "lecture" in resp.text


class TestClassifierDocumentNeverCard:
    def test_short_document_is_lecture_not_card(self):
        got = MaterialClassifier().classify(".docx", content="短" * 100, title="知识要点卡片")
        assert got["type"] == "lecture", got
        assert "讲义" in got["reason"]

    def test_long_document_is_lecture(self):
        got = MaterialClassifier().classify(".pdf", content="字" * 5000, title="某省考纲")
        assert got["type"] == "lecture", got

    def test_unknown_ext_still_article(self):
        assert MaterialClassifier().classify(".xyz")["type"] == "article"


class TestDuplicateFileUpload:
    def test_same_file_twice_is_rejected(self, client, admin_headers):
        payload = _docx_bytes(SHORT_DOC)
        first = _upload(client, admin_headers, "b3_dup_same.docx", payload)
        assert first.status_code == 200, first.text
        first_id = first.json()["import_id"]
        _confirm(client, admin_headers, first_id)

        second = _upload(client, admin_headers, "b3_dup_same.docx", payload)
        assert second.status_code == 409, second.text
        detail = second.json().get("detail") or ""
        assert f"#{first_id}" in detail, detail
        assert "重复上传" in detail, detail

    def test_force_allows_reupload(self, client, admin_headers):
        payload = _docx_bytes(SHORT_DOC + ["加一行让内容略不同。"])
        first = _upload(client, admin_headers, "b3_force.docx", payload)
        assert first.status_code == 200, first.text
        _confirm(client, admin_headers, first.json()["import_id"], force=True)

        again = _upload(client, admin_headers, "b3_force.docx", payload, force=True)
        assert again.status_code == 200, again.text

    def test_different_name_same_bytes_not_blocked(self, client, admin_headers):
        """同名才按"同一个文件"处理；换名由内容级去重负责（confirm 阶段）。"""
        payload = _docx_bytes(SHORT_DOC + ["换个文件名再传一次。"])
        a = _upload(client, admin_headers, "b3_name_a.docx", payload)
        assert a.status_code == 200, a.text
        b = _upload(client, admin_headers, "b3_name_b.docx", payload)
        assert b.status_code == 200, b.text

    def test_failed_parse_does_not_block_reupload(self, client, admin_headers):
        """解析失败的文件不该占坑：修好后重传同一文件必须能过。"""
        good = _docx_bytes(SHORT_DOC + ["解析失败后重传。"] * 3)
        broken = b"PK\x03\x04not-a-real-docx"
        bad = _upload(client, admin_headers, "b3_broken.docx", broken)
        assert bad.status_code == 200, bad.text
        assert bad.json()["parse_status"] == "failed"

        good_resp = _upload(client, admin_headers, "b3_broken.docx", good)
        assert good_resp.status_code == 200, good_resp.text


class TestDuplicateContentConfirm:
    def test_same_content_different_file_is_rejected(
        self, client, admin_headers, db_session
    ):
        payload = _docx_bytes(SHORT_DOC + ["内容级去重必须命中。"])
        a = _upload(client, admin_headers, "b3_content_a.docx", payload)
        _confirm(client, admin_headers, a.json()["import_id"])

        b = _upload(client, admin_headers, "b3_content_b.docx", payload)
        assert b.status_code == 200, b.text
        resp = _confirm(client, admin_headers, b.json()["import_id"])
        assert resp.status_code == 409, resp.text
        detail = resp.json().get("detail") or ""
        assert "完全相同" in detail, detail
        assert "force=true" in detail, detail

    def test_force_creates_second_copy(self, client, admin_headers, db_session):
        payload = _docx_bytes(SHORT_DOC + ["强制保留两份。"])
        a = _upload(client, admin_headers, "b3_force_a.docx", payload)
        first_ids = _confirm(client, admin_headers, a.json()["import_id"]).json()["material_ids"]

        b = _upload(client, admin_headers, "b3_force_b.docx", payload)
        resp = _confirm(client, admin_headers, b.json()["import_id"], force=True)
        assert resp.status_code == 200, resp.text
        second_ids = resp.json()["material_ids"]

        rows = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id.in_(first_ids + second_ids)).all()
        assert len(rows) == 2, "force=true 应允许保留两份"

    def test_deleted_copy_does_not_block_reimport(
        self, client, admin_headers, db_session
    ):
        """软删（status=-1）后重新导入同内容不该被自己挡住。"""
        payload = _docx_bytes(SHORT_DOC + ["删了再导。"])
        a = _upload(client, admin_headers, "b3_del_a.docx", payload)
        mid = _confirm(client, admin_headers, a.json()["import_id"]).json()["material_ids"][0]
        client.delete(f"/api/materials/admin/{mid}", headers=admin_headers)

        b = _upload(client, admin_headers, "b3_del_b.docx", payload)
        resp = _confirm(client, admin_headers, b.json()["import_id"])
        assert resp.status_code == 200, resp.text
        assert resp.json()["created"] == 1
