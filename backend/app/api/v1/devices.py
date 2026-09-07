"""
设备管理 API
"""
import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import SysUser

router = APIRouter(prefix="/api/auth/devices", tags=["设备管理"])

MAX_DEVICES = 3
SESSION_CLEANUP_DAYS = 30

def cleanup_old_sessions(sessions: list) -> list:
    """清理超过30天的旧会话"""
    cutoff = datetime.utcnow() - timedelta(days=SESSION_CLEANUP_DAYS)
    return [
        s for s in sessions 
        if datetime.fromisoformat(s.get("last_active", "2000-01-01")) > cutoff
    ]

@router.get("/", summary="获取设备列表")
async def list_devices(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户所有登录设备"""
    sessions = current_user.device_sessions or []
    sessions = cleanup_old_sessions(sessions)
    
    # 标记当前设备
    for session in sessions:
        session["is_current"] = False
    
    return {
        "devices": sessions,
        "max_devices": MAX_DEVICES
    }

@router.delete("/{device_id}", summary="移除设备")
async def remove_device(
    device_id: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移除指定登录设备"""
    sessions = current_user.device_sessions or []
    sessions = [
        s for s in sessions 
        if s.get("device_id") != device_id
    ]
    
    current_user.device_sessions = sessions
    db.commit()
    
    return {"message": "设备已移除"}

@router.post("/revoke-all", summary="强制下线所有设备")
async def revoke_all_devices(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """强制下线所有设备（除当前设备）"""
    current_user.device_sessions = []
    db.commit()
    
    return {"message": "所有设备已下线"}
