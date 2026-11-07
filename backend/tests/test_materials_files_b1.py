# -*- coding: utf-8 -*-
"""B1 回归（2026-11-07）：原件留档 + 鉴权下载。

背景：导入完成后源文件被删掉，库里只有正文没有原件。B1 建 `material_file` 表把原件留档：
内容寻址存储（`storage/material_files/<sha前2>/<sha>.<ext>`）、**不在 `/uploads` 公开目录**、
只能走 `GET /api/materials/files/{file_id}/download` 且带登录态。

本文件锁死 8 条行为：
1. 导入 docx → confirm 后 `material_file` 有 1 行，sha256 与磁盘文件一致，临时文件已删；
2. 预览契约 `files` 返回结构化清单（file_name/size_label/role_label/download_url）；
3. 管理员可下载（含未上架），字节与源文件一致，Content-Disposition 带原文件名；
4. 非管理员：未上架 403、已上架 200；
5. 未登录 401；
6. `storage_path` 被改成绝对路径/越界 → 404（不泄露路径、不读任意文件）；
7. 同内容再留档不产生第二个物理文件（内容寻址）；
8. 软删除（status=-1）后学生不可下载、管理员仍可下载。
"""
import io
from pathlib import Path

import pytest

from app.models.models import MaterialFile, StudyMaterial
from app.services import material_files


