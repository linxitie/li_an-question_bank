"""
统一练习统计三端点冒烟测试
覆盖: 鉴权 / 参数校验(422) / 空数据边界 / 四来源混合数值与智能组卷双计排除
规格: docs/superpowers/specs/2026-08-24-practice-records-v2-design.md §8/§9
"""
import pytest
from datetime import datetime, date

from app.models.models import (
    QuestionSubject, SubCategory, KnowledgePoint, QuestionKnowledge,
    PracticeRecord, SmartExamRecord, ExamPaper, ExamRecord, ExamAnswerDetail,
    YearPaper, QuestionBank,
)


class TestAuthAndValidation:
    def test_unified_stats_requires_auth(self, client):
        assert client.get("/api/practice/unified-stats").status_code in (401, 403)

    def test_knowledge_progress_requires_auth(self, client):
        assert client.get("/api/practice/knowledge-progress").status_code in (401, 403)

    def test_recent_records_requires_auth(self, client):
        assert client.get("/api/practice/recent-records").status_code in (401, 403)

    def test_recent_records_validates_params(self, client, auth_headers):
        h = auth_headers
        assert client.get("/api/practice/recent-records", params={"limit": 0}, headers=h).status_code == 422
        assert client.get("/api/practice/recent-records", params={"limit": 999}, headers=h).status_code == 422
        assert client.get("/api/practice/recent-records", params={"offset": -1}, headers=h).status_code == 422
        assert client.get("/api/practice/recent-records", params={"source": "不存在的来源"}, headers=h).status_code == 422
        assert client.get("/api/practice/recent-records", params={"status": "bogus"}, headers=h).status_code == 422


