"""
Redis客户端 - 二维码状态管理
"""
import redis.asyncio as redis
from typing import Optional
import json
from datetime import datetime

from .config import settings

redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    """获取Redis客户端实例"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client

async def close_redis():
    """关闭Redis连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None

class QRCodeStore:
    """二维码状态管理（Redis）"""
    
    PREFIX = "qr:"
    CONFIRMED_SUFFIX = ":confirmed"
    TTL_SECONDS = 60
    CONFIRMED_TTL_SECONDS = 300
    
    @staticmethod
    async def create_qr(uuid: str, device_info: dict) -> None:
        """创建二维码状态"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}"
        data = {
            "status": "pending",
            "pc_device_info": device_info,
            "created_at": datetime.utcnow().isoformat()
        }
        await r.set(key, json.dumps(data), ex=QRCodeStore.TTL_SECONDS)
    
    @staticmethod
    async def get_qr(uuid: str) -> Optional[dict]:
        """获取二维码状态"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}"
        data = await r.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    async def confirm_qr(uuid: str, user_id: int, token: str) -> None:
        """确认二维码登录"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}{QRCodeStore.CONFIRMED_SUFFIX}"
        data = {
            "user_id": user_id,
            "token": token,
            "confirmed_at": datetime.utcnow().isoformat()
        }
        await r.set(key, json.dumps(data), ex=QRCodeStore.CONFIRMED_TTL_SECONDS)
        
        # 更新状态为已确认
        qr_key = f"{QRCodeStore.PREFIX}{uuid}"
        qr_data = await r.get(qr_key)
        if qr_data:
            qr = json.loads(qr_data)
            qr["status"] = "confirmed"
            await r.set(qr_key, json.dumps(qr), ex=QRCodeStore.TTL_SECONDS)
    
    @staticmethod
    async def get_confirmation(uuid: str) -> Optional[dict]:
        """获取确认数据"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}{QRCodeStore.CONFIRMED_SUFFIX}"
        data = await r.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    async def delete_qr(uuid: str) -> None:
        """删除二维码状态"""
        r = await get_redis()
        await r.delete(f"{QRCodeStore.PREFIX}{uuid}")
        await r.delete(f"{QRCodeStore.PREFIX}{uuid}{QRCodeStore.CONFIRMED_SUFFIX}")
