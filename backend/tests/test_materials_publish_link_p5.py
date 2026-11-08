# -*- coding: utf-8 -*-
"""P5：资料上/下架 → 可作答卷 `paper_type` 联动（2026-11-08，方案 A3）。

依据《试卷管理收敛_单一入口与上架即审批_方案_v1.md》§2.3：
- 上架（`status=1`）→ 关联卷 `PUBLISHED`；下架/软删（`0` / `-1`）→ `DRAFT`；
- `ENDED`（回收站卷）**永不复活**；无关联卷时安静 no-op；
- 唯一真源是 `study_material.status`，反方向不驱动。

实现分层：`library/materials.py`（3 处触发）→ `services/material_paper_sync.py`（接线）
→ `api/v1/exam/contract.py`（考试域状态机）→ `exam_paper`。三者同一事务。
"""
import pytest

from app.core.config import settings
from app.models.models import ExamPaper, StudyMaterial, SysOperationLog


def _mk_paper(db, subject_id, creator_id, *, code="P5-T-1",
              paper_type="PUBLISHED", name="P5 联动卷"):
    paper = ExamPaper(
        paper_name=name,
        paper_code=code,
        subject_id=subject_id,
        composition_method="MANUAL",
        creator_id=creator_id,
        duration=120,
        total_score=100,
        difficulty=3,
        exam_type="SIMULATION",
        paper_type=paper_type,
        question_count=0,
        max_attempts=5,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def _mk_material(db, *, status=1, code="P5-T-1", mtype="paper",
                 title="P5 试卷资料", subject="gongzhuan"):
    body = dict(subject=subject, type=mtype, title=title, status=status,
                paper_code=code, badge=code)
    if mtype == "card":
        body.update(card_front="正面", card_back="背面", paper_code=None, badge=None)
    m = StudyMaterial(**body)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _refresh(db, model, pk_name, pk):
    db.expire_all()
    return db.query(model).filter(getattr(model, pk_name) == pk).first()


def _paper_type(db, paper_id):
    return _refresh(db, ExamPaper, "paper_id", paper_id).paper_type


def _exam_codes(client, headers):
    r = client.get("/api/exams/list?page_size=100", headers=headers)
    assert r.status_code == 200, r.text
    return {row["paper_code"] for row in r.json()["data"]}


def _set_status(client, headers, material_id, status):
    return client.put(f"/api/materials/admin/{material_id}/status",
                      json={"status": status}, headers=headers)


# ---------------------------------------------------------------- 上架 / 下架

def test_unpublish_mirrors_draft_and_hides_from_exam_list(
        client, db_session, test_subject, test_admin, test_user,
        admin_headers, auth_headers):
    """T1：下架 → 卷变 DRAFT，学生考试列表立刻查不到。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id)
    material = _mk_material(db_session, status=1, code=paper.paper_code)

    assert paper.paper_code in _exam_codes(client, auth_headers), "前置：上架态应可见"

    r = _set_status(client, admin_headers, material.material_id, 0)
    assert r.status_code == 200, r.text
    sync = r.json()["paper_sync"]
    assert sync["before"] == "PUBLISHED" and sync["after"] == "DRAFT"
    assert sync["changed"] is True and sync["paper_id"] == paper.paper_id
    assert _paper_type(db_session, paper.paper_id) == "DRAFT"
    assert paper.paper_code not in _exam_codes(client, auth_headers)


def test_republish_restores_published_and_visible(
        client, db_session, test_subject, test_admin, admin_headers, auth_headers):
    """T2：再上架 → 卷回 PUBLISHED，学生列表恢复。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      paper_type="DRAFT")
    material = _mk_material(db_session, status=0, code=paper.paper_code)

    r = _set_status(client, admin_headers, material.material_id, 1)
    assert r.status_code == 200, r.text
    assert r.json()["paper_sync"]["after"] == "PUBLISHED"
    assert _paper_type(db_session, paper.paper_id) == "PUBLISHED"
    assert paper.paper_code in _exam_codes(client, auth_headers)


def test_publish_flips_pending_and_approved(
        client, db_session, test_subject, test_admin, admin_headers):
    """T5（D-P5-2）：审批中间态被上架动作覆盖为 PUBLISHED（"上架即终审"）。"""
    for state in ("PENDING", "APPROVED"):
        paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                          code=f"P5-{state}", paper_type=state)
        material = _mk_material(db_session, status=0, code=paper.paper_code,
                                title=f"P5 {state} 资料")
        r = _set_status(client, admin_headers, material.material_id, 1)
        assert r.status_code == 200, r.text
        assert _paper_type(db_session, paper.paper_id) == "PUBLISHED", state


# ---------------------------------------------------------------- 边界与跳过

def test_publish_without_paper_is_noop(
        client, db_session, test_admin, admin_headers):
    """T3：#127 那种"有编号但题库没建卷" → 安静 no-op，不报错不写脏数据。"""
    material = _mk_material(db_session, status=0, code="P5-NO-PAPER")
    before = db_session.query(ExamPaper).count()

    r = _set_status(client, admin_headers, material.material_id, 1)
    assert r.status_code == 200, r.text
    sync = r.json()["paper_sync"]
    assert sync["skipped"] == "no_paper" and sync["changed"] is False
    assert db_session.query(ExamPaper).count() == before


