# -*- coding: utf-8 -*-
"""P1（2026-11-09）上传即建卷。

**为什么要有这一批**：A2 之前，「试卷资料 → 可作答卷」必须由管理员在列表里点一次
「建卷」。#127 就是这样漏掉的：资料上架了、学生端却看不到（`exam_paper` 里没有卷）。
P1 把这一步接进上传链路 —— 投放位是「仅考试页 / 都投」时，上传当场建卷。

用户决策（2026-11-09 批准）：
  ① 只在 `placement ∈ {exam, both}` 触发；纯资料库不建卷（避免 0 题空卷塞满题库）；
  ② 卷名 = 文件名去扩展名（不用资料展示标题）；
  ③ 编号解析不出来（缺年份/地区）**不阻断上传**，只回 hint 让人去补编号。

覆盖：exam/both 建卷、library 不建、附件不复建、同编号幂等、缺年份不建、
表单科目兜底（#128 那条真实文件名）、卷名取文件名、0 题保护、审计留痕。
"""
import io

from app.models.models import ExamPaper, StudyMaterial


def _docx_bytes(text="试卷正文"):
    from docx import Document
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _upload(client, headers, filename, content=None, **form):
    data = {"subject": "gongzhuan", "type": "paper"}
    data.update({k: str(v) for k, v in form.items()})
    return client.post("/api/materials/admin/files/upload",
                       files={"file": (filename, content or _docx_bytes())},
                       data=data, headers=headers)


def _papers_of(db, code):
    db.expire_all()
    return db.query(ExamPaper).filter(ExamPaper.paper_code == code).all()


BJ_2019 = "2019年北京市公务员考试《公安专业科目》真题.docx"


# ------------------------------------------------------------------ 建卷触发
def test_exam_placement_creates_draft_paper(client, db_session, admin_headers):
    resp = _upload(client, admin_headers, BJ_2019, placement="exam")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["created"] is True
    assert body["paper"]["created"] is True
    assert body["paper"]["paper_code"] == "GZ-2019-BJ-T"
    paper = db_session.query(ExamPaper).filter(
        ExamPaper.paper_id == body["paper"]["paper_id"]).one()
    assert paper.paper_type == "DRAFT"        # 一律草稿：能否考由「资料上架」联动
    assert paper.question_count == 0
    assert paper.subject_id == 3              # 公专
    assert paper.composition_method == "IMPORT"

    material = db_session.query(StudyMaterial).filter(
        StudyMaterial.material_id == body["material_id"]).one()
    assert material.status == 0               # 批量导入默认未上架
    assert material.paper_code == "GZ-2019-BJ-T"
    assert material.placement == "exam"


def test_both_placement_creates_paper(client, db_session, admin_headers):
    body = _upload(client, admin_headers, BJ_2019, placement="both").json()
    assert body["paper"]["created"] is True
    assert len(_papers_of(db_session, "GZ-2019-BJ-T")) == 1


def test_library_placement_does_not_create_paper(client, db_session, admin_headers):
    """仅资料页：编号照落（下载/检索要用），但**不建卷** —— 决策 ①。"""
    body = _upload(client, admin_headers, BJ_2019, placement="library").json()
    assert body["paper"] is None
    material = db_session.query(StudyMaterial).filter(
        StudyMaterial.material_id == body["material_id"]).one()
    assert material.paper_code == "GZ-2019-BJ-T"
    assert material.placement == "library"
    assert _papers_of(db_session, "GZ-2019-BJ-T") == []


def test_default_placement_is_both_and_creates_paper(client, db_session, admin_headers):
    """不传 placement 时试卷默认 both（与 L1 之前的行为一致）→ 应当建卷。"""
    body = _upload(client, admin_headers, BJ_2019).json()
    assert body["paper"]["created"] is True


# ------------------------------------------------------------------ 幂等 / 复用
def test_same_code_reuses_paper(client, db_session, admin_headers):
    first = _upload(client, admin_headers, BJ_2019,
                    _docx_bytes("第一份内容"), placement="both").json()
    second = _upload(client, admin_headers, BJ_2019,
                     _docx_bytes("第二份内容不同，sha256 不会命中重复"),
                     placement="both").json()

    assert first["material_id"] != second["material_id"]   # 两份资料
    assert first["paper"]["created"] is True
    assert second["paper"]["created"] is False             # 卷只有一张
    assert second["paper"]["paper_id"] == first["paper"]["paper_id"]
    assert len(_papers_of(db_session, "GZ-2019-BJ-T")) == 1


