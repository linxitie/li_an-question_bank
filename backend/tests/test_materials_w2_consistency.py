# -*- coding: utf-8 -*-
"""W2 一致性收口（2026-11-09）。

方案里 W2 的四件事，逐条钉成用例：
  1. **`POST /admin` 默认未上架**（D1）：以前不带 status 时走模型默认 1 = 建好就等于审批通过；
  2. **`POST /admin/batch` 同口径**：默认未上架、同内容**跳过**而不是整批回滚；
  3. **上传「立即上架」开关**：`publish=1` 才直接上架，且必须走 P5 联动（卷状态跟着变）；
  4. **`content_hash` 去重**：同内容不重复建（单条 409 / 批量 skip）；
  5. **教师可预览未上架**（D3）：`user_type=teacher` 能看 `status=0` 的详情，学生/游客 404。
"""
import io

from app.models.models import ExamPaper, StudyMaterial


def _docx_bytes(paragraphs=("正文",)):
    from docx import Document
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _create(client, headers, **body):
    payload = {"subject": "gongzhuan", "type": "card",
               "title": "测试卡", "card_front": "正面", "card_back": "背面"}
    payload.update(body)
    return client.post("/api/materials/admin", json=payload, headers=headers)


def _upload(client, headers, filename="讲义.docx", content=None, **form):
    data = {"subject": "gongzhuan", "type": "lecture"}
    data.update({k: str(v) for k, v in form.items()})
    return client.post("/api/materials/admin/files/upload",
                       files={"file": (filename, content or _docx_bytes())},
                       data=data, headers=headers)


class TestDefaultUnpublished:
    def test_create_defaults_to_unpublished(self, client, db_session, admin_headers):
        resp = _create(client, admin_headers, title="默认未上架卡", card_front="甲", card_back="乙")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == 0
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == body["id"]).one()
        assert row.status == 0, "POST /admin 不带 status 必须是未上架（D1）"

    def test_create_can_explicitly_publish(self, client, db_session, admin_headers):
        resp = _create(client, admin_headers, title="显式上架卡",
                       card_front="丙", card_back="丁", status=1)
        assert resp.status_code == 200 and resp.json()["status"] == 1
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == resp.json()["id"]).one()
        assert row.status == 1

    def test_create_rejects_illegal_status(self, client, admin_headers):
        resp = _create(client, admin_headers, title="非法状态", status=2)
        assert resp.status_code == 400 and "status" in resp.json()["detail"]

    def test_batch_create_defaults_unpublished(self, client, db_session, admin_headers):
        resp = client.post("/api/materials/admin/batch", headers=admin_headers,
                           json={"items": [
                               {"subject": "gongzhuan", "type": "card", "title": "批量甲",
                                "card_front": "甲", "card_back": "甲背"},
                               {"subject": "gongzhuan", "type": "card", "title": "批量乙",
                                "card_front": "乙", "card_back": "乙背"},
                           ]})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["created"] == 2
        rows = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id.in_(body["material_ids"])).all()
        assert all(r.status == 0 for r in rows), "批量建也必须默认未上架"


class TestContentHashDedupe:
    def test_create_same_content_returns_409(self, client, admin_headers):
        first = _create(client, admin_headers, title="重复卡A", card_front="同一段正面",
                        card_back="同一段背面")
        assert first.status_code == 200
        second = _create(client, admin_headers, title="重复卡A（副本）",
                         card_front="同一段正面", card_back="同一段背面")
        assert second.status_code == 409
        assert str(first.json()["id"]) in second.json()["detail"]

    def test_batch_create_skips_duplicates_within_batch(self, client, admin_headers):
        item = {"subject": "gongzhuan", "type": "card", "title": "批内重复",
                "card_front": "相同的正面", "card_back": "相同的背面"}
        resp = client.post("/api/materials/admin/batch", headers=admin_headers,
                           json={"items": [item, dict(item, title="批内重复2")]})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["created"] == 1
        assert len(body["skipped_duplicates"]) == 1

    def test_hash_written_for_created_material(self, client, db_session, admin_headers):
        resp = _create(client, admin_headers, title="有哈希卡",
                       card_front="哈希正面", card_back="哈希背面")
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == resp.json()["id"]).one()
        assert row.content_hash and len(row.content_hash) == 32


