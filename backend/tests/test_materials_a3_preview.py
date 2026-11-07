# -*- coding: utf-8 -*-
"""A3 回归（2026-11-07）：管理端统一预览契约 `GET /api/materials/admin/{id}/preview`。

一个契约覆盖 6 类：卡片 / 文章 / 讲义 / 试卷 / 两种视频。
本轮只保证 card / article / video 有内容；chapters / files / paper 先给空值（B/C 批填）。
"""
from app.models.models import StudyMaterial


def _mk(db, creator_id, **kw):
    body = dict(subject="gongzhuan", type="card", title="样例资料",
                card_front="正面", card_back="背面", status=0, creator_id=creator_id)
    body.update(kw)
    m = StudyMaterial(**body)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _preview(client, headers, mid):
    return client.get(f"/api/materials/admin/{mid}/preview", headers=headers)


class TestContract:
    def test_card_shape(self, client, db_session, test_admin, admin_headers):
        m = _mk(db_session, test_admin.user_id, type="card",
                card_front="继续盘问的适用对象？", card_back="四类人员",
                cover_image="/uploads/c1.png", content='<p><img src="/uploads/c2.png" /></p>')
        r = _preview(client, admin_headers, m.material_id)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["type"] == "card" and d["type_label"] == "知识卡片"
        assert d["subject_label"] == "公专"
        assert d["card"]["front"] == "继续盘问的适用对象？"
        assert d["card"]["back"] == "四类人员"
        assert d["card"]["images"] == ["/uploads/c1.png", "/uploads/c2.png"]
        # 卡片不走 content_html（正反面单独给）
        assert d["content_html"] is None
        assert d["video"] is None

    def test_article_html_is_sanitized(self, client, db_session, test_admin, admin_headers):
        m = _mk(db_session, test_admin.user_id, type="article", title="申论四步法",
                content='<p>正文</p><script>alert(1)</script><img src=x onerror=alert(2)>')
        d = _preview(client, admin_headers, m.material_id).json()
        assert d["type"] == "article"
        assert "<script" not in d["content_html"].lower()
        assert "onerror" not in d["content_html"].lower()
        assert "正文" in d["content_html"]
        assert d["card"] is None

    def test_video_url(self, client, db_session, test_admin, admin_headers):
        m = _mk(db_session, test_admin.user_id, type="video_intro", title="入门课",
                video_id=77, duration=300)
        d = _preview(client, admin_headers, m.material_id).json()
        assert d["video"]["url"] == "/api/video/77/stream"
        assert d["duration"] == 300
        assert d["content_html"] is None

    def test_video_without_id_gives_empty_url(self, client, db_session, test_admin, admin_headers):
        m = _mk(db_session, test_admin.user_id, type="video_advanced", title="无视频")
        d = _preview(client, admin_headers, m.material_id).json()
        assert d["video"]["url"] == ""

    def test_future_fields_are_empty_but_present(self, client, db_session, test_admin, admin_headers):
        """chapters / files / paper / uploaded_at 必须先存在（契约稳定），值为空。"""
        m = _mk(db_session, test_admin.user_id, type="lecture", title="讲义", content="<p>第一章</p>")
        d = _preview(client, admin_headers, m.material_id).json()
        assert d["chapters"] == []
        assert d["files"] == []
        assert d["paper"] is None
        assert d["uploaded_at"] is None
        assert "第一章" in d["content_html"]


class TestMeta:
    def test_publisher_and_created_at(self, client, db_session, test_admin, admin_headers):
        m = _mk(db_session, test_admin.user_id)
        d = _preview(client, admin_headers, m.material_id).json()
        assert d["publisher"]["id"] == test_admin.user_id
        assert d["publisher"]["role_label"] == "管理员"
        assert d["created_at"].endswith("+08:00")

    def test_unpublished_is_visible_to_admin(self, client, db_session, test_admin, admin_headers):
        """下架（status=0）资料管理员也要能预览——这正是管理端预览的意义。"""
        m = _mk(db_session, test_admin.user_id, status=0)
        assert _preview(client, admin_headers, m.material_id).json()["status"] == 0


class TestGuard:
    def test_missing_material_404(self, client, db_session, test_admin, admin_headers):
        assert _preview(client, admin_headers, 999999).status_code == 404

    def test_student_forbidden(self, client, db_session, auth_headers):
        assert client.get("/api/materials/admin/1/preview", headers=auth_headers).status_code == 403

    def test_anonymous_unauthorized(self, client, db_session):
        assert client.get("/api/materials/admin/1/preview").status_code in (401, 403)
