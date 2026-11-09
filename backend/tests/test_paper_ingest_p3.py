# -*- coding: utf-8 -*-
"""P3 上传即导题（2026-11-09）。

三层覆盖：
  1. `splitter` 纯函数：题号/选项/题型状态/情境材料/告警（最容易被"换一份卷子"打穿的地方）；
  2. `readers`：docx 段落顺序 + 图片归属、不支持格式报错；
  3. 端点全链路：上传即解析 → 草稿 → 改草稿 → 确认入库（题目+挂卷+题量）→ 二次确认 409 / 覆盖。

为什么值得为拆题写这么多：错位入库等于让学生做错题，而且"错得看起来很合理"——
所以这里把每种排版写法都钉成用例。
"""
import io
import json

import pytest

from app.models.models import (ExamPaper, MaterialFile, PaperParseDraft,
                               PaperQuestionRelation, QuestionBank, StudyMaterial)
from app.services.paper_ingest import readers, splitter


# ------------------------------------------------------------------ 造文件
def _png_bytes(width=640, height=320, color=(90, 120, 200)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _docx_bytes(*, with_image=False, paragraphs=None):
    from docx import Document
    from docx.shared import Inches
    doc = Document()
    for text in (paragraphs or []):
        doc.add_paragraph(text)
    if with_image:
        doc.add_picture(io.BytesIO(_png_bytes()), width=Inches(3.2))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


PAPER_LINES = [
    "一、单项选择题（每题 1 分）",
    "1、人民警察首要的政治要求是（　　）。",
    "A、对党忠诚    B、服务人民    C、执法公正    D、纪律严明",
    "2、下列属于治安管理处罚种类的是（　　）。",
    "A．警告",
    "B．拘役",
    "C．罚金",
    "D．管制",
    "二、多项选择题（每题 2 分）",
    "3、人民警察的纪律包括（　　）。",
    "A、政治纪律 B、组织纪律 C、执法纪律 D、保密纪律",
    "三、单项选择题",
    "根据以下情境材料，回答 4~5 题",
    "某市发生一起盗窃案，民警到场处置。",
    "4、民警到达现场首先应当（　　）。",
    "A、保护现场 B、讯问嫌疑人 C、制作笔录 D、通知家属",
    "5、下列说法正确的是（　　）（多选）",
    "A、甲 B、乙 C、丙 D、丁",
]


# ================================================================== splitter
class TestSplitter:
    def test_parses_numbers_options_and_section_types(self):
        items = splitter.split_questions(PAPER_LINES)
        assert [i["no"] for i in items] == [1, 2, 3, 4, 5]
        # 章标题切换默认题型：一、单项选择 → 1/2 单选；二、多项选择 → 3 多选；
        # 三、单项选择 → 4 单选；5 题面上写 （多选）→ 覆盖成多选
        assert [i["type"] for i in items] == ["单选", "单选", "多选", "单选", "多选"]
        assert items[0]["options"]["A"] == "对党忠诚"
        # 一行一个选项也要拆开（A．警告 ...）
        assert items[1]["options"] == {"A": "警告", "B": "拘役", "C": "罚金", "D": "管制"}

    def test_shared_material_attached_to_group(self):
        items = splitter.split_questions(PAPER_LINES)
        grouped = [i for i in items if i["section"]]
        assert [i["no"] for i in grouped] == [4, 5]
        assert grouped[0]["shared"].startswith("某市发生一起盗窃案")
        assert grouped[0]["shared"] == grouped[1]["shared"]
        assert items[0]["shared"] == ""            # 组外不带材料

    def test_inline_type_marker_overrides_section_default(self):
        items = splitter.split_questions(PAPER_LINES)
        # 第 5 题在"多项选择"章里但题面内联 (多选)，仍应判多选；第 4 题无标记 → 该章默认多选
        assert items[4]["type"] == "多选"

    def test_inline_marker_split_by_newline_still_detected(self):
        lines = ["1、下列说法正确的是（多", "选）", "A、甲 B、乙 C、丙 D、丁"]
        items = splitter.split_questions(lines)
        assert items[0]["type"] == "多选"

    def test_year_like_text_is_not_question_number(self):
        lines = ["2023 年 9 月 11 日发生一起案件。", "1、题干（　　）。",
                 "A、甲 B、乙 C、丙 D、丁"]
        items = splitter.split_questions(lines)
        assert [i["no"] for i in items] == [1]

    def test_continuation_line_appends_to_current_option(self):
        lines = ["1、题干（　　）。", "A、第一个选项很长", "被 PDF 折行了",
                 "B、第二个 C、第三个 D、第四个"]
        items = splitter.split_questions(lines)
        assert items[0]["options"]["A"] == "第一个选项很长被 PDF 折行了"
        assert items[0]["options"]["B"] == "第二个"

    def test_flags_for_missing_option_and_figure(self):
        lines = ["1、如图所示，下列说法正确的是（　　）。", "A、甲 B、乙 C、丙"]
        items = splitter.split_questions(lines)
        assert any(f.startswith("选项不全") for f in items[0]["flags"])
        assert "依赖图" in items[0]["flags"]

    def test_no_question_returns_empty_and_warns(self):
        items = splitter.split_questions(["这只是一段说明文字。", "没有题号。"])
        assert items == []
        assert splitter.draft_warnings(items)[0].startswith("没有拆出题目")

    def test_warnings_report_gap_and_duplicate(self):
        lines = ["1、题（　　）。", "A、甲 B、乙 C、丙 D、丁",
                 "1、重复题号（　　）。", "A、甲 B、乙 C、丙 D、丁",
                 "4、跳到 4（　　）。", "A、甲 B、乙 C、丙 D、丁"]
        items = splitter.split_questions(lines)
        warns = splitter.draft_warnings(items)
        assert any("题号重复" in w for w in warns)
        assert any("题号缺号" in w for w in warns)

    def test_clean_cn_removes_cjk_spaces_only(self):
        # 汉字之间的空格（PDF 折行造成）删掉；数字与"年月"之间的空格也删；
        # 但英文单词/字母之间的空格要保留（否则 `A 选项`、`The People` 会被粘错）
        assert splitter.clean_cn("会议指 出，2023 年 5 月") == "会议指出，2023年5月"
        assert splitter.clean_cn("选项 A 与 B") == "选项 A 与 B"


# ================================================================== readers
class TestReaders:
    def test_docx_lines_and_image_attribution(self, tmp_path):
        path = tmp_path / "paper.docx"
        path.write_bytes(_docx_bytes(with_image=True, paragraphs=[
            "一、单项选择题",
            "1、第一题（　　）。", "A、甲 B、乙 C、丙 D、丁",
        ]))
        data = readers.read_any(str(path), "docx")
        assert any("第一题" in ln for ln in data["lines"])
        assert len(data["images"]) == 1
        # 图在最后一段 → 归"它上方最近的题号"= 第 1 题
        assert data["images"][0]["no"] == 1
        items = splitter.split_questions(data["lines"])
        orphans = readers.attach_images(items, data["images"])[0]
        assert orphans == 0
        assert items[0]["images"]

    def test_docx_small_logo_is_dropped(self, tmp_path):
        """几十像素的行内小图不是题图（真实卷子里常出现 logo/水印）。"""
        from docx import Document
        from docx.shared import Inches
        doc = Document()
        doc.add_paragraph("1、题干（　　）。")
        doc.add_paragraph("A、甲 B、乙 C、丙 D、丁")
        doc.add_picture(io.BytesIO(_png_bytes(40, 30)), width=Inches(0.1))
        path = tmp_path / "small.docx"
        doc.save(str(path))
        data = readers.read_any(str(path), "docx")
        assert data["images"] == []

    def test_unsupported_ext_raises(self, tmp_path):
        p = tmp_path / "a.xlsx"
        p.write_bytes(b"PK\x03\x04")
        with pytest.raises(readers.ReaderError):
            readers.read_any(str(p), "xlsx")


# ================================================================== 端点全链路
def _upload_paper(client, headers, filename, content, **form):
    data = {"subject": "gongzhuan", "type": "paper", "placement": "both"}
    data.update({k: str(v) for k, v in form.items()})
    return client.post("/api/materials/admin/files/upload",
                       files={"file": (filename, content)}, data=data, headers=headers)


def _paper_docx(paragraphs=None):
    return _docx_bytes(paragraphs=paragraphs or PAPER_LINES)


class TestUploadParsePipeline:
    def test_upload_parses_into_pending_draft(self, client, db_session, admin_headers):
        body = _upload_paper(client, admin_headers,
                             "2019年北京市公务员考试《公安专业科目》真题.docx",
                             _paper_docx()).json()
        assert body["parse"] is not None
        assert body["parse"]["status"] == "pending"
        assert body["parse"]["item_count"] == 5
        assert body["paper"]["created"] is True        # P1 同时建卷

        draft = db_session.query(PaperParseDraft).filter(
            PaperParseDraft.material_id == body["material_id"]).one()
        assert draft.status == "pending"
        assert draft.paper_id == body["paper"]["paper_id"]
        assert draft.expires_at is not None            # S3：30 天保留
        # 草稿阶段**不能**写题库
        assert db_session.query(QuestionBank).count() == 0

    def test_detail_returns_items_and_can_edit(self, client, db_session, admin_headers):
        mid = _upload_paper(client, admin_headers,
                            "2019年北京市公务员考试《公安专业科目》真题.docx",
                            _paper_docx()).json()["material_id"]
        drafts = client.get("/api/materials/admin/parse-drafts?status=pending",
                            headers=admin_headers).json()
        assert drafts["total"] == 1
        draft_id = drafts["items"][0]["draft_id"]

        detail = client.get(f"/api/materials/admin/parse-drafts/{draft_id}",
                            headers=admin_headers).json()
        assert detail["can_edit"] is True
        items = detail["items"]
        assert [i["no"] for i in items] == [1, 2, 3, 4, 5]

        # 删掉第 5 题、把第 3 题改成单选（模拟人工修正）
        keep = [i for i in items if i["no"] != 5]
        keep[2]["type"] = "单选"
        resp = client.put(f"/api/materials/admin/parse-drafts/{draft_id}/items",
                          json={"items": keep}, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["item_count"] == 4

        bad = client.put(f"/api/materials/admin/parse-drafts/{draft_id}/items",
                         json={"items": [{"no": 1, "type": "单选", "stem": "a"},
                                         {"no": 1, "type": "单选", "stem": "b"}]},
                         headers=admin_headers)
        assert bad.status_code == 400 and "重复" in bad.json()["detail"]
        assert mid

    def test_confirm_creates_questions_relations_and_count(
            self, client, db_session, admin_headers, test_question_type):
        body = _upload_paper(client, admin_headers,
                             "2019年北京市公务员考试《公安专业科目》真题.docx",
                             _paper_docx()).json()
        paper_id = body["paper"]["paper_id"]
        draft_id = body["parse"]["draft_id"]

        resp = client.post(f"/api/materials/admin/parse-drafts/{draft_id}/confirm",
                           json={}, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["created"] == 5
        assert result["paper_id"] == paper_id

        db_session.expire_all()
        paper = db_session.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).one()
        assert paper.question_count == 5
        # 满分同步成"各题分值之和"（5 题 × 1 分 = 5），否则结果页会出现「0 / 100」这种
        # 分母比可得分还大的怪数字（#128 实测：97 题 × 1 分，卷满分却是 100）
        assert float(paper.total_score) == 5.0
        assert result["total_score"] == 5.0
        relations = db_session.query(PaperQuestionRelation).filter(
            PaperQuestionRelation.paper_id == paper_id).all()
        assert len(relations) == 5
        assert [r.question_order for r in relations] == [1, 2, 3, 4, 5]
        assert all(r.question_score for r in relations)

        questions = db_session.query(QuestionBank).all()
        assert len(questions) == 5
        q1 = questions[0]
        assert "人民警察首要的政治要求" in q1.question_content
        assert json.loads(json.dumps(q1.options))[0]["key"] == "A"
        assert q1.answer == ""                    # 决策 ⑤：答案后补
        assert q1.status == 1 and q1.audit_status == 1
        # 情境组的 4/5 题带 level=2 且共享材料写进正文
        grouped = [q for q in questions if "某市发生一起盗窃案" in q.question_content]
        assert len(grouped) == 2
        assert grouped[0].question_level == 2

        db_session.refresh(db_session.query(PaperParseDraft).filter(
            PaperParseDraft.draft_id == draft_id).one())

    def test_confirm_twice_is_rejected(self, client, db_session, admin_headers):
        body = _upload_paper(client, admin_headers,
                             "2019年北京市公务员考试《公安专业科目》真题.docx",
                             _paper_docx()).json()
        draft_id = body["parse"]["draft_id"]
        assert client.post(f"/api/materials/admin/parse-drafts/{draft_id}/confirm",
                           json={}, headers=admin_headers).status_code == 200
        again = client.post(f"/api/materials/admin/parse-drafts/{draft_id}/confirm",
                            json={}, headers=admin_headers)
        assert again.status_code == 400
        assert "已经入库" in again.json()["detail"]

    def test_confirm_rejects_when_paper_has_questions(self, client, db_session,
                                                      admin_headers, test_question_type,
                                                      test_subject, test_admin):
        body = _upload_paper(client, admin_headers,
                             "2019年北京市公务员考试《公安专业科目》真题.docx",
                             _paper_docx()).json()
        paper_id = body["paper"]["paper_id"]
        # 造一道"卷里已有题"的真实数据（判据看关系表实数，不信 question_count 缓存）
        q = QuestionBank(subject_id=test_subject.subject_id,
                         type_id=test_question_type.type_id,
                         question_content="既有题", answer="A", score=1,
                         creator_id=test_admin.user_id)
        db_session.add(q)
        db_session.commit()
        db_session.add(PaperQuestionRelation(paper_id=paper_id,
                                            question_id=q.question_id,
                                            question_order=1, question_score=1))
        db_session.commit()

        resp = client.post(
            f"/api/materials/admin/parse-drafts/{body['parse']['draft_id']}/confirm",
            json={}, headers=admin_headers)
        assert resp.status_code == 409
        assert "已有 1 道题" in resp.json()["detail"]

        # replace=true：只删关系，题目本体保留（可能被错题本/其它卷引用），再重新挂
        again = client.post(
            f"/api/materials/admin/parse-drafts/{body['parse']['draft_id']}/confirm",
            json={"replace": True}, headers=admin_headers)
        assert again.status_code == 200, again.text
        assert again.json()["replaced"] == 1
        assert db_session.query(QuestionBank).filter(
            QuestionBank.question_id == q.question_id).first() is not None

    def test_discard_marks_draft_and_keeps_questions_empty(self, client, db_session,
                                                           admin_headers):
        body = _upload_paper(client, admin_headers,
                             "2019年北京市公务员考试《公安专业科目》真题.docx",
                             _paper_docx()).json()
        draft_id = body["parse"]["draft_id"]
        resp = client.delete(f"/api/materials/admin/parse-drafts/{draft_id}",
                             headers=admin_headers)
        assert resp.status_code == 200 and resp.json()["status"] == "discarded"
        assert client.post(f"/api/materials/admin/parse-drafts/{draft_id}/confirm",
                           json={}, headers=admin_headers).status_code == 400
        assert db_session.query(QuestionBank).count() == 0

    def test_admin_list_exposes_parse_draft(self, client, admin_headers):
        body = _upload_paper(client, admin_headers,
                             "2019年北京市公务员考试《公安专业科目》真题.docx",
                             _paper_docx()).json()
        rows = client.get("/api/materials/admin/list?type=paper&page_size=50",
                          headers=admin_headers).json()["items"]
        row = next(r for r in rows if r["id"] == body["material_id"])
        assert row["parse_draft"]["status"] == "pending"
        assert row["parse_draft"]["item_count"] == 5

    def test_manual_parse_endpoint_is_idempotent_replace_pending(
            self, client, db_session, admin_headers):
        body = _upload_paper(client, admin_headers,
                             "2019年北京市公务员考试《公安专业科目》真题.docx",
                             _paper_docx()).json()
        mid = body["material_id"]
        first = client.post(f"/api/materials/admin/{mid}/parse", headers=admin_headers)
        assert first.status_code == 200, first.text
        second = client.post(f"/api/materials/admin/{mid}/parse", headers=admin_headers)
        assert second.status_code == 200
        # 旧 pending 作废，只留一条待确认（否则列表会冒出两个「待确认」）
        pending = db_session.query(PaperParseDraft).filter(
            PaperParseDraft.material_id == mid,
            PaperParseDraft.status == "pending").all()
        assert len(pending) == 1

    def test_parse_requires_paper_and_file(self, client, db_session, admin_headers):
        lecture = client.post("/api/materials/admin/files/upload",
                              files={"file": ("讲义.docx", _docx_bytes(paragraphs=["正文"]))},
                              data={"subject": "gongzhuan", "type": "lecture"},
                              headers=admin_headers).json()
        resp = client.post(f"/api/materials/admin/{lecture['material_id']}/parse",
                           headers=admin_headers)
        assert resp.status_code == 400 and "试卷" in resp.json()["detail"]

    def test_non_paper_file_fails_without_breaking_upload(self, client, admin_headers):
        """不是题本的文件（这里用一段普通文字）→ 草稿 failed，但资料/原件/卷都正常。"""
        body = _upload_paper(client, admin_headers,
                             "2020年天津市公务员考试《公安专业科目》答案.docx",
                             _docx_bytes(paragraphs=["本文只是答案解析说明，没有题号。"])).json()
        assert body["parse"]["status"] == "failed"
        assert "没有拆出题目" in body["parse"]["message"]
        material = client.get(f"/api/materials/admin/{body['material_id']}/preview",
                              headers=admin_headers).json()
        assert material["files"], "原件仍应留档"