class TestUploadPublishToggle:
    def test_upload_defaults_unpublished(self, client, db_session, admin_headers):
        body = _upload(client, admin_headers, "默认不上架.docx",
                       _docx_bytes(("默认不上架正文",))).json()
        assert body["published"] is False and body["status"] == 0

    def test_upload_publish_one_marks_published(self, client, db_session, admin_headers):
        body = _upload(client, admin_headers, "立即上架讲义.docx",
                       _docx_bytes(("立即上架正文",)), publish=1).json()
        assert body["published"] is True and body["status"] == 1
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == body["material_id"]).one()
        assert row.status == 1

    def test_upload_publish_syncs_paper_via_p5(self, client, db_session, admin_headers):
        """试卷 + 立即上架 → 卷必须同步变成 PUBLISHED（否则"资料上架了但学生考不了"）。"""
        body = _upload(client, admin_headers,
                       "2019年北京市公务员考试《公安专业科目》真题.docx",
                       _docx_bytes(("题本正文",)), type="paper", placement="both",
                       publish=1, auto_parse=0).json()
        paper_id = body["paper"]["paper_id"]
        db_session.expire_all()
        paper = db_session.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).one()
        assert paper.paper_type == "PUBLISHED"

    def test_upload_without_publish_keeps_paper_draft(self, client, db_session, admin_headers):
        body = _upload(client, admin_headers,
                       "2020年天津市公务员考试《公安专业科目》真题.docx",
                       _docx_bytes(("题本正文",)), type="paper", placement="both",
                       auto_parse=0).json()
        db_session.expire_all()
        paper = db_session.query(ExamPaper).filter(
            ExamPaper.paper_id == body["paper"]["paper_id"]).one()
        assert paper.paper_type == "DRAFT"


class TestTeacherPreviewUnpublished:
    def test_teacher_sees_unpublished_detail(self, client, db_session, admin_headers,
                                             teacher_headers):
        mid = _create(client, admin_headers, title="教师待审稿",
                      card_front="待审正面", card_back="待审背面").json()["id"]
        resp = client.get(f"/api/materials/{mid}", headers=teacher_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == mid

    def test_student_cannot_see_unpublished_detail(self, client, admin_headers, auth_headers):
        mid = _create(client, admin_headers, title="学生看不到的稿",
                      card_front="学生正面", card_back="学生背面").json()["id"]
        resp = client.get(f"/api/materials/{mid}", headers=auth_headers)
        assert resp.status_code == 404

    def test_guest_cannot_see_unpublished_detail(self, client, admin_headers):
        mid = _create(client, admin_headers, title="游客看不到的稿",
                      card_front="游客正面", card_back="游客背面").json()["id"]
        assert client.get(f"/api/materials/{mid}").status_code == 404

    def test_published_still_visible_to_student(self, client, admin_headers, auth_headers):
        mid = _create(client, admin_headers, title="已上架可见",
                      card_front="上架正面", card_back="上架背面", status=1).json()["id"]
        assert client.get(f"/api/materials/{mid}", headers=auth_headers).status_code == 200

    def test_staff_do_not_see_recycled(self, client, db_session, admin_headers, teacher_headers):
        """回收站（status=-1）在详情里谁都不该看到。"""
        mid = _create(client, admin_headers, title="要删的稿",
                      card_front="删正面", card_back="删背面").json()["id"]
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == mid).one()
        row.status = -1
        db_session.commit()
        assert client.get(f"/api/materials/{mid}", headers=teacher_headers).status_code == 404


class TestBatchPublish:
    """2026-11-09 用户点单：批量导入/批量创建要能「一键上架」。

    除了把 status 写 1，**必须**顺带 P5 联动（卷同步 PUBLISHED），
    否则就是历史坑：资料显示已上架，学生点「去考试」却提示"未发布"。
    """

    def _draft_paper(self, db_session, code="BATCH-PUB-1"):
        from app.models.models import ExamPaper
        paper = ExamPaper(
            paper_name="批量上架测试卷", paper_code=code, subject_id=3,
            composition_method="IMPORT", creator_id=1, duration=120,
            total_score=100, difficulty=3, exam_type="SIMULATION",
            paper_type="DRAFT", question_count=2, max_attempts=5,
        )
        db_session.add(paper)
        db_session.commit()
        db_session.refresh(paper)
        return paper

    def test_batch_publish_sets_status_and_syncs_paper(self, client, db_session, admin_headers):
        paper = self._draft_paper(db_session)
        resp = client.post("/api/materials/admin/batch", headers=admin_headers, json={
            "publish": True,
            "items": [{
                "subject": "gongzhuan", "type": "paper", "title": "批量一键上架卷",
                "paper_code": paper.paper_code,
            }],
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["created"] == 1
        assert body["published"] == 1

        from app.models.models import StudyMaterial
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == body["material_ids"][0]).one()
        assert row.status == 1, "publish=true 必须覆盖为已上架"

        db_session.refresh(paper)
        assert paper.paper_type == "PUBLISHED", "上架必须联动卷状态（P5），否则学生考不了"

    def test_batch_without_publish_stays_unpublished(self, client, db_session, admin_headers):
        paper = self._draft_paper(db_session, code="BATCH-PUB-2")
        resp = client.post("/api/materials/admin/batch", headers=admin_headers, json={
            "items": [{
                "subject": "gongzhuan", "type": "paper", "title": "批量不上架卷",
                "paper_code": paper.paper_code,
            }],
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["published"] == 0

        from app.models.models import StudyMaterial
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == body["material_ids"][0]).one()
        assert row.status == 0
        db_session.refresh(paper)
        assert paper.paper_type == "DRAFT", "没勾一键上架就不该动卷状态"
