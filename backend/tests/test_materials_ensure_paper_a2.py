# -*- coding: utf-8 -*-
"""A2（2026-11-08）：「试卷资料 → 可作答卷」。

解决 #127 那种"有资料无卷"：上传只落 `study_material` + `paper_code`，
`exam_paper` 里没有对应卷，学生端永远看不到。

覆盖：
- 建卷成功（元数据来自 paper_meta，状态固定 DRAFT）
- 幂等（同编号复用，不覆盖已有卷、不重复建）
- 已有 PUBLISHED 卷时只复用、不改状态
- 非试卷类型 / 无编号 → 400（带可操作提示）
- 权限：非管理员 403
- 无 paper_meta 时用兜底 120 分钟 / 100 分
- 建出的卷与资料 `paper_code` 一致；上架后经 P5 联动变 PUBLISHED（联动回归）
"""
import pytest

from app.models.models import ExamPaper, StudyMaterial


def _mk_material(db, *, subject="gongzhuan", mtype="paper", code="A2-T-1",
                 title="A2 测试卷", status=0, paper_meta=None):
    m = StudyMaterial(
        subject=subject, type=mtype, title=title, status=status,
        paper_code=code, badge=code, paper_meta=paper_meta,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _ensure(client, headers, mid):
    return client.post(f"/api/materials/admin/{mid}/ensure-paper", headers=headers)


def _papers(db):
    db.expire_all()
    return db.query(ExamPaper).all()


def test_creates_draft_paper_with_metadata(client, db_session, admin_headers):
    m = _mk_material(db_session, code="A2-PUB-1",
                     paper_meta='{"duration": 90, "total_score": 60.0}')
    r = _ensure(client, admin_headers, m.material_id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["paper_code"] == "A2-PUB-1"
    assert body["paper_type"] == "DRAFT"
    assert body["question_count"] == 0

    paper = db_session.query(ExamPaper).filter(
        ExamPaper.paper_code == "A2-PUB-1").one()
    assert paper.paper_type == "DRAFT"
    assert paper.duration == 90          # 取 paper_meta 订正
    assert float(paper.total_score) == 60.0
    assert paper.paper_name == "A2 测试卷"
    assert paper.subject_id == 3         # 公专
    assert paper.composition_method == "IMPORT"
    # 资料侧编号不变（关联键仍是 paper_code）
    db_session.refresh(m)
    assert m.paper_code == "A2-PUB-1"


def test_metadata_fallback_when_missing(client, db_session, admin_headers):
    m = _mk_material(db_session, code="A2-DEF-1")
    body = _ensure(client, admin_headers, m.material_id).json()
    paper = db_session.query(ExamPaper).filter(
        ExamPaper.paper_id == body["paper_id"]).one()
    assert paper.duration == 120
    assert float(paper.total_score) == 100.0


def test_is_idempotent(client, db_session, admin_headers):
    m = _mk_material(db_session, code="A2-IDEM-1")
    first = _ensure(client, admin_headers, m.material_id).json()
    second = _ensure(client, admin_headers, m.material_id).json()

    assert first["created"] is True
    assert second["created"] is False
    assert second["paper_id"] == first["paper_id"]
    assert len([p for p in _papers(db_session) if p.paper_code == "A2-IDEM-1"]) == 1


def test_reuses_existing_published_paper_without_touching_it(
        client, db_session, test_subject, test_admin, admin_headers):
    """同编号的卷已存在（哪怕是已发布）→ 只复用，绝不把状态改成 DRAFT。"""
    existing = ExamPaper(
        paper_name="已存在的卷", paper_code="A2-EXIST-1",
        subject_id=test_subject.subject_id, composition_method="MANUAL",
        creator_id=test_admin.user_id, duration=100, total_score=100,
        difficulty=3, exam_type="SIMULATION", paper_type="PUBLISHED",
        question_count=0, max_attempts=5,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    m = _mk_material(db_session, code="A2-EXIST-1")
    body = _ensure(client, admin_headers, m.material_id).json()

    assert body["created"] is False
    assert body["paper_id"] == existing.paper_id
    db_session.refresh(existing)
    assert existing.paper_type == "PUBLISHED", "不得覆盖已有卷状态"


def test_rejects_non_paper_material(client, db_session, admin_headers):
    m = _mk_material(db_session, mtype="card", code="", title="一张卡")
    r = _ensure(client, admin_headers, m.material_id)
    assert r.status_code == 400
    assert "只有" in r.json()["detail"]


def test_rejects_paper_without_code(client, db_session, admin_headers):
    m = _mk_material(db_session, code="", title="没编号的试卷资料")
    # badge 也清空，模拟"上传时解析失败"
    m.badge = None
    db_session.commit()
    r = _ensure(client, admin_headers, m.material_id)
    assert r.status_code == 400
    assert "编号" in r.json()["detail"]
    assert len(_papers(db_session)) == 0


def test_student_forbidden(client, db_session, auth_headers):
    m = _mk_material(db_session, code="A2-PERM-1")
    r = _ensure(client, auth_headers, m.material_id)
    assert r.status_code == 403
    assert len(_papers(db_session)) == 0


def test_missing_material_404(client, admin_headers):
    assert _ensure(client, admin_headers, 999999).status_code == 404


def test_publish_material_opens_paper_via_p5(client, db_session, admin_headers):
    """A2 + P5 串起来：建卷（DRAFT）→ 资料上架 → 卷自动 PUBLISHED。"""
    m = _mk_material(db_session, code="A2-P5-1", status=0)
    paper_id = _ensure(client, admin_headers, m.material_id).json()["paper_id"]

    r = client.put(f"/api/materials/admin/{m.material_id}/status",
                   json={"status": 1}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["paper_sync"]["after"] == "PUBLISHED"

    db_session.expire_all()
    paper = db_session.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).one()
    assert paper.paper_type == "PUBLISHED"
