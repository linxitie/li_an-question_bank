"""
增强安全模块 - JWT/OAuth2.0认证、权限控制、限流熔断
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, WebSocket, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import time
import asyncio
from collections import defaultdict
import threading
import hashlib

from .config import settings
from .database import get_db
from ..models.models import SysUser


class UserRole(str, Enum):
    """用户角色枚举"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

class Permission(str, Enum):
    """权限枚举"""
    #题目权限
    QUESTION_CREATE = "question:create"
    QUESTION_UPDATE = "question:update"
    QUESTION_DELETE = "question:delete"
    QUESTION_VIEW = "question:view"
    QUESTION_AUDIT = "question:audit"
    QUESTION_IMPORT = "question:import"

    #试卷权限
    PAPER_CREATE = "paper:create"
    PAPER_APPROVE = "paper:approve"
    PAPER_PUBLISH = "paper:publish"
    PAPER_VIEW = "paper:view"
    PAPER_UPDATE = "paper:update"


    #考试权限
    EXAM_START = "exam:start"
    EXAM_VIEW_ALL = "exam:view_all"
    EXAM_VIEW = "exam:view"
    EXAM_GRADE = "exam:grade"

    #用户管理权限
    USER_MANAGE = "user:manage"
    USER_VIEW = "user:view"

    #系统权限
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"

    #视频权限
    VIDEO_UPLOAD = "video:upload"
    VIDEO_DELETE = "video:delete"

    #llm授权
    LLM_USE = "llm:use"

#角色权限映射
ROLE_PERMISSIONS: Dict[str, List[Permission]] = {
    UserRole.STUDENT: [
        Permission.QUESTION_VIEW,
        Permission.EXAM_START,
        Permission.EXAM_VIEW,
        Permission.LLM_USE,
    ],
    UserRole.TEACHER: [
        Permission.QUESTION_CREATE,
        Permission.QUESTION_UPDATE,
        Permission.QUESTION_VIEW,
        Permission.QUESTION_AUDIT,
        Permission.QUESTION_IMPORT,
        Permission.PAPER_CREATE,
        Permission.PAPER_UPDATE,
        Permission.PAPER_VIEW,
        Permission.PAPER_PUBLISH,
        Permission.PAPER_APPROVE,
        Permission.EXAM_START,
        Permission.EXAM_VIEW_ALL,
        Permission.EXAM_GRADE,
        Permission.EXAM_VIEW,
        Permission.USER_VIEW,
        Permission.VIDEO_UPLOAD,
        Permission.LLM_USE,
    ],
    UserRole.ADMIN: [
        Permission.QUESTION_CREATE,
        Permission.QUESTION_UPDATE,
        Permission.QUESTION_DELETE,
        Permission.QUESTION_VIEW,
        Permission.PAPER_CREATE,
        Permission.PAPER_APPROVE,
        Permission.PAPER_PUBLISH,
        Permission.EXAM_START,
        Permission.EXAM_VIEW_ALL,
        Permission.EXAM_GRADE,
        Permission.USER_VIEW,
        Permission.USER_MANAGE,
        Permission.VIDEO_DELETE,
        Permission.SYSTEM_CONFIG,
        Permission.LLM_USE
    ],
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "type": TokenType.ACCESS.value,
        "iat":datetime.utcnow()
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """创建刷新令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=30)
    to_encode.update({
        "exp": expire,
        "type": TokenType.REFRESH.value,
        "iat":datetime.utcnow()
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    """解码令牌 """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效的认证凭据:{str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> SysUser:
    """获取当前用户"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)

    if payload.get("type") != TokenType.ACCESS.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌类型",
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌载荷",
        )

    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    return user

async def get_current_active_user(
    current_user: SysUser = Depends(get_current_user)
) -> SysUser:
    """获取当前活跃用户"""
    if current_user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return current_user

def check_permission(user: SysUser, permission: Permission) -> bool:
    """检查用户是否有指定权限"""
    try:
        user_role = UserRole(user.user_type)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(user_role, [])

