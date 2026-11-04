"""论坛/反馈图片上传（P1）。

安全策略：
- 扩展名白名单 + Pillow 真实解码校验，防止伪造扩展名；
- 单张 ≤5MB；
- 非 GIF 一律重编码，顺带去掉 EXIF；
- UUID 文件名 + 按年月分目录，避免覆盖与路径穿越；
- 返回值与论坛 attachments 结构对齐。
"""
import io
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image

from ....core.config import settings
from ....core.security import get_current_user
from ....models.models import SysUser

router = APIRouter(prefix="/api/media", tags=["媒体"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def _decode_image(content: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="文件不是有效图片") from exc
    # verify() 之后需要重新打开才能读取像素
    return Image.open(io.BytesIO(content))


def _reencode(image: Image.Image, ext: str) -> tuple[bytes, str, str]:
    """返回 (bytes, ext, mime)。GIF 保留原图，其余重编码去 EXIF。"""
    if image.format == "GIF":
        buffer = io.BytesIO()
        image.save(buffer, format="GIF", save_all=True)
        return buffer.getvalue(), ".gif", "image/gif"

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    buffer = io.BytesIO()
    if image.format == "PNG" or ext == ".png":
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), ".png", "image/png"
    if image.format == "WEBP" or ext == ".webp":
        image.save(buffer, format="WEBP", quality=88)
        return buffer.getvalue(), ".webp", "image/webp"

    image.convert("RGB").save(buffer, format="JPEG", quality=88, optimize=True)
    return buffer.getvalue(), ".jpg", "image/jpeg"


@router.post("/image", summary="上传论坛/反馈图片")
async def upload_image(
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user),
):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/gif/webp")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="图片不能超过 5MB")

    image = _decode_image(content)
    encoded, out_ext, mime = _reencode(image, ext)
    if len(encoded) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="图片压缩后仍超过 5MB")

    now = datetime.now()
    relative_dir = f"forum/{now:%Y%m}"
    upload_dir = os.path.join(settings.UPLOAD_DIR, "forum", f"{now:%Y%m}")
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{out_ext}"
    with open(os.path.join(upload_dir, stored_name), "wb") as handle:
        handle.write(encoded)

    return {
        "url": f"/uploads/{relative_dir}/{stored_name}",
        "name": filename,
        "size": len(encoded),
        "type": mime,
        "width": image.width,
        "height": image.height,
    }
