# -*- coding: utf-8 -*-
"""管理端删除 = 软删除（2026-11-07，用户裁定 B）。

背景：原实现 `DELETE /api/materials/admin/{id}` 与 `/admin/batch` 都是 `db.delete()` **物理删除**，
还会清掉 `user_material_progress`；而《试卷管理收敛_单一入口与上架即审批_方案_v1.md》§2.2
写的是「（删除）|-1|软删除，不参与列表与统计」。实测偏差已导致两条测试资料（121/122）不可恢复地消失。

现在断言的行为：
- 删除只置 `status=-1`，行仍在表里，学习进度保留；
- 默认列表/统计排除 -1，显式 `?status=-1` 可查「回收站」；
- `PUT /admin/{id}/status {status:0}` = 恢复（回到未上架，学生仍不可见），审计记为「恢复资料」；
- 批量删除同样软删，已删除的不重复计数；教师调用 403。
"""
from app.models.models import StudyMaterial, SysOperationLog, UserMaterialProgress


def _mk(db, **kw):
    body = dict(subject="gongzhuan", type="card", title="样例",
                card_front="正面", card_back="背面", status=1)
    body.update(kw)
    m = StudyMaterial(**body)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _row(db, mid):
    db.expire_all()
    return db.query(StudyMaterial).filter(StudyMaterial.material_id == mid).first()


def _stats(client, headers):
    r = client.get("/api/materials/admin/stats", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


class TestSoftDelete:
    def test_delete_keeps_row_and_sets_status_minus_one(
        self, client, db_session, test_admin, admin_headers
    ):
        m = _mk(db_session, title="待删")
        r = client.delete(f"/api/materials/admin/{m.material_id}", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

        row = _row(db_session, m.material_id)
        assert row is not None, "软删除不得物理删行"
        assert row.status == -1

    def test_delete_keeps_study_progress(
        self, client, db_session, test_admin, test_user, admin_headers
    ):
        m = _mk(db_session)
        db_session.add(UserMaterialProgress(user_id=test_user.user_id,
                                            material_id=m.material_id, status=2))
        db_session.commit()

        client.delete(f"/api/materials/admin/{m.material_id}", headers=admin_headers)

        db_session.expire_all()
        prog = db_session.query(UserMaterialProgress).filter(
            UserMaterialProgress.material_id == m.material_id).first()
        assert prog is not None, "恢复后学生进度应还在"

    def test_deleted_row_leaves_default_list_and_enters_recycle_bin(
        self, client, db_session, test_admin, admin_headers
    ):
        keep = _mk(db_session, title="在用的")
        gone = _mk(db_session, title="被删的")
        client.delete(f"/api/materials/admin/{gone.material_id}", headers=admin_headers)

        default = client.get("/api/materials/admin/list", headers=admin_headers).json()
        assert [i["id"] for i in default["items"]] == [keep.material_id]

        bin_ = client.get("/api/materials/admin/list", headers=admin_headers,
                          params={"status": -1}).json()
        assert [i["id"] for i in bin_["items"]] == [gone.material_id]

    def test_stats_total_down_deleted_up(
        self, client, db_session, test_admin, admin_headers
    ):
        m = _mk(db_session, status=1)
        before = _stats(client, admin_headers)
        client.delete(f"/api/materials/admin/{m.material_id}", headers=admin_headers)
        after = _stats(client, admin_headers)

        assert after["total"] == before["total"] - 1
        assert after["by_status"]["deleted"] == before["by_status"]["deleted"] + 1
        assert after["by_status"]["published"] == before["by_status"]["published"] - 1

    def test_delete_is_idempotent(
        self, client, db_session, test_admin, admin_headers
    ):
        m = _mk(db_session)
        first = client.delete(f"/api/materials/admin/{m.material_id}", headers=admin_headers)
        assert first.status_code == 200
        assert "already_deleted" not in first.json()

        second = client.delete(f"/api/materials/admin/{m.material_id}", headers=admin_headers)
        assert second.status_code == 200, "重复删除不应 404"
        assert second.json().get("already_deleted") is True

    def test_delete_missing_row_is_404(self, client, test_admin, admin_headers):
        r = client.delete("/api/materials/admin/99999999", headers=admin_headers)
        assert r.status_code == 404

    def test_teacher_cannot_delete(self, client, db_session, test_teacher, teacher_headers):
        m = _mk(db_session)
        r = client.delete(f"/api/materials/admin/{m.material_id}", headers=teacher_headers)
        assert r.status_code == 403
        assert _row(db_session, m.material_id).status == 1


class TestRestore:
    def test_restore_returns_unpublished_and_visible_to_admin(
        self, client, db_session, test_admin, admin_headers
    ):
        m = _mk(db_session, status=1)
        client.delete(f"/api/materials/admin/{m.material_id}", headers=admin_headers)

        r = client.put(f"/api/materials/admin/{m.material_id}/status",
                       json={"status": 0}, headers=admin_headers)
        assert r.status_code == 200, r.text

        row = _row(db_session, m.material_id)
        assert row.status == 0, "恢复后必须是未上架，不能直接回到已上架"

        default = client.get("/api/materials/admin/list", headers=admin_headers).json()
        assert [i["id"] for i in default["items"]] == [m.material_id]

    def test_restore_writes_restore_audit(
        self, client, db_session, test_admin, admin_headers
    ):
        m = _mk(db_session)
        client.delete(f"/api/materials/admin/{m.material_id}", headers=admin_headers)
        client.put(f"/api/materials/admin/{m.material_id}/status",
                   json={"status": 0}, headers=admin_headers)

        db_session.expire_all()
        logs = db_session.query(SysOperationLog).filter(
            SysOperationLog.operation_type == "恢复资料").all()
        assert logs, "恢复动作要能在审计里和普通上下架区分开"

    def test_status_endpoint_still_rejects_other_values(
        self, client, db_session, test_admin, admin_headers
    ):
        m = _mk(db_session)
        r = client.put(f"/api/materials/admin/{m.material_id}/status",
                       json={"status": -1}, headers=admin_headers)
        assert r.status_code == 400, "删除要走 DELETE，不能被 status 端点当普通状态写入"


class TestBatchSoftDelete:
    def test_batch_delete_is_soft(
        self, client, db_session, test_admin, admin_headers
    ):
        a = _mk(db_session, title="A")
        b = _mk(db_session, title="B")
        r = client.request("DELETE", "/api/materials/admin/batch",
                           json={"ids": [a.material_id, b.material_id]},
                           headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["deleted"] == 2

        assert _row(db_session, a.material_id).status == -1
        assert _row(db_session, b.material_id).status == -1

    def test_batch_delete_skips_already_deleted(
        self, client, db_session, test_admin, admin_headers
    ):
        alive = _mk(db_session, title="在用")
        dead = _mk(db_session, title="已删", status=-1)
        r = client.request("DELETE", "/api/materials/admin/batch",
                           json={"ids": [alive.material_id, dead.material_id]},
                           headers=admin_headers)
        assert r.json()["deleted"] == 1, "已删除的不重复计数"

    def test_batch_delete_requires_ids(self, client, test_admin, admin_headers):
        r = client.request("DELETE", "/api/materials/admin/batch",
                           json={"ids": []}, headers=admin_headers)
        assert r.status_code == 400