def test_attachment_upload_does_not_create_new_paper(client, db_session, admin_headers):
    """给已有资料补附件（带 material_id）不该再建卷。"""
    mid = _upload(client, admin_headers, BJ_2019, placement="both").json()["material_id"]
    resp = _upload(client, admin_headers, BJ_2019, _docx_bytes("PDF 版正文"),
                   material_id=mid, placement="both")
    assert resp.status_code == 200, resp.text
    assert resp.json()["paper"] is None
    assert len(_papers_of(db_session, "GZ-2019-BJ-T")) == 1


# ------------------------------------------------------------------ 解析不出编号
def test_missing_year_keeps_material_and_hints(client, db_session, admin_headers):
    """缺年份 → 不建卷，但**资料照建**，回包给可操作 hint（不抛 400）。"""
    body = _upload(client, admin_headers, "北京公专真题.docx", placement="both").json()
    assert body["created"] is True
    assert body["paper"]["created"] is False
    assert body["paper"]["reason"] == "no_code"
    assert "编号" in body["paper"]["hint"]
    material = db_session.query(StudyMaterial).filter(
        StudyMaterial.material_id == body["material_id"]).one()
    assert not (material.paper_code or "").strip()
    assert db_session.query(ExamPaper).count() == 0


def test_missing_region_keeps_material_and_hints(client, db_session, admin_headers):
    body = _upload(client, admin_headers, "2019年公安专业科目真题.docx",
                   placement="both").json()
    assert body["paper"]["reason"] == "no_code"
    assert db_session.query(ExamPaper).count() == 0


def test_form_subject_fills_missing_keyword(client, db_session, admin_headers):
    """#128 真实文件名：「人民警察基础知识」不在科目关键词里 → 用表单科目兜底。

    修复前 `build_paper_code` 因缺 subject 拒绝生成编号，列表里连「建卷」都不出现。
    """
    name = "2016江西招警考试《人民警察基础知识》真题（部分）.docx"
    body = _upload(client, admin_headers, name, placement="both").json()
    assert body["paper"]["created"] is True
    assert body["paper"]["paper_code"] == "GZ-2016-JX-T"


# ------------------------------------------------------------------ 卷名 / 审计
def test_paper_name_uses_file_stem(client, db_session, admin_headers):
    """决策 ②：卷名 = 文件名去扩展名，即使管理端另填了展示标题。"""
    body = _upload(client, admin_headers, BJ_2019, placement="both",
                   title="2019 北京公专真题（精校版）").json()
    paper = db_session.query(ExamPaper).filter(
        ExamPaper.paper_id == body["paper"]["paper_id"]).one()
    material = db_session.query(StudyMaterial).filter(
        StudyMaterial.material_id == body["material_id"]).one()
    assert material.title == "2019 北京公专真题（精校版）"
    assert paper.paper_name == "2019年北京市公务员考试《公安专业科目》真题"


def test_paper_name_without_title_equals_material_title(client, db_session, admin_headers):
    body = _upload(client, admin_headers, BJ_2019, placement="both").json()
    paper = db_session.query(ExamPaper).filter(
        ExamPaper.paper_id == body["paper"]["paper_id"]).one()
    assert paper.paper_name == "2019年北京市公务员考试《公安专业科目》真题"


def test_auto_create_is_audited(client, db_session, admin_headers):
    """自动建卷也要留痕：审计表里能查到这次动作。"""
    from app.models.models import SysOperationLog

    _upload(client, admin_headers, BJ_2019, placement="both")
    rows = db_session.query(SysOperationLog).filter(
        SysOperationLog.operation_type == "自动建卷").all()
    assert rows, "自动建卷没有写审计"
    assert any("GZ-2019-BJ-T" in (r.operation_desc or "") for r in rows)


def test_skipped_auto_create_is_audited_with_reason(client, db_session, admin_headers):
    from app.models.models import SysOperationLog

    _upload(client, admin_headers, "北京公专真题.docx", placement="both")
    rows = db_session.query(SysOperationLog).filter(
        SysOperationLog.operation_type == "自动建卷").all()
    assert rows and "跳过" in (rows[-1].operation_desc or "")
