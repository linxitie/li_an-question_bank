# -*- coding: utf-8 -*-
"""资料原件留档服务（B1，2026-11-07）。

职责：把上传/导入的 **原始文件**（docx/xlsx/pdf）落到磁盘并登记到 `material_file`，
以及为下载接口提供安全路径解析。三类使用者：

1. 导入确认（`materials.import_confirm`）→ 解析完成后把源文件留档，再删临时文件；
2. 管理端上传（B2 批量上传）→ 直接落档；
3. 下载接口（`GET /api/materials/files/{file_id}/download`）→ `resolve_abs_path()` 取物理路径。

三条硬约束（都是被事故教出来的）：

* **路径不得逃逸根目录**：`storage_path` 只接受"相对路径"，落盘前 `resolve()` 后必须仍在
  `MATERIAL_FILES_DIR` 之下（`resolve_abs_path` 里用 `is_relative_to` 兜住，
  防的是历史脏数据/人为改库把 `../../.env` 当文件读）。
* **写入必须原子**：先写 `*.part` 再 `os.replace()`。半截文件被当成完整原件，比没有更糟。
* **内容寻址**：物理文件名 = `sha256 + 扩展名`，同一份文件只写一次；
  删除资料**不删物理文件**，清理交给独立脚本（避免"引用计数算错→把别人还在用的文件删了"）。
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.models import MaterialFile

logger = logging.getLogger(__name__)

#: 允许留档的扩展名 → 下载时的 Content-Type
ALLOWED_EXT_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "pdf": "application/pdf",
}
#: 单文件上限（与导入上传一致，20MB）
MAX_FILE_BYTES = 20 * 1024 * 1024
#: 角色白名单
ROLES = ("primary", "attachment")


def files_root() -> Path:
    """原件根目录：`settings.MATERIAL_FILES_DIR`（默认 `backend/storage/material_files`）。

    为什么不用 `/uploads`：那里是 `StaticFiles` **公开挂载**，试卷原件放进去等于任何人拿到
    URL 就能下。
    为什么也不用 `backend/data/`（与 SQLite 同目录）：实测在 OneDrive 里每写一个新文件都会触发
    目录同步扫描，扫描期间库文件被锁 → 上传/导入接口偶发卡死 30s。独立目录后测试 11 例连跑稳定。
    """
    return Path(settings.MATERIAL_FILES_DIR).resolve()


def _ext_of(name: str) -> str:
    return (os.path.splitext(name or "")[1].lstrip(".") or "").lower()


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def storage_rel_path(sha256: str, ext: str) -> str:
    """内容寻址的相对路径：`ab/abcdef….docx`（前两位分桶，避免单目录堆几万个文件）。"""
    return f"{sha256[:2]}/{sha256}.{ext}"


def resolve_abs_path(rel_or_row) -> Path:
    """把 `storage_path` 解析成绝对路径，并确认没有逃出根目录。

    非法（绝对路径 / 越界 / 不存在）一律抛 `FileNotFoundError`，由调用方转成 404——
    不区分"不存在"和"越界"，避免给探测者额外信息。
    """
    rel = rel_or_row.storage_path if isinstance(rel_or_row, MaterialFile) else str(rel_or_row or "")
    if not rel or os.path.isabs(rel):
        raise FileNotFoundError("非法的存储路径")
    root = files_root()
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise FileNotFoundError("非法的存储路径")
    if not target.is_file():
        raise FileNotFoundError("文件不存在")
    return target


def _atomic_write(target: Path, src: Path) -> None:
    """先写 `.part` 再 `os.replace`：避免半截文件被当成完整原件。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    if src is not None:
        shutil.copyfile(src, tmp)
    os.replace(tmp, target)


def save_bytes(db: Session, material_id: int, data: bytes, file_name: str,
               role: str = "primary", source: str = "upload",
               uploader_id: Optional[int] = None) -> MaterialFile:
    """保存字节流原件。同内容（sha256）在磁盘上只写一次。"""
    if role not in ROLES:
        raise ValueError(f"role 只能是 {ROLES}")
    ext = _ext_of(file_name)
    if ext not in ALLOWED_EXT_MIME:
        raise ValueError("仅支持 docx/doc/xlsx/xls/pdf 原件")
    if not data:
        raise ValueError("空文件不能留档")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"文件超过 {MAX_FILE_BYTES // 1024 // 1024}MB 上限")

    sha = sha256_of_bytes(data)
    rel = storage_rel_path(sha, ext)
    target = files_root() / rel
    if not target.is_file():
        files_root().mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        os.replace(tmp, target)
    return _upsert_row(db, material_id, rel, sha, len(data), file_name, ext,
                       role=role, source=source, uploader_id=uploader_id)


