# -*- coding: utf-8 -*-
"""C3 回归（2026-11-08）：管理列表的「年份 / 地区 / 卷别」筛选。

口径（与预览一致）：`paper_meta` 人工订正 **优先于** 文件名解析；
带试卷筛选时**非试卷类一律排除**（问的是"2019 年的试卷"，卡片/讲义不该出现）；
地区同时接受代码（BJ）与中文（北京）。
"""
import json

from app.models.models import StudyMaterial


def _paper(db, title, code=None, meta=None, status=0, subject="gongzhuan"):
    m = StudyMaterial(subject=subject, type="paper", title=title,
                      paper_code=code, badge=code, status=status, content="")
    if meta:
        m.paper_meta = json.dumps(meta, ensure_ascii=False)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _ids(client, headers, **params):
    r = client.get("/api/materials/admin/list", headers=headers, params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["total"], [i["id"] for i in body["items"]]


class TestPaperFilters:
    def test_year_filter(self, client, admin_headers, db_session):
        a = _paper(db_session, "2019年北京市公务员考试真题")
        b = _paper(db_session, "2017年江苏省公务员考试真题")
        total, ids = _ids(client, admin_headers, type="paper", paper_year=2019)
        assert total == 1 and ids == [a.material_id]
        assert b.material_id not in ids

    def test_region_accepts_code_and_chinese(self, client, admin_headers, db_session):
        a = _paper(db_session, "2019年北京市公务员考试真题")
        _paper(db_session, "2017年江苏省公务员考试真题")
        assert _ids(client, admin_headers, region="BJ")[1] == [a.material_id]
        assert _ids(client, admin_headers, region="北京")[1] == [a.material_id]

    def test_book_kind_filter(self, client, admin_headers, db_session):
        t = _paper(db_session, "2020年国考题本")
        a = _paper(db_session, "2020年国考答案")
        assert _ids(client, admin_headers, book_kind="A")[1] == [a.material_id]
        assert _ids(client, admin_headers, book_kind="T")[1] == [t.material_id]

    def test_override_beats_filename_parse(self, client, admin_headers, db_session):
        # 标题写着 2019 北京，但管理员订正为 2020 江苏
        m = _paper(db_session, "2019年北京市公务员考试真题",
                   meta={"year": 2020, "region_code": "JS", "region_name": "江苏"})
        assert _ids(client, admin_headers, paper_year=2019)[0] == 0
        assert _ids(client, admin_headers, paper_year=2020)[1] == [m.material_id]
        assert _ids(client, admin_headers, region="江苏")[1] == [m.material_id]

    def test_combined_filters(self, client, admin_headers, db_session):
        hit = _paper(db_session, "2019年北京市公务员考试真题")
        _paper(db_session, "2019年江苏省公务员考试真题")
        _paper(db_session, "2021年北京市公务员考试真题")
        total, ids = _ids(client, admin_headers,
                          paper_year=2019, region="北京", book_kind="T")
        assert total == 1 and ids == [hit.material_id]

    def test_non_paper_excluded_when_paper_filters_on(self, client, admin_headers, db_session):
        db_session.add(StudyMaterial(subject="gongzhuan", type="lecture",
                                     title="2019年北京讲义", status=0))
        db_session.commit()
        paper = _paper(db_session, "2019年北京市公务员考试真题")
        total, ids = _ids(client, admin_headers, paper_year=2019)
        assert total == 1 and ids == [paper.material_id]

    def test_unparseable_paper_not_matched(self, client, admin_headers, db_session):
        _paper(db_session, "扫描件_001")           # 没有年份/地区可解析
        assert _ids(client, admin_headers, paper_year=2019)[0] == 0
        assert _ids(client, admin_headers, region="BJ")[0] == 0

    def test_filters_combine_with_other_conditions(self, client, admin_headers, db_session):
        published = _paper(db_session, "2019年北京市公务员考试真题", status=1)
        _paper(db_session, "2019年北京市公务员考试真题（草稿）", status=0)
        total, ids = _ids(client, admin_headers, paper_year=2019, status=1)
        assert total == 1 and ids == [published.material_id]

    def test_pagination_applies_to_filtered_set(self, client, admin_headers, db_session):
        created = [_paper(db_session, f"2019年北京市公务员考试真题#{i}") for i in range(5)]
        total, ids = _ids(client, admin_headers, paper_year=2019, page=2, page_size=2)
        assert total == 5 and len(ids) == 2
        assert set(ids) <= {m.material_id for m in created}

    def test_no_paper_filters_keeps_old_behaviour(self, client, admin_headers, db_session):
        _paper(db_session, "2019年北京市公务员考试真题")
        db_session.add(StudyMaterial(subject="gongzhuan", type="lecture",
                                     title="讲义", status=0))
        db_session.commit()
        total, ids = _ids(client, admin_headers)
        assert total == 2, "不带试卷筛选时不做类型排除"

    def test_row_exposes_filter_fields(self, client, admin_headers, db_session):
        m = _paper(db_session, "2019年北京市公务员考试真题", code="GZ-2019-BJ-T")
        body = client.get("/api/materials/admin/list", headers=admin_headers,
                          params={"paper_year": 2019}).json()
        row = [i for i in body["items"] if i["id"] == m.material_id][0]
        assert row["paper_year"] == 2019
        assert row["paper_region"] == "北京"
        assert row["paper_book_kind"] == "T"
