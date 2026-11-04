"""
视频资源模块路由
"""
import os
import uuid
import shutil
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.orm import Session

from ....core.config import settings
from ....core.database import get_db
from ....models.models import VideoResource, QuestionBank, SysUser
from ....schemas.schemas import VideoResourceResponse, VideoListResponse, SuccessResponse
from ....core.security import get_current_user, require_admin
from ....services import media_service

router = APIRouter(prefix="/api/video", tags=["视频资源"])

# 允许的视频格式
ALLOWED_FORMATS = {"mp4", "avi", "mov", "wmv", "flv", "webm", "mkv"}


def init_upload_dirs():
    """初始化上传目录"""
    os.makedirs(settings.VIDEO_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "chunks"), exist_ok=True)


@router.get("/list", response_model=VideoListResponse, summary="获取视频列表")
async def get_video_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    question_id: Optional[int] = Query(None, description="按题目筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    db: Session = Depends(get_db)
):
    """
    获取视频列表，支持按题目和状态筛选
    """
    query = db.query(VideoResource)

    if question_id:
        query = query.filter(VideoResource.question_id == question_id)
    if status:
        query = query.filter(VideoResource.status == status)

    total = query.count()
    videos = query.order_by(
        VideoResource.create_time.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    return VideoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=videos
    )