def save_from_path(db: Session, material_id: int, src_path: Path | str, file_name: str,
                   role: str = "primary", source: str = "import",
                   uploader_id: Optional[int] = None) -> MaterialFile:
    """保存已有临时文件（导入确认时用）。文件不存在/超限/扩展名不支持 → 抛异常由调用方降级。"""
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError("源文件不存在")
    ext = _ext_of(file_name or src.name)
    if ext not in ALLOWED_EXT_MIME:
        raise ValueError("仅支持 docx/doc/xlsx/xls/pdf 原件")
    size = src.stat().st_size
    if size <= 0:
        raise ValueError("空文件不能留档")
    if size > MAX_FILE_BYTES:
        raise ValueError(f"文件超过 {MAX_FILE_BYTES // 1024 // 1024}MB 上限")

    sha = sha256_of_file(src)
    rel = storage_rel_path(sha, ext)
    target = files_root() / rel
    if not target.is_file():
        _atomic_write(target, src)
    return _upsert_row(db, material_id, rel, sha, size, file_name or src.name, ext,
                       role=role, source=source, uploader_id=uploader_id)


def _upsert_row(db: Session, material_id: int, rel: str, sha: str, size: int,
                file_name: str, ext: str, role: str, source: str,
                uploader_id: Optional[int]) -> MaterialFile:
    """同 (material, sha, role) 只登记一行；重复留档直接返回旧行。"""
    row = (db.query(MaterialFile)
           .filter(MaterialFile.material_id == material_id,
                   MaterialFile.sha256 == sha,
                   MaterialFile.role == role)
           .first())
    if row:
        return row
    row = MaterialFile(
        material_id=material_id, role=role, file_name=(file_name or "")[:255],
        file_ext=ext, mime_type=ALLOWED_EXT_MIME.get(ext, "application/octet-stream"),
        file_size=size, sha256=sha, storage_path=rel, source=source,
        uploader_id=uploader_id)
    db.add(row)
    db.flush()
    return row


def list_for_material(db: Session, material_id: int) -> list[MaterialFile]:
    """主文件在前、附件在后，各自按登记时间升序（B2 配对后顺序稳定）。"""
    rows = (db.query(MaterialFile)
            .filter(MaterialFile.material_id == material_id)
            .all())
    order = {"primary": 0, "attachment": 1}
    return sorted(rows, key=lambda r: (order.get(r.role or "", 9), r.file_id or 0))


def human_size(size: Optional[int]) -> str:
    """字节 → 人读大小（列表/抽屉展示用）。"""
    n = int(size or 0)
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def can_download(*, is_admin: bool, material_status: Optional[int]) -> bool:
    """下载权限判定（纯函数，便于单测与 B2 复用）。

    口径（用户 2026-11-07 裁定 A）：
      · 管理员（含超管）→ 一律可下（含未上架 `0`、已删除 `-1`，核对原件是恢复的前提）；
      · 其他人 → 只有**已上架**（`status == 1`）的资料可下；未上架/已删除都不可。

    把这条规则从路由里抽出来，是因为它是**安全边界**：写死在端点里就只能靠 HTTP 用例验证，
    而 HTTP 用例一旦跑不动（见 B1 交付记录里的 TestClient 流式响应坑），边界就没人守了。
    """
    if is_admin:
        return True
    return material_status == 1


def serialize(row: MaterialFile) -> dict:
    """给管理端预览/列表的契约（A3 的 `files` 字段填这个）。"""
    return {
        "file_id": row.file_id,
        "file_name": row.file_name,
        "file_ext": row.file_ext,
        "mime_type": row.mime_type,
        "size": row.file_size,
        "size_label": human_size(row.file_size),
        "sha256_short": (row.sha256 or "")[:12],
        "role": row.role,
        "role_label": "主文件" if row.role == "primary" else "附件",
        "source": row.source,
        "download_url": f"/api/materials/files/{row.file_id}/download",
        "uploaded_at": row.create_time.strftime("%Y-%m-%d %H:%M") if row.create_time else None,
    }


def orphan_count(db: Session) -> int:
    """物理文件多于登记行的数量（对账用；清理脚本删除前先看这个数）。"""
    root = files_root()
    if not root.is_dir():
        return 0
    on_disk = sum(1 for p in root.rglob("*") if p.is_file() and p.suffix != ".part")
    registered = db.query(MaterialFile).count()
    return max(0, on_disk - registered)