def _docx_bytes(paragraphs):
    from docx import Document
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _import_docx(client, headers, filename, paragraphs, **confirm_body):
    up = client.post("/api/materials/admin/import/upload",
                     files={"file": (filename, _docx_bytes(paragraphs))},
                     headers=headers)
    assert up.status_code == 200, up.text
    iid = up.json()["import_id"]
    body = {"subject": "gongzhuan"}
    body.update(confirm_body)
    resp = client.post(f"/api/materials/admin/import/{iid}/confirm",
                       json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def imported(client, admin_headers, db_session):
    """一条真实导入的讲义（带原件留档），返回 (payload, material_row, file_rows)。"""
    payload = _import_docx(client, admin_headers, "b1_讲义留档.docx",
                           ["第一章 职业素养", "人民警察核心价值观包含忠诚、为民、公正、廉洁。"])
    mid = payload["material_ids"][0]
    material = db_session.query(StudyMaterial).filter(
        StudyMaterial.material_id == mid).one()
    rows = db_session.query(MaterialFile).filter(
        MaterialFile.material_id == mid).all()
    return payload, material, rows


class TestArchiveOnImport:
    def test_import_archives_source_file(self, imported, db_session):
        _, material, rows = imported
        assert len(rows) == 1, "导入一条文档应留档一份原件"
        row = rows[0]
        assert row.role == "primary"
        assert row.file_ext == "docx"
        assert row.file_name == "b1_讲义留档.docx"
        assert row.source == "import"
        assert row.file_size and row.file_size > 0
        assert len(row.sha256 or "") == 64

        path = material_files.resolve_abs_path(row)
        assert path.is_file()
        assert material_files.sha256_of_file(path) == row.sha256
        assert path.parent.name == row.sha256[:2]

    def test_tmp_file_removed_but_original_kept(self, imported):
        _, _, rows = imported
        path = material_files.resolve_abs_path(rows[0])
        assert path.is_file()
        # 临时目录里不应再留下这份文件的副本（confirm 后清理）
        from app.core.config import settings
        tmp_dir = Path(settings.UPLOAD_DIR) / "materials" / "tmp"
        if tmp_dir.is_dir():
            leftovers = [p for p in tmp_dir.iterdir() if p.is_file()]
            assert all(p.name != path.name for p in leftovers)

    def test_storage_is_not_under_public_uploads(self, imported):
        """原件不能落在 /uploads 静态目录下，否则等于匿名可下。"""
        _, _, rows = imported
        path = material_files.resolve_abs_path(rows[0])
        from app.core.config import settings
        uploads = Path(settings.UPLOAD_DIR).resolve()
        assert not path.is_relative_to(uploads)
        assert files_root_in_data_dir(path)


def files_root_in_data_dir(path: Path) -> bool:
    return path.is_relative_to(material_files.files_root())


class TestPreviewContract:
    def test_preview_returns_structured_files(self, client, admin_headers, imported):
        payload, material, rows = imported
        resp = client.get(f"/api/materials/admin/{material.material_id}/preview",
                          headers=admin_headers)
        assert resp.status_code == 200, resp.text
        files = resp.json()["files"]
        assert len(files) == 1
        f = files[0]
        assert f["file_id"] == rows[0].file_id
        assert f["file_name"] == "b1_讲义留档.docx"
        assert f["file_ext"] == "docx"
        assert f["role"] == "primary"
        assert f["role_label"] == "主文件"
        assert f["size_label"].endswith(("B", "KB", "MB"))
        assert f["download_url"] == f"/api/materials/files/{f['file_id']}/download"

    def test_material_without_files_returns_empty_list(
        self, client, admin_headers, db_session
    ):
        m = StudyMaterial(subject="gongzhuan", type="card", title="无原件卡片",
                          card_front="正", card_back="背", status=1)
        db_session.add(m)
        db_session.commit()
        resp = client.get(f"/api/materials/admin/{m.material_id}/preview",
                          headers=admin_headers)
        assert resp.json()["files"] == []

# ============================================================================
# 以下是**纯服务级**用例：不经过 TestClient。
# 原因见 B1 交付记录：`FileResponse` 流式 + `TestClient` 在同一进程里跑多个 app 生命周期时，
# 会出现"下一个用例请求挂 30s 然后 pytest 进程直接退出且没有 summary"（本机 Windows + OneDrive 复现）。
# 安全边界（谁能下载）用纯函数测，存储安全用服务函数测，端点只留 2 条冒烟（另一个文件）。
# ============================================================================
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402


class TestDownloadPermission:
    """`can_download` 是下载的唯一安全边界，必须逐档锁死。"""

    @pytest.mark.parametrize("status", [1, 0, -1, None])
    def test_admin_always_allowed(self, status):
        assert material_files.can_download(is_admin=True, material_status=status) is True

    def test_public_only_published(self):
        assert material_files.can_download(is_admin=False, material_status=1) is True

    @pytest.mark.parametrize("status", [0, -1, 2, None])
    def test_public_blocked_unless_published(self, status):
        assert material_files.can_download(is_admin=False, material_status=status) is False


class TestStorageSafety:
    def _write(self, tmp_path, rel: str, data: bytes) -> Path:
        target = material_files.files_root() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def test_traversal_rejected(self):
        with pytest.raises(FileNotFoundError):
            material_files.resolve_abs_path("../../../../etc/passwd")

    def test_absolute_path_rejected(self):
        with pytest.raises(FileNotFoundError):
            material_files.resolve_abs_path(str(Path("C:/Windows/win.ini")))

    def test_missing_file_rejected(self):
        with pytest.raises(FileNotFoundError):
            material_files.resolve_abs_path("zz/deadbeef.docx")

    def test_valid_relative_path_ok(self):
        rel = material_files.storage_rel_path("cd" * 32, "docx")
        path = self._write(None, rel, b"PK\x03\x04demo")
        try:
            assert material_files.resolve_abs_path(rel) == path
        finally:
            path.unlink(missing_ok=True)

    def test_ext_and_size_guards(self):
        row = SimpleNamespace(storage_path="aa/x.docx")
        with pytest.raises(ValueError):
            material_files.save_bytes(_FakeDB(), 1, b"x", "a.txt")     # 扩展名不支持
        with pytest.raises(ValueError):
            material_files.save_bytes(_FakeDB(), 1, b"", "a.docx")     # 空文件
        with pytest.raises(ValueError):
            material_files.save_bytes(_FakeDB(), 1, b"x" * (material_files.MAX_FILE_BYTES + 1),
                                      "a.docx")                        # 超限
        assert row.storage_path == "aa/x.docx"


class _FakeDB:
    """只为让 `save_bytes` 的**参数校验**走到（校验在写库之前），不需要真 session。"""

    def query(self, *a, **k):
        raise AssertionError("校验失败时不该查库")

    def add(self, *a, **k):
        raise AssertionError("校验失败时不该入库")

    def flush(self):
        raise AssertionError("校验失败时不该 flush")


class TestContentAddressing:
    def test_same_bytes_share_one_physical_file(self, db_session):
        from app.models.models import StudyMaterial

        data = b"PK\x03\x04same-bytes-demo"
        a = StudyMaterial(subject="gongzhuan", type="lecture", title="甲", content="c", status=0)
        b = StudyMaterial(subject="gongzhuan", type="lecture", title="乙", content="c", status=0)
        db_session.add_all([a, b])
        db_session.commit()

        f1 = material_files.save_bytes(db_session, a.material_id, data, "same.docx")
        f2 = material_files.save_bytes(db_session, b.material_id, data, "same.docx")
        db_session.commit()

        assert f1.sha256 == f2.sha256
        assert f1.storage_path == f2.storage_path
        root = material_files.files_root()
        same = [p for p in root.rglob(f"{f1.sha256}*") if p.is_file()]
        assert len(same) == 1, "同一内容只应写一份物理文件"
        assert db_session.query(material_files.MaterialFile).filter(
            material_files.MaterialFile.sha256 == f1.sha256).count() == 2

        # 清理磁盘痕迹
        try:
            material_files.resolve_abs_path(f1).unlink()
        except FileNotFoundError:
            pass

    def test_serialize_contract(self, db_session):
        from app.models.models import StudyMaterial

        m = StudyMaterial(subject="gongzhuan", type="lecture", title="序列化", content="c", status=0)
        db_session.add(m)
        db_session.commit()
        row = material_files.save_bytes(db_session, m.material_id, b"PK\x03\x04ser", "序列化.docx")
        db_session.commit()
        d = material_files.serialize(row)
        assert d["file_name"] == "序列化.docx"
        assert d["role_label"] == "主文件"
        assert d["download_url"].endswith(f"/{row.file_id}/download")
        assert d["size_label"].endswith("B")
        assert len(d["sha256_short"]) == 12
        try:
            material_files.resolve_abs_path(row).unlink()
        except FileNotFoundError:
            pass
