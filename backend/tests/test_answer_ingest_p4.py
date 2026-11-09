# -*- coding: utf-8 -*-
"""P4 答案上传（2026-11-09）。

用户「按建议」批准的 4 条决策逐条钉成用例：
  Q1 已有答案不同 → **默认保留**（`kept`），`overwrite=true` 才覆盖；
  Q2 推断层（L3）→ **只给建议不自动填**（answer 为空、suggestion 有值）；
  Q3 解析正文 → 一起写 `answer_analysis`；
  Q4 不做"按文件名自动匹配卷" → 题号不属于该卷直接阻断。

外加实测踩过的两个坑：**幻影题号**（解析里的编号列表）与 **列举被吞**（`A、B、C 项：正确`）。
"""
import io
import json

import pytest

from app.models.models import (ExamPaper, PaperAnswerDraft, PaperQuestionRelation,
                               QuestionBank, StudyMaterial)
from app.services.answer_ingest import extractor

ANSWER_PDF_TEXT = """1、A 本题考查公安时政。2023 年 9 月 28 日，公安部党委会议在京召开。
2、B 本题考查公安时政。2023 年 4 月 12 日，公安部召开主题教育动员部署会议。
3、正确答案为 D。本题考查宣传思想文化工作。
4、A、B、C 项：正确，D 项：正确，故本题全选。
5、故本题选 BC。
6、本题考查某知识点，A 项正确，C 项正确，B 项错误。
7、这一段没有任何答案线索，只有解析。
2.重点环节。1 控制场所。这是解析里的编号列表，不该被当成第 2 题。
"""

PLAIN_TEXT = """1 A
2 B
3 D
"""