def test_publish_does_not_revive_ended_paper(
        client, db_session, test_subject, test_admin, admin_headers):
    """T4（D-P5-3）：回收站卷不因上架复活。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-ENDED", paper_type="ENDED", name="P5 回收站卷")
    material = _mk_material(db_session, status=0, code=paper.paper_code)

    r = _set_status(client, admin_headers, material.material_id, 1)
    assert r.status_code == 200, r.text
    sync = r.json()["paper_sync"]
    assert sync["skipped"] == "ended" and sync["changed"] is False
    assert _paper_type(db_session, paper.paper_id) == "ENDED"


def test_card_material_does_not_touch_papers(
        client, db_session, test_subject, test_admin, admin_headers):
    """T11：卡片资料没有编号 → 契约不查库、不碰任何卷。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-CARD", paper_type="DRAFT")
    card = _mk_material(db_session, status=0, mtype="card", code="")

    r = _set_status(client, admin_headers, card.material_id, 1)
    assert r.status_code == 200, r.text
    assert r.json()["paper_sync"]["skipped"] == "not_paper"
    assert _paper_type(db_session, paper.paper_id) == "DRAFT"


def test_kill_switch_disables_sync(
        client, db_session, test_subject, test_admin, admin_headers, monkeypatch):
    """T13（D7 回滚开关）：MATERIAL_PAPER_SYNC=false → 只改资料不动卷。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-KILL", paper_type="DRAFT")
    material = _mk_material(db_session, status=0, code=paper.paper_code)
    monkeypatch.setattr(settings, "MATERIAL_PAPER_SYNC", False)

    r = _set_status(client, admin_headers, material.material_id, 1)
    assert r.status_code == 200, r.text
    assert r.json()["paper_sync"]["skipped"] == "disabled"
    assert _paper_type(db_session, paper.paper_id) == "DRAFT"


# ---------------------------------------------------------------- 删除 / 恢复

def test_soft_delete_mirrors_draft_then_restore_stays_draft(
        client, db_session, test_subject, test_admin, admin_headers):
    """T6（D-P5-4）：软删即不可考；恢复为"未上架"时仍不可考，再上架才可考。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-DEL")
    material = _mk_material(db_session, status=1, code=paper.paper_code)

    r = client.delete(f"/api/materials/admin/{material.material_id}",
                      headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["paper_sync"]["after"] == "DRAFT"
    assert _paper_type(db_session, paper.paper_id) == "DRAFT"

    # 恢复（-1 → 0）不改卷：仍是 DRAFT
    _set_status(client, admin_headers, material.material_id, 0)
    assert _paper_type(db_session, paper.paper_id) == "DRAFT"

    # 再上架 → 才回 PUBLISHED
    _set_status(client, admin_headers, material.material_id, 1)
    assert _paper_type(db_session, paper.paper_id) == "PUBLISHED"


def test_batch_delete_mirrors_draft(
        client, db_session, test_subject, test_admin, admin_headers):
    """T7：批量删除同样联动（bulk update 改逐条后仍保持同样语义）。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-BATCH")
    material = _mk_material(db_session, status=1, code=paper.paper_code)

    r = client.request("DELETE", "/api/materials/admin/batch",
                       json={"ids": [material.material_id]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted"] == 1
    assert body["paper_sync"] and body["paper_sync"][0]["after"] == "DRAFT"
    assert _paper_type(db_session, paper.paper_id) == "DRAFT"


# ---------------------------------------------------------------- 幂等 / 事务 / 审计

def test_second_publish_is_idempotent(
        client, db_session, test_subject, test_admin, admin_headers):
    """T8：连续两次上架 → 第二次 changed=False，不重复写。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-IDEM", paper_type="DRAFT")
    material = _mk_material(db_session, status=0, code=paper.paper_code)

    first = _set_status(client, admin_headers, material.material_id, 1).json()["paper_sync"]
    second = _set_status(client, admin_headers, material.material_id, 1).json()["paper_sync"]
    assert first["changed"] is True
    assert second["changed"] is False and second["after"] == "PUBLISHED"


def test_sync_failure_rolls_back_material_status(
        client, db_session, test_subject, test_admin, admin_headers, monkeypatch):
    """T9：联动抛异常 → 资料状态不提交，卷也不变（同事务，不会半成功）。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-TX", paper_type="PUBLISHED")
    material = _mk_material(db_session, status=1, code=paper.paper_code)

    from app.services import material_paper_sync

    def boom(*args, **kwargs):
        raise RuntimeError("sync exploded")

    monkeypatch.setattr(material_paper_sync, "sync_material", boom)
    with pytest.raises(RuntimeError):
        _set_status(client, admin_headers, material.material_id, 0)

    db_session.rollback()
    row = _refresh(db_session, StudyMaterial, "material_id", material.material_id)
    assert row.status == 1, "联动失败时资料状态不得提交"
    assert _paper_type(db_session, paper.paper_id) == "PUBLISHED"


def test_audit_detail_records_paper_transition(
        client, db_session, test_subject, test_admin, admin_headers):
    """T10：审计里那句话要能解释"卷为什么变了"。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-AUDIT")
    material = _mk_material(db_session, status=1, code=paper.paper_code)

    _set_status(client, admin_headers, material.material_id, 0)

    db_session.expire_all()
    log = (db_session.query(SysOperationLog)
           .filter(SysOperationLog.operation_type == "状态变更")
           .order_by(SysOperationLog.log_id.desc()).first())
    assert log is not None
    assert "下架" in log.operation_desc
    assert "P5-AUDIT" in log.operation_desc
    assert "PUBLISHED→DRAFT" in log.operation_desc


# ---------------------------------------------------------------- 权限

def test_student_cannot_change_status(
        client, db_session, test_subject, test_admin, test_user, auth_headers):
    """T12：非管理员 403，且卷不受影响。"""
    paper = _mk_paper(db_session, test_subject.subject_id, test_admin.user_id,
                      code="P5-PERM")
    material = _mk_material(db_session, status=1, code=paper.paper_code)

    r = _set_status(client, auth_headers, material.material_id, 0)
    assert r.status_code == 403, r.text
    assert _paper_type(db_session, paper.paper_id) == "PUBLISHED"
