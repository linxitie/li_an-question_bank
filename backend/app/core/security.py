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
from ..models.models import SysUser, SysConfig


class UserRole(str, Enum):
    """用户角色枚举"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

class Permission(str, Enum):
    """权限枚举 — 三端分离架构 22 项细粒度权限"""
    # 题目权限
    QUESTION_CREATE = "question:create"
    QUESTION_UPDATE = "question:update"
    QUESTION_DELETE = "question:delete"
    QUESTION_VIEW = "question:view"
    QUESTION_AUDIT = "question:audit"
    QUESTION_IMPORT = "question:import"

    # 试卷权限
    PAPER_CREATE = "paper:create"
    PAPER_APPROVE = "paper:approve"
    PAPER_PUBLISH = "paper:publish"
    PAPER_VIEW = "paper:view"
    PAPER_UPDATE = "paper:update"

    # 考试权限
    EXAM_START = "exam:start"
    EXAM_VIEW_ALL = "exam:view_all"
    EXAM_VIEW = "exam:view"
    EXAM_GRADE = "exam:grade"

    # 用户管理权限
    USER_MANAGE = "user:manage"
    USER_VIEW = "user:view"

    # 系统权限
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"

    # 日志审计权限（新增）
    LOG_AUDIT = "log:audit"

    # 数据备份权限（新增）
    DATA_BACKUP = "data:backup"

    # 视频权限
    VIDEO_UPLOAD = "video:upload"
    VIDEO_DELETE = "video:delete"

    # 论坛权限（新增）
    FORUM_POST = "forum:post"
    FORUM_MANAGE = "forum:manage"
    FORUM_MODERATE = "forum:moderate"
    FORUM_REPORT_HANDLE = "forum:report_handle"

    # 练习反馈权限（新增）
    FEEDBACK_READ = "feedback:read"
    FEEDBACK_HANDLE = "feedback:handle"
    FEEDBACK_STATS = "feedback:stats"

    # 练习管理员任命权限（新增）
    PRACTICE_ADMIN_GRANT_TEACHER = "practice_admin:grant_teacher"
    PRACTICE_ADMIN_GRANT_STUDENT = "practice_admin:grant_student"

    # LLM 授权
    LLM_USE = "llm:use"

# 角色权限映射 — 三端分离架构
# role_level: 0=学生, 1=教师, 2=管理员, 3=超级管理员
ROLE_PERMISSIONS: Dict[str, List[Permission]] = {
    UserRole.STUDENT: [
        Permission.QUESTION_VIEW,
        Permission.PAPER_VIEW,
        Permission.EXAM_START,
        Permission.EXAM_VIEW,
        Permission.LLM_USE,
        Permission.FORUM_POST,
    ],
    UserRole.TEACHER: [
        # 题目全生命周期
        Permission.QUESTION_CREATE,
        Permission.QUESTION_UPDATE,
        Permission.QUESTION_DELETE,
        Permission.QUESTION_VIEW,
        Permission.QUESTION_AUDIT,
        Permission.QUESTION_IMPORT,
        # 试卷全生命周期
        Permission.PAPER_CREATE,
        Permission.PAPER_UPDATE,
        Permission.PAPER_VIEW,
        Permission.PAPER_PUBLISH,
        Permission.PAPER_APPROVE,
        # 考试与成绩
        Permission.EXAM_START,
        Permission.EXAM_VIEW_ALL,
        Permission.EXAM_GRADE,
        Permission.EXAM_VIEW,
        # 用户查看
        Permission.USER_VIEW,
        # 视频上传
        Permission.VIDEO_UPLOAD,
        # 论坛与AI
        Permission.FORUM_POST,
        Permission.LLM_USE,
    ],
    UserRole.ADMIN: [
        # 管理员拥有教师全部权限 + 管理权限
        Permission.QUESTION_CREATE,
        Permission.QUESTION_UPDATE,
        Permission.QUESTION_DELETE,
        Permission.QUESTION_VIEW,
        Permission.QUESTION_AUDIT,
        Permission.QUESTION_IMPORT,
        Permission.PAPER_CREATE,
        Permission.PAPER_UPDATE,
        Permission.PAPER_VIEW,
        Permission.PAPER_APPROVE,
        Permission.PAPER_PUBLISH,
        Permission.EXAM_START,
        Permission.EXAM_VIEW_ALL,
        Permission.EXAM_GRADE,
        Permission.EXAM_VIEW,
        Permission.USER_VIEW,
        Permission.USER_MANAGE,
        Permission.VIDEO_UPLOAD,
        Permission.VIDEO_DELETE,
        Permission.SYSTEM_CONFIG,
        Permission.SYSTEM_MONITOR,
        Permission.LOG_AUDIT,
        Permission.FORUM_POST,
        Permission.FORUM_MANAGE,
        Permission.FORUM_MODERATE,
        Permission.FORUM_REPORT_HANDLE,
        Permission.FEEDBACK_READ,
        Permission.FEEDBACK_HANDLE,
        Permission.FEEDBACK_STATS,
        Permission.PRACTICE_ADMIN_GRANT_TEACHER,
        Permission.PRACTICE_ADMIN_GRANT_STUDENT,
        Permission.LLM_USE,
    ],
}

# 超级管理员额外权限（role_level >= 3）
SUPER_ADMIN_PERMISSIONS: List[Permission] = [
    Permission.DATA_BACKUP,
]

def get_user_permissions(user: SysUser) -> List[Permission]:
    """获取用户完整权限列表（含 role_level 升级）"""
    try:
        user_role = UserRole(user.user_type)
    except ValueError:
        return []
    perms = list(ROLE_PERMISSIONS.get(user_role, []))
    # 超级管理员 (role_level >= 3) 追加数据备份权限
    if user.role_level >= 3:
        for p in SUPER_ADMIN_PERMISSIONS:
            if p not in perms:
                perms.append(p)
    return perms


def get_user_permissions_with_db(user: SysUser, db: Session) -> List[Permission]:
    """获取用户完整权限列表（优先读 SysConfig 自定义配置，无则回退硬编码默认）

    权限编辑功能（PUT /api/admin/permissions）将自定义权限写入 SysConfig 的
    role_permissions_{role} 键。此函数在运行时读取该配置，使编辑真正生效。
    未编辑过的角色回退到 ROLE_PERMISSIONS 硬编码默认值，保证向后兼容。
    """
    import json as _json
    try:
        user_role = UserRole(user.user_type)
    except ValueError:
        return []

    # 1) 读取 SysConfig 自定义权限配置
    custom_perms: List[Permission] = []
    try:
        config = db.query(SysConfig).filter(
            SysConfig.config_key == f"role_permissions_{user.user_type}"
        ).first()
        if config and config.config_value:
            perm_values = _json.loads(config.config_value)
            custom_perms = [Permission(v) for v in perm_values if v in Permission._value2member_map_]
    except Exception:
        custom_perms = []

    # 2) 有自定义配置则用自定义，否则回退硬编码默认
    if custom_perms:
        perms = custom_perms
    else:
        perms = list(ROLE_PERMISSIONS.get(user_role, []))

    # 3) 超级管理员 (role_level >= 3) 始终追加数据备份权限（不可被编辑移除）
    if user.role_level >= 3:
        for p in SUPER_ADMIN_PERMISSIONS:
            if p not in perms:
                perms.append(p)

    # 4) 叠加按用户授予的能力包（练习管理员等）
    try:
        from .capabilities import get_capability_permission_values

        for value in get_capability_permission_values(user.user_id, db):
            try:
                permission = Permission(value)
            except ValueError:
                continue
            if permission not in perms:
                perms.append(permission)
    except Exception:
        # 能力包表尚未创建或查询失败时，不影响基础权限
        pass

    return perms


def get_effective_permissions(user: SysUser, db: Session) -> List[Permission]:
    """用户最终权限 = 角色权限 ∪ 能力包权限（对外统一入口）。"""
    return get_user_permissions_with_db(user, db)


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

def decode_token_unverified(token: str) -> Dict[str, Any]:
    """不校验签名地解出令牌载荷（仅限测试与排障）。

    为什么单独封装而不是让调用方自己拼参数：
        本项目用 python-jose，其 jwt.decode 必须显式传 key；散落在测试里会重复密钥细节，
        将来换库（PyJWT / python-jose 新版）也没有统一收敛点。这里是唯一入口。
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_signature": False},
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

    # 三端分离：检查 is_disabled 标志
    if getattr(user, 'is_disabled', 0) == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被管理员禁用，请联系管理员",
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