# ------------------------------------------------------------------ 造卷
def _make_paper(db, subject_id, type_id, creator_id, *,
                code="P4-T-1", count=4, types=None, with_answers=False):
    paper = ExamPaper(
        paper_name=f"P4 测试卷 {code}", paper_code=code, subject_id=subject_id,
        composition_method="MANUAL", creator_id=creator_id, duration=120,
        total_score=100, difficulty=3, exam_type="SIMULATION",
        paper_type="PUBLISHED", question_count=count, max_attempts=5,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    for i in range(1, count + 1):
        tid = (types or {}).get(i, 1)
        q = QuestionBank(subject_id=subject_id, type_id=tid,
                         question_content=f"<p>第 {i} 题题干</p>",
                         options=[{"key": "A", "value": "甲"}, {"key": "B", "value": "乙"}],
                         answer=("A" if with_answers else ""),
                         answer_analysis="",
                         difficulty=3, score=1, creator_id=creator_id,
                         status=1, audit_status=1)
        db.add(q)
        db.commit()
        db.refresh(q)
        db.add(PaperQuestionRelation(paper_id=paper.paper_id, question_id=q.question_id,
                                    question_order=i, question_score=1))
    db.commit()
    return paper


# ================================================================== extractor
class TestExtractor:
    def test_four_tiers(self):
        items = {it["no"]: it for it in extractor.parse_text(ANSWER_PDF_TEXT)}
        assert items[1]["answer"] == "A" and items[1]["tier"] == "L0"
        assert items[2]["answer"] == "B" and items[2]["tier"] == "L0"
        assert items[3]["answer"] == "D" and items[3]["tier"] == "L1"
        assert items[5]["answer"] == "BC" and items[5]["tier"] == "L2"

    def test_phantom_question_number_keeps_first(self):
        """解析里的 `2.重点环节…` 不能覆盖真实第 2 题（实测 2024 国考就是这样被顶掉的）。"""
        items = extractor.parse_text(ANSWER_PDF_TEXT)
        second = [it for it in items if it["no"] == 2]
        assert len(second) == 1
        assert second[0]["answer"] == "B"

    def test_enumeration_not_swallowed_by_L0(self):
        """`4、A、B、C 项：正确…` 不能被读成 `A`（真实答案 ABCD）。"""
        it = {i["no"]: i for i in extractor.parse_text(ANSWER_PDF_TEXT)}[4]
        assert it["answer"] != "A"

    def test_inference_layer_only_suggests(self):
        """Q2：推断层只给建议，answer 必须为空。"""
        it = {i["no"]: i for i in extractor.parse_text(ANSWER_PDF_TEXT)}[6]
        assert it["answer"] == ""
        assert it["suggestion"] == "AC"
        assert "仅推断建议" in it["flags"]

    def test_unidentified_flagged(self):
        it = {i["no"]: i for i in extractor.parse_text(ANSWER_PDF_TEXT)}[7]
        assert it["answer"] == "" and it["suggestion"] == ""
        assert "未识别答案" in it["flags"]

    def test_normalize_letters(self):
        assert extractor.normalize_letters("b,a") == "AB"
        assert extractor.normalize_letters("ABCA") == "ABC"
        assert extractor.normalize_letters("E") == ""
        assert extractor.normalize_letters(None) == ""

    def test_plain_channel(self):
        pairs = extractor.plain_pairs(PLAIN_TEXT)
        assert pairs == {1: "A", 2: "B", 3: "D"}


# ================================================================== 端点
def _upload_answers(client, headers, paper_id, content, filename="答案及解析.txt"):
    return client.post(f"/api/materials/admin/papers/{paper_id}/answers/parse",
                       files={"file": (filename, content)}, headers=headers)


class TestAnswerEndpoints:
    def test_parse_txt_creates_pending_draft(self, client, db_session, admin_headers,
                                             test_subject, test_question_type, test_admin):
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=3)
        resp = _upload_answers(client, admin_headers, paper.paper_id, PLAIN_TEXT.encode())
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "pending"
        assert body["item_count"] == 3
        assert body["paper_code"] == paper.paper_code
        # 解析阶段**不写题库**
        assert db_session.query(QuestionBank).filter(
            QuestionBank.answer != "").count() == 0

    def test_number_out_of_paper_range_is_blocked(self, client, db_session, admin_headers,
                                                  test_subject, test_question_type, test_admin):
        """Q4：题号不属于该卷 → 判失败，不让人误把别的卷的答案写进来。"""
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=3)
        resp = _upload_answers(client, admin_headers, paper.paper_id,
                               "1 A\n2 B\n3 C\n9 D\n".encode())
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert "不属于这张卷" in resp.json()["message"]

    def test_type_conflict_flagged(self, client, db_session, admin_headers,
                                   test_subject, test_question_type, test_admin):
        """单选却给了 3 个字母 → 标「题型冲突」（实测 2017 江苏 #87 就是这样被抓出来的）。"""
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id,
                            count=3, types={1: 1, 2: 1, 3: 1})   # 全单选
        resp = _upload_answers(client, admin_headers, paper.paper_id,
                               "1 ABC\n2 B\n3 C\n".encode())
        draft_id = resp.json()["draft_id"]
        assert resp.json()["conflict_count"] == 1
        detail = client.get(f"/api/materials/admin/answers/drafts/{draft_id}",
                            headers=admin_headers).json()
        first = next(i for i in detail["items"] if i["no"] == 1)
        assert "题型冲突" in first["flags"]

    def test_apply_fills_empty_and_writes_analysis(self, client, db_session, admin_headers,
                                                   test_subject, test_question_type, test_admin):
        """Q3：答案 + 解析一起入库。

        答案文本覆盖 1–7，所以卷也造 7 题；4/5/6 是多选（`BC`、`ABCD` 这类答案才自洽）。
        """
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id,
                            count=7, types={4: 2, 5: 2, 6: 2})
        resp = _upload_answers(client, admin_headers, paper.paper_id,
                               ANSWER_PDF_TEXT.encode())
        draft_id = resp.json()["draft_id"]
        apply = client.post(f"/api/materials/admin/answers/drafts/{draft_id}/apply",
                            json={}, headers=admin_headers)
        assert apply.status_code == 200, apply.text
        assert apply.json()["filled"] == 4      # 1A / 2B / 3D / 5BC；4 与 6 只有推断建议

        db_session.expire_all()
        answers = [r.answer for r in db_session.query(QuestionBank)
                   .join(PaperQuestionRelation,
                         PaperQuestionRelation.question_id == QuestionBank.question_id)
                   .filter(PaperQuestionRelation.paper_id == paper.paper_id)
                   .order_by(PaperQuestionRelation.question_order).all()]
        assert answers[0] == "A" and answers[1] == "B" and answers[2] == "D"
        assert answers[4] == "BC"
        q1 = db_session.query(QuestionBank).join(
            PaperQuestionRelation,
            PaperQuestionRelation.question_id == QuestionBank.question_id).filter(
            PaperQuestionRelation.paper_id == paper.paper_id,
            PaperQuestionRelation.question_order == 1).one()
        assert "本题考查公安时政" in (q1.answer_analysis or "")

    def test_apply_keeps_existing_by_default_and_overwrite_flag(
            self, client, db_session, admin_headers, test_subject,
            test_question_type, test_admin):
        """Q1：已有答案不同 → 默认保留；`overwrite=true` 才改。"""
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id,
                            count=2, with_answers=True)     # 库里已有 A
        draft_id = _upload_answers(client, admin_headers, paper.paper_id,
                                   "1 D\n2 C\n".encode()).json()["draft_id"]

        first = client.post(f"/api/materials/admin/answers/drafts/{draft_id}/apply",
                            json={}, headers=admin_headers).json()
        assert first["overwritten"] == 0
        assert first["kept"] == 2
        db_session.expire_all()
        assert db_session.query(QuestionBank).filter(
            QuestionBank.answer == "A").count() == 2

        # 再解析一次 → overwrite
        draft2 = _upload_answers(client, admin_headers, paper.paper_id,
                                 "1 D\n2 C\n".encode()).json()["draft_id"]
        second = client.post(f"/api/materials/admin/answers/drafts/{draft2}/apply",
                             json={"overwrite": True}, headers=admin_headers).json()
        assert second["overwritten"] == 2
        db_session.expire_all()
        got = sorted(r.answer for r in db_session.query(QuestionBank).all())
        assert got == ["C", "D"]

    def test_apply_twice_rejected(self, client, db_session, admin_headers,
                                  test_subject, test_question_type, test_admin):
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=3)
        draft_id = _upload_answers(client, admin_headers, paper.paper_id,
                                   PLAIN_TEXT.encode()).json()["draft_id"]
        assert client.post(f"/api/materials/admin/answers/drafts/{draft_id}/apply",
                           json={}, headers=admin_headers).status_code == 200
        again = client.post(f"/api/materials/admin/answers/drafts/{draft_id}/apply",
                            json={}, headers=admin_headers)
        assert again.status_code == 400 and "已经写入" in again.json()["detail"]

    def test_manual_fix_then_apply(self, client, db_session, admin_headers,
                                   test_subject, test_question_type, test_admin):
        """人工把"推断建议"改成正式答案，再写入（第 6 题原文只有推断建议 AC）。"""
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id,
                            count=7, types={4: 2, 5: 2, 6: 2})
        draft_id = _upload_answers(client, admin_headers, paper.paper_id,
                                   ANSWER_PDF_TEXT.encode()).json()["draft_id"]
        detail = client.get(f"/api/materials/admin/answers/drafts/{draft_id}",
                            headers=admin_headers).json()
        items = detail["items"]
        for it in items:
            if it["no"] == 6:
                assert it["answer"] == ""
                it["answer"] = it["suggestion"]      # 采纳建议：AC
        resp = client.put(f"/api/materials/admin/answers/drafts/{draft_id}/items",
                          json={"items": items}, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        apply = client.post(f"/api/materials/admin/answers/drafts/{draft_id}/apply",
                            json={}, headers=admin_headers).json()
        assert apply["filled"] == 5
        db_session.expire_all()
        got = db_session.query(QuestionBank).join(
            PaperQuestionRelation,
            PaperQuestionRelation.question_id == QuestionBank.question_id).filter(
            PaperQuestionRelation.paper_id == paper.paper_id,
            PaperQuestionRelation.question_order == 6).one()
        assert got.answer == "AC"

    def test_bad_letter_and_unknown_number_rejected_in_edit(
            self, client, db_session, admin_headers, test_subject,
            test_question_type, test_admin):
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=3)
        draft_id = _upload_answers(client, admin_headers, paper.paper_id,
                                   PLAIN_TEXT.encode()).json()["draft_id"]
        bad_no = client.put(f"/api/materials/admin/answers/drafts/{draft_id}/items",
                            json={"items": [{"no": 9, "answer": "A"}]},
                            headers=admin_headers)
        assert bad_no.status_code == 400 and "不属于这张卷" in bad_no.json()["detail"]

    def test_discard(self, client, db_session, admin_headers,
                     test_subject, test_question_type, test_admin):
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=3)
        draft_id = _upload_answers(client, admin_headers, paper.paper_id,
                                   PLAIN_TEXT.encode()).json()["draft_id"]
        resp = client.delete(f"/api/materials/admin/answers/drafts/{draft_id}",
                             headers=admin_headers)
        assert resp.status_code == 200 and resp.json()["status"] == "discarded"

    def test_paper_without_questions_rejected(self, client, db_session, admin_headers,
                                              test_subject, test_question_type, test_admin):
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=1)
        db_session.query(PaperQuestionRelation).filter(
            PaperQuestionRelation.paper_id == paper.paper_id).delete()
        db_session.commit()
        resp = _upload_answers(client, admin_headers, paper.paper_id, PLAIN_TEXT.encode())
        assert resp.status_code == 400 and "还没有题目" in resp.json()["detail"]

    def test_unsupported_ext_rejected(self, client, db_session, admin_headers,
                                      test_subject, test_question_type, test_admin):
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=2)
        resp = _upload_answers(client, admin_headers, paper.paper_id,
                               b"GIF89a", filename="answer.gif")
        assert resp.status_code == 400 and "仅支持" in resp.json()["detail"]

    def test_student_forbidden(self, client, db_session, auth_headers,
                               test_subject, test_question_type, test_admin):
        paper = _make_paper(db_session, test_subject.subject_id,
                            test_question_type.type_id, test_admin.user_id, count=2)
        resp = _upload_answers(client, auth_headers, paper.paper_id, PLAIN_TEXT.encode())
        assert resp.status_code == 403
