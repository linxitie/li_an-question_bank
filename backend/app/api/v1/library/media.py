from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
import os

from ....core.database import get_db
from ....core.config import settings
from ....models.models import SysUser as UserModel
from ....core.security import get_current_user
from ....schemas.schemas import UserBase
from ....services import media_service

router = APIRouter(prefix="/api/media",tags=['论坛'])


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    current_user: UserBase= Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed_extensions = [".mp4", ".mov", ".avi", ".wmv", ".flv", ".webm"]
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB")
    
    if settings.MEDIA_STORE_ENABLED:
        try:
            asset = media_service.store_bytes(
                db, content, kind="video", original_name=file.filename,
                created_by=getattr(current_user, "user_id", None),
                max_bytes=max_size,
            )
        except media_service.MediaTooLarge:
            raise HTTPException(status_code=400, detail="File size exceeds 50MB")
        except media_service.MediaValidationError:
            raise HTTPException(status_code=400, detail="Invalid file format")
        except media_service.ObjectStoreUnavailable:
            raise HTTPException(status_code=503, detail="Storage temporarily unavailable")
        db.commit()
        return {"url": f"/media/{asset.asset_id}"}

    # 回滚分支：只取 basename，禁止原始文件名路径穿越。
    upload_dir = "./uploads/videos"
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "video")
    file_path = os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/videos/{safe_name}"}


@router.post("/import")
async def import_data(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    allowed_extensions = [".csv", ".xlsx", ".json"]
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    import_dir = "./uploads/imports"
    os.makedirs(import_dir, exist_ok=True)
    
    file_path = os.path.join(import_dir, file.filename)
    content = await file.read()
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {"message": "File uploaded successfully. Import will be processed."}


@router.get("/export")
async def export_data(
    type: str = "questions",
    current_user: UserBase = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    export_dir = "./uploads/exports"
    os.makedirs(export_dir, exist_ok=True)
    
    if type == "users":
        users = db.query(UserModel).all()
        content = "\n".join([f"{u.id},{u.username},{u.email},{u.phone}" for u in users])
        filename = f"users_{current_user.id}.csv"
    elif type == "questions":
        content = "Question export placeholder"
        filename = f"questions_{current_user.id}.csv"
    else:
        raise HTTPException(status_code=400, detail="Invalid export type")
    
    file_path = os.path.join(export_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return {"message": f"Data exported to {filename}"}