@router.get("/{video_id}", response_model=VideoResourceResponse, summary="获取视频信息")
async def get_video_info(
    video_id: int,
    db: Session = Depends(get_db)
):
    """
    获取视频详细信息
    """
    video = db.query(VideoResource).filter(VideoResource.video_id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    return video


@router.post("/upload", response_model=VideoResourceResponse, summary="上传视频")
async def upload_video(
    file: UploadFile = File(...),
    question_id: Optional[int] = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传视频文件（小文件直传）
    """
    init_upload_dirs()

    # 验证文件格式
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持格式: {file_ext}，支持: {', '.join(sorted(ALLOWED_FORMATS))}"
        )

    # 验证文件大小
    if file.size > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / 1024 / 1024
        raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 {max_mb:.0f}MB）")

    # 验证题目ID
    if question_id:
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == question_id
        ).first()
        if not question:
            raise HTTPException(status_code=404, detail="关联题目不存在")

    if settings.MEDIA_STORE_ENABLED:
        # F3：视频字节进对象存储，storage_path 只保存稳定代理 URL。
        try:
            asset = media_service.store_file(
                db, file.file, kind="video", original_name=file.filename,
                created_by=current_user.user_id,
                max_bytes=settings.MAX_UPLOAD_SIZE,
            )
        except media_service.MediaTooLarge:
            max_mb = settings.MAX_UPLOAD_SIZE / 1024 / 1024
            raise HTTPException(400, f"文件大小超过限制（最大 {max_mb:.0f}MB）")
        except media_service.MediaValidationError as exc:
            raise HTTPException(400, str(exc))
        except media_service.ObjectStoreUnavailable:
            raise HTTPException(503, "视频存储暂不可用，请稍后重试")
        storage_path = f"/media/{asset.asset_id}"
        file_size = asset.size_bytes
    else:
        # 回滚分支：保留原 uploads/videos 写路径。
        file_uuid = str(uuid.uuid4())
        filename = f"{file_uuid}.{file_ext}"
        storage_path = os.path.join(settings.VIDEO_DIR, filename)

        with open(storage_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = file.size

    # 创建视频记录
    video = VideoResource(
        question_id=question_id,
        title=file.filename,
        original_filename=file.filename,
        storage_path=storage_path,
        duration=0,
        file_size=file_size,
        format=file_ext,
        status="COMPLETED"
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    return video


@router.post("/upload/init", response_model=SuccessResponse, summary="初始化分片上传")
async def init_chunk_upload(
    filename: str,
    file_size: int,
    question_id: Optional[int] = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    初始化分片上传（大文件）
    """
    init_upload_dirs()

    file_ext = filename.split(".")[-1].lower() if "." in filename else ""
    if file_ext not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持格式: {file_ext}")

    if file_size > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / 1024 / 1024
        raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 {max_mb:.0f}MB）")

    if question_id:
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == question_id
        ).first()
        if not question:
            raise HTTPException(status_code=404, detail="关联题目不存在")

    upload_id = str(uuid.uuid4())
    chunk_size = 5 * 1024 * 1024  # 5MB
    total_chunks = (file_size + chunk_size - 1) // chunk_size

    return SuccessResponse(
        data={
            "upload_id": upload_id,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
        },
        message="分片上传初始化成功"
    )


@router.post("/upload/chunk", response_model=SuccessResponse, summary="上传分片")
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user)
):
    """
    上传单个分片
    """
    init_upload_dirs()

    chunk_dir = os.path.join(settings.UPLOAD_DIR, "chunks", upload_id)
    os.makedirs(chunk_dir, exist_ok=True)

    chunk_path = os.path.join(chunk_dir, f"{chunk_index:06d}.chunk")

    with open(chunk_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return SuccessResponse(message=f"分片 {chunk_index} 上传成功")


@router.post("/upload/complete", response_model=VideoResourceResponse, summary="完成分片上传")
async def complete_chunk_upload(
    upload_id: str,
    filename: str,
    question_id: Optional[int] = None,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    合并分片，完成上传
    """
    init_upload_dirs()

    chunk_dir = os.path.join(settings.UPLOAD_DIR, "chunks", upload_id)

    if not os.path.exists(chunk_dir):
        raise HTTPException(status_code=404, detail="上传会话不存在或已过期")

    # 获取所有分片并排序
    chunks = sorted(
        [f for f in os.listdir(chunk_dir) if f.endswith(".chunk")],
        key=lambda x: int(x.split(".")[0])
    )

    if not chunks:
        raise HTTPException(status_code=400, detail="未收到任何分片文件")

    # 验证题目
    if question_id:
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == question_id
        ).first()
        if not question:
            shutil.rmtree(chunk_dir, ignore_errors=True)
            raise HTTPException(status_code=404, detail="关联题目不存在")

    # 合并分片（complete 也可能被直接调用，必须重新校验扩展名）
    file_ext = filename.split(".")[-1].lower()
    if file_ext not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持格式: {file_ext}")

    if settings.MEDIA_STORE_ENABLED:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=f".{file_ext}")
        os.close(tmp_fd)
        try:
            total_size = 0
            with open(tmp_path, "wb") as final_file:
                for chunk_name in chunks:
                    chunk_path = os.path.join(chunk_dir, chunk_name)
                    with open(chunk_path, "rb") as chunk_file:
                        while True:
                            data = chunk_file.read(1024 * 1024)
                            if not data:
                                break
                            total_size += len(data)
                            if total_size > settings.MAX_UPLOAD_SIZE:
                                raise HTTPException(
                                    400,
                                    f"文件大小超过限制（最大 "
                                    f"{settings.MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB）",
                                )
                            final_file.write(data)
            try:
                with open(tmp_path, "rb") as fh:
                    asset = media_service.store_file(
                        db, fh, kind="video", original_name=filename,
                        created_by=current_user.user_id,
                        max_bytes=settings.MAX_UPLOAD_SIZE,
                    )
            except media_service.MediaTooLarge:
                raise HTTPException(400, "文件大小超过限制")
            except media_service.MediaValidationError as exc:
                raise HTTPException(400, str(exc))
            except media_service.ObjectStoreUnavailable:
                raise HTTPException(503, "视频存储暂不可用，请稍后重试")
            storage_path = f"/media/{asset.asset_id}"
            file_size = asset.size_bytes
        finally:
            try:
                os.unlink(tmp_path)
            except OSError as cleanup_exc:
                logger.warning("视频临时文件清理失败 %s: %s", tmp_path, cleanup_exc)
    else:
        # 回滚分支：保留原 uploads/videos 写路径。
        file_uuid = str(uuid.uuid4())
        final_filename = f"{file_uuid}.{file_ext}"
        storage_path = os.path.join(settings.VIDEO_DIR, final_filename)
        file_size = 0
        with open(storage_path, "wb") as final_file:
            for chunk_name in chunks:
                chunk_path = os.path.join(chunk_dir, chunk_name)
                with open(chunk_path, "rb") as chunk_file:
                    data = chunk_file.read()
                    final_file.write(data)
                    file_size += len(data)

    # 成功落存储后才清理分片
    shutil.rmtree(chunk_dir, ignore_errors=True)

    # 创建视频记录
    video = VideoResource(
        question_id=question_id,
        title=filename,
        original_filename=filename,
        storage_path=storage_path,
        duration=0,
        file_size=file_size,
        format=file_ext,
        status="COMPLETED"
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    return video


@router.get("/{video_id}/stream", summary="流式播放视频")
async def stream_video(
    video_id: int,
    range: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    流式播放视频（支持 Range 请求实现拖动）
    """
    video = db.query(VideoResource).filter(
        VideoResource.video_id == video_id
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if (video.storage_path or "").startswith("/media/"):
        # F3 资产交给 /media 路由处理 Range/ETag；307 不改变请求方法，
        # 客户端会带着 Range 头重新请求。
        return RedirectResponse(url=video.storage_path, status_code=307)

    if not os.path.exists(video.storage_path):
        raise HTTPException(status_code=404, detail="视频文件不存在")

    file_size = os.path.getsize(video.storage_path)
    chunk_size = 1024 * 1024  # 1MB

    start = 0
    end = file_size - 1

    if range:
        range_header = range.replace("bytes=", "")
        parts = range_header.split("-")
        start = int(parts[0])
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

    # 边界保护
    start = max(0, min(start, file_size - 1))
    end = max(start, min(end, file_size - 1))
    length = end - start + 1

    def generate():
        with open(video.storage_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    content_type = f"video/{video.format}" if video.format else "video/mp4"

    return StreamingResponse(
        generate(),
        status_code=206 if range else 200,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }
    )


@router.delete("/{video_id}", response_model=SuccessResponse, summary="删除视频")
async def delete_video(
    video_id: int,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    删除视频（需管理员权限）
    """
    video = db.query(VideoResource).filter(
        VideoResource.video_id == video_id
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if (video.storage_path or "").startswith("/media/"):
        asset_id = video.storage_path[len("/media/"):].split("?", 1)[0]
        try:
            media_service.delete_asset(db, asset_id)
        except media_service.MediaNotFound:
            pass  # 元数据已被清理，仍删除视频行
    else:
        # 旧资产的物理文件删除逻辑保持不变。
        if os.path.exists(video.storage_path):
            os.remove(video.storage_path)

    if video.thumbnail_path and os.path.exists(video.thumbnail_path):
        os.remove(video.thumbnail_path)

    db.delete(video)
    db.commit()

    return SuccessResponse(message="视频删除成功")