def require_permission(permission: Permission):
    """需要指定权限的装饰器"""
    async def permission_checker(
        current_user: SysUser = Depends(get_current_user)
    ) -> SysUser:
        if not check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少必要权限: {permission.value}",
            )
        return current_user
    return permission_checker

def require_role(*roles: UserRole):
    """需要指定角色的装饰器"""
    async def role_checker(
        current_user: SysUser = Depends(get_current_user)
    ) -> SysUser:
        try:
            user_role = UserRole(current_user.user_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无效的用户角色",
            )

        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user
    return role_checker

def require_teacher_or_admin(current_user:SysUser = Depends(get_current_user)) -> SysUser:
    """需要教师或者管理员权限"""
    if current_user.user_type not in [UserRole.TEACHER.value,UserRole.ADMIN.value]:
        raise HTTPException(
            status_code= status.HTTP_403_FORBIDDEN,
            detail="需要教师或者管理员权限"
        )
    return current_user

def require_admin(current_user: SysUser = Depends(get_current_user)) -> SysUser:
    """需要管理员权限"""
    if current_user.role_level < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user

def require_super_admin(current_user: SysUser = Depends(get_current_user)) -> SysUser:
    """需要超级管理员权限"""
    if current_user.role_level < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限",
        )
    return current_user

def require_student(current_user:SysUser = Depends(get_current_user)) -> SysUser:
    """仅学生可以访问"""
    if current_user.user_type != UserRole.STUDENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅学生可以访问"
        )
    return current_user



#====================================token管理器====================================
class TokenManager:
    """令牌管理器-支持黑名单和刷新令牌储存"""
    def __init__(self):
        self._refresh_tokens: Dict[str, Dict[str, Any]] = {}
        self._blacklist: set = set()
        self._lock = threading.Lock()

    def store_refresh_token(self, token: str, user_id: int,device_info:str="") -> None:
        """储存刷新令牌"""
        with self._lock:
            token_fingerprint = hashlib.sha256(token.encode()).hexdigest()[:16]
            self._refresh_tokens[token_fingerprint] = {
                "token":token,
                "user_id": user_id,
                "device":device_info,
                "created_at": datetime.utcnow()
            }

    def validate_refresh_token(self, token: str) -> Optional[int]:
        """验证刷线令牌"""
        with self._lock:
            token_fingerprint = hashlib.sha256(token.encode()).hexdigest()[:16]
            token_data = self._refresh_tokens.get(token_fingerprint)
            if not token_data:
                return None

            #检查是否在黑名单
            if token in self._blacklist:
                del self._refresh_tokens[token_fingerprint]
                return None
            #检查是否过期
            created_at = token_data["created_at"]
            if datetime.utcnow() - created_at > timedelta(days=30):
                del self._refresh_tokens[token_fingerprint]
                return None

            return token_data["user_id"]

    def revoke_refresh_token(self, token: str) -> None:
        """撤销刷新令牌"""
        with self._lock:
            token_fingerprint = hashlib.sha256(token.encode()).hexdigest()[:16]
            if token_fingerprint in self._refresh_tokens:
                del self._refresh_tokens[token_fingerprint]
            self._blacklist.add(token)

            #定期清理黑名单
            if len(self._blacklist) > 10000:
                self._blacklist.clear()

def revoke_all_user_tokens(self, user_id: int) -> None:
    """撤销用户的所有令牌"""
    with self._lock:
        to_remove = []
        for fingerprint, data in self._refresh_tokens.items():
            if data["user_id"] == user_id:
                to_remove.append(fingerprint)

        for fingerprint in to_remove:
            del self._refresh_tokens[fingerprint]

token_manager = TokenManager()




