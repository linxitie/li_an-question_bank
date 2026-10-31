"""备考资料（E8）模块测试（P2-36 / P2-39）。

覆盖：
- 登录用户首次打开资料详情 → 恰好发布一次 ``material.opened``；
- 同一用户同一资料再次打开 → 不重复发布（幂等）；
- 同一用户不同资料 → 各发布一次；
- 列表 / 进度上报等接口不发布学习行为事件；
- 匿名访问详情不发布，且不写打开记录；
- 学生调用上传接口返回 403，管理员可上传。
"""
import pytest

from app.api.v1.library import materials as materials_api
from app.core.trigger_types import TRIGGER_MATERIAL_OPENED
from app.models.models import StudyMaterial, UserMaterialProgress


@pytest.fixture
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append({"user_id": user_id, "trigger_type": trigger_type})
        return True

    monkeypatch.setattr(materials_api, "record_user_action", fake_record)
    return events


@pytest.fixture
def make_material(db_session):
    def _make(index: int, subject: str = "xingce") -> StudyMaterial:
        row = StudyMaterial(
            subject=subject,
            type="article",
            category="备考指南",
            title=f"行测备考指南 {index}",
            summary="摘要",
            content="<p>正文</p>",
            status=1,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        return row

    return _make


def _events(events, trigger_type):
    return [e for e in events if e["trigger_type"] == trigger_type]


def test_trigger_type_value_is_frozen():
    assert TRIGGER_MATERIAL_OPENED == "material.opened"


def test_first_detail_open_publishes_once(
    client, auth_headers, make_material, published
):
    material = make_material(1)

    response = client.get(
        f"/api/materials/{material.material_id}", headers=auth_headers
    )

    assert response.status_code == 200
    assert len(_events(published, TRIGGER_MATERIAL_OPENED)) == 1


def test_second_open_same_material_does_not_republish(
    client, auth_headers, make_material, published
):
    material = make_material(2)

    first = client.get(
        f"/api/materials/{material.material_id}", headers=auth_headers
    )
    second = client.get(
        f"/api/materials/{material.material_id}", headers=auth_headers
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(_events(published, TRIGGER_MATERIAL_OPENED)) == 1


def test_different_materials_publish_separately(
    client, auth_headers, make_material, published
):
    first_material = make_material(3)
    second_material = make_material(4)

    client.get(f"/api/materials/{first_material.material_id}", headers=auth_headers)
    client.get(f"/api/materials/{second_material.material_id}", headers=auth_headers)

    assert len(_events(published, TRIGGER_MATERIAL_OPENED)) == 2


def test_list_endpoint_does_not_publish(
    client, auth_headers, make_material, published
):
    make_material(5)

    response = client.get("/api/materials?subject=xingce", headers=auth_headers)

    assert response.status_code == 200
    assert published == []


def test_progress_report_does_not_republish_open_event(
    client, auth_headers, make_material, published
):
    material = make_material(6)
    client.get(f"/api/materials/{material.material_id}", headers=auth_headers)
    published.clear()

    response = client.post(
        "/api/materials/progress",
        headers=auth_headers,
        json={"material_id": material.material_id, "progress_percent": 100},
    )

    assert response.status_code == 200
    assert response.json()["completed"] is True
    assert published == []


def test_anonymous_detail_does_not_publish_or_record(
    client, db_session, make_material, published
):
    material = make_material(7)

    response = client.get(f"/api/materials/{material.material_id}")

    assert response.status_code == 200
    assert published == []
    assert db_session.query(UserMaterialProgress).count() == 0


def test_missing_material_does_not_publish(client, auth_headers, published):
    response = client.get("/api/materials/999999", headers=auth_headers)

    assert response.status_code == 404
    assert published == []


def test_student_cannot_upload_image(
    client, auth_headers, published
):
    response = client.post(
        "/api/materials/admin/upload/image",
        headers=auth_headers,
        files={"file": ("cover.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 403


def test_admin_can_upload_image(
    client, admin_headers, monkeypatch, published
):
    monkeypatch.setattr(
        materials_api,
        "_safe_image_upload",
        lambda file, db=None, user_id=None: "/uploads/materials/images/x.png",
    )

    response = client.post(
        "/api/materials/admin/upload/image",
        headers=admin_headers,
        files={"file": ("cover.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["url"] == "/uploads/materials/images/x.png"
