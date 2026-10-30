# -*- coding: utf-8 -*-
"""RT-8 题组材料图片上传端点测试。"""
import base64
import shutil
from pathlib import Path

import pytest

from app.models.models import QuestionGroup

# 真实 1x1 PNG（不是伪造文本），用于走通类型/大小校验与落盘。
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8B"
    "QDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

GROUP_IMG_ROOT = (
    Path(__file__).resolve().parents[1] / "app" / "static" / "question-groups"
)


@pytest.fixture
def group_id(db_session):
    group = QuestionGroup(group_type="material", shared_content="测试材料")
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    gid = group.id
    try:
        yield gid
    finally:
        shutil.rmtree(GROUP_IMG_ROOT / str(gid), ignore_errors=True)


def _post(client, gid, filename, payload, content_type, headers):
    return client.post(
        f"/api/questions/group/{gid}/images",
        files={"file": (filename, payload, content_type)},
        headers=headers,
    )


def test_upload_png_success(client, admin_headers, group_id):
    resp = _post(client, group_id, "x.png", PNG_1X1, "image/png", admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["url"].startswith(f"/static/question-groups/{group_id}/")
    assert data["filename"].endswith(".png")

    saved = GROUP_IMG_ROOT / str(group_id) / data["filename"]
    assert saved.is_file()
    assert saved.read_bytes() == PNG_1X1


def test_upload_unknown_group_returns_404(client, admin_headers):
    resp = _post(client, 999999, "x.png", PNG_1X1, "image/png", admin_headers)
    assert resp.status_code == 404, resp.text


def test_upload_non_image_returns_400(client, admin_headers, group_id):
    resp = _post(
        client, group_id, "x.txt", b"not an image", "text/plain", admin_headers
    )
    assert resp.status_code == 400, resp.text


def test_upload_requires_teacher_or_admin(client, group_id):
    resp = _post(client, group_id, "x.png", PNG_1X1, "image/png", None)
    assert resp.status_code in (401, 403), resp.text