class TestEmptyData:
    def test_empty_overview(self, client, auth_headers):
        r = client.get("/api/practice/unified-stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["today"]["count"] == 0
        assert data["week"]["count"] == 0
        assert data["total"]["count"] == 0
        assert data["total"]["accuracy"] == 0
        assert data["total"]["time_spent_seconds"] == 0
        assert len(data["daily_trend"]) == 7

    def test_empty_knowledge_progress(self, client, auth_headers):
        r = client.get("/api/practice/knowledge-progress", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == {"subjects": []}

    def test_empty_recent_records(self, client, auth_headers):
        r = client.get("/api/practice/recent-records", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert body["limit"] == 10 and body["offset"] == 0


class TestMixedSources:
    """四来源混合数据：验证统计口径、跳转映射与智能组卷双计排除"""

    @pytest.fixture
    def mixed_env(self, client, test_user, db_session):
        uid = test_user.user_id
        today = date.today()

        # 科目 / 子科目 / 考点 / 考点-题目关联
        subj = QuestionSubject(subject_name="行测", subject_code="xc", status=1)
        db_session.add(subj); db_session.commit(); db_session.refresh(subj)

        subcat = SubCategory(name="政治理论", subject_id=subj.subject_id, status=1, sort_order=1)
        db_session.add(subcat); db_session.commit(); db_session.refresh(subcat)

        # level=3 / status=1 必须有：/knowledge-progress 只取 level==3 且 status==1 的考点
        # （实测库内 level 分布 2:516 / 3:526 / 4:7，status 0:531 / 1:518，两列都参与筛选）
        kp = KnowledgePoint(point_name="政治立场与忠诚度", subject_id=subj.subject_id,
                            sub_category_id=subcat.id, sort_order=1, level=3, status=1)
        db_session.add(kp); db_session.commit(); db_session.refresh(kp)

        for qid in (90001, 90002):
            db_session.add(QuestionKnowledge(question_id=qid, knowledge_point_id=kp.point_id))
        db_session.commit()

        # 题目本体必须落库并带 point_id：/knowledge-progress 的统计口径走 question_bank.point_id
        # （实测库内 point_id 非 0 有 2131 行，是该端点的既有实现；question_knowledge 是并行的多对多表，
        #  两者在真实数据里相差 1 行，属已知口径分歧，已记入 docs/design/题库领域词表_v1.md §8）
        for qid in (90001, 90002):
            db_session.add(QuestionBank(
                question_id=qid, subject_id=subj.subject_id, type_id=1,
                question_content=f"考点进度测试题 {qid}", answer="A", creator_id=uid,
                point_id=kp.point_id, status=1, audit_status=1,
            ))
        db_session.commit()

        # ── 来源1 快速练习: 今天2题(对1错1)，每题60秒 ──
        for i, qid in enumerate((90001, 90002)):
            db_session.add(PracticeRecord(
                user_id=uid, question_id=qid, subject_id=subj.subject_id,
                is_correct=1 if i == 0 else 0, time_spent=60,
                practice_date=today, practice_time=datetime.now(),
                source_type="快速练习",
            ))

        # ── 来源3 智能组卷: 会话(completed) + 关联exam_record(应被排除) + 按题流水2题(全对) ──
        paper_s = ExamPaper(
            paper_name="智能卷A", paper_code="PC-SMART-1", subject_id=subj.subject_id,
            composition_method="SMART", creator_id=uid, duration=60, total_score=100,
        )
        db_session.add(paper_s); db_session.commit(); db_session.refresh(paper_s)

        er_smart = ExamRecord(
            paper_id=paper_s.paper_id, user_id=uid, exam_type="SELF_TEST",
            start_time=datetime.combine(today, datetime.min.time().replace(hour=9)),
            duration_used=120, total_score=80, is_completed=1,
        )
        db_session.add(er_smart); db_session.commit(); db_session.refresh(er_smart)
        # 该明细若未被排除，unified-stats 总数会多 1（双计探针）
        db_session.add(ExamAnswerDetail(record_id=er_smart.record_id, question_id=91001, is_correct=1))

        smart = SmartExamRecord(
            user_id=uid, paper_id=paper_s.paper_id, exam_record_id=er_smart.record_id,
            paper_name="智能卷A", subject_mode="xingce",
            total_questions=2, completed_count=2, earned_score=80,
            status="completed", time_spent=300,
            start_time=datetime.now(), end_time=datetime.now(),
        )
        db_session.add(smart)
        for i in range(2):
            db_session.add(PracticeRecord(
                user_id=uid, question_id=92000 + i, subject_id=subj.subject_id,
                is_correct=1, time_spent=150,
                practice_date=today, practice_time=datetime.now(),
                source_type="智能组卷",
            ))
        db_session.commit(); db_session.refresh(smart)

        # ── 来源2 历年试卷: SELF_TEST + YearPaper, 已完成, 明细2题(对1错1), 用时500 ──
        paper_p = ExamPaper(
            paper_name="2025年真题", paper_code="PC-PAST-1", subject_id=subj.subject_id,
            composition_method="IMPORT", creator_id=uid, duration=120, total_score=100,
        )
        db_session.add(paper_p); db_session.commit(); db_session.refresh(paper_p)

        er_past = ExamRecord(
            paper_id=paper_p.paper_id, user_id=uid, exam_type="SELF_TEST",
            start_time=datetime.combine(today, datetime.min.time().replace(hour=8)),
            duration_used=500, total_score=60, is_completed=1,
        )
        db_session.add(er_past); db_session.commit(); db_session.refresh(er_past)
        db_session.add(YearPaper(record_id=er_past.record_id, year=2025,
                                 paper_title="2025年公安联考行测真题"))
        db_session.add(ExamAnswerDetail(record_id=er_past.record_id, question_id=93001, is_correct=1))
        db_session.add(ExamAnswerDetail(record_id=er_past.record_id, question_id=93002, is_correct=0))

        # ── 来源4 小模考: MOCK_EXAM, 进行中, 明细1题(对), 用时200 ──
        paper_m = ExamPaper(
            paper_name="第3次小模考", paper_code="PC-MOCK-1", subject_id=subj.subject_id,
            composition_method="MANUAL", creator_id=uid, duration=90, total_score=100,
        )
        db_session.add(paper_m); db_session.commit(); db_session.refresh(paper_m)

        er_mock = ExamRecord(
            paper_id=paper_m.paper_id, user_id=uid, exam_type="MOCK_EXAM",
            start_time=datetime.combine(today, datetime.min.time().replace(hour=7)),
            duration_used=200, total_score=0, is_completed=0,
        )
        db_session.add(er_mock); db_session.commit(); db_session.refresh(er_mock)
        db_session.add(ExamAnswerDetail(record_id=er_mock.record_id, question_id=94001, is_correct=1))
        db_session.commit()

        return {
            "point_id": kp.point_id,
            "past_record_id": er_past.record_id,
            "mock_record_id": er_mock.record_id,
            "smart_paper_id": paper_s.paper_id,
            "smart_record_pk": smart.id,
        }

    def test_unified_stats_numbers_and_double_count_exclusion(self, client, auth_headers, mixed_env):
        r = client.get("/api/practice/unified-stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        # 总数 = 快速练习2 + 智能组卷按题流水2 + 历年明细2 + 模考明细1 = 7
        # （er_smart 的明细已被排除；若双计未排除则为 8）
        assert data["total"]["count"] == 7
        # 正确 = 1 + 2 + 1 + 1 = 5 → 71.4%
        assert data["total"]["correct"] == 5
        assert data["total"]["accuracy"] == 71.4
        # 全部发生在今天
        assert data["today"]["count"] == 7
        assert data["week"]["count"] == 7
        trend_today = [d for d in data["daily_trend"] if d["date"] == date.today().isoformat()]
        assert len(trend_today) == 1
        assert trend_today[0]["count"] == 7
        assert trend_today[0]["weekday"] == ["一", "二", "三", "四", "五", "六", "日"][date.today().weekday()]

    def test_knowledge_progress_values(self, client, auth_headers, mixed_env):
        r = client.get("/api/practice/knowledge-progress", headers=auth_headers)
        assert r.status_code == 200
        subjects = r.json()["subjects"]
        assert len(subjects) == 1
        s = subjects[0]
        assert s["subject_code"] == "xc"
        assert s["subject_name"] == "行测"
        assert len(s["kps"]) == 1
        kp = s["kps"][0]
        assert kp["point_name"] == "政治立场与忠诚度"
        assert kp["total"] == 2
        assert kp["done"] == 2
        assert kp["done_pct"] == 100.0
        # 该考点 attempts=2 corrects=1 → 50%（智能组卷流水题目不属于此考点）
        assert kp["accuracy"] == 50.0

    def test_recent_records_all_sources_and_jumps(self, client, auth_headers, mixed_env):
        env = mixed_env
        r = client.get("/api/practice/recent-records", params={"limit": 50},
                       headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        sources = {i["source"] for i in body["items"]}
        assert sources == {"快速练习", "智能组卷", "历年试卷", "小模考"}

        by_key = {i["record_key"]: i for i in body["items"]}

        past = by_key[f"exam_{env['past_record_id']}"]
        assert past["name"] == "2025年公安联考行测真题"
        assert past["status"] == "completed"
        assert past["question_count"] == 2
        assert past["accuracy"] == 50.0
        assert past["time_spent_seconds"] == 500
        assert past["jump"] == {"path": "/paper-result", "params": {"record_id": env["past_record_id"]}}

        mock = by_key[f"exam_{env['mock_record_id']}"]
        assert mock["name"] == "第3次小模考"
        assert mock["status"] == "in_progress"
        assert mock["jump"]["path"] == "/paper-answer"
        assert mock["jump"]["params"]["record_id"] == env["mock_record_id"]
        assert mock["jump"]["params"]["paper_id"]

        smart = by_key[f"smart_{env['smart_record_pk']}"]
        assert smart["name"] == "智能卷A"
        assert smart["status"] == "completed"
        assert smart["score"] == 80
        assert smart["jump"]["path"] == "/smart-answer"
        assert smart["jump"]["params"]["paper_id"] == env["smart_paper_id"]

        qp_items = [i for i in body["items"] if i["source"] == "快速练习"]
        assert len(qp_items) == 1
        qp = qp_items[0]
        assert qp["question_count"] == 2
        assert qp["accuracy"] == 50.0
        assert qp["time_spent_seconds"] == 120
        assert qp["jump"]["path"] == "/exercise"
        assert qp["jump"]["params"]["subject"] == "xc"

    def test_recent_records_filters(self, client, auth_headers, mixed_env):
        r = client.get("/api/practice/recent-records",
                       params={"source": "快速练习"}, headers=auth_headers)
        items = r.json()["items"]
        assert items and {i["source"] for i in items} == {"快速练习"}
        assert r.json()["total"] == len(items)

        r = client.get("/api/practice/recent-records",
                       params={"status": "in_progress", "limit": 50}, headers=auth_headers)
        items = r.json()["items"]
        assert items
        assert all(i["status"] == "in_progress" for i in items)
        assert any(i["source"] == "小模考" for i in items)

    def test_recent_records_pagination(self, client, auth_headers, mixed_env):
        full = client.get("/api/practice/recent-records", params={"limit": 50},
                          headers=auth_headers).json()
        paged = client.get("/api/practice/recent-records", params={"limit": 2, "offset": 0},
                           headers=auth_headers).json()
        assert paged["total"] == full["total"]
        assert len(paged["items"]) == min(2, full["total"])
        if full["total"] >= 2:
            assert paged["items"][0] == full["items"][0]


class TestQpJumpSubjectKeyMapping:
    """回归：subject_code 为 auto_* 形式时，qp_ 跳转必须映射为约定键 xc/sl/ga"""

    def test_auto_code_maps_to_convention_key(self, client, auth_headers, test_user, db_session):
        today = date.today()
        # 显式占用 subject_id=1，但 code 用真实库中出现的 auto_* 形式
        subj = QuestionSubject(subject_id=1, subject_name="行测",
                               subject_code="auto_weird", status=1)
        db_session.add(subj); db_session.commit()

        db_session.add(PracticeRecord(
            user_id=test_user.user_id, question_id=80001, subject_id=1,
            is_correct=1, time_spent=10,
            practice_date=today, practice_time=datetime.now(),
            source_type="快速练习",
        ))
        db_session.commit()

        r = client.get("/api/practice/recent-records", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["source"] == "快速练习"
        assert items[0]["jump"]["params"]["subject"] == "xc"