async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[SysUser]:
    """获取当前用户（可选认证，不强制登录）"""
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != TokenType.ACCESS.value:
            return None
        user_id = payload.get("user_id")
        if not user_id:
            return None
        user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
        if user and user.status != 0:
            return user
    except Exception:
        pass
    return None

def check_permission(user: SysUser, permission: Permission) -> bool:
    """检查用户是否有指定权限（含 disabled 检查）"""
    # 禁用用户无任何权限
    if getattr(user, 'is_disabled', 0) == 1:
        return False
    if user.status == 0:
        return False
    user_perms = get_user_permissions(user)
    return permission in user_perms

def check_any_permission(user: SysUser, *permissions: Permission) -> bool:
    """检查用户是否有任一权限"""
    if getattr(user, 'is_disabled', 0) == 1 or user.status == 0:
        return False
    user_perms = get_user_permissions(user)
    return any(p in user_perms for p in permissions)

def require_permission(permission: Permission):
    """需要指定权限的依赖（角色权限 ∪ 能力包权限）。"""
    async def permission_checker(
        current_user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> SysUser:
        if getattr(current_user, 'is_disabled', 0) == 1 or current_user.status == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用",
            )
        if permission not in get_effective_permissions(current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少必要权限: {permission.value}",
            )
        return current_user
    return permission_checker