# ===================================限流器===================================
class RateLimiter:
    """滑动窗口限流器"""
    def __init__(self, rate: int = 100, per: int = 60):
        self.rate = rate
        self.per = per
        self.allowance: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _cleanup_old_requests(self, key: str, current_time: float) -> None:
        """清理过期请求"""
        cutoff = current_time - self.per
        self.allowance[key] = [t for t in self.allowance[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        current_time = time.time()

        with self._lock:
            self._cleanup_old_requests(key, current_time)

            if len(self.allowance[key]) < self.rate:
                self.allowance[key].append(current_time)
                return True
            return False

    def get_retry_after(self, key: str) -> int:
        """获取充实等待时间"""
        current_time = time.time()

        with self._lock:
            self._cleanup_old_requests(key, current_time)

            if len(self.allowance[key]) < self.rate:
                return 0

            oldest_request = min(self.allowance[key])
            return int(self.per - (current_time - oldest_request)) + 1

rate_limiter = RateLimiter(rate=100, per=60)


class LeakyBucketRateLimiter:
    """漏桶限流器"""
    def __init__(self, capacity: int = 100, leak_rate: float = 1.0):
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "water": 0.0,
            "last_check": time.time()
        })
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        with self._lock:
            bucket = self.buckets[key]
            current_time = time.time()
            elapsed = current_time - bucket["last_check"]

            bucket["water"] = max(0, bucket["water"] - elapsed * self.leak_rate)
            bucket["last_check"] = current_time

            if bucket["water"] < self.capacity:
                bucket["water"] += 1
                return True
            return False

    def get_retry_after(self, key: str) -> int:
        """获取重新等待时间"""
        with self._lock:
            bucket = self.buckets[key]
            if bucket["water"] < self.capacity:
                return 0
            return int((bucket["water"] - self.capacity + 1) / self.leak_rate) + 1

leaky_bucket_limiter = LeakyBucketRateLimiter(capacity=100, leak_rate=1.67)




# ===================================熔断器========================================
class CircuitBreaker:
    """熔断器实现"""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, half_max: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_max = half_max
        self.state = "CLOSED"
        self.failure_count = 0
        self.half_open_successes = 0
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def record_success(self) -> None:
        with self._lock:
            if self.state == "HALF_OPEN":
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_max:
                    self._reset()
            elif self.state == "CLOSED":
                self.failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self.last_failure_time = time.time()

            if self.state == "HALF_OPEN":
                self._trip()
            elif self.state == "CLOSED":
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self._trip()

    def _trip(self) -> None:
        """触发熔断"""
        self.state = "OPEN"
        self.half_open_successes = 0

    def _reset(self) -> None:
        """重置熔断"""
        self.state = "CLOSED"
        self.failure_count = 0
        self.half_open_successes = 0
        self.last_failure_time = None

    def is_available(self) -> bool:
        """检查服务器是否可用"""
        with self._lock:
            if self.state == "CLOSED":
                return True

            if self.state == "OPEN":
                if self.last_failure_time and \
                   time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    return True
                return False

            if self.state == "HALF_OPEN":
                return True

        return True

circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)




# ===================================WebSocket管理器================================
class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        """建立websocket连接"""
        await websocket.accept()
        async with self._lock:
            self.active_connections[user_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        """断开Websocket连接"""
        async with self._lock:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)

    async def send_personal_message(self, message: str, user_id: int) -> None:
        """发送个人信息"""
        async with self._lock:
            for connection in self.active_connections.get(user_id, []):
                disconnected = []
                try:
                    await connection.send_text(message)
                except Exception:
                    disconnected.append(connection)


            #清理断开连接
            for conn in disconnected:
                if conn in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(conn)

    async def broadcast(self, message: str) -> None:
        """广播消息"""
        async with self._lock:
            for user_id, connections in list(self.active_connections.items()):
                disconnected = []
                for connection in connections:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        disconnected.append(connection)

                #清理断开连接
                for conn in disconnected:
                    if conn in self.active_connections[user_id]:
                        self.active_connections[user_id].remove(conn)

    def get_online_users(self) -> List[int]:
        """获取用户的连接数"""
        return list(self.active_connections.keys())

ws_manager = WebSocketManager()


# ================================= 工具函数=====================================
generate_verify_code = lambda length=6: ''.join(__import__('random').choices('0123456789', k=length))
def get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def generate_api_key(user_id: int, secret: str) -> str:
    """生成API密钥"""
    timestamp = str(int(time.time()))
    data = f"{user_id}:{timestamp}:{secret}"
    signature = hashlib.sha256(data.encode()).hexdigest()
    return f"{user_id}:{timestamp}:{signature}"
