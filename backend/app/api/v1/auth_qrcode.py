"""
二维码扫码登录 API
"""
import uuid
import qrcode
import base64
from io import BytesIO
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user, create_access_token
from ...core.redis_client import QRCodeStore
from ...models.models import SysUser

router = APIRouter(prefix="/api/auth/qrcode", tags=["二维码登录"])

def get_device_info(request: Request) -> dict:
    """从请求头提取设备信息"""
    user_agent = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else "unknown"
    
    # 简单的设备检测
    browser = "Unknown"
    os = "Unknown"
    
    if "Chrome" in user_agent:
        browser = "Chrome"
    elif "Firefox" in user_agent:
        browser = "Firefox"
    elif "Safari" in user_agent:
        browser = "Safari"
    elif "Edge" in user_agent:
        browser = "Edge"
    
    if "Windows" in user_agent:
        os = "Windows"
    elif "Mac" in user_agent:
        os = "macOS"
    elif "Linux" in user_agent:
        os = "Linux"
    elif "Android" in user_agent:
        os = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        os = "iOS"
    
    return {
        "browser": browser,
        "os": os,
        "ip": ip,
        "user_agent": user_agent
    }

@router.post("/generate", summary="生成二维码")
async def generate_qrcode(
    request: Request,
    current_user: SysUser = Depends(get_current_user)
):
    """PC端生成登录二维码"""
    qr_uuid = str(uuid.uuid4())
    device_info = get_device_info(request)
    
    # 存储到Redis
    await QRCodeStore.create_qr(qr_uuid, device_info)
    
    # 生成二维码图片
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(f"liani://login/{qr_uuid}")
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1A365D", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return {
        "uuid": qr_uuid,
        "qr_url": f"liani://login/{qr_uuid}",
        "qr_image_base64": f"data:image/png;base64,{qr_base64}",
        "expires_in": 60
    }

@router.get("/{qr_uuid}/info", summary="获取PC端信息")
async def get_pc_info(qr_uuid: str):
    """移动端扫码获取PC端设备信息"""
    qr_data = await QRCodeStore.get_qr(qr_uuid)
    
    if not qr_data:
        raise HTTPException(status_code=404, detail="二维码不存在或已过期")
    
    return {
        "device": qr_data["pc_device_info"],
        "login_time": qr_data["created_at"]
    }

@router.post("/{qr_uuid}/confirm", summary="确认登录")
async def confirm_login(
    qr_uuid: str,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移动端确认登录"""
    qr_data = await QRCodeStore.get_qr(qr_uuid)
    
    if not qr_data:
        raise HTTPException(status_code=404, detail="二维码不存在或已过期")
    
    if qr_data.get("status") == "confirmed":
        raise HTTPException(status_code=400, detail="二维码已使用")
    
    # 为PC端生成token
    token = create_access_token(data={"sub": current_user.username})
    
    # 存储确认信息
    await QRCodeStore.confirm_qr(qr_uuid, current_user.user_id, token)
    
    return {
        "success": True,
        "message": "登录确认成功"
    }

@router.get("/{qr_uuid}/status", summary="查询二维码状态")
async def check_status(qr_uuid: str):
    """PC端轮询二维码状态"""
    qr_data = await QRCodeStore.get_qr(qr_uuid)
    
    if not qr_data:
        return {"status": "expired"}
    
    if qr_data.get("status") == "confirmed":
        confirmation = await QRCodeStore.get_confirmation(qr_uuid)
        return {
            "status": "confirmed",
            "token": confirmation["token"] if confirmation else None
        }
    
    return {"status": "pending"}