def assert_scope_covers(
    grantor_scopes: List[Dict[str, Any]],
    target_scope_type: str,
    target_scope_id: Optional[int] = None,
) -> None:
    """校验授权人的范围是否覆盖目标范围；不足抛 403。

    grantor_scopes 形如 [{"scope_type": "subject", "scope_id": 3}, ...]。
    global 覆盖一切；subject/class 必须类型与 ID 同时匹配。
    """
    if target_scope_type == "global":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以授予全校范围",
        )
    for scope in grantor_scopes:
        if scope.get("scope_type") == "global":
            return
        if (
            scope.get("scope_type") == target_scope_type
            and scope.get("scope_id") == target_scope_id
        ):
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="授权范围不足",
    )

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

# === 三端分离架构：便捷角色依赖函数 ===

async def get_current_teacher(
    current_user: SysUser = Depends(get_current_user)
) -> SysUser:
    """获取当前教师用户（teacher/admin 均可）"""
    if current_user.user_type not in [UserRole.TEACHER.value, UserRole.ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要教师或管理员权限"
        )
    return current_user

async def get_current_admin(
    current_user: SysUser = Depends(get_current_user)
) -> SysUser:
    """获取当前管理员用户（role_level >= 2）"""
    if current_user.user_type != UserRole.ADMIN.value or current_user.role_level < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user

async def get_current_super_admin(
    current_user: SysUser = Depends(get_current_user)
) -> SysUser:
    """获取当前超级管理员用户（role_level >= 3）"""
    if current_user.user_type != UserRole.ADMIN.value or current_user.role_level < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
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
    def __init__(self, rate: int = 300, per: int = 60):
        # 2026-08: 100→300。原阈值下，批量导入97题的逐题请求(旧前端实现)
        # 叠加仪表盘轮询即触顶429；批处理端点(/batch-parsed)上线后单次请求
        # 即可完成整卷导入，300/60s 对正常交互仍具保护意义。
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

rate_limiter = RateLimiter(rate=300, per=60)


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

            # 先判断"加水后是否会溢出"再加水。
            # 为什么不能写成 water < capacity 再 +=1：每次调用会先按 elapsed*leak_rate 漏水，
            # 亚秒级间隔下漏掉的量是 1e-6 级，water 永远差一点点到不了 capacity，
            # 结果比标的容量多放 1 个请求（实测 capacity=2 时放行了 3 个）。
            if bucket["water"] + 1 <= self.capacity:
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

circuit_breaker = CircuitBreaker(failure_threshold=20, recovery_timeout=60)




# ===================================Session 管理器================================
class SessionManager:
    """服务端 Session 管理器 — 三层认证中的 Session 层"""
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_session(self, user_id: int, ip: str, device: str = "") -> str:
        """创建 session，返回 session_id"""
        import uuid
        session_id = uuid.uuid4().hex
        with self._lock:
            self._sessions[session_id] = {
                "user_id": user_id,
                "ip": ip,
                "device": device,
                "login_time": datetime.utcnow(),
                "last_active": datetime.utcnow(),
            }
        # 清理过期 session（超过 8 小时未活跃）
        self._cleanup()
        return session_id

    def validate_session(self, session_id: str) -> Optional[int]:
        """验证 session，返回 user_id 或 None"""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            # 检查过期（8 小时未活跃）
            if datetime.utcnow() - session["last_active"] > timedelta(hours=8):
                del self._sessions[session_id]
                return None
            session["last_active"] = datetime.utcnow()
            return session["user_id"]

    def destroy_session(self, session_id: str) -> None:
        """销毁 session"""
        with self._lock:
            self._sessions.pop(session_id, None)

    def destroy_user_sessions(self, user_id: int) -> None:
        """销毁某用户的所有 session（强制下线）"""
        with self._lock:
            to_remove = [sid for sid, s in self._sessions.items() if s["user_id"] == user_id]
            for sid in to_remove:
                del self._sessions[sid]

    def _cleanup(self) -> None:
        """清理过期 session"""
        cutoff = datetime.utcnow() - timedelta(hours=8)
        to_remove = [sid for sid, s in self._sessions.items() if s["last_active"] < cutoff]
        for sid in to_remove:
            del self._sessions[sid]

session_manager = SessionManager()


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
