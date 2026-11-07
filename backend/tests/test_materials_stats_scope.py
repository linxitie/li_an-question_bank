# -*- coding: utf-8 -*-
"""统计口径回归（2026-11-07，用户裁定 A）：全部聚合排除软删除，总数必须自洽。

现象（修正前）：119 总资料 = 103 已上架 + 11 未上架 + **5 已删除**，
而 `by_status` 只给 published/draft → 「已上架 + 未上架 ≠ 总资料」；
`admin_list` 不传 status 时也不过滤 -1 → 删掉的资料还在列表里。

修正后：total / by_type / by_subject / by_status 统一过滤 `status >= 0`；
列表默认同样过滤，显式传 `status=-1` 仍可查已删除。
"""
from app.models.models import StudyMaterial


def _mk(db, **kw):
    body = dict(subject="gongzhuan", type="card", title="样例",
                card_front="正面", card_back="背面", status=1)
    body.update(kw)
    m = StudyMaterial(**body)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _stats(client, headers):
    r = client.get("/api/materials/admin/stats", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


class TestStatsScope:
    def test_total_equals_published_plus_draft(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, status=1)
        _mk(db_session, status=1)
        _mk(db_session, status=0)
        _mk(db_session, status=-1)   # 软删除，不该出现在任何聚合里

        s = _stats(client, admin_headers)
        assert s["total"] == 3
        assert s["by_status"]["published"] == 2
        assert s["by_status"]["draft"] == 1
        assert s["by_status"]["published"] + s["by_status"]["draft"] == s["total"]

    def test_by_type_sum_equals_total(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, type="card", status=1)
        _mk(db_session, type="article", status=0)
        _mk(db_session, type="paper", status=1)
        _mk(db_session, type="card", status=-1)   # 被排除

        s = _stats(client, admin_headers)
        assert sum(s["by_type"].values()) == s["total"] == 3
        assert s["by_type"]["card"] == 1          # 不含已删除的那张
        assert s["by_type"]["paper"] == 1

    def test_by_subject_sum_equals_total(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, subject="xingce")
        _mk(db_session, subject="shenlun")
        _mk(db_session, subject="gongzhuan", status=-1)

        s = _stats(client, admin_headers)
        assert sum(s["by_subject"].values()) == s["total"] == 2

    def test_deleted_bucket_is_reported_separately(self, client, db_session, test_admin, admin_headers):
        """已删除数量单列在 by_status.deleted，便于追溯，但不进 total。"""
        _mk(db_session, status=-1)
        _mk(db_session, status=-1)
        _mk(db_session, status=1)
        s = _stats(client, admin_headers)
        assert s["total"] == 1
        assert s["by_status"]["deleted"] == 2

    def test_personal_library_is_counted_but_not_mixed_into_draft(
        self, client, db_session, test_admin, admin_headers
    ):
        """学生个人库（status=2）计入总数，但单列，不混进「未上架」。"""
        _mk(db_session, status=2)
        _mk(db_session, status=0)
        s = _stats(client, admin_headers)
        assert s["total"] == 2
        assert s["by_status"]["personal"] == 1
        assert s["by_status"]["draft"] == 1


class TestListScope:
    def test_default_list_excludes_deleted(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, title="在用的")
        _mk(db_session, title="已删除的", status=-1)

        r = client.get("/api/materials/admin/list", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 1
        assert [i["title"] for i in data["items"]] == ["在用的"]

    def test_list_total_matches_stats_total(self, client, db_session, test_admin, admin_headers):
        for _ in range(3):
            _mk(db_session, status=1)
        _mk(db_session, status=0)
        _mk(db_session, status=-1)

        list_total = client.get("/api/materials/admin/list", headers=admin_headers).json()["total"]
        stats_total = _stats(client, admin_headers)["total"]
        assert list_total == stats_total == 4

    def test_explicit_deleted_filter_still_works(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, title="在用")
        _mk(db_session, title="已删除", status=-1)

        r = client.get("/api/materials/admin/list", headers=admin_headers,
                       params={"status": -1})
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["title"] == "已删除"

    def test_explicit_published_filter(self, client, db_session, test_admin, admin_headers):
        _mk(db_session, title="上架", status=1)
        _mk(db_session, title="下架", status=0)
        r = client.get("/api/materials/admin/list", headers=admin_headers, params={"status": 1})
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["title"] == "上架"